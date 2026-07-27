#!/usr/bin/env python3
"""Prove the target's suite is green on *this* working tree — once, not thrice.

The fix loop used to run the target's full test suite three times per finding:
the fix subagent ran it, the orchestrator re-ran it after committing, and the
``fix_commit`` gate ran it again. Only the last was enforced, and the last two
execute on a byte-identical tree (``git commit`` does not touch working-tree
contents). On the eval harness's own numbers that is ~4.7 h of pytest where
~1.5 h was budgeted.

This script splits "run the suite" from "know the suite passed" so the run can
happen once and the gate can be a predicate instead of a second execution.

Two modes, and the split is the whole design:

``--record``
    The **agent** path. Computes a hash of the working tree, runs the suite,
    and — only on green — records a ``suite_green`` event naming that hash.
    No transition is in flight here, so calling the daemon is safe.

``--check``
    The **gate** path. Recomputes the tree hash and asks whether a
    ``suite_green`` already names it. Pure predicate, exit 0/1, and it never
    touches the daemon socket: ``sahjhan query`` opens the ledger file
    directly (see ``src/cli/query.rs`` — it loads config, resolves the ledger,
    and runs SQL; no socket anywhere), so a gate running inside a transition
    cannot re-enter the daemon that is evaluating it.

Reading through ``sahjhan query`` rather than parsing ``ledger.jsonl`` here is
deliberate. The engine resolves the active ledger through a chain — explicit
``--ledger`` flag, then the ``active-ledger`` marker looked up in
``ledgers.toml``, then the registry default, then ``data_dir/ledger.jsonl``.
Reimplementing that chain in Python would be a mirror of engine logic, and a
mirror that drifts points the gate at a different ledger than the one the
transition evaluates. Delegating means block condition and evidence read the
same file by construction.

**The agent cannot forge a ``suite_green``.** Three independent layers:

1. The event is ``restricted``, so the daemon refuses a bare ``sahjhan event``.
2. This script lives under ``enforcement/`` — a managed path the pre-edit hook
   and ``bash_guard`` refuse to let the agent modify (cf. #71).
3. ``enforcement/trusted-callers.toml`` pins its SHA-256, so a modified copy
   fails peer authentication and the daemon rejects the write.

And it accepts no caller-supplied hash or result: the tree hash is computed
here, the suite is run here, and the event is written only on an observed
exit 0.

``--scope affected`` narrows the run to the tests the impact graph says cover
what changed since the last ``full`` green. It is a **cost** optimisation, not
a second integrity claim: the source-to-test map is agent-authored, so the
guarantee comes from the periodic full run that ``iteration_boundary``
demands. Every uncertainty in the selection widens back to the full suite —
see ``select_affected``.

Known limitation, stated so nobody "fixes" it by accident: the hash covers
tracked and untracked-but-not-ignored file *contents*, not the interpreter or
installed dependencies. Upgrading a dependency without touching a lockfile
leaves a stale ``suite_green`` valid. Lockfiles are tracked, so the ordinary
case is covered; a bare ``pip install -U`` is not.

Usage::

    python3 verify_suite.py --record [--scope full|affected] [--cwd .]
    python3 verify_suite.py --check  [--scope full|affected] [--cwd .]
    python3 verify_suite.py --print-affected [--cwd .]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys

# The suite command, in one place. `-x --ff` is the fail-fast pair T1 settled
# on: `--lf`/`--last-failed` is banned because it runs *only* the previously
# failing tests, so a gate using it can pass having executed a two-test subset
# — the false-green class of #83. `--no-cov` is likewise not in the default:
# it is a pytest-cov option, and on a target without that plugin pytest exits 4
# on the unrecognized argument, breaking every such target.
#
# `enforcement/transitions.toml` currently carries three copies of this string.
# That duplication is transient: T4 replaces those gate commands with
# `verify_suite.py --check`, at which point this is the only copy in the tree.
# Do not add a fourth.
DEFAULT_PYTEST = "python3 -m pytest -x --ff --tb=short -q"

# `suite_green` is spelled out as a string literal at the write site and in the
# gate's SQL below, deliberately, and must stay that way. `enforcement_lint.py`
# discovers write paths by scanning for the event type as a literal argument to
# `record_authed_event` — that scan is what falsifies the `[[producers]]`
# declaration in events.toml. Hoisting the name into a module constant hides
# the writer from H2/H3, and an event whose declared producer cannot be
# confirmed is exactly the class of defect those checks exist to catch.

# `full` ran everything; `affected` ran the impact-graph subset for the files
# that changed. Ordered weakest-first: a `full` run satisfies a request for
# `affected`, never the reverse — narrowing must always be the explicit ask,
# so a missing scope can only ever over-test.
SCOPES: tuple[str, ...] = ("affected", "full")

# STATUS.md and PUNCHLIST.md are rewritten on every fix, and the ledger itself
# is appended to by `--record`. Neither can affect the target's tests, and
# including them would invalidate the hash the instant it was recorded.
EXCLUDED_PREFIXES = ("docs/holtz/",)

# The only map holtz has from a changed source file to the tests that cover it.
# It is agent-authored, which bounds what an `affected` green may claim — see
# `select_affected`.
GRAPH_PATH = os.path.join("docs", "holtz", "impact-graph.json")

# pytest's exit codes for "the narrowed command could not be run", as distinct
# from "the tests ran and something failed": 4 is a usage error (a path that
# does not collect, or a `$HOLTZ_PYTEST` override that rejects trailing paths)
# and 5 is nothing-collected. Either way the narrowed run proved nothing, so
# the answer is to widen to the full suite. Widening can only ever run more
# tests, so it is always the safe direction; recording the narrow result is
# not.
SELECTION_FAILURE_EXITS = (4, 5)

_PASSED_RE = re.compile(r"(\d+) passed")
_TREE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

# pytest's own default collection patterns, applied to the basename. Notably
# *not* "anything under tests/": `tests/helpers.py` collects nothing, so
# treating it as a test file could hand pytest a selection with zero tests in
# it. Files that do not match simply need a `tests` edge like any other.
_TEST_FILE_RE = re.compile(r"^(test_.*\.py|.*_test\.py)$")


# ── Tree hashing ─────────────────────────────────────────────────────────────


def _git(args: list[str], cwd: str) -> str | None:
    """Run a git command, returning stripped stdout or None on any failure."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def repo_root(cwd: str) -> str | None:
    """The git top-level containing ``cwd``, or None if it is not a repo."""
    return _git(["rev-parse", "--show-toplevel"], cwd)


def _file_digest(root: str, rel: str) -> str:
    """SHA-256 of one file's bytes, or ``deleted`` when it is gone.

    A deleted-but-tracked file is a real tree difference, so it must move the
    hash — dropping it would let "delete the failing test" reuse a green.
    """
    path = os.path.join(root, rel)
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return "deleted"
    return digest.hexdigest()


def compute_tree_hash(root: str) -> str:
    """A stable 64-hex digest of the working tree's testable content.

    HEAD's oid covers every tracked file that matches HEAD; the per-file
    digests cover exactly the ones that do not — tracked-and-modified plus
    untracked-and-not-ignored. Ignored paths (``.venv``, ``__pycache__``,
    build output) are excluded by ``--exclude-standard``, which is what keeps
    a byte-compile from invalidating a green suite.
    """
    head = _git(["rev-parse", "HEAD"], root)
    parts = [f"head:{head or ''}"]

    changed: set[str] = set()
    # With no commits HEAD names nothing, so every tracked file has to be
    # digested individually rather than covered by the oid.
    diff = (
        _git(["diff", "--name-only", "--no-renames", "HEAD"], root)
        if head
        else _git(["ls-files"], root)
    )
    if diff:
        changed.update(diff.splitlines())

    untracked = _git(["ls-files", "--others", "--exclude-standard"], root)
    if untracked:
        changed.update(untracked.splitlines())

    for rel in sorted(changed):
        if not rel or rel.startswith(EXCLUDED_PREFIXES):
            continue
        parts.append(f"{rel}:{_file_digest(root, rel)}")

    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# ── Shared helpers ───────────────────────────────────────────────────────────


def suite_command() -> str:
    """The suite command this run will execute (or did)."""
    return os.environ.get("HOLTZ_PYTEST") or DEFAULT_PYTEST


def accepted_scopes(requested: str) -> tuple[str, ...]:
    """Scopes that satisfy a request for ``requested``, weakest first.

    ``full`` is accepted everywhere: running more tests than asked can never
    turn a red suite green.
    """
    return SCOPES[SCOPES.index(requested):]


def _run_number(cwd: str) -> str:
    """Current run number from sahjhan's active-ledger marker ('0' if none)."""
    marker = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-ledger")
    try:
        with open(marker, encoding="utf-8") as fh:
            return fh.read().strip().replace("run-", "") or "0"
    except OSError:
        return "0"


def _hooks_dir() -> str:
    """``enforcement/hooks``, which is a sibling of this script's directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"
    )


def _record_command(scope: str) -> str:
    """The exact command that satisfies a failing ``--check``.

    A block whose printed escape does not run is the #77 deadlock shape, so
    this names the absolute path of the very file being executed.
    """
    return f"python3 {os.path.abspath(__file__)} --record --scope {scope}"


def _block(reason: str, tree_hash: str, accepted: tuple[str, ...], scope: str) -> int:
    """Report a blocked check: why, on what tree, and what to run.

    Every ``--check`` failure that ``--record`` can clear goes through here,
    including the ones that are really configuration problems. A ledger that
    does not exist yet reads to the engine as an I/O error, but to the agent
    it means exactly what an empty ledger means — no evidence — and it is
    cleared by exactly the same command. Naming the underlying error *and* the
    escape keeps both audiences served: the operator learns the ledger is
    missing, the agent still has a runnable next step.
    """
    print(
        f"FAIL: {reason}\n"
        f"  tree_hash={tree_hash}\n"
        f"  accepted scopes: {', '.join(accepted)}\n"
        f"  Run: {_record_command(scope)}",
        file=sys.stderr,
    )
    return 1


# ── Ledger reads ─────────────────────────────────────────────────────────────


def _sahjhan_target(cwd: str) -> tuple[str | None, str | None, str]:
    """Locate the sahjhan binary and the enforcement config for ``cwd``.

    Returns ``(binary, config_dir, "")`` or ``(None, None, problem)``.
    """
    sys.path.insert(0, _hooks_dir())
    from _common import resolve_config_dir  # noqa: PLC0415
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    config_dir, found = resolve_config_dir(cwd)
    if binary is None or not found:
        return None, None, (
            f"sahjhan binary={'missing' if binary is None else binary}, "
            f"config_dir={'not found' if not found else config_dir}"
        )
    return binary, config_dir, ""


def _query_ledger(
    binary: str, config_dir: str, cwd: str, sql: str
) -> tuple[list[dict] | None, str]:
    """Run SQL over the active ledger, returning ``(rows, problem)``.

    Daemon-free by construction — see the module docstring. Both readers go
    through here so the gate's evidence and the baseline lookup can never
    resolve to different ledgers.
    """
    try:
        proc = subprocess.run(
            [binary, "--config-dir", config_dir, "query", sql, "--format", "json"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cannot query the ledger: {exc}"

    if proc.returncode != 0:
        # A ledger that has never been initialised surfaces here as an I/O
        # error rather than a zero count. Either way there is no evidence.
        return None, (
            f"ledger query failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"cannot read the ledger query result: {exc}"
    if not isinstance(rows, list):
        return None, f"ledger query returned {type(rows).__name__}, not a list"
    return rows, ""


# ── Affected-scope selection ─────────────────────────────────────────────────


def _baseline_commit(cwd: str) -> tuple[str | None, str]:
    """HEAD of the most recent tree proven green at ``full`` scope.

    Basing ``affected`` on the last *full* green, rather than on the last
    green of any scope, is deliberate. Chaining affected runs off each other
    is only sound if the selection is complete, and a hand-authored impact
    graph is not — a source file nobody drew a `tests` edge for would fall out
    of every window forever. Measuring from the last full green instead bounds
    the untested gap to one iteration: `iteration_boundary` demands a full
    run every few fixes, and that re-bases the window.
    """
    binary, config_dir, problem = _sahjhan_target(cwd)
    if binary is None or config_dir is None:
        return None, f"cannot reach the ledger — {problem}"

    rows, problem = _query_ledger(
        binary,
        config_dir,
        cwd,
        "SELECT commit_hash FROM events WHERE type='suite_green' "
        "AND scope='full' AND commit_hash IS NOT NULL ORDER BY seq DESC LIMIT 1",
    )
    if rows is None:
        return None, problem
    if not rows:
        return None, "no full-scope suite_green to measure changes against"

    commit = str(rows[0].get("commit_hash") or "")
    if not _COMMIT_RE.match(commit):
        return None, f"the last full suite_green names no usable commit ({commit!r})"
    return commit, ""


def _changed_since(root: str, baseline: str) -> tuple[list[str] | None, str]:
    """Paths that differ from ``baseline``, including uncommitted work.

    ``git diff --name-only <commit>`` compares the commit against the
    *working tree*, so one command covers both the commits made since the
    baseline and edits not yet committed. That matters because the fix loop
    records on both sides of a commit: the subagent proves its work before
    committing, the orchestrator proves the committed tree after.
    """
    if _git(["cat-file", "-e", f"{baseline}^{{commit}}"], root) is None:
        return None, f"baseline commit {baseline} is not in this repository"

    diff = _git(["diff", "--name-only", "--no-renames", baseline], root)
    if diff is None:
        return None, f"git could not diff against {baseline}"
    untracked = _git(["ls-files", "--others", "--exclude-standard"], root) or ""

    changed = {
        path
        for path in (diff.splitlines() + untracked.splitlines())
        if path and not path.startswith(EXCLUDED_PREFIXES)
    }
    return sorted(changed), ""


def _load_graph(cwd: str) -> tuple[dict, list] | None:
    """Read the impact graph as *data*, or None if it is unusable.

    Parsed here rather than imported from
    ``skills/holtz/scripts/impact_graph.py`` on purpose. This process is the
    one the daemon authenticates to write a restricted ``suite_green``;
    importing a module from a path the agent can write would let
    agent-authored *code* run under that identity, which is a strictly bigger
    hole than reading agent-authored *data*. What is needed here is a
    one-hop edge lookup, not a copy of ``blast_radius``.
    """
    try:
        with open(os.path.join(cwd, GRAPH_PATH), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    nodes = data.get("nodes") if isinstance(data, dict) else None
    edges = data.get("edges") if isinstance(data, dict) else None
    if not isinstance(nodes, dict) or not isinstance(edges, list):
        return None
    return nodes, edges


def _covering_tests(rel: str, nodes: dict, edges: list) -> set[str]:
    """Files of the test nodes joined to ``rel`` by a ``tests`` edge.

    Direction follows ``references/impact-graph-operations.md``, which teaches
    ``add_edge <test_file_id> <function_id> tests`` — the *source* is the
    test. Reading it the other way round would silently return the wrong set,
    so it is asserted by a test rather than left to the comment.
    """
    covered = {
        nid for nid, node in nodes.items()
        if isinstance(node, dict) and node.get("file") == rel
    }
    if not covered:
        return set()

    sources = {
        edge.get("source") for edge in edges
        if isinstance(edge, dict)
        and edge.get("type") == "tests"
        and edge.get("target") in covered
    }
    files = set()
    for source in sources:
        node = nodes.get(source)
        if isinstance(node, dict) and node.get("file"):
            files.add(node["file"])
    return files


def select_affected(root: str, cwd: str) -> tuple[list[str] | None, str]:
    """Test files covering everything changed since the last full green.

    Returns ``(files, "")`` when the subset can be trusted, or
    ``(None, reason)`` when it cannot — and *every* uncertainty returns None.
    Narrowing is earned per changed file: one file the graph cannot account
    for widens the whole run back to the full suite. That is #83's lesson
    stated positively — a selective suite that quietly skips the file you just
    changed is a green that means nothing.

    What an ``affected`` green does and does not claim: the source-to-test map
    is ``docs/holtz/impact-graph.json``, which the agent writes. So this is a
    **cost** optimisation bounded by the periodic full run that
    ``iteration_boundary`` requires, not an independent integrity claim. A
    bogus ``tests`` edge can narrow one ``fix_commit``; it cannot survive the
    next boundary, which accepts ``full`` and nothing else.
    """
    baseline, reason = _baseline_commit(cwd)
    if baseline is None:
        return None, reason

    changed, reason = _changed_since(root, baseline)
    if changed is None:
        return None, reason
    if not changed:
        return None, f"nothing has changed since {baseline[:7]}"

    # Loaded on first need, not up front: a change that is only test files
    # answers itself, and a project that has not been mapped yet should not be
    # denied that. Once a source file needs the map, an unreadable one widens.
    graph: tuple[dict, list] | None = None

    selected: set[str] = set()
    for rel in changed:
        if os.path.basename(rel) == "conftest.py":
            # A conftest reshapes collection and fixtures for every test
            # beneath it. No `tests` edge expresses that, and no selection
            # short of the full suite is honest about it.
            return None, f"{rel} changed — a conftest's reach is every test below it"
        if _TEST_FILE_RE.match(os.path.basename(rel)):
            selected.add(rel)
            continue
        if graph is None:
            graph = _load_graph(cwd)
            if graph is None:
                return None, f"no readable impact graph at {GRAPH_PATH}"
        nodes, edges = graph
        covering = _covering_tests(rel, nodes, edges)
        if not covering:
            return None, (
                f"no `tests` edge covers {rel} — add one with "
                "`impact_graph.py add_edge <test_file_id> <entity_id> tests`"
            )
        selected |= covering

    present = sorted(
        path for path in selected if os.path.isfile(os.path.join(root, path))
    )
    if not present:
        return None, "every selected test file is missing from the working tree"
    return present, ""


def _suite_invocation(cwd: str, root: str, scope: str) -> tuple[str, str]:
    """The command to run and the scope it will actually prove.

    The returned scope is what gets recorded, so it is always what ran: a
    request for ``affected`` that could not be narrowed comes back as
    ``full``. Recording the request rather than the result would understate a
    full run, and ``full`` satisfies an ``affected`` check anyway.
    """
    base = suite_command()
    if scope != "affected":
        return base, "full"

    files, reason = select_affected(root, cwd)
    if files is None:
        print(f"verify_suite: running the full suite — {reason}", file=sys.stderr)
        return base, "full"

    print(
        f"verify_suite: affected subset, {len(files)} file(s): {' '.join(files)}",
        file=sys.stderr,
    )
    return base + " " + " ".join(shlex.quote(path) for path in files), "affected"


# ── Modes ────────────────────────────────────────────────────────────────────


def _run_suite(command: str, cwd: str) -> subprocess.CompletedProcess:
    """Run the suite command, echoing its output as it is a user's evidence."""
    print(f"verify_suite: running {command}", file=sys.stderr)
    proc = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc


def mode_record(cwd: str, root: str, scope: str) -> int:
    """Run the suite and, on green, record ``suite_green`` for this tree."""
    sys.path.insert(0, _hooks_dir())
    from _common import record_authed_event  # noqa: PLC0415

    tree_hash = compute_tree_hash(root)
    print(f"verify_suite: tree_hash={tree_hash}", file=sys.stderr)

    command, scope = _suite_invocation(cwd, root, scope)
    proc = _run_suite(command, cwd)

    if scope == "affected" and proc.returncode in SELECTION_FAILURE_EXITS:
        # The narrowed command did not run tests and fail — it failed to run
        # tests. A usage error or an empty collection says the selection is
        # unusable here, not that the code is broken, and the honest response
        # to "I could not test the subset" is to test everything.
        print(
            f"verify_suite: the affected subset proved nothing "
            f"(exit {proc.returncode}) — widening to the full suite",
            file=sys.stderr,
        )
        command, scope = suite_command(), "full"
        proc = _run_suite(command, cwd)

    if proc.returncode != 0:
        print(
            f"FAIL: suite exited {proc.returncode} — nothing recorded. "
            "Fix the failures and run this again."
            + (
                "\n  If the failure is the subset itself rather than the code, "
                f"--scope full always satisfies a --scope {scope} check."
                if scope == "affected"
                else ""
            ),
            file=sys.stderr,
        )
        return proc.returncode

    fields = {
        "project": os.path.basename(root),
        "run": _run_number(cwd),
        "auditor": "holtz",
        "tree_hash": tree_hash,
        "scope": scope,
        "command": command,
    }
    # The baseline the *next* affected run measures its diff from. Recorded
    # from `git rev-parse` here, never from a caller.
    head = _git(["rev-parse", "HEAD"], root)
    if head and _COMMIT_RE.match(head):
        fields["commit_hash"] = head
    passed = _PASSED_RE.search(proc.stdout)
    if passed:
        fields["test_count"] = passed.group(1)

    try:
        record_authed_event("suite_green", fields, cwd)
    except (OSError, RuntimeError) as exc:
        print(
            f"FAIL: suite passed but recording suite_green failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: suite green, recorded suite_green scope={scope} tree_hash={tree_hash}")
    return 0


def mode_check(cwd: str, root: str, scope: str) -> int:
    """Exit 0 iff a ``suite_green`` already covers this exact tree."""
    tree_hash = compute_tree_hash(root)
    accepted = accepted_scopes(scope)
    scope_list = ", ".join(f"'{s}'" for s in accepted)
    # The scopes come from a fixed tuple and the hash is computed here, never
    # supplied by a caller — but assert the hex shape anyway before it reaches
    # a SQL string. The property that makes the interpolation safe should be
    # checked at the point that relies on it, not just argued for in a comment.
    if not _TREE_HASH_RE.match(tree_hash):  # pragma: no cover - unreachable
        print(f"FAIL: computed tree hash is malformed: {tree_hash!r}", file=sys.stderr)
        return 1
    sql = (
        "SELECT count(*) AS n FROM events WHERE type='suite_green' "
        f"AND tree_hash='{tree_hash}' AND scope IN ({scope_list})"
    )

    binary, config_dir, problem = _sahjhan_target(cwd)
    # Fail closed, and *without* an escape line. An unevaluable suite gate that
    # allowed the transition would be a silent false green — the thing this
    # whole mechanism exists to prevent — so a broken toolchain blocks and says
    # which part broke. It does not print `Run: … --record`, because with no
    # sahjhan binary that command cannot work either; an escape that does not
    # run is the #77 deadlock shape.
    if binary is None or config_dir is None:
        print(f"FAIL: cannot evaluate the suite gate — {problem}", file=sys.stderr)
        return 1

    rows, problem = _query_ledger(binary, config_dir, cwd, sql)
    if rows is None:
        return _block(problem, tree_hash, accepted, scope)

    try:
        count = int(rows[0]["n"])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        return _block(
            f"cannot read the ledger query result: {exc}", tree_hash, accepted, scope
        )

    if count > 0:
        print(f"PASS: suite_green recorded for tree_hash={tree_hash} (scope in {accepted})")
        return 0

    return _block(
        "no suite_green for this working tree", tree_hash, accepted, scope
    )


# ── Entrypoint ───────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record or check that the suite passed on this working tree"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record",
        action="store_true",
        help="run the suite and record suite_green on success (agent path)",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="exit 0 iff suite_green already covers this tree (gate path)",
    )
    group.add_argument(
        "--print-tree-hash",
        action="store_true",
        help="print the computed tree hash and exit (diagnostic)",
    )
    group.add_argument(
        "--print-affected",
        action="store_true",
        help=(
            "print the test files --scope affected would run, one per line, "
            "and why it would not narrow (diagnostic; empty means full suite)"
        ),
    )
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        default="full",
        help=(
            "which slice of the suite: 'full' runs everything (default); "
            "'affected' runs the tests covering what changed since the last "
            "full green, and widens back to 'full' whenever it cannot prove "
            "that subset is complete"
        ),
    )
    parser.add_argument("--cwd", default=".", help="target project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    root = repo_root(cwd)
    if root is None:
        print(
            f"FAIL: {cwd} is not inside a git repository — the tree hash "
            "cannot be computed, so the suite result cannot be pinned to a tree.",
            file=sys.stderr,
        )
        return 1

    if args.print_tree_hash:
        print(compute_tree_hash(root))
        return 0

    if args.print_affected:
        files, reason = select_affected(root, cwd)
        if files is None:
            print(f"verify_suite: would run the full suite — {reason}", file=sys.stderr)
            return 0
        print("\n".join(files))
        return 0

    if args.record:
        return mode_record(cwd, root, args.scope)
    return mode_check(cwd, root, args.scope)


if __name__ == "__main__":
    sys.exit(main())

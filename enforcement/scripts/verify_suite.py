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

Known limitation, stated so nobody "fixes" it by accident: the hash covers
tracked and untracked-but-not-ignored file *contents*, not the interpreter or
installed dependencies. Upgrading a dependency without touching a lockfile
leaves a stale ``suite_green`` valid. Lockfiles are tracked, so the ordinary
case is covered; a bare ``pip install -U`` is not.

Usage::

    python3 verify_suite.py --record [--scope full] [--cwd .]
    python3 verify_suite.py --check  [--scope full] [--cwd .]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
# that changed (T3). Ordered weakest-first: a `full` run satisfies a request
# for `affected`, never the reverse — narrowing must always be the explicit
# ask, so a missing scope can only ever over-test.
SCOPES: tuple[str, ...] = ("affected", "full")

# STATUS.md and PUNCHLIST.md are rewritten on every fix, and the ledger itself
# is appended to by `--record`. Neither can affect the target's tests, and
# including them would invalidate the hash the instant it was recorded.
EXCLUDED_PREFIXES = ("docs/holtz/",)

_PASSED_RE = re.compile(r"(\d+) passed")
_TREE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


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


# ── Modes ────────────────────────────────────────────────────────────────────


def mode_record(cwd: str, root: str, scope: str) -> int:
    """Run the suite and, on green, record ``suite_green`` for this tree."""
    sys.path.insert(0, _hooks_dir())
    from _common import record_authed_event  # noqa: PLC0415

    tree_hash = compute_tree_hash(root)
    command = suite_command()

    print(f"verify_suite: tree_hash={tree_hash}", file=sys.stderr)
    print(f"verify_suite: running {command}", file=sys.stderr)
    proc = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)

    if proc.returncode != 0:
        print(
            f"FAIL: suite exited {proc.returncode} — nothing recorded. "
            "Fix the failures and run this again.",
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
    sys.path.insert(0, _hooks_dir())
    from _common import resolve_config_dir  # noqa: PLC0415
    from _resolve import ensure_sahjhan  # noqa: PLC0415

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

    binary = ensure_sahjhan()
    config_dir, found = resolve_config_dir(cwd)
    # Fail closed. An unevaluable suite gate that allowed the transition would
    # be a silent false green — exactly what this whole mechanism exists to
    # prevent — so a broken toolchain blocks and says which part broke.
    if binary is None or not found:
        print(
            "FAIL: cannot evaluate the suite gate — "
            f"sahjhan binary={'missing' if binary is None else binary}, "
            f"config_dir={'not found' if not found else config_dir}",
            file=sys.stderr,
        )
        return 1

    try:
        proc = subprocess.run(
            [binary, "--config-dir", config_dir, "query", sql, "--format", "json"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _block(f"cannot query the ledger: {exc}", tree_hash, accepted, scope)

    if proc.returncode != 0:
        # A ledger that has never been initialised surfaces here as an I/O
        # error rather than a zero count. Either way there is no evidence, and
        # either way `--record` is the thing to run.
        return _block(
            f"ledger query failed (exit {proc.returncode}): {proc.stderr.strip()}",
            tree_hash, accepted, scope,
        )

    try:
        rows = json.loads(proc.stdout)
        count = int(rows[0]["n"])
    except (json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError) as exc:
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
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        default="full",
        help="which slice of the suite: 'full' runs everything (default)",
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

    if args.record:
        return mode_record(cwd, root, args.scope)
    return mode_check(cwd, root, args.scope)


if __name__ == "__main__":
    sys.exit(main())

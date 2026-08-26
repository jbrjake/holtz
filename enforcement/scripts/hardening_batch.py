#!/usr/bin/env python3
"""Close a module's `fault_injected` findings with one hardening commit.

P0.5's second route (D29), sequenced by D34 and given its module rule by D35.
~22 of the audited run's 62 commits went to defects reachable only by making
some other call raise — a full fix cycle each — while 51 of its 75 open HIGHs
predated the first commit and were never worked. The clause does not discard
those defects; it stops paying a fix cycle for each one.

**A module is the containing directory** (D35): `tqdm/std.py:736` and
`tqdm/utils.py:240` batch together under `tqdm`; `tqdm/contrib/x.py:12` is its
own. The rule is applied here, in Python, because `location` is free text —
`file.py:88`, `` `file.py:88` `` and `file.py:88 (function f)` all appear in
this repo's archived ledgers. The ledger holds the *result*, one
`finding_resolved` per covered id, so nothing downstream does string surgery.

The split mirrors `stale_sweep.py`: this runs in the agent's shell, which is
sandboxed and cannot reach the daemon, so it derives, checks and prints.
`hardening_batch_courier.py` runs outside the sandbox, re-derives the same
population and writes the resolutions.

What makes the claim cost something is the commit. Four refusals:

* **A module nobody filed against.** The batch has to name a directory the
  board actually carries.
* **A commit that names only some of the module.** "One hardening commit per
  module" is the clause; closing half a directory leaves the rest to a second
  commit and the saving with it.
* **A commit that names another module's findings.** One commit, one module —
  otherwise a single commit disposes of the whole board.
* **A commit already spent, or with no changes in it.** A message is cheap; a
  diff that has not been used before is the work.

A finding whose `location` cannot be placed is refused too, and named. It
belongs to no module, so no batch could ever cover it and `converge` would
block forever; saying so while re-filing it is still cheap is the escape.

Usage::

    python3 hardening_batch.py --record --module tqdm
    python3 hardening_batch.py --show [--cwd .]
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ledger_query import query_ledger, sahjhan_target  # noqa: E402
from merge_punchlists import parse_location  # noqa: E402

# The line `--record` prints and `hardening_batch_courier.py` requires before it
# writes anything. Named here, imported there — the two ends of a channel that
# would fail silently if they ever disagreed about the word.
RECORD_MARKER = "HARDENING-BATCH:"

# The predicate, by name. Resolved out of `protocol.toml` at runtime rather than
# restated here — H7 exists because a script carrying its own copy of a gate's
# SQL is how #77 shipped.
POPULATION_QUERY = "open_fault_injected_findings"

# Every commit hash a resolution already carries. Named for the same reason,
# and it is what keeps "one hardening commit per module" from costing one
# commit in total.
SPENT_QUERY = "resolution_commit_hashes"

# Where a batch happens: `phase-convergence.md`, Step 15, immediately before
# `transition converge`. Constants for the same reason `stale_sweep.py` carries
# SWEEP_PHASE — the courier writes a resolution the agent no longer can, and a
# writer of someone else's resolution reads nothing out of a tree the agent can
# edit. Pinned against the document by
# `test_the_stamp_names_the_step_that_teaches_the_batch`.
BATCH_PHASE = "convergence"
BATCH_STEP = "15"

# The root module. `os.path.dirname("setup.py")` is the empty string, which is
# not a name a message or a refusal can print.
ROOT_MODULE = "."


def module_of(location: str) -> str | None:
    """The containing directory of the file ``location`` names (D35).

    ``None`` when no path can be read out of it — an answer, not a default.
    Bucketing an unplaceable finding into the root module would let a commit
    that has nothing to do with it close it.
    """
    path = parse_location(location).path
    if not path.strip():
        return None
    return os.path.dirname(path.strip()) or ROOT_MODULE


class Board(NamedTuple):
    """The open `fault_injected` population, as the ledger states it."""

    modules: dict[str, list[str]]
    context: dict[str, dict[str, str]]
    unplaceable: list[str]


def _ask(cwd: str, query_name: str) -> tuple[list[dict] | None, str]:
    """Run a `[queries.<name>]` predicate over the active ledger.

    Resolving the name rather than restating the SQL is the whole point: there
    is one predicate and every consumer reaches the same one. H7 exists because
    a second copy is how #77 shipped.
    """
    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        return None, f"cannot reach the ledger — {problem}"

    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
    from _protocol_cache import named_query_sql  # noqa: PLC0415

    sql = named_query_sql(config_dir, query_name)
    if sql is None:
        return None, f"protocol.toml has no [queries.{query_name}]"
    return query_ledger(binary, config_dir, cwd, sql)


def board(cwd: str) -> tuple[Board | None, str]:
    """Every open `fault_injected` finding, grouped by containing directory."""
    rows, problem = _ask(cwd, POPULATION_QUERY)
    if rows is None:
        return None, problem

    modules: dict[str, list[str]] = {}
    context: dict[str, dict[str, str]] = {}
    unplaceable: list[str] = []
    for row in rows:
        finding_id = str(row.get("id") or "")
        if not finding_id:
            continue
        module = module_of(str(row.get("location") or ""))
        if module is None:
            unplaceable.append(finding_id)
            continue
        modules.setdefault(module, []).append(finding_id)
        context[finding_id] = {
            "project": str(row.get("project") or ""),
            "run": str(row.get("run") or ""),
            "auditor": str(row.get("auditor") or ""),
        }
    return Board({name: sorted(set(ids)) for name, ids in sorted(modules.items())},
                 context, sorted(set(unplaceable))), ""


class Batch(NamedTuple):
    """A checked batch: the ids one hardening commit is about to close."""

    module: str
    ids: list[str]
    commit_hash: str
    context: dict[str, dict[str, str]]


def _git(cwd: str, *args: str) -> tuple[str | None, str]:
    """Trimmed stdout of a git command, or ``(None, problem)``."""
    try:
        result = subprocess.run(["git", "-C", cwd, *args],
                                capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cannot run git {' '.join(args)}: {exc}"
    if result.returncode != 0:
        return None, f"git {' '.join(args)} failed: {result.stderr.strip()}"
    return result.stdout.strip(), ""


def check(cwd: str, module: str) -> tuple[Batch | None, str]:
    """The batch this commit may close, or the reason it may not."""
    state, problem = board(cwd)
    if state is None:
        return None, problem

    if state.unplaceable:
        return None, (
            f"{len(state.unplaceable)} finding(s) name a location no module "
            f"can be read from: {', '.join(state.unplaceable)}.\n"
            "  No batch can cover them and `converge` will block. Re-file each "
            "with a `file:line` location."
        )

    ids = state.modules.get(module)
    if not ids:
        known = ", ".join(state.modules) or "none"
        return None, (
            f"no open fault_injected findings in module {module!r} "
            f"(modules on the board: {known})"
        )

    commit_hash, problem = _git(cwd, "rev-parse", "--short=7", "HEAD")
    if commit_hash is None:
        return None, problem

    changed, problem = _git(cwd, "show", "--name-only", "--format=", "HEAD")
    if changed is None:
        return None, problem
    if not changed.strip():
        return None, f"HEAD ({commit_hash}) has no changes in it — nothing was hardened"

    message, problem = _git(cwd, "log", "-1", "--format=%B")
    if message is None:
        return None, problem

    if missing := [item for item in ids if item not in message]:
        return None, (
            f"HEAD ({commit_hash}) does not name {len(missing)} of the "
            f"{len(ids)} open fault_injected finding(s) in {module}: "
            f"{', '.join(missing)}"
        )

    elsewhere = sorted(
        item
        for name, other in state.modules.items() if name != module
        for item in other if item in message
    )
    if elsewhere:
        return None, (
            f"HEAD ({commit_hash}) also names findings outside {module}: "
            f"{', '.join(elsewhere)}. One hardening commit covers one module."
        )

    spent, problem = _spent_commits(cwd)
    if spent is None:
        return None, problem
    if commit_hash in spent:
        return None, (
            f"HEAD ({commit_hash}) has already closed a finding — a second "
            "module cannot ride the same commit. Make the hardening commit "
            f"for {module} first."
        )

    return Batch(module, ids, commit_hash,
                 {item: state.context[item] for item in ids}), ""


def _spent_commits(cwd: str) -> tuple[set[str] | None, str]:
    """Every `commit_hash` already carried by a resolution on this ledger."""
    rows, problem = _ask(cwd, SPENT_QUERY)
    if rows is None:
        return None, problem
    return {str(row.get("commit_hash") or "") for row in rows}, ""


# ── Command recognition ──────────────────────────────────────────────────────

# One recognizer, defined beside the command it recognizes, imported by the
# courier rather than restated there — a drift between what the skill file
# teaches and what the courier accepts would be a silent deadlock.
_SCRIPT_TAIL = os.path.join("enforcement", "scripts", "hardening_batch.py")
_INTERPRETERS = frozenset({"python", "python3", "py"})


def module_of_command(segment: str) -> str | None:
    """The ``--module`` value if ``segment`` is the record command.

    Read from the command text *as typed*, which is what the host reports to a
    PostToolUse hook — ``${CLAUDE_PLUGIN_ROOT}`` is still a literal there, so
    the script is identified by its tail rather than by resolving a path the
    hook cannot expand the way the shell did.

    ``--cwd`` is rejected rather than parsed: the courier derives against the
    *event's* cwd, so a batch pointed elsewhere would attach another project's
    board to this ledger. The flag is for tests and diagnostics.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None
    if os.path.basename(tokens[0]) not in _INTERPRETERS:
        return None
    if not tokens[1].endswith(_SCRIPT_TAIL):
        return None

    module: str | None = None
    seen_record = False
    rest = tokens[2:]
    while rest:
        flag = rest.pop(0)
        if flag == "--record":
            seen_record = True
        elif flag == "--module" and rest:
            module = rest.pop(0)
        else:
            return None
    return module if seen_record else None


# ── Modes ────────────────────────────────────────────────────────────────────


def mode_record(cwd: str, module: str) -> int:
    """Check the commit against the board and print the courier's line."""
    batch, problem = check(cwd, module)
    if batch is None:
        print(
            f"FAIL: this commit does not close {module} — {problem}\n"
            "  Nothing was recorded, so the findings are still open.",
            file=sys.stderr,
        )
        return 1

    print(
        f"hardening_batch: {len(batch.ids)} finding(s) in {module} hardened by "
        f"{batch.commit_hash}",
        file=sys.stderr,
    )
    # Printed last so it survives output truncation. It carries nothing the
    # courier reads back — the courier re-derives the whole batch for itself.
    print(f"{RECORD_MARKER} {json.dumps({'module': module}, sort_keys=True)}")
    return 0


def mode_show(cwd: str) -> int:
    """Print the module -> ids map without recording anything (diagnostic)."""
    state, problem = board(cwd)
    if state is None:
        print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    if state.unplaceable:
        print(
            "WARNING: no module can be read from the location of "
            f"{', '.join(state.unplaceable)}",
            file=sys.stderr,
        )
    print(json.dumps(state.modules, sort_keys=True))
    return 0


# ── Entrypoint ───────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Close a module's fault_injected findings with one hardening commit"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record",
        action="store_true",
        help="emit the evidence the courier turns into finding_resolved rows",
    )
    group.add_argument(
        "--show",
        action="store_true",
        help="print the module -> ids map this batch works from (diagnostic)",
    )
    parser.add_argument("--module", help="the containing directory this commit hardens")
    parser.add_argument("--cwd", default=".", help="target project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    if args.show:
        return mode_show(cwd)
    if not args.module:
        parser.error("--record requires --module")
    return mode_record(cwd, args.module)


if __name__ == "__main__":
    sys.exit(main())

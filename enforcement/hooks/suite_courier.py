#!/usr/bin/env python3
"""PostToolUse courier: record `suite_green` for a suite the agent just ran.

`verify_suite.py --record` runs the project's tests, which means it runs in the
agent's shell — inside the sandbox, where the daemon socket is unreachable. It
cannot write a restricted event. This hook runs outside the sandbox and can.

The division is chosen so that nothing a gate reads passes through the agent:

  tree_hash    — this hook runs `git` itself, outside the sandbox
  commit_hash  — likewise
  scope        — from the command text the *host* reports, upgraded only when
                 this hook re-derives the same "cannot narrow" answer the run
                 reached; never from the run's account of itself
  project/run  — derived from the tree and the active-ledger marker
  command      — from the marker; informational, no gate reads it
  test_count   — from the marker; informational, optional

Two independent signals must agree before anything is written, because either
one alone has a hole. Claude Code 2.x omits `exit_code` and fires PostToolUse
only on success, so "the event fired" is the exit status — but a future version
that fired on failure would turn a red suite into a recorded green. And the
marker alone is just text on a stream the agent owns. Together: the host says
the command succeeded, and the script says it saw green. Neither is something
the agent can produce by asking.

The command must also be a single shell segment matching the invocation
`phase-fix-loop.md` prescribes, so there is no `echo 'SUITE-GREEN: …'` and no
work chained around a real run.

What remains agent-influenced is what was always agent-influenced: the tests
themselves, and `$HOLTZ_PYTEST`. Confining the shell does not make a project's
own test suite honest, and this hook does not pretend otherwise.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from verify_suite import (  # noqa: E402
    _COMMIT_RE,
    RECORD_MARKER,
    _git,
    _run_number,
    compute_tree_hash,
    record_scope_of,
    repo_root,
    select_affected,
)

from _common import (  # noqa: E402
    bash_exit_code,
    bash_output,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
)
from _protocol_cache import _split_shell_segments  # noqa: E402

_TEST_COUNT_RE = re.compile(r"^\d+$")


def _evidence(output: str) -> dict | None:
    """The `SUITE-GREEN:` payload from the tool output, or None if absent.

    Scanned from the end: the marker is printed last so it survives output
    truncation, and a green run's own output is the only other thing that
    could contain the word.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if not stripped.startswith(RECORD_MARKER):
            continue
        try:
            payload = json.loads(stripped[len(RECORD_MARKER):])
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _scope(command: str) -> str | None:
    """The scope this Bash line records for, if it is exactly that command.

    A single segment, deliberately. `verify_suite.py --record && git commit`
    is not the prescribed command, and accepting it would let arbitrary work
    ride the one Bash line whose success this hook converts into evidence.
    """
    segments = _split_shell_segments(command)
    if len(segments) != 1:
        return None
    return record_scope_of(segments[0])


def _effective_scope(scope: str, root: str, cwd: str) -> str:
    """Upgrade `affected` to `full` when the subset provably could not narrow.

    A `--scope affected` run widens to the whole suite whenever it cannot
    prove a subset is complete, and that run really did test everything — so
    recording it as `affected` would throw away a full green and force the
    suite to run again before the three transitions that demand one.

    The upgrade is *re-derived*, not read from the run's report. `scope` is a
    field gates consult, so taking the run's word for it would put an
    agent-authored value where a gate believes it. `select_affected` is a
    function of the tree, the impact graph and the baseline commit; running it
    here, outside the sandbox, on the same unchanged tree, answers the same
    question the run answered without trusting the answer.

    The reverse direction is never taken. A narrowed run that widened at
    runtime — pytest collected nothing, so `verify_suite` re-ran everything —
    is recorded as `affected`, because that is a fact about the run this hook
    cannot re-derive, and under-claiming only ever costs a suite run.
    """
    if scope != "affected":
        return scope
    files, _reason = select_affected(root, cwd)
    return "full" if files is None else "affected"


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    scope = _scope(command)
    if scope is None:
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    evidence = _evidence(bash_output(event))
    if evidence is None:
        # The command the host says succeeded, without the line the script
        # only prints on green. Warned rather than passed over in silence:
        # nothing was recorded, so `fix_commit` will block later with no
        # obvious connection to this moment.
        exit_warn(
            "suite_green NOT recorded: the suite run reported success but its "
            f"'{RECORD_MARKER}' evidence line is missing from the output. Run "
            "the same command again; if it keeps happening the output is being "
            "truncated and the suite must be run with less noise.",
            "PostToolUse",
        )

    cwd = event.get("cwd", os.getcwd())
    root = repo_root(cwd)
    if root is None:
        exit_warn(
            "suite_green NOT recorded: this is not a git working tree, so the "
            "tree hash the fix_commit gate compares against cannot be computed.",
            "PostToolUse",
        )

    # The exit helpers are re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing above. Same idiom as
    # pre_tool_hook.py.
    assert scope is not None
    assert evidence is not None
    assert root is not None

    fields = {
        "project": os.path.basename(root),
        "run": _run_number(cwd),
        "auditor": "holtz",
        "tree_hash": compute_tree_hash(root),
        "scope": _effective_scope(scope, root, cwd),
        "command": str(evidence.get("command") or "unreported"),
    }
    # The baseline the *next* affected run measures its diff from — read from
    # git here, never from the run that is being recorded.
    head = _git(["rev-parse", "HEAD"], root)
    if head and _COMMIT_RE.match(head):
        fields["commit_hash"] = head
    count = str(evidence.get("test_count") or "")
    if _TEST_COUNT_RE.match(count):
        fields["test_count"] = count

    try:
        record_authed_event("suite_green", fields, cwd)
    except (OSError, RuntimeError) as exc:
        exit_warn(
            f"suite_green NOT recorded: the daemon refused ({exc}). The suite "
            "passed, but fix_commit reads the ledger and will block until this "
            "is written.",
            "PostToolUse",
        )

    exit_ok()


if __name__ == "__main__":
    main()

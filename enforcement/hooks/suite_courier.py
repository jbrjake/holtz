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
  test_count   — from the marker; must be a nonzero count of passes

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

The marker is only as good as the script that printed it, so three more checks
stand behind it (D-v). The script the command ran must be this plugin's own
`verify_suite.py`, and its sha256 must match its row in `trusted-callers.toml`;
a same-named file anywhere else prints the same marker. That script runs
`<python> -m pytest` with fixed flags, so the only thing the evidence reports
that it did not decide itself is the interpreter — and a named interpreter
must be a compiled executable, read here and never run. And the run must have
passed at least one test.

What remains agent-influenced is what was always agent-influenced: the tests
themselves, and the environment they run in — the interpreter's own packages
included. Confining the shell does not make a project's own test suite honest,
and this hook does not pretend otherwise.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
import tomllib

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from _recorded_command import (  # noqa: E402
    looks_like_a_record,
    not_the_taught_form,
)
from verify_suite import (  # noqa: E402
    _COMMIT_RE,
    RECORD_MARKER,
    SCRIPT_TAIL,
    TAUGHT_PREFIX,
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
    project_anchor,
    read_event,
    record_authed_event,
)
from _protocol_cache import _split_shell_segments  # noqa: E402

_TEST_COUNT_RE = re.compile(r"^\d+$")

_CONFIG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLUGIN_ROOT = os.path.dirname(_CONFIG_DIR)

# The one script whose green this hook records, and where its hash is pinned:
# `trusted-callers.toml`, the manifest the daemon authenticates callers by,
# keyed config-dir-relative the same way (D-v).
PINNED_SCRIPT = os.path.join(_CONFIG_DIR, "scripts", "verify_suite.py")
MANIFEST = os.path.join(_CONFIG_DIR, "trusted-callers.toml")
_MANIFEST_KEY = "scripts/verify_suite.py"

# The first bytes of a compiled executable: ELF; Mach-O in both widths and
# byte orders; a universal binary.
_EXECUTABLE_MAGIC = (
    b"\x7fELF",
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)


def _executed_script(segment: str, cwd: str) -> str:
    """The file a recognized segment ran, resolved the way the shell did.

    The host reports the command as typed, so `${CLAUDE_PLUGIN_ROOT}` is still
    a literal here and is expanded to the value the shell had.
    """
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or _PLUGIN_ROOT
    path = shlex.split(segment)[1]
    path = path.replace("${CLAUDE_PLUGIN_ROOT}", root).replace("$CLAUDE_PLUGIN_ROOT", root)
    return os.path.realpath(os.path.join(cwd, path))


def _pin_problem(script: str, manifest: str) -> str | None:
    """Why ``script`` is not the manifest's ``verify_suite.py``, or None."""
    try:
        with open(manifest, "rb") as fh:
            callers = tomllib.load(fh).get("callers", {})
        with open(script, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return f"cannot check {script} against {manifest}: {exc}"
    pinned = callers.get(_MANIFEST_KEY)
    if pinned is None:
        return (f"{manifest} has no row for {_MANIFEST_KEY}. "
                "Run scripts/hash-trusted-callers.sh.")
    if pinned != f"sha256:{digest}":
        return (f"{script} does not match its row in {manifest}. "
                "Run scripts/hash-trusted-callers.sh.")
    return None


def _script_problem(segment: str, cwd: str) -> str | None:
    """Why the script this segment ran is not the pinned one, or None."""
    script = _executed_script(segment, cwd)
    if script != os.path.realpath(PINNED_SCRIPT):
        return f"{script} is not the plugin's verify_suite.py ({PINNED_SCRIPT})."
    return _pin_problem(script, MANIFEST)


def _interpreter_problem(python: str, cwd: str) -> str | None:
    """Why the interpreter the run named is not a compiled executable, or None.

    Read, never run: executing it here would run agent-chosen code outside
    the sandbox. A bare name like ``python3`` resolves through the agent's
    PATH, which this hook cannot see, so only a named path is inspected. A
    file with no ``#!`` is refused too — ``sh`` runs one as a script.
    """
    if os.sep not in python:
        return None
    try:
        with open(os.path.realpath(os.path.join(cwd, python)), "rb") as fh:
            head = fh.read(4)
    except OSError as exc:
        return f"the interpreter {python} cannot be read ({exc})."
    if not head.startswith(_EXECUTABLE_MAGIC):
        return f"the interpreter {python} is not a compiled executable."
    return None


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



def _warn_if_it_meant_to_record(command: str, event: dict) -> None:
    """Say something when the recognizer refused a line that asked to record.

    The `None` above answers two questions at once — "not my command" and "my
    command, in a shape I refuse" — and exiting 0 on both is items 34 and 28:
    the agent believes it recorded something, nothing was written, and the gate
    that needed the evidence blocks later with no connection to this moment.

    Only when the host says the command *succeeded*. A non-zero exit means the
    script's own parser already refused it and said why, and repeating that
    here would turn one clear message into two.
    """
    if bash_exit_code(event) != 0:
        return
    if not looks_like_a_record(command, SCRIPT_TAIL):
        return
    exit_warn(not_the_taught_form('suite_green', TAUGHT_PREFIX), "PostToolUse")


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    scope = _scope(command)
    if scope is None:
        _warn_if_it_meant_to_record(command, event)
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    problem = _script_problem(_split_shell_segments(command)[0], cwd)
    if problem:
        exit_warn(f"suite_green NOT recorded: {problem}", "PostToolUse")

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

    assert evidence is not None
    python = evidence.get("python")
    if not isinstance(python, str) or not python:
        exit_warn(
            "suite_green NOT recorded: the evidence line names no interpreter, "
            "and the pinned verify_suite.py always does.",
            "PostToolUse",
        )
    assert isinstance(python, str)
    problem = _interpreter_problem(python, cwd)
    if problem:
        exit_warn(f"suite_green NOT recorded: {problem}", "PostToolUse")

    count = str(evidence.get("test_count") or "")
    if not (_TEST_COUNT_RE.match(count) and int(count) > 0):
        exit_warn(
            "suite_green NOT recorded: the run reported no passing test, and a "
            "green that passed nothing proves nothing.",
            "PostToolUse",
        )

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
        # The project, not the checkout. `root` is this event's git top-level,
        # which in a fix subagent's linked worktree is the worktree directory —
        # so a three-wide run recorded three different project names for one
        # project. `tree_hash` and the scope below stay on `root` on purpose:
        # those describe the tree that was actually tested.
        "project": os.path.basename(project_anchor(cwd)),
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

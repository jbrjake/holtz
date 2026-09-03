#!/usr/bin/env python3
"""PostToolUse courier: close a module's `fault_injected` findings.

`hardening_batch.py --record` runs in the agent's shell — inside the sandbox,
where the daemon socket is unreachable — so it derives, checks and prints. This
hook runs outside the sandbox and writes.

It writes **N events**, one `finding_resolved` per covered id, and that is the
reason it exists rather than a transition `emits`. `EmitConfig`
(sahjhan `src/config/transitions.rs:101`) produces exactly one event with a
fixed field map and `emits` is a `Vec<EmitConfig>`, not a fan-out: no
transition can write one resolution per id in a batch whose size the config
does not know. A courier can.

Closing with `finding_resolved` rather than a deferral or a coverage marker
keeps D29's rule — there stays exactly one definition of closed, so every
counter, render and gate that already reads resolution sees a hardened finding
without being told anything new, and `all_critical_resolved` (which refuses a
deferral by design) can clear.

  ids / module   — re-derived here from the ledger, never read back from the
                   script's report
  commit_hash    — HEAD, read here
  project / run / auditor — off each finding's own latest filing
  phase / step   — constants: a batch is Step 15 of convergence, and the doc
                   that teaches it is pinned against them in the suite

Two signals must agree before anything is written. The host says the command
succeeded, and the script says it got far enough to print its marker. The
marker alone is text on a stream the agent owns, and "PostToolUse fired" alone
would become a false record the day the harness starts firing on failure.

The whole check runs again here rather than being trusted from the script's
exit code. The script is in a tree the agent can edit; the ledger is not.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from _recorded_command import (  # noqa: E402
    looks_like_a_record,
    not_the_taught_form,
)
from hardening_batch import (  # noqa: E402
    BATCH_PHASE,
    BATCH_STEP,
    RECORD_MARKER,
    SCRIPT_TAIL,
    TAUGHT_PREFIX,
    check,
    module_of_command,
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


def _marked(output: str) -> bool:
    """True if the script printed its marker.

    Scanned from the end: the marker is printed last so it survives output
    truncation.
    """
    return any(
        line.strip().startswith(RECORD_MARKER) for line in reversed(output.splitlines())
    )


def _module(command: str) -> str | None:
    """The module this Bash line batches, if it is exactly that command.

    A single segment, deliberately. Accepting `hardening_batch.py --record &&…`
    would let arbitrary work ride the one Bash line whose success this hook
    turns into a board full of closed findings.
    """
    segments = _split_shell_segments(command)
    if len(segments) != 1:
        return None
    return module_of_command(segments[0])



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
    exit_warn(not_the_taught_form('hardening batch', TAUGHT_PREFIX), "PostToolUse")


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    module = _module(command)
    if module is None:
        _warn_if_it_meant_to_record(command, event)
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    if not _marked(bash_output(event)):
        # The command the host says succeeded, without the line the script
        # prints once it has checked the board. Warned rather than passed over
        # in silence: nothing was closed, so `converge` will refuse later with
        # no obvious connection to this moment.
        exit_warn(
            "hardening batch NOT recorded: the batch command reported success "
            f"but its '{RECORD_MARKER}' evidence line is missing from the "
            "output. Run the same command again.",
            "PostToolUse",
        )

    cwd = event.get("cwd", os.getcwd())
    batch, problem = check(cwd, module)
    if batch is None:
        exit_warn(f"hardening batch NOT recorded: {problem}", "PostToolUse")

    # `exit_warn` is re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing from the guard above.
    assert batch is not None

    refused = []
    for finding_id in batch.ids:
        context = batch.context.get(finding_id, {})
        fields = {
            "id": finding_id,
            "commit_hash": batch.commit_hash,
            "project": context.get("project", ""),
            "run": context.get("run", ""),
            "auditor": context.get("auditor", ""),
            "phase": BATCH_PHASE,
            "step": BATCH_STEP,
        }
        try:
            record_authed_event("finding_resolved", fields, cwd)
        except (OSError, RuntimeError) as exc:
            refused.append(f"{finding_id} ({exc})")

    if refused:
        exit_warn(
            "hardening batch NOT recorded for: the daemon refused "
            + ", ".join(refused),
            "PostToolUse",
        )
    exit_ok()


if __name__ == "__main__":
    main()

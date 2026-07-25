"""Tests for session_start.py — the SessionStart hook (issue #79).

The invariant under test: `context_reset` is recorded **iff the context was
actually reset**. Before #79 it was recorded iff a prompt was submitted, so the
`awaiting_clear -> fix_loop` gate opened on any incidental turn — including an
automated background-task notification — with the pre-reset context intact.

Everything here drives the hook by subprocess, which is the interface Claude
Code actually uses (CLAUDE.md testing methodology, rule 2).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from _resolve import ensure_sahjhan  # noqa: E402
from test_sahjhan_integration import (  # noqa: E402
    _create_mock_binary,
    _mock_env,
    run_enforcement_hook,
)

SAHJHAN = ensure_sahjhan()
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")

pytestmark = pytest.mark.skipif(
    SAHJHAN is None, reason="sahjhan binary not available"
)

# Sources that wipe or replace the context. The hook must record for these.
RESET_SOURCES = ["clear", "compact", "startup"]
# Sources that carry the prior transcript forward. The hook must stay silent.
NON_RESET_SOURCES = ["resume", "fork"]


def _init_sahjhan(tmp_path):
    """Initialize a sahjhan working dir so `status` reports a live run."""
    subprocess.run(
        [SAHJHAN, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, timeout=5, cwd=str(tmp_path),
        check=True,
    )
    ledger_path = str(tmp_path / "run-1.jsonl")
    subprocess.run(
        [SAHJHAN, "--config-dir", CONFIG_DIR, "ledger", "create",
         "--name", "run-1", "--path", ledger_path],
        capture_output=True, text=True, timeout=5, cwd=str(tmp_path),
        check=True,
    )


def _resets(daemon):
    return [
        e for e in daemon.recorded_events if e.get("event_type") == "context_reset"
    ]


def _run(tmp_path, source: str | None):
    event: dict = {"cwd": str(tmp_path), "hook_event_name": "SessionStart"}
    if source is not None:
        event["source"] = source
    return run_enforcement_hook("session_start.py", event, cwd=str(tmp_path))


@pytest.mark.hook_e2e
class TestRecordsOnlyOnRealReset:
    """`source` decides whether the reset happened. Nothing else does."""

    @pytest.mark.parametrize("source", RESET_SOURCES)
    def test_records_for_reset_source(self, tmp_path, mock_daemon, source):
        """clear/compact/startup all leave the model with no prior context."""
        _init_sahjhan(tmp_path)

        code, _, _ = _run(tmp_path, source)
        assert code == 0

        resets = _resets(mock_daemon)
        assert len(resets) == 1, (
            f"SessionStart source={source!r} is a real context reset and must "
            f"record exactly one context_reset. Got: {resets!r}"
        )
        assert resets[0]["op"] == "record_event"

    @pytest.mark.parametrize("source", NON_RESET_SOURCES)
    def test_no_record_for_non_reset_source(self, tmp_path, mock_daemon, source):
        """resume restores the transcript; fork copies it. Neither is a reset."""
        _init_sahjhan(tmp_path)

        code, _, _ = _run(tmp_path, source)
        assert code == 0
        assert not _resets(mock_daemon), (
            f"SessionStart source={source!r} carries the prior context forward — "
            f"recording context_reset would reopen the #79 hole."
        )

    def test_no_record_when_source_missing(self, tmp_path, mock_daemon):
        """An absent `source` is not evidence of anything. Fail closed."""
        _init_sahjhan(tmp_path)

        code, _, _ = _run(tmp_path, None)
        assert code == 0
        assert not _resets(mock_daemon), (
            "a SessionStart payload with no `source` proves nothing about the "
            "context and must not satisfy the awaiting_clear gate"
        )

    def test_no_record_for_unknown_source(self, tmp_path, mock_daemon):
        """A source Claude Code adds later must not silently count as a reset."""
        _init_sahjhan(tmp_path)

        code, _, _ = _run(tmp_path, "teleport")
        assert code == 0
        assert not _resets(mock_daemon), (
            "unknown sources must fail closed — an allowlist, not a denylist"
        )


@pytest.mark.hook_e2e
class TestRecordedProvenance:
    """The event carries the provenance the `resume` gate filters on."""

    def test_fields_identify_the_reset(self, tmp_path, mock_daemon):
        _init_sahjhan(tmp_path)

        _run(tmp_path, "compact")

        fields = _resets(mock_daemon)[0]["fields"]
        assert fields["trigger"] == "session_start", (
            "transitions.toml filters the resume gate on trigger=session_start; "
            "any other value silently disables the gate"
        )
        assert fields["source"] == "compact"
        assert fields["project"] == "holtz"
        assert fields["auditor"] == "holtz"
        assert fields["run"].isdigit()


@pytest.mark.hook_e2e
class TestNoActiveRun:
    """No audit, or a dead one — stay out of the way."""

    def test_silent_without_sahjhan_dir(self, tmp_path, mock_daemon):
        """No docs/holtz/.sahjhan → nothing to record, no binary bootstrap.

        Runs from a sibling dir: the mock_daemon fixture creates .sahjhan under
        tmp_path itself, and the daemon must stay reachable so "no record" is a
        real observation rather than an unreachable-socket artifact.
        """
        no_audit = tmp_path / "elsewhere"
        no_audit.mkdir()

        code, output, _ = _run(no_audit, "clear")
        assert code == 0
        assert not _resets(mock_daemon)
        assert output.get("hookSpecificOutput", {}).get("additionalContext", "") == ""

    def test_silent_when_audit_terminated(self, tmp_path, mock_daemon):
        """The primer announces termination on the next prompt — don't double it."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        code, output, _ = _run(tmp_path, "clear")
        assert code == 0
        assert not _resets(mock_daemon)
        assert output.get("hookSpecificOutput", {}).get("additionalContext", "") == ""


@pytest.mark.hook_e2e
class TestFailureSurfaces:
    """A context_reset that never landed strands the run in awaiting_clear."""

    def test_daemon_rejection_injects_enforcement_failure(self, tmp_path, mock_daemon):
        """Daemon reachable but rejects record_event → ENFORCEMENT FAILURE.

        Moved from the primer with the recording itself. The production bug it
        guards: the daemon refuses an unlisted/stale-hash caller, the write is
        swallowed, and nothing surfaces.
        """
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        # Alive init PID → not a daemon death → enforcement-failure branch.
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")
        mock_daemon.record_event_response = {
            "ok": False,
            "error": "auth_failed",
            "message": "caller not authenticated",
            "reason": "pid_resolution_failed",
        }

        code, output, _ = _run(tmp_path, "clear")
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" in context, (
            f"a rejected context_reset must surface, not be swallowed. Got: {context!r}"
        )

    def test_dead_daemon_writes_terminated_marker(self, tmp_path):
        """Dead init PID → terminated marker + termination message, no restart."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        code, output, _ = _run(tmp_path, "clear")
        assert code == 0
        assert (sahjhan_dir / "terminated").exists()
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "AUDIT TERMINATED" in context
        assert "/stop" not in context, (
            f"/stop is not a real Claude Code command (issue #55). Got: {context!r}"
        )

    def test_output_is_session_start_shaped(self, tmp_path):
        """SessionStart cannot block — output must never carry a decision."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        _, output, _ = _run(tmp_path, "clear")
        assert "decision" not in output
        hso = output.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "SessionStart"


@pytest.mark.hook_e2e
class TestRunStateGuards:
    """No live run to reset — record nothing, say nothing."""

    def _mock_run(self, tmp_path, status_body):
        (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
        _create_mock_binary(tmp_path, status_body)
        event = {
            "cwd": str(tmp_path),
            "hook_event_name": "SessionStart",
            "source": "clear",
        }
        return run_enforcement_hook(
            "session_start.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path),
        )

    def test_no_record_in_terminal_state(self, tmp_path, mock_daemon):
        """A finished run has nothing to resume — don't append to its ledger."""
        code, _, _ = self._mock_run(
            tmp_path, 'echo "state: finalized (12 events, chain valid)"'
        )
        assert code == 0
        assert not _resets(mock_daemon), (
            "recording a context_reset into a terminal run is noise the resume "
            "gate can never consume"
        )

    def test_no_record_when_status_fails(self, tmp_path, mock_daemon):
        """If sahjhan can't report state, claim nothing about the context."""
        code, _, _ = self._mock_run(tmp_path, "exit 1")
        assert code == 0
        assert not _resets(mock_daemon)

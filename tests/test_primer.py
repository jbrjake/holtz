"""Tests for primer.py — UserPromptSubmit hook."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from _resolve import ensure_sahjhan  # noqa: E402
from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

SAHJHAN = ensure_sahjhan()
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")

pytestmark = pytest.mark.skipif(
    SAHJHAN is None, reason="sahjhan binary not available"
)


def _init_sahjhan(tmp_path):
    """Initialize sahjhan working directory so status commands succeed."""
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


class TestPrimerTerminatedAudit:
    """Primer detects terminated audit and injects termination message."""

    def test_injects_termination_when_marker_exists(self, tmp_path):
        """Terminated marker present → inject termination message."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        # Primer uses exit_warn with "UserPromptSubmit" → hookSpecificOutput
        hook_output = output.get("hookSpecificOutput", {})
        context = hook_output.get("additionalContext", "")
        assert "AUDIT TERMINATED" in context

    def test_no_restart_attempt_on_socket_failure(self, tmp_path):
        """Socket failure does not attempt daemon restart."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        # No daemon running — record_authed_event will fail
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        # Should write terminated marker since init PID is dead
        assert (sahjhan_dir / "terminated").exists()


class TestPrimerAuthFailureFailClosed:
    """Auth failure must inject hard stop instruction, not soft warning."""

    def test_auth_failure_injects_hard_stop(self, tmp_path):
        """When context_reset auth fails (daemon alive but auth broken),
        primer must inject enforcement failure stop instruction."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        # Write a PID that IS alive (our own PID) so it's not a daemon death
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")
        # No daemon socket → record_authed_event will fail with OSError
        # But PID is alive → not a daemon death → auth failure path

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        hook_output = output.get("hookSpecificOutput", {})
        context = hook_output.get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" in context
        assert "STOP" in context


class TestPrimerNoAudit:
    """Primer exits clean when no audit is active."""

    def test_allows_when_no_sahjhan_dir(self, tmp_path):
        """No .sahjhan dir → no injection, silent allow."""
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0


class TestPrimerErrorMessageQuality:
    """Error messages must reference real recovery commands (issue #55)."""

    def test_terminated_marker_message_no_slash_stop(self, tmp_path):
        """/stop doesn't exist as a CC command — must not appear in terminated message."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "/stop" not in context, (
            f"primer.py references nonexistent /stop command in terminated message. "
            f"Use /plugin or ! sahjhan daemon stop instead. Got: {context!r}"
        )

    def test_awaiting_clear_death_message_no_slash_stop(self, tmp_path):
        """The awaiting_clear → dead-daemon branch must not reference /stop."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        # Dead PID triggers the awaiting_clear death branch (primer.py:112-122)
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "/stop" not in context, (
            f"primer.py references nonexistent /stop command in awaiting_clear death message. "
            f"Use /plugin or ! sahjhan daemon stop instead. Got: {context!r}"
        )


@pytest.mark.hook_e2e
class TestPrimerContextResetRecording:
    """context_reset is recorded via the daemon `record_event` socket op.

    Regression coverage for the swallowed-returncode bug. In production the
    daemon was REACHABLE but rejected the restricted-event submit (the bare
    `sahjhan authed-event` courier could never resolve to a trusted hook →
    pid_resolution_failed). The old CLI path returned that as a non-zero exit
    code the primer never checked, so no context_reset landed AND no failure
    surfaced. record_authed_event now records over the daemon socket and
    raises on rejection, so both outcomes are observable.
    """

    def test_daemon_rejection_injects_enforcement_failure(self, tmp_path, mock_daemon):
        """Daemon reachable but rejects record_event → ENFORCEMENT FAILURE.

        This is the exact production scenario the old code swallowed.
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

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" in context, (
            f"a rejected context_reset must surface, not be swallowed. Got: {context!r}"
        )
        attempts = [
            e for e in mock_daemon.recorded_events if e.get("event_type") == "context_reset"
        ]
        assert attempts, "primer should have attempted a context_reset record_event"
        assert attempts[0]["op"] == "record_event"

    def test_daemon_success_records_context_reset(self, tmp_path, mock_daemon):
        """Daemon accepts record_event → context_reset recorded, no failure."""
        _init_sahjhan(tmp_path)
        # mock_daemon default response is ok:true.

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" not in context, (
            f"a successful record must not report failure. Got: {context!r}"
        )
        resets = [
            e for e in mock_daemon.recorded_events if e.get("event_type") == "context_reset"
        ]
        assert len(resets) == 1, "primer should record exactly one context_reset"
        assert resets[0]["op"] == "record_event"
        assert resets[0]["fields"]["trigger"] == "user_prompt_submit"

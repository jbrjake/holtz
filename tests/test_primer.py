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
class TestPrimerNeverRecordsContextReset:
    """Issue #79 regression guard.

    The primer used to record `context_reset` on every UserPromptSubmit. That
    event gates `awaiting_clear -> fix_loop`, and UserPromptSubmit fires on any
    turn — an ordinary typed message, or an automated background-task
    notification with no human and no /clear. So the gate opened with the full
    recon+audit+merge context intact, silently, while `status` reported
    `resume: ready`.

    The recording now belongs to session_start.py, which fires only when the
    host reports a real reset. The primer must never write it again, on any
    prompt, under any daemon condition — otherwise the hole reopens.
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "continue",
            "/clear",  # the text of a clear is not a clear
            "<task-notification>subagent finished</task-notification>",
        ],
    )
    def test_no_context_reset_for_any_prompt(self, tmp_path, mock_daemon, prompt):
        _init_sahjhan(tmp_path)

        event = {"cwd": str(tmp_path), "user_prompt": prompt}
        code, _, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0

        resets = [
            e for e in mock_daemon.recorded_events
            if e.get("event_type") == "context_reset"
        ]
        assert not resets, (
            f"primer recorded a context_reset for prompt {prompt!r}. A prompt is "
            f"not a context reset — this is exactly issue #79. Got: {resets!r}"
        )

    def test_healthy_daemon_reports_no_enforcement_failure(self, tmp_path, mock_daemon):
        """A reachable, authenticating daemon must not raise a false alarm.

        The health probe replaced a write with an `enforcement_read`, and an
        audit that hasn't cached state yet answers `not_found`. That is a
        healthy daemon, not a broken one.
        """
        _init_sahjhan(tmp_path)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" not in context, (
            f"a healthy daemon must not report failure. Got: {context!r}"
        )

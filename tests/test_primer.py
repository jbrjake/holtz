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

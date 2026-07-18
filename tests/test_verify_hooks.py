"""Tests for hook registration verification."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VERIFY_SCRIPT = REPO_ROOT / "enforcement" / "hooks" / "verify_hooks.py"


def test_detects_missing_hooks(tmp_path):
    """verify_hooks exits 1 when required hooks are missing."""
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {}}))
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--settings", str(settings)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 1
    assert "missing" in result.stderr.lower()


def test_passes_with_all_hooks(tmp_path):
    """verify_hooks exits 0 when all required hooks are present."""
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    hooks = {
        "PreToolUse": [
            {"matcher": "*", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_daemon_lifecycle.py"},
            ]},
            {"matcher": "Write|Edit", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py"},
                {"type": "command", "command": "python enforcement/hooks/pre_tool_hook.py"},
            ]},
            {"matcher": "Read", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py"},
            ]},
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/commit_gate.py"},
            ]},
        ],
        "PostToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/bash_guard.py"},
                {"type": "command", "command": "python enforcement/hooks/protocol_tracker.py"},
                {"type": "command", "command": "python enforcement/hooks/quiz_capture.py"},
            ]},
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/post_tool_hook.py"},
            ]},
        ],
        "UserPromptSubmit": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/primer.py"},
            ]},
        ],
        "Stop": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/stop_hook.py"},
            ]},
        ],
        "SubagentStop": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/lens_quiz.py"},
                {"type": "command", "command": "python hooks/subagent_findings_check.py"},
            ]},
        ],
    }
    settings.write_text(json.dumps({"hooks": hooks}))
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--settings", str(settings)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0


def test_detects_partial_hooks(tmp_path):
    """verify_hooks detects when some but not all hooks are present."""
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    # Only has PreToolUse, missing everything else
    hooks = {
        "PreToolUse": [
            {"matcher": "Write|Edit", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py"},
                {"type": "command", "command": "python enforcement/hooks/pre_tool_hook.py"},
            ]},
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/commit_gate.py"},
            ]},
        ],
    }
    settings.write_text(json.dumps({"hooks": hooks}))
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--settings", str(settings)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 1
    assert "missing" in result.stderr.lower()

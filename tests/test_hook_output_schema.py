"""Offline hook output schema validation — no network required.

Runs each hook registered in hooks.json with a representative event
and validates the output JSON matches the expected structure from
tests/fixtures/hook_output_schema.json.

This catches "hook emits invalid JSON" in CI without needing network
access to fetch Claude Code docs (unlike test_hook_schema_freshness.py).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hook_schema import validate_hook_output

pytestmark = pytest.mark.hook_e2e

REPO_ROOT = Path(__file__).parent.parent
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "hook_output_schema.json"


def load_schema() -> dict:
    with open(SCHEMA_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def load_hooks_config() -> dict:
    with open(HOOKS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _invoke_hook(script_path: str, event: dict, cwd: str) -> tuple[int, dict, str]:
    """Run a hook script via subprocess, exactly as Claude Code does."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [sys.executable, script_path],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=15,
        cwd=cwd,
        env=env,
    )

    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        output = {"__raw_stdout": result.stdout}

    return result.returncode, output, result.stderr


def _extract_script_path(command: str) -> str | None:
    """Extract the script path from a hooks.json command string."""
    expanded = command.replace("${CLAUDE_PLUGIN_ROOT}", str(REPO_ROOT))
    match = re.search(r'python\s+"?([^"]+)"?', expanded)
    return match.group(1) if match else None


def _build_event(event_type: str, cwd: str) -> dict:
    """Build a representative event for the given event type."""
    if event_type == "PreToolUse":
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": cwd,
        }
    elif event_type == "PostToolUse":
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"exit_code": 0, "output": "hello\n"},
            "cwd": cwd,
        }
    elif event_type == "Stop":
        return {"cwd": cwd}
    elif event_type == "SubagentStop":
        return {
            "tool_name": "Agent",
            "tool_input": {"prompt": "test"},
            "tool_output": "done",
            "last_assistant_message": "done",
            "cwd": cwd,
        }
    elif event_type == "UserPromptSubmit":
        return {"cwd": cwd, "user_prompt": "test"}
    return {"cwd": cwd}


# ── Collect all hook scripts per event type ──

def _collect_hooks() -> list[tuple[str, str, str]]:
    """Return (event_type, hook_command, script_path) tuples for all hooks."""
    config = load_hooks_config()
    hooks = []
    seen = set()
    for event_type, matchers in config["hooks"].items():
        for matcher_group in matchers:
            for hook in matcher_group["hooks"]:
                cmd = hook["command"]
                script = _extract_script_path(cmd)
                if script and script not in seen:
                    seen.add(script)
                    hooks.append((event_type, cmd, script))
    return hooks


_ALL_HOOKS = _collect_hooks()


# ── Tests ──


@pytest.fixture
def project_dir(tmp_path: Path) -> str:
    """Minimal project dir with no active audit."""
    (tmp_path / "src").mkdir()
    return str(tmp_path)


@pytest.fixture
def schema() -> dict:
    return load_schema()


class TestHookOutputStructure:
    """Each hook must emit valid JSON matching its event type's schema."""

    @pytest.mark.parametrize(
        "event_type,hook_cmd,script_path",
        _ALL_HOOKS,
        ids=[os.path.basename(s) for _, _, s in _ALL_HOOKS],
    )
    def test_hook_emits_valid_json(
        self, event_type, hook_cmd, script_path, project_dir,
    ):
        """Hook must exit 0 and emit parseable JSON (or empty for Stop allow)."""
        event = _build_event(event_type, project_dir)
        code, output, stderr = _invoke_hook(script_path, event, project_dir)

        assert code == 0, f"{hook_cmd} exited {code}, stderr: {stderr[:300]}"
        assert "__raw_stdout" not in output, (
            f"{hook_cmd} emitted non-JSON: {output.get('__raw_stdout', '')[:200]}"
        )

    @pytest.mark.parametrize(
        "event_type,hook_cmd,script_path",
        _ALL_HOOKS,
        ids=[os.path.basename(s) for _, _, s in _ALL_HOOKS],
    )
    def test_hook_output_matches_schema(
        self, event_type, hook_cmd, script_path, project_dir,
    ):
        """Hook output must pass the canonical schema validator."""
        event = _build_event(event_type, project_dir)
        code, output, stderr = _invoke_hook(script_path, event, project_dir)

        if code != 0:
            pytest.skip(f"Hook exited {code} — covered by test_hook_emits_valid_json")

        errors = validate_hook_output(event_type, output)
        assert not errors, (
            f"Schema errors for {hook_cmd}:\n" + "\n".join(errors)
        )


class TestPreToolUseDecisionValues:
    """PreToolUse hooks must only use valid permissionDecision values."""

    @pytest.mark.parametrize(
        "event_type,hook_cmd,script_path",
        [(e, c, s) for e, c, s in _ALL_HOOKS if e == "PreToolUse"],
        ids=[os.path.basename(s) for e, _, s in _ALL_HOOKS if e == "PreToolUse"],
    )
    def test_permission_decision_is_valid(
        self, event_type, hook_cmd, script_path, project_dir, schema,
    ):
        """permissionDecision must be in the allowed set."""
        event = _build_event(event_type, project_dir)
        _, output, _ = _invoke_hook(script_path, event, project_dir)

        hso = output.get("hookSpecificOutput", {})
        if not hso:
            return  # Empty output is valid

        decision = hso.get("permissionDecision")
        valid = set(schema["PreToolUse"]["valid_decisions"])
        assert decision in valid, (
            f"{hook_cmd}: permissionDecision={decision!r}, valid={valid}"
        )


class TestStopHookConstraints:
    """Stop/SubagentStop hooks must not use hookSpecificOutput."""

    @pytest.mark.parametrize(
        "event_type,hook_cmd,script_path",
        [(e, c, s) for e, c, s in _ALL_HOOKS if e in ("Stop", "SubagentStop")],
        ids=[os.path.basename(s) for e, _, s in _ALL_HOOKS if e in ("Stop", "SubagentStop")],
    )
    def test_no_hook_specific_output(
        self, event_type, hook_cmd, script_path, project_dir, schema,
    ):
        """Stop hooks must not include hookSpecificOutput."""
        event = _build_event(event_type, project_dir)
        _, output, _ = _invoke_hook(script_path, event, project_dir)

        forbidden = schema.get(event_type, {}).get("forbidden_fields", [])
        for field in forbidden:
            assert field not in output, (
                f"{hook_cmd}: {event_type} output must not contain '{field}'"
            )


class TestSchemaFixtureConsistency:
    """The fixture must agree with hook_schema.py."""

    def test_pretooluse_decisions_match(self, schema):
        from hook_schema import PRETOOLUSE_VALID_DECISIONS
        assert set(schema["PreToolUse"]["valid_decisions"]) == PRETOOLUSE_VALID_DECISIONS

    def test_stop_decisions_match(self, schema):
        from hook_schema import STOP_VALID_DECISIONS
        assert set(schema["Stop"]["valid_decisions"]) == STOP_VALID_DECISIONS

    def test_all_event_types_covered(self, schema):
        config = load_hooks_config()
        for event_type in config["hooks"]:
            assert event_type in schema, (
                f"Event type '{event_type}' in hooks.json but missing from schema fixture"
            )

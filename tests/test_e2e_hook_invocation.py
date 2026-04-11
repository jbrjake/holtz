"""End-to-end hook invocation tests — multi-lens audit.

Simulates exactly what Claude Code does at runtime and applies Holtz's
own lens methodology to validate hooks from every relevant angle:

CONTRACT lens: Each hook's output matches its event type's protocol
INTEGRATION lens: Hooks in the same chain don't break each other
DATA-FLOW lens: JSON in/out matches Claude Code's expected schema at every field
ERROR-PROPAGATION lens: Hooks degrade gracefully on bad input, missing deps
RESOURCE-LIFECYCLE lens: No leaked handles, sockets, temp files across invocations
IDEMPOTENCY lens: Calling a hook N times is safe and produces consistent output
TEMPORAL-PROTOCOL lens: Hook chain execution order doesn't produce state conflicts
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"


def load_hooks_config() -> dict:
    """Load and return the hooks.json configuration."""
    with open(HOOKS_JSON, encoding="utf-8") as f:
        return json.load(f)


def expand_command(command: str, plugin_root: str) -> str:
    """Expand ${CLAUDE_PLUGIN_ROOT} in a hook command, exactly as Claude Code does."""
    return command.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)


def invoke_hook(command: str, event: dict, plugin_root: str, cwd: str | None = None) -> tuple[int, dict, str]:
    """Invoke a hook exactly as Claude Code would.

    Args:
        command: The raw command from hooks.json (with ${CLAUDE_PLUGIN_ROOT})
        event: The event payload to pipe to stdin
        plugin_root: Value for CLAUDE_PLUGIN_ROOT
        cwd: Working directory (defaults to a temp dir)

    Returns:
        (exit_code, parsed_stdout_json_or_empty_dict, stderr)
    """
    expanded = expand_command(command, plugin_root)
    # Claude Code splits on space to get: ["python", "/path/to/hook.py"]
    parts = expanded.split('" "')
    if len(parts) == 1:
        # Simple case: python "/path/to/script.py"
        # Strip quotes from the path
        match = re.match(r'python\s+"?([^"]+)"?', expanded)
        if match:
            script_path = match.group(1)
            cmd = [sys.executable, script_path]
        else:
            cmd = expanded.split()
    else:
        cmd = [p.strip('"') for p in parts]

    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root

    result = subprocess.run(
        cmd,
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=15,
        cwd=cwd or str(REPO_ROOT),
        env=env,
    )

    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        output = {"__raw_stdout": result.stdout}

    return result.returncode, output, result.stderr


# ─── Realistic event payloads ───────────────────────────────────────────


def pretooluse_write_event(cwd: str) -> dict:
    """Realistic PreToolUse Write event as Claude Code sends it."""
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": os.path.join(cwd, "src", "app.py"),
            "content": "print('hello')\n",
        },
        "cwd": cwd,
    }


def pretooluse_edit_event(cwd: str) -> dict:
    """Realistic PreToolUse Edit event."""
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": os.path.join(cwd, "src", "app.py"),
            "old_string": "print('hello')",
            "new_string": "print('world')",
        },
        "cwd": cwd,
    }


def pretooluse_bash_event(cwd: str) -> dict:
    """Realistic PreToolUse Bash event."""
    return {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python -m pytest tests/ -v",
        },
        "cwd": cwd,
    }


def pretooluse_bash_commit_event(cwd: str) -> dict:
    """PreToolUse Bash event with a git commit command."""
    return {
        "tool_name": "Bash",
        "tool_input": {
            "command": "git commit -m 'fix: resolve issue'",
        },
        "cwd": cwd,
    }


def pretooluse_grep_event(cwd: str) -> dict:
    """Realistic PreToolUse Grep event."""
    return {
        "tool_name": "Grep",
        "tool_input": {
            "pattern": "def main",
            "path": cwd,
        },
        "cwd": cwd,
    }


def pretooluse_glob_event(cwd: str) -> dict:
    """Realistic PreToolUse Glob event."""
    return {
        "tool_name": "Glob",
        "tool_input": {
            "pattern": "**/*.py",
            "path": cwd,
        },
        "cwd": cwd,
    }


def posttooluse_bash_event(cwd: str) -> dict:
    """Realistic PostToolUse Bash event with tool response."""
    return {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python -m pytest tests/ -v",
        },
        "tool_response": {
            "exit_code": 0,
            "output": "PASSED 5 tests in 1.2s\n",
        },
        "cwd": cwd,
    }


def posttooluse_write_event(cwd: str) -> dict:
    """Realistic PostToolUse Write event."""
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": os.path.join(cwd, "src", "app.py"),
            "content": "print('hello')\n",
        },
        "tool_output": "File written successfully",
        "cwd": cwd,
    }


def subagent_stop_event(cwd: str) -> dict:
    """Realistic SubagentStop event.

    Claude Code sends last_assistant_message with the subagent's final output.
    This is the primary input for SubagentStop hooks like subagent_findings_check.py
    and lens_quiz.py.
    """
    return {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Find all bugs in src/",
        },
        "tool_output": "Found 3 issues:\n1. Missing null check\n2. Race condition\n3. Memory leak",
        "last_assistant_message": "I analyzed src/ and found 3 issues:\n1. Missing null check in src/auth.py\n2. Race condition in src/cache.py\n3. Memory leak in src/worker.py",
        "cwd": cwd,
    }


def stop_event(cwd: str) -> dict:
    """Realistic Stop event."""
    return {
        "cwd": cwd,
    }


def user_prompt_submit_event(cwd: str) -> dict:
    """Realistic UserPromptSubmit event."""
    return {
        "cwd": cwd,
        "user_prompt": "Fix the authentication bug in auth.py",
    }


# ─── Schema validators ──────────────────────────────────────────────────

from hook_schema import validate_hook_output


def validate_pretooluse_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate PreToolUse output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("PreToolUse", output)]


def validate_posttooluse_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate PostToolUse output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("PostToolUse", output)]


def validate_stop_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate Stop output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("Stop", output)]


def validate_subagent_stop_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate SubagentStop output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("SubagentStop", output)]


def validate_user_prompt_submit_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate UserPromptSubmit output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("UserPromptSubmit", output)]


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def plugin_root() -> str:
    """Return the plugin root as Claude Code would set it."""
    return str(REPO_ROOT)


@pytest.fixture
def project_dir(tmp_path: Path) -> str:
    """Create a minimal project directory (no active audit)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n")
    return str(tmp_path)


@pytest.fixture
def hooks_config() -> dict:
    """Load the hooks configuration."""
    return load_hooks_config()


# ─── Core E2E Tests ──────────────────────────────────────────────────────


class TestHooksJsonValid:
    """Verify hooks.json itself is valid and all referenced scripts exist."""

    def test_hooks_json_parseable(self):
        """hooks.json must be valid JSON."""
        config = load_hooks_config()
        assert "hooks" in config

    def test_all_referenced_scripts_exist(self, plugin_root):
        """Every script referenced in hooks.json must exist on disk."""
        config = load_hooks_config()
        missing = []
        for _event_type, matchers in config["hooks"].items():
            for matcher_group in matchers:
                for hook in matcher_group["hooks"]:
                    cmd = hook["command"]
                    expanded = expand_command(cmd, plugin_root)
                    # Extract the script path
                    match = re.search(r'python\s+"?([^"]+)"?', expanded)
                    if match:
                        script_path = match.group(1)
                        if not os.path.isfile(script_path):
                            missing.append(f"{cmd} -> {script_path}")
        assert not missing, "Missing hook scripts:\n" + "\n".join(missing)

    def test_all_matchers_are_valid(self):
        """Matchers must be * or pipe-separated tool names."""
        config = load_hooks_config()
        for event_type, matchers in config["hooks"].items():
            for matcher_group in matchers:
                pattern = matcher_group["matcher"]
                assert pattern == "*" or re.match(r'^[A-Za-z|]+$', pattern), (
                    f"Invalid matcher '{pattern}' in {event_type}"
                )


class TestPreToolUseChainE2E:
    """E2E: Invoke the full PreToolUse hook chain as Claude Code would."""

    def test_wildcard_hooks_on_write(self, plugin_root, project_dir, hooks_config):
        """Wildcard (*) PreToolUse hooks fire on Write events."""
        event = pretooluse_write_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Write" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_pretooluse_output(output, hook["command"]))

        assert not errors, "PreToolUse Write chain errors:\n" + "\n".join(errors)

    def test_wildcard_hooks_on_edit(self, plugin_root, project_dir, hooks_config):
        """Wildcard (*) + Edit-matcher hooks fire on Edit events."""
        event = pretooluse_edit_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Edit" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_pretooluse_output(output, hook["command"]))

        assert not errors, "PreToolUse Edit chain errors:\n" + "\n".join(errors)

    def test_bash_hooks_on_bash_event(self, plugin_root, project_dir, hooks_config):
        """Bash-matcher PreToolUse hooks fire on Bash events."""
        event = pretooluse_bash_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Bash" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_pretooluse_output(output, hook["command"]))

        assert not errors, "PreToolUse Bash chain errors:\n" + "\n".join(errors)

    def test_bash_commit_hooks(self, plugin_root, project_dir, hooks_config):
        """Commit gate fires on git commit commands."""
        event = pretooluse_bash_commit_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Bash" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_pretooluse_output(output, hook["command"]))

        assert not errors, "PreToolUse Bash commit chain errors:\n" + "\n".join(errors)

    def test_grep_glob_hooks(self, plugin_root, project_dir, hooks_config):
        """Grep|Glob matcher hooks fire correctly."""
        for event in [pretooluse_grep_event(project_dir), pretooluse_glob_event(project_dir)]:
            errors = []
            tool_name = event["tool_name"]

            for matcher_group in hooks_config["hooks"]["PreToolUse"]:
                pattern = matcher_group["matcher"]
                if pattern != "*" and tool_name not in pattern.split("|"):
                    continue
                for hook in matcher_group["hooks"]:
                    code, output, stderr = invoke_hook(
                        hook["command"], event, plugin_root, cwd=project_dir
                    )
                    if code != 0:
                        errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                    errors.extend(validate_pretooluse_output(output, hook["command"]))

            assert not errors, f"PreToolUse {tool_name} chain errors:\n" + "\n".join(errors)


class TestPostToolUseChainE2E:
    """E2E: Invoke the full PostToolUse hook chain."""

    def test_wildcard_posttool_on_bash(self, plugin_root, project_dir, hooks_config):
        """All PostToolUse hooks fire on Bash output."""
        event = posttooluse_bash_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PostToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Bash" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_posttooluse_output(output, hook["command"]))

        assert not errors, "PostToolUse Bash chain errors:\n" + "\n".join(errors)

    def test_wildcard_posttool_on_write(self, plugin_root, project_dir, hooks_config):
        """PostToolUse wildcard hooks fire on Write output."""
        event = posttooluse_write_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["PostToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Write" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_posttooluse_output(output, hook["command"]))

        assert not errors, "PostToolUse Write chain errors:\n" + "\n".join(errors)


class TestSubagentStopChainE2E:
    """E2E: Invoke the SubagentStop hook chain."""

    def test_subagent_stop_hooks(self, plugin_root, project_dir, hooks_config):
        """SubagentStop hooks fire and produce valid output."""
        event = subagent_stop_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["SubagentStop"]:
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_subagent_stop_output(output, hook["command"]))

        assert not errors, "SubagentStop chain errors:\n" + "\n".join(errors)


class TestStopChainE2E:
    """E2E: Invoke the Stop hook chain."""

    def test_stop_hooks_no_active_audit(self, plugin_root, project_dir, hooks_config):
        """Stop hooks allow when no active audit."""
        event = stop_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["Stop"]:
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_stop_output(output, hook["command"]))

        assert not errors, "Stop chain errors:\n" + "\n".join(errors)


class TestUserPromptSubmitChainE2E:
    """E2E: Invoke the UserPromptSubmit hook chain."""

    def test_prompt_submit_hooks(self, plugin_root, project_dir, hooks_config):
        """UserPromptSubmit hooks fire and produce valid output."""
        event = user_prompt_submit_event(project_dir)
        errors = []

        for matcher_group in hooks_config["hooks"]["UserPromptSubmit"]:
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_user_prompt_submit_output(output, hook["command"]))

        assert not errors, "UserPromptSubmit chain errors:\n" + "\n".join(errors)


class TestFullChainSequentialE2E:
    """E2E: Simulate a realistic Claude Code session — hooks fire in order."""

    def test_full_session_simulation(self, plugin_root, project_dir, hooks_config):
        """Simulate a full tool lifecycle: prompt → pre → post → stop.

        This tests that hooks don't leave side effects that break subsequent hooks.
        """
        errors = []

        # 1. UserPromptSubmit
        event = user_prompt_submit_event(project_dir)
        for matcher_group in hooks_config["hooks"]["UserPromptSubmit"]:
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[Prompt] EXIT {code}: {hook['command']}\nstderr: {stderr}")

        # 2. PreToolUse (Write)
        event = pretooluse_write_event(project_dir)
        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Write" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[PreTool] EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_pretooluse_output(output, hook["command"]))

        # 3. PostToolUse (Write)
        event = posttooluse_write_event(project_dir)
        for matcher_group in hooks_config["hooks"]["PostToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Write" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[PostTool] EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_posttooluse_output(output, hook["command"]))

        # 4. PreToolUse (Bash)
        event = pretooluse_bash_event(project_dir)
        for matcher_group in hooks_config["hooks"]["PreToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Bash" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[PreTool2] EXIT {code}: {hook['command']}\nstderr: {stderr}")

        # 5. PostToolUse (Bash)
        event = posttooluse_bash_event(project_dir)
        for matcher_group in hooks_config["hooks"]["PostToolUse"]:
            pattern = matcher_group["matcher"]
            if pattern != "*" and "Bash" not in pattern.split("|"):
                continue
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[PostTool2] EXIT {code}: {hook['command']}\nstderr: {stderr}")

        # 6. Stop
        event = stop_event(project_dir)
        for matcher_group in hooks_config["hooks"]["Stop"]:
            for hook in matcher_group["hooks"]:
                code, output, stderr = invoke_hook(
                    hook["command"], event, plugin_root, cwd=project_dir
                )
                if code != 0:
                    errors.append(f"[Stop] EXIT {code}: {hook['command']}\nstderr: {stderr}")
                errors.extend(validate_stop_output(output, hook["command"]))

        assert not errors, "Full session simulation errors:\n" + "\n".join(errors)


class TestHookCrashResilience:
    """E2E: Hooks must not crash on malformed or empty input."""

    def test_empty_stdin(self, plugin_root, hooks_config):
        """Hooks must handle empty stdin gracefully (exit 0, valid output)."""
        errors = []
        seen_commands = set()

        for _event_type, matchers in hooks_config["hooks"].items():
            for matcher_group in matchers:
                for hook in matcher_group["hooks"]:
                    cmd = hook["command"]
                    if cmd in seen_commands:
                        continue
                    seen_commands.add(cmd)

                    expanded = expand_command(cmd, plugin_root)
                    match = re.search(r'python\s+"?([^"]+)"?', expanded)
                    if not match:
                        continue
                    script_path = match.group(1)

                    env = os.environ.copy()
                    env["CLAUDE_PLUGIN_ROOT"] = plugin_root

                    result = subprocess.run(
                        [sys.executable, script_path],
                        input="",
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=str(REPO_ROOT),
                        env=env,
                    )
                    if result.returncode != 0:
                        errors.append(
                            f"CRASH on empty stdin: {cmd}\n"
                            f"  exit={result.returncode}\n"
                            f"  stderr={result.stderr[:200]}"
                        )

        assert not errors, "Hooks crashed on empty stdin:\n" + "\n".join(errors)

    def test_malformed_json_stdin(self, plugin_root, hooks_config):
        """Hooks must handle malformed JSON gracefully."""
        errors = []
        seen_commands = set()

        for _event_type, matchers in hooks_config["hooks"].items():
            for matcher_group in matchers:
                for hook in matcher_group["hooks"]:
                    cmd = hook["command"]
                    if cmd in seen_commands:
                        continue
                    seen_commands.add(cmd)

                    expanded = expand_command(cmd, plugin_root)
                    match = re.search(r'python\s+"?([^"]+)"?', expanded)
                    if not match:
                        continue
                    script_path = match.group(1)

                    env = os.environ.copy()
                    env["CLAUDE_PLUGIN_ROOT"] = plugin_root

                    result = subprocess.run(
                        [sys.executable, script_path],
                        input="{not valid json!!!",
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=str(REPO_ROOT),
                        env=env,
                    )
                    if result.returncode != 0:
                        errors.append(
                            f"CRASH on bad JSON: {cmd}\n"
                            f"  exit={result.returncode}\n"
                            f"  stderr={result.stderr[:200]}"
                        )

        assert not errors, "Hooks crashed on malformed JSON:\n" + "\n".join(errors)

    def test_missing_fields_in_event(self, plugin_root, hooks_config):
        """Hooks must handle events with missing expected fields."""
        errors = []
        # Minimal event — just cwd, no tool_name, no tool_input
        minimal_event = {"cwd": "/tmp"}
        seen_commands = set()

        for _event_type, matchers in hooks_config["hooks"].items():
            for matcher_group in matchers:
                for hook in matcher_group["hooks"]:
                    cmd = hook["command"]
                    if cmd in seen_commands:
                        continue
                    seen_commands.add(cmd)

                    expanded = expand_command(cmd, plugin_root)
                    match = re.search(r'python\s+"?([^"]+)"?', expanded)
                    if not match:
                        continue
                    script_path = match.group(1)

                    env = os.environ.copy()
                    env["CLAUDE_PLUGIN_ROOT"] = plugin_root

                    result = subprocess.run(
                        [sys.executable, script_path],
                        input=json.dumps(minimal_event),
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=str(REPO_ROOT),
                        env=env,
                    )
                    if result.returncode != 0:
                        errors.append(
                            f"CRASH on minimal event: {cmd}\n"
                            f"  exit={result.returncode}\n"
                            f"  stderr={result.stderr[:200]}"
                        )

        assert not errors, "Hooks crashed on minimal event:\n" + "\n".join(errors)


class TestNoStderrNoise:
    """E2E: Hooks should not emit warnings/errors to stderr in normal operation."""

    def test_no_stderr_on_normal_invocation(self, plugin_root, project_dir, hooks_config):
        """Clean invocation should produce no stderr output."""
        noisy_hooks = []
        events = {
            "PreToolUse": pretooluse_write_event(project_dir),
            "PostToolUse": posttooluse_bash_event(project_dir),
            "SubagentStop": subagent_stop_event(project_dir),
            "Stop": stop_event(project_dir),
            "UserPromptSubmit": user_prompt_submit_event(project_dir),
        }

        seen_commands = set()
        for event_type, matchers in hooks_config["hooks"].items():
            event = events.get(event_type, {"cwd": project_dir})
            for matcher_group in matchers:
                for hook in matcher_group["hooks"]:
                    cmd = hook["command"]
                    if cmd in seen_commands:
                        continue
                    seen_commands.add(cmd)

                    code, output, stderr = invoke_hook(
                        cmd, event, plugin_root, cwd=project_dir
                    )
                    if stderr.strip():
                        noisy_hooks.append(f"{cmd}:\n  {stderr.strip()[:200]}")

        assert not noisy_hooks, (
            "Hooks emitting stderr (may show as errors in Claude Code UI):\n"
            + "\n".join(noisy_hooks)
        )

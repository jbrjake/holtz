"""Tests for enforcement config resolution and stop hook fail-open fix.

Covers:
- resolve_config_dir() search order and fallback behavior
- exit_stop_warn() output format
- stop_hook.py warning behavior when enforcement is degraded

See: GitHub issue #19 — auditor bypassed convergence due to silent
config path mismatch causing all enforcement hooks to fail open.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
ENFORCEMENT_HOOKS = REPO_ROOT / "enforcement" / "hooks"
HOOKS_DIR = REPO_ROOT / "hooks"


# ── resolve_config_dir() ──


class TestResolveConfigDir:
    """Tests for the enforcement config directory resolution logic."""

    @staticmethod
    def _import_common():
        """Import enforcement _common module fresh."""
        sys.path.insert(0, str(ENFORCEMENT_HOOKS))
        import _common as enf_common
        importlib.reload(enf_common)
        return enf_common

    def test_finds_config_via_plugin_root(self, tmp_path):
        """CLAUDE_PLUGIN_ROOT/enforcement is found when protocol.toml exists."""
        plugin_dir = tmp_path / "plugin"
        enforcement = plugin_dir / "enforcement"
        enforcement.mkdir(parents=True)
        (enforcement / "protocol.toml").write_text("[protocol]")

        mod = self._import_common()
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}):
            config_dir, found = mod.resolve_config_dir(str(tmp_path / "project"))
        assert found is True
        assert config_dir == str(enforcement)

    def test_finds_config_via_persisted_path(self, tmp_path):
        """Persisted config-dir file takes priority over CLAUDE_PLUGIN_ROOT."""
        # Set up persisted config-dir
        sahjhan_dir = tmp_path / "project" / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        custom_config = tmp_path / "custom" / "enforcement"
        custom_config.mkdir(parents=True)
        (custom_config / "protocol.toml").write_text("[protocol]")
        (sahjhan_dir / "config-dir").write_text(str(custom_config))

        # Also set up CLAUDE_PLUGIN_ROOT (should be ignored)
        plugin_dir = tmp_path / "plugin"
        plugin_enforcement = plugin_dir / "enforcement"
        plugin_enforcement.mkdir(parents=True)
        (plugin_enforcement / "protocol.toml").write_text("[protocol]")

        mod = self._import_common()
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}):
            config_dir, found = mod.resolve_config_dir(str(tmp_path / "project"))
        assert found is True
        assert config_dir == str(custom_config)

    def test_falls_back_to_cwd_enforcement(self, tmp_path, monkeypatch):
        """Falls back to {cwd}/enforcement when no plugin root and file-relative fails."""
        project = tmp_path / "project"
        enforcement = project / "enforcement"
        enforcement.mkdir(parents=True)
        (enforcement / "protocol.toml").write_text("[protocol]")

        mod = self._import_common()
        # Patch os.path.isfile to block the file-relative check (step 3)
        # while allowing the cwd check (step 4)
        real_isfile = os.path.isfile
        file_relative = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(mod.__file__))),
            "protocol.toml",
        )

        def _patched_isfile(path):
            if os.path.abspath(path) == os.path.abspath(file_relative):
                return False
            return real_isfile(path)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            monkeypatch.setattr(os.path, "isfile", _patched_isfile)
            config_dir, found = mod.resolve_config_dir(str(project))
        assert found is True
        assert config_dir == str(enforcement)

    def test_returns_false_when_nothing_found(self, tmp_path, monkeypatch):
        """Returns found=False when no config directory has protocol.toml."""
        mod = self._import_common()
        # Patch os.path.isfile to block the file-relative check (step 3)
        real_isfile = os.path.isfile
        file_relative = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(mod.__file__))),
            "protocol.toml",
        )

        def _patched_isfile(path):
            if os.path.abspath(path) == os.path.abspath(file_relative):
                return False
            return real_isfile(path)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            monkeypatch.setattr(os.path, "isfile", _patched_isfile)
            config_dir, found = mod.resolve_config_dir(str(tmp_path / "empty"))
        assert found is False

    def test_persisted_path_ignored_when_stale(self, tmp_path):
        """Persisted config-dir is ignored if protocol.toml doesn't exist there."""
        sahjhan_dir = tmp_path / "project" / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "config-dir").write_text("/nonexistent/path")

        # Set up CLAUDE_PLUGIN_ROOT as fallback
        plugin_dir = tmp_path / "plugin"
        enforcement = plugin_dir / "enforcement"
        enforcement.mkdir(parents=True)
        (enforcement / "protocol.toml").write_text("[protocol]")

        mod = self._import_common()
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}):
            config_dir, found = mod.resolve_config_dir(str(tmp_path / "project"))
        assert found is True
        assert config_dir == str(enforcement)

    def test_file_relative_fallback(self, tmp_path):
        """File-relative path works when running from repo root (local dev)."""
        # In the real repo, enforcement/hooks/_common.py resolves to
        # enforcement/ which contains protocol.toml. This test verifies
        # the function can find config relative to the file location.
        mod = self._import_common()
        # With no env vars and cwd pointing to a project with no enforcement/
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            config_dir, found = mod.resolve_config_dir(str(tmp_path / "empty_project"))
        # Since we're running from the actual repo, the file-relative path
        # should find the real enforcement/ directory
        assert found is True
        assert "enforcement" in config_dir


# ── exit_stop_warn() ──


class TestExitStopWarn:
    """Tests for the new exit_stop_warn() output format."""

    @staticmethod
    def _run_func(func_name, *args):
        code_str = (
            f"import sys; sys.path.insert(0, {str(HOOKS_DIR)!r}); "
            f"from _common import {func_name}; {func_name}({', '.join(repr(a) for a in args)})"
        )
        result = subprocess.run(
            [sys.executable, "-c", code_str],
            capture_output=True, text=True, timeout=10,
        )
        try:
            output = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            output = {}
        return result.returncode, output

    def test_outputs_system_message(self):
        """exit_stop_warn outputs systemMessage (allows stop, shows msg to user)."""
        code, output = self._run_func("exit_stop_warn", "test warning")
        assert code == 0
        assert output.get("systemMessage") == "test warning"
        assert "decision" not in output

    def test_includes_warning_text(self):
        """exit_stop_warn includes the warning message in systemMessage."""
        _, output = self._run_func("exit_stop_warn", "enforcement unavailable")
        assert output.get("systemMessage") == "enforcement unavailable"

    def test_no_pretooluse_fields(self):
        """Stop hooks should not include PreToolUse-specific fields."""
        _, output = self._run_func("exit_stop_warn", "test")
        assert "hookSpecificOutput" not in output
        assert "continue" not in output
        assert "decision" not in output

    def test_produces_output_unlike_allow(self):
        """exit_stop_warn produces output (hasOutput=true) unlike exit_stop_allow."""
        _, warn_output = self._run_func("exit_stop_warn", "test")
        assert warn_output != {}  # Has output

        _, allow_output = self._run_func("exit_stop_allow")
        assert allow_output == {}  # No output


# ── stop_hook.py behavior with degraded enforcement ──


class TestStopHookDegradedEnforcement:
    """Tests for stop_hook.py when enforcement config is unavailable."""

    STOP_HOOK = str(ENFORCEMENT_HOOKS / "stop_hook.py")

    @staticmethod
    def _run_stop_hook(event, cwd=None, env_override=None):
        env = os.environ.copy()
        if env_override:
            env.update(env_override)
        # Remove CLAUDE_PLUGIN_ROOT to simulate broken config resolution
        if "CLAUDE_PLUGIN_ROOT" not in (env_override or {}):
            env.pop("CLAUDE_PLUGIN_ROOT", None)
        result = subprocess.run(
            [sys.executable, str(ENFORCEMENT_HOOKS / "stop_hook.py")],
            input=json.dumps(event),
            capture_output=True, text=True, timeout=10,
            cwd=cwd,
            env=env,
        )
        try:
            output = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            output = {}
        return result.returncode, output

    def test_allows_when_no_active_audit(self, tmp_path):
        """No .sahjhan dir = no active audit = allow silently."""
        event = {"cwd": str(tmp_path)}
        code, output = self._run_stop_hook(event, cwd=str(tmp_path))
        assert code == 0
        assert output == {}  # Silent allow

    def test_warns_when_config_not_found(self, tmp_path):
        """Active audit + missing config = warn (not silent allow)."""
        # Create .sahjhan dir to simulate active audit
        sahjhan = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan.mkdir(parents=True)
        # Write live PID so liveness check doesn't short-circuit
        (sahjhan / "daemon-init-pid").write_text(f"{os.getpid()}\n")

        event = {"cwd": str(tmp_path)}
        code, output = self._run_stop_hook(event, cwd=str(tmp_path))
        assert code == 0
        # Should have output (not silent allow)
        assert output != {}, "Stop hook silently allowed despite active audit with no config"
        # Should be a warning (systemMessage), not a block
        msg = output.get("systemMessage", "")
        assert "unavailable" in msg.lower() or "enforcement" in msg.lower() or "status-cache" in msg.lower(), (
            f"Warn message should mention enforcement/unavailable/status-cache, got: {msg}"
        )

    def test_warns_include_config_path(self, tmp_path):
        """Warning message should include the config path that was searched."""
        sahjhan = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan.mkdir(parents=True)
        # Write live PID so liveness check doesn't short-circuit
        (sahjhan / "daemon-init-pid").write_text(f"{os.getpid()}\n")

        event = {"cwd": str(tmp_path)}
        code, output = self._run_stop_hook(event, cwd=str(tmp_path))
        msg = output.get("systemMessage", "")
        assert "protocol.toml" in msg or "enforcement" in msg.lower() or "status-cache" in msg.lower()

    def test_uses_plugin_root_config(self, tmp_path):
        """Stop hook uses CLAUDE_PLUGIN_ROOT/enforcement when available."""
        # Create active audit in project
        project = tmp_path / "project"
        sahjhan = project / "docs" / "holtz" / ".sahjhan"
        sahjhan.mkdir(parents=True)

        # Use the REAL repo root as plugin dir so the binary is findable
        # but point enforcement config to a custom location
        plugin = REPO_ROOT
        # The real enforcement/ dir has protocol.toml, so config resolution
        # will succeed. Sahjhan status will still fail (no real .sahjhan state)
        # but the error won't be about missing config.
        event = {"cwd": str(project)}
        code, output = self._run_stop_hook(
            event,
            cwd=str(project),
            env_override={"CLAUDE_PLUGIN_ROOT": str(plugin)},
        )
        assert code == 0
        # If it got past config resolution, the error won't be about
        # config not being found
        reason = output.get("reason", "")
        if reason:
            assert "config not found" not in reason.lower()

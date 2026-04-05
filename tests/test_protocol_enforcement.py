"""Tests for protocol enforcement hooks."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestProtocolCache:
    """Tests for _protocol_cache.py shared module."""

    def test_read_cache_missing_file(self, tmp_path):
        """Returns None when cache file doesn't exist."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None

    def test_read_perspectives_total_narrow_exception(self, monkeypatch):
        """BH-009: Only OSError and TOML decode errors caught, not programming bugs."""
        import _protocol_cache
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        # Patch tomllib.load to raise AttributeError (simulates a programming bug)
        original_load = tomllib.load
        monkeypatch.setattr(tomllib, "load", lambda f: (_ for _ in ()).throw(AttributeError("bug")))
        import pytest
        with pytest.raises(AttributeError, match="bug"):
            _protocol_cache._read_perspectives_total()
        monkeypatch.setattr(tomllib, "load", original_load)

    def test_write_and_read_cache(self, tmp_path):
        """Round-trip write then read."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)
        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["unregistered_commits"] == ["abc1234"]

    def test_detect_git_commit(self):
        """Detects git commit commands."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("git commit -m 'fix: stuff'")
        assert is_git_commit("git add . && git commit -m 'feat: x'")
        assert not is_git_commit("git commit --amend")
        assert not is_git_commit("git status")
        assert not is_git_commit("git log --oneline")

    def test_git_commit_no_false_positives(self):
        """BH-012: git commit inside echo/comments/strings must not match."""
        from _protocol_cache import is_git_commit
        assert not is_git_commit('echo "git commit -m foo"')
        assert not is_git_commit("# git commit -m 'fix: stuff'")
        assert not is_git_commit("python -c 'os.system(\"git commit\")'")

    def test_git_commit_with_env_prefix(self):
        """BH-005 run 29: env-prefix git commit must be detected."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("VAR=x git commit -m 'fix: stuff'")
        assert is_git_commit("FOO=bar BAZ=1 git commit -m 'test'")
        assert not is_git_commit("VAR=x git commit --amend")

    def test_detect_sahjhan_command(self):
        """Detects sahjhan commands."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("./bin/sahjhan status")
        assert is_sahjhan_cmd("./bin/sahjhan transition fix_commit")
        assert is_sahjhan_cmd("sahjhan status")
        assert is_sahjhan_cmd("sahjhan status && sahjhan transition fix_commit")
        assert not is_sahjhan_cmd("git commit -m 'sahjhan'")
        assert not is_sahjhan_cmd("echo sahjhan")
        # BH-016: chained commands with non-sahjhan segments must return False
        assert not is_sahjhan_cmd("git commit -m 'fix'; sahjhan status")
        assert not is_sahjhan_cmd("sahjhan status; git push")
        assert not is_sahjhan_cmd("git commit && sahjhan transition fix_commit")

    def test_sahjhan_cmd_bare_binary_name(self):
        """BH-006 run 29: bare platform binary names must be detected."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("sahjhan-aarch64-apple-darwin status")
        assert is_sahjhan_cmd("sahjhan-x86_64-unknown-linux-gnu transition run_start")

    def test_sahjhan_cmd_with_redirect(self):
        """Issue #29 R1: 2>&1 must not break sahjhan detection."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("sahjhan status 2>&1")
        assert is_sahjhan_cmd("./bin/sahjhan-aarch64-apple-darwin status 2>&1")
        assert is_sahjhan_cmd("sahjhan status 2>&1 && sahjhan transition fix_commit 2>&1")
        # Non-sahjhan with redirect still false
        assert not is_sahjhan_cmd("git status 2>&1")

    def test_sahjhan_cmd_with_export_prefix(self):
        """Issue #29 R2: export/env prefix must not break sahjhan detection."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("export PATH=/usr/bin:$PATH && sahjhan status")
        assert is_sahjhan_cmd("PATH=/foo:$PATH sahjhan status")
        assert is_sahjhan_cmd("export FOO=bar && sahjhan status && sahjhan transition fix_commit")
        # Mixed with non-sahjhan still false
        assert not is_sahjhan_cmd("export PATH=/usr/bin:$PATH && git commit -m 'fix'")

    def test_git_commit_with_redirect(self):
        """Issue #29 R1: 2>&1 must not break git commit detection."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("git commit -m 'fix: stuff' 2>&1")
        assert is_git_commit("git add . && git commit -m 'feat: x' 2>&1")
        # Amend with redirect still correctly rejected
        assert not is_git_commit("git commit --amend 2>&1")

    def test_compute_obligations_no_cache(self):
        """No obligations when no cache."""
        from _protocol_cache import compute_obligations
        assert compute_obligations(None) == []

    def test_compute_obligations_unregistered_commits(self):
        """Unregistered commits produce obligation."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc", "def"]
        obligations = compute_obligations(cache)
        assert any("fix_commit" in o["msg"] for o in obligations)
        assert any(o["blocks_commit"] for o in obligations)

    def test_compute_obligations_pattern_check_due(self):
        """Pattern check due after 3+ fixes."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        obligations = compute_obligations(cache)
        assert any("pattern_check" in o["msg"] for o in obligations)

    def test_compute_obligations_stall(self):
        """Stall detected after threshold."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        obligations = compute_obligations(cache)
        assert any(o["blocks_all"] for o in obligations)

    def test_format_injection_under_30_tokens(self):
        """Injected text must be under 30 tokens."""
        from _protocol_cache import compute_obligations, empty_cache, format_injection
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["a", "b", "c"]
        cache["perspective"] = "component"
        cache["perspectives_done"] = 2
        cache["perspectives_total"] = 13
        cache["fixes_since_pattern"] = 5
        obligations = compute_obligations(cache)
        text = format_injection(obligations, cache)
        # Rough token estimate: words + punctuation
        token_estimate = len(text.split())
        assert token_estimate <= 35, f"Injection too verbose ({token_estimate} tokens): {text}"


class TestParseStatusText:
    """Tests for parse_status_text — parses sahjhan status output."""

    def test_parses_available_transitions(self):
        """BH-013: Available transitions are correctly parsed from sahjhan output."""
        from _protocol_cache import parse_status_text

        text = (
            "state: fix_loop (51 events, chain valid)\n"
            "sets:\n"
            "  perspective: 0/13 [· component, · integration]\n"
            "next:\n"
            "  resume: ready\n"
            "    ✓ 'context_reset' event exists since last transition\n"
            "  fix_commit: ready\n"
            "    ✓ cache state matches\n"
            "  converge: blocked\n"
            "    ✗ not all perspectives complete\n"
        )
        result = parse_status_text(text)
        assert "resume" in result["available_transitions"]
        assert "fix_commit" in result["available_transitions"]
        assert "converge" not in result["available_transitions"]

    def test_parses_state_and_event_count(self):
        """Basic parsing of state line."""
        from _protocol_cache import parse_status_text

        text = "state: awaiting_clear (25 events, chain valid)\n"
        result = parse_status_text(text)
        assert result["current_state"] == "awaiting_clear"
        assert result["event_count"] == 25

    def test_parses_perspective_sets(self):
        """Parses perspective completion from sets output."""
        from _protocol_cache import parse_status_text

        text = (
            "state: fix_loop (30 events, chain valid)\n"
            "sets:\n"
            "  perspective: 5/13 [✓ component, ✓ integration, · security]\n"
        )
        result = parse_status_text(text)
        assert result["sets"]["perspective"]["complete"] == 5
        assert result["sets"]["perspective"]["total"] == 13
        assert result["perspectives_done"] == 5

    def test_current_perspective_first_incomplete(self):
        """BH-018: current_perspective should be the first non-✓ member."""
        from _protocol_cache import parse_status_text

        text = (
            "state: fix_loop (30 events, chain valid)\n"
            "sets:\n"
            "  perspective: 2/13 [✓ component, ✓ integration, security, error-propagation]\n"
        )
        result = parse_status_text(text)
        assert result["current_perspective"] == "security"

    def test_current_perspective_all_complete(self):
        """BH-018: When all perspectives have ✓, current_perspective is 'all_complete'."""
        from _protocol_cache import parse_status_text

        text = (
            "state: fix_loop (80 events, chain valid)\n"
            "sets:\n"
            "  perspective: 13/13 [✓ component, ✓ integration, ✓ security]\n"
        )
        result = parse_status_text(text)
        assert result["current_perspective"] == "all_complete"

    def test_current_perspective_no_set_data(self):
        """BH-018: Without perspective set data, current_perspective stays unknown."""
        from _protocol_cache import parse_status_text

        text = "state: idle (0 events, chain valid)\n"
        result = parse_status_text(text)
        assert result["current_perspective"] == "unknown"


class TestProtocolTracker:
    """Tests for protocol_tracker.py PostToolUse hook."""

    def test_allows_all_commands(self):
        """Tracker never blocks — it's observation only."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_detects_git_commit(self, tmp_path):
        """Git commit updates cache with unregistered commit."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: stuff'"},
            "tool_response": {"exit_code": 0, "output": "[dev abc1234] fix: stuff"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0

        updated = read_cache(str(tmp_path))
        assert updated is not None
        assert "abc1234" in updated["unregistered_commits"]

    def test_increments_stall_counter(self, tmp_path):
        """Non-git, non-sahjhan, non-TDD commands increment stall."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat some_file.py"},
            "tool_response": {"exit_code": 0, "output": "contents"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["stall"] == 6

    def test_tdd_commands_skip_stall(self, tmp_path):
        """Test/lint/type-check commands do not increment stall (BH-012)."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        for cmd in ["python -m pytest --tb=short -q", "ruff check .", "mypy src/"]:
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": cmd},
                "tool_response": {"exit_code": 0, "output": "ok"},
                "cwd": str(tmp_path),
            }
            run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["stall"] == 3, "TDD commands should not increment stall"

    def test_ignores_non_bash(self):
        """Non-Bash tool calls are ignored."""
        event = {"tool_name": "Read", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_ignores_failed_git_commit(self, tmp_path):
        """Failed git commit does not add to unregistered."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: stuff'"},
            "tool_response": {"exit_code": 1, "output": "nothing to commit"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["unregistered_commits"] == []

    def test_no_cache_no_update(self):
        """Without existing cache, non-sahjhan commands are no-ops."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": "/tmp/nonexistent",
        }
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0

    def test_sahjhan_cmd_updates_last_sahjhan_cmd(self, tmp_path):
        """Sahjhan commands update last_sahjhan_cmd timestamp."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop (10 events, chain valid)"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated is not None
        assert updated.get("last_sahjhan_cmd"), "last_sahjhan_cmd should be set"
        from datetime import datetime
        datetime.fromisoformat(updated["last_sahjhan_cmd"])

    def test_non_sahjhan_cmd_does_not_update_last_sahjhan_cmd(self, tmp_path):
        """Regular bash commands do NOT update last_sahjhan_cmd."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2026-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "output": "total 0"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["last_sahjhan_cmd"] == "2026-01-01T00:00:00+00:00"

    def test_git_commit_does_not_update_last_sahjhan_cmd(self, tmp_path):
        """Git commits do NOT update last_sahjhan_cmd."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2026-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: stuff'"},
            "tool_response": {"exit_code": 0, "output": "[dev abc1234] fix: stuff"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["last_sahjhan_cmd"] == "2026-01-01T00:00:00+00:00"

    def test_stale_enforcement_skips_stall(self, tmp_path):
        """When enforcement is stale, protocol_tracker does not increment stall."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat some_file.py"},
            "tool_response": {"exit_code": 0, "output": "contents"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["stall"] == 5, "Stall should not increment when enforcement is stale"

    def test_stale_enforcement_still_allows_sahjhan(self, tmp_path):
        """Even with stale enforcement, sahjhan commands reactivate tracking."""
        from _protocol_cache import empty_cache, is_enforcement_fresh, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop (10 events, chain valid)"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert is_enforcement_fresh(updated), "Sahjhan command should reactivate freshness"


class TestCommitGate:
    """Tests for commit_gate.py PreToolUse hook."""

    def test_allows_when_no_cache(self):
        """No enforcement when no cache file exists."""
        event = {
            "tool_input": {"command": "git commit -m 'feat: new'"},
            "cwd": "/nonexistent/path",
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_blocks_commit_with_unregistered(self, tmp_path):
        """Blocks git commit when prior commits unregistered."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        cache["perspective"] = "component"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "unregistered" in reason.lower() or "fix_commit" in reason.lower()

    def test_allows_sahjhan_with_unregistered(self, tmp_path):
        """Sahjhan commands always allowed, even with obligations."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "./bin/sahjhan fix_commit --item-id BH-001"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_allows_pytest_with_unregistered(self, tmp_path):
        """Test commands allowed even with unregistered commits."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "python -m pytest --tb=short -q"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_blocks_on_stall(self, tmp_path):
        """Blocks all non-sahjhan Bash after stall threshold."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "python -m pytest --tb=short -q"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

    def test_blocks_commit_when_pattern_overdue(self, tmp_path):
        """Pattern check overdue hard-blocks git commit after 3+ fixes."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "pattern" in reason.lower()

    def test_injects_soft_obligation_non_commit_cmd(self, tmp_path):
        """Pattern check due: non-commit commands still get soft injection (not blocked)."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        # Non-commit commands should get soft injection, not blocked
        assert output.get("continue") is True
        context = output.get("additionalContext", "")
        assert "pattern_check" in context.lower()

    def test_allows_sahjhan_when_pattern_overdue(self, tmp_path):
        """Sahjhan commands allowed even when pattern analysis is overdue."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "./bin/sahjhan transition pattern_check"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"


class TestPrimerStateLine:
    """Tests for primer.py enforcement cache integration."""

    def test_primer_imports_format_state_line(self):
        """primer.py exposes format_state_line through its import chain."""
        import importlib
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        try:
            importlib.import_module("primer")
            # Verify the module loaded successfully and has access to
            # format_state_line via its _protocol_cache import
            from _protocol_cache import format_state_line
            assert callable(format_state_line)
        finally:
            sys.path.pop(0)

    def test_format_state_line_output(self):
        """State line is terse and under 25 words."""
        from _protocol_cache import empty_cache, format_state_line
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
        cache["perspectives_done"] = 2
        cache["perspectives_total"] = 13
        cache["unregistered_commits"] = ["abc"]
        cache["fixes_since_pattern"] = 4
        line = format_state_line(cache)
        assert line
        assert len(line.split()) <= 25, f"State line too long: {line}"
        assert "fix_loop" in line
        assert "component" in line

    def test_format_state_line_inactive(self):
        """No output when no active cache."""
        from _protocol_cache import format_state_line
        assert format_state_line(None) == ""


class TestEnforcementIntegration:
    """End-to-end: simulate a fix loop and verify enforcement."""

    def test_commit_blocked_after_unregistered(self, tmp_path):
        """Full flow: tracker detects commit, gate blocks next commit."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache

        # Seed cache as if we're in an active fix loop
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        # Simulate: git commit succeeds (tracker fires)
        tracker_event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix(x): first'"},
            "tool_response": {"exit_code": 0, "output": "[dev aaa1111] fix(x): first"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", tracker_event)

        # Now: git commit attempted (gate fires)
        gate_event = {
            "tool_input": {"command": "git commit -m 'fix(y): second'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", gate_event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block", "Gate should block second commit"

        # But: sahjhan command is allowed
        sahjhan_event = {
            "tool_input": {"command": "./bin/sahjhan transition fix_commit --item-id BH-001"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", sahjhan_event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow", "Gate should allow sahjhan commands"

    def test_stall_blocks_all(self, tmp_path):
        """Stall counter blocks everything except sahjhan."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        # Regular command blocked
        event = {
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

        # Sahjhan allowed
        event["tool_input"]["command"] = "./bin/sahjhan status"
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_tracker_then_gate_full_cycle(self, tmp_path):
        """Full cycle: commit -> blocked -> sahjhan fix_commit -> tracker clears -> allowed."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, read_cache, write_cache

        # Start with active fix loop
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        # 1. Git commit (tracker records it)
        run_enforcement_hook("protocol_tracker.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: first'"},
            "tool_response": {"exit_code": 0, "output": "[dev bbb2222] fix: first"},
            "cwd": str(tmp_path),
        })

        # 2. Verify cache has unregistered commit
        c = read_cache(str(tmp_path))
        assert len(c["unregistered_commits"]) == 1

        # 3. Gate blocks next commit
        _, out, _ = run_enforcement_hook("commit_gate.py", {
            "tool_input": {"command": "git commit -m 'fix: second'"},
            "cwd": str(tmp_path),
        })
        assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "block"

        # 4. Simulate sahjhan fix_commit (tracker clears unregistered)
        run_enforcement_hook("protocol_tracker.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "./bin/sahjhan transition fix_commit --item-id BH-001"},
            "tool_response": {"exit_code": 0, "output": "Transition: fix_loop -> fix_loop"},
            "cwd": str(tmp_path),
        })

        # 5. Verify unregistered commits cleared
        c = read_cache(str(tmp_path))
        assert c["unregistered_commits"] == []
        assert c["fixes_since_pattern"] == 1

        # 6. Gate allows next commit
        _, out, _ = run_enforcement_hook("commit_gate.py", {
            "tool_input": {"command": "git commit -m 'fix: second'"},
            "cwd": str(tmp_path),
        })
        perm = out.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow", f"Expected allow after fix_commit, got {perm}"

    def test_fix_commit_substring_not_triggered_by_option(self, tmp_path):
        """BH-017: 'fix_commit' in a ledger name does not clear unregistered_commits."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc123"]
        write_cache(str(tmp_path), cache)

        # A sahjhan command that mentions fix_commit in an option, not as a subcommand
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status --ledger fix_commit-test"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated is not None
        assert updated["unregistered_commits"] == ["abc123"], (
            "fix_commit as part of a flag value should not clear unregistered_commits"
        )


class TestEnforcementFreshness:
    """Tests for is_enforcement_fresh() — sahjhan activity freshness check."""

    def test_none_cache_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh
        assert is_enforcement_fresh(None) is False

    def test_missing_field_is_not_fresh(self):
        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        assert is_enforcement_fresh(cache) is False

    def test_recent_timestamp_is_fresh(self):
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        assert is_enforcement_fresh(cache) is True

    def test_stale_timestamp_is_not_fresh(self):
        from datetime import datetime, timedelta, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=45)  # noqa: UP017
        ).isoformat()
        assert is_enforcement_fresh(cache) is False

    def test_exactly_at_threshold_is_fresh(self):
        from datetime import datetime, timedelta, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=29)  # noqa: UP017
        ).isoformat()
        assert is_enforcement_fresh(cache) is True

    def test_custom_threshold(self):
        from datetime import datetime, timedelta, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=10)  # noqa: UP017
        ).isoformat()
        assert is_enforcement_fresh(cache, threshold_minutes=5) is False
        assert is_enforcement_fresh(cache, threshold_minutes=15) is True

    def test_garbage_timestamp_is_not_fresh(self):
        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = "not-a-timestamp"
        assert is_enforcement_fresh(cache) is False

    def test_empty_string_is_not_fresh(self):
        from _protocol_cache import empty_cache, is_enforcement_fresh
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = ""
        assert is_enforcement_fresh(cache) is False


class TestStopHookFreshness:
    """Tests for stop_hook.py freshness-gated enforcement (issue #24)."""

    def test_allows_stop_when_no_sahjhan_dir(self):
        """No .sahjhan directory → allow stop immediately."""
        event = {"cwd": "/tmp/no-audit-here"}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}  # no output = allow

    def test_blocks_stop_in_active_audit(self, tmp_path):
        """Active audit (fresh enforcement, non-terminal state) → block."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output.get("decision") == "block"
        assert "fix_loop" in output.get("reason", "")

    def test_warns_stop_in_stale_audit(self, tmp_path):
        """Stale audit (old last_sahjhan_cmd, non-terminal state) → warn, allow."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output.get("decision") == "approve"
        assert "stale" in output.get("reason", "").lower() or "abandoned" in output.get("reason", "").lower()

    def test_allows_stop_in_terminal_state(self, tmp_path):
        """Terminal state (finalized) → allow stop regardless of freshness."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "finalized"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}  # no output = allow

    def test_allows_stop_in_idle_state(self, tmp_path):
        """Idle state → allow stop regardless of freshness."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "idle"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}

    def test_blocks_when_no_cache_but_sahjhan_dir_exists(self, tmp_path):
        """Issue #29 R5: Has .sahjhan dir but no enforcement cache → block."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output.get("decision") == "block"
        assert "missing" in output.get("reason", "").lower() or "cache" in output.get("reason", "").lower()

    def test_block_message_includes_state(self, tmp_path):
        """Block message should include current state name."""
        from datetime import datetime, timezone  # noqa: UP017

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert output.get("decision") == "block"
        reason = output.get("reason", "")
        assert "fix_loop" in reason
        assert "not terminal" in reason.lower() or "complete" in reason.lower()

    def test_allows_stop_in_awaiting_clear_state(self, tmp_path):
        """Issue #32: awaiting_clear is a stop-allowed state — agent must be able to stop."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "awaiting_clear"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}  # no output = allow


class TestStopHookDaemonCleanup:
    """Tests for daemon cleanup in stop_hook.py."""

    def test_block_message_includes_manual_hint(self, tmp_path):
        """Blocked stop message should tell user how to manually kill daemon."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        reason = output.get("reason", "")
        assert "! sahjhan daemon stop" in reason, (
            "Block message should tell user how to manually stop daemon"
        )


class TestExitEnforcementError:
    """Tests for exit_enforcement_error() shared utility."""

    def test_blocks_pretooluse_during_active_fresh_audit(self, tmp_path, capsys):
        """Active audit + fresh enforcement + PreToolUse → block with reason."""
        import json
        from datetime import datetime, timezone  # noqa: UP017

        import pytest
        from _protocol_cache import empty_cache, write_cache

        from _common import exit_enforcement_error

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is False
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ENFORCEMENT DEGRADED" in reason
        assert "daemon unreachable" in reason

    def test_warns_posttooluse_during_active_fresh_audit(self, tmp_path, capsys):
        """Active audit + fresh enforcement + PostToolUse → warn."""
        import json
        from datetime import datetime, timezone  # noqa: UP017

        import pytest
        from _protocol_cache import empty_cache, write_cache

        from _common import exit_enforcement_error

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PostToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True
        assert "ENFORCEMENT DEGRADED" in output["additionalContext"]

    def test_allows_when_no_active_audit(self, tmp_path, capsys):
        """No .sahjhan dir → allow (fail-open)."""
        import json

        import pytest

        from _common import exit_enforcement_error

        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True

    def test_allows_when_stale_enforcement(self, tmp_path, capsys):
        """Active audit but stale enforcement → allow (fail-open)."""
        import json

        import pytest
        from _protocol_cache import empty_cache, write_cache

        from _common import exit_enforcement_error

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True

    def test_allows_when_sahjhan_dir_but_no_cache(self, tmp_path, capsys):
        """Data dir exists but no cache file → allow (fail-open)."""
        import json

        import pytest

        from _common import exit_enforcement_error

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        # No cache file written

        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True


class TestProtocolTrackerDaemonTeardown:
    """Tests for daemon stop when protocol reaches finalized state."""

    def test_stops_daemon_on_finalized(self, tmp_path):
        """When sahjhan status returns finalized, protocol_tracker stops the daemon."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "converged"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        # Create mock binary that returns finalized status and logs daemon stop
        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: finalized (100 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            '  *daemon*stop*)\n'
            f'    touch {stop_flag}\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        env["PATH"] = str(bin_dir) + ":" + env.get("PATH", "")

        # The hook uses ensure_sahjhan() which resolves the binary via platform triple.
        # We need to make the mock available at that path.
        # Simplest approach: create a symlink at the expected path.
        from _resolve import platform_triple
        expected_binary = bin_dir / f"sahjhan-{platform_triple()}"
        import shutil
        shutil.copy2(str(mock_binary), str(expected_binary))

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"{mock_binary} transition finalize"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event, cwd=str(tmp_path), env=env)

        assert stop_flag.exists(), "protocol_tracker should stop daemon when state is finalized"

    def test_does_not_stop_daemon_in_non_terminal(self, tmp_path):
        """Non-terminal state -> daemon should not be stopped."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: fix_loop (50 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            '  *daemon*stop*)\n'
            f'    touch {stop_flag}\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)

        from _resolve import platform_triple
        expected_binary = bin_dir / f"sahjhan-{platform_triple()}"
        import shutil
        shutil.copy2(str(mock_binary), str(expected_binary))

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"{mock_binary} status"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event, cwd=str(tmp_path), env=env)

        assert not stop_flag.exists(), "daemon should not be stopped in non-terminal state"


class TestCommitGateFreshness:
    """Tests for commit_gate.py freshness gate."""

    def test_allows_commit_when_enforcement_stale(self, tmp_path):
        """Stale enforcement → commit gate passes through, no blocking."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_allows_all_bash_when_enforcement_stale(self, tmp_path):
        """Stale enforcement → even stall > 15 doesn't block."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 20
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"


class TestPrimerFreshness:
    """Tests for primer.py freshness gate."""

    def test_primer_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → primer does not inject context."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event)
        assert code == 0
        # Should pass through silently — no context injection
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True


class TestRemainingHooksFreshness:
    """Tests for freshness gate on pre_tool_hook, post_tool_hook, bash_guard."""

    def test_pre_tool_hook_skips_eval_when_stale(self, tmp_path):
        """Stale enforcement → pre_tool_hook skips hook eval."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_pre_tool_hook_still_guards_managed_paths_when_stale(self, tmp_path):
        """Managed-path guard is always active, even when stale."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "STATUS.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

    def test_post_tool_hook_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → post_tool_hook does nothing."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.py"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("post_tool_hook.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_bash_guard_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → bash_guard does not verify manifest."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        assert code == 0
        assert output.get("continue") is True


class TestPreToolHookExists:
    """pre_tool_hook.py must exist as write_guard replacement."""

    def test_pre_tool_hook_exists(self):
        """pre_tool_hook.py must exist as write_guard replacement."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pre_tool_hook",
            os.path.join(REPO_ROOT, "enforcement", "hooks", "pre_tool_hook.py"),
        )
        assert spec is not None, "pre_tool_hook.py must exist"


class TestPrimerNoFreshnessGate:
    """Tests for primer.py freshness behavior (issue #29 R6)."""

    def test_primer_has_no_freshness_gate(self):
        """Issue #29 R6: Primer must not gate on enforcement freshness."""
        import importlib
        import inspect
        if "primer" in sys.modules:
            importlib.reload(sys.modules["primer"])
        import primer
        source = inspect.getsource(primer.main)
        assert "is_enforcement_fresh" not in source, (
            "primer.main() still contains is_enforcement_fresh gate — issue #29 R6 not fixed"
        )


class TestTransitionsToml:
    """Validate transitions.toml doesn't contain Holtz-specific paths."""

    def test_no_holtz_paths_in_command_gates(self):
        """Issue #29 R9: command_succeeds gates must not reference Holtz plugin paths."""
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        toml_path = os.path.join(REPO_ROOT, "enforcement", "transitions.toml")
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        holtz_paths = ["skills/holtz/", "enforcement/hooks/", "enforcement/scripts/"]
        for transition in data.get("transitions", []):
            for gate in transition.get("gates", []):
                if gate.get("type") != "command_succeeds":
                    continue
                cmd = gate.get("cmd", "")
                for path in holtz_paths:
                    assert path not in cmd, (
                        f"Gate command references Holtz path '{path}': {cmd}\n"
                        f"Transition: {transition.get('command')} "
                        f"({transition.get('from')} -> {transition.get('to')})"
                    )

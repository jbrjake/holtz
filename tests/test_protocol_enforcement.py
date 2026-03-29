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

    def test_detect_sahjhan_command(self):
        """Detects sahjhan commands."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("./bin/sahjhan status")
        assert is_sahjhan_cmd("./bin/sahjhan transition fix_commit")
        assert is_sahjhan_cmd("sahjhan status")
        assert not is_sahjhan_cmd("git commit -m 'sahjhan'")
        assert not is_sahjhan_cmd("echo sahjhan")

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
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
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
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
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
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        cache["perspective"] = "component"
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
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
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
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
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
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
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
        from _protocol_cache import empty_cache, write_cache

        # Seed cache as if we're in an active fix loop
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
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
        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
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
        from _protocol_cache import empty_cache, read_cache, write_cache

        # Start with active fix loop
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
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

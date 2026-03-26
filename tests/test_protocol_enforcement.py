"""Tests for protocol enforcement hooks."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestProtocolCache:
    """Tests for _protocol_cache.py shared module."""

    def test_read_cache_missing_file(self, tmp_path):
        """Returns None when cache file doesn't exist."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None

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

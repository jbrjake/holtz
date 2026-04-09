"""Tests for daemon-backed enforcement cache (read/write/update)."""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestReadCacheDaemon:
    """read_cache returns cache from daemon or None on failure."""

    def test_returns_none_when_daemon_unreachable(self, tmp_path):
        """No daemon running → returns None (fail-open)."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None

    def test_returns_dict_when_daemon_has_state(self, tmp_path, mock_daemon):
        """Daemon has enforcement state → returns parsed dict."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["stall"] == 3

    def test_returns_none_when_daemon_has_no_state(self, tmp_path, mock_daemon):
        """Daemon running but no enforcement state written yet → returns None."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None


class TestWriteCacheDaemon:
    """write_cache sends state to daemon."""

    def test_round_trip_write_read(self, tmp_path, mock_daemon):
        """Write then read returns same data."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "pattern_analysis"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "pattern_analysis"
        assert loaded["unregistered_commits"] == ["abc1234"]
        assert loaded["last_refresh"] != ""  # daemon sets this

    def test_raises_when_daemon_unreachable(self, tmp_path):
        """No daemon running → raises RuntimeError."""
        from _protocol_cache import empty_cache, write_cache
        with pytest.raises(RuntimeError):
            write_cache(str(tmp_path), empty_cache())


class TestUpdateCacheDaemon:
    """update_cache atomically patches state in daemon."""

    def test_patches_single_field(self, tmp_path, mock_daemon):
        """Patch stall counter, other fields preserved."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 0
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 5})
        assert updated["stall"] == 5
        assert updated["state"] == "fix_loop"  # preserved

    def test_patches_list_field(self, tmp_path, mock_daemon):
        """Patch unregistered_commits with full replacement."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["aaa"]
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"unregistered_commits": ["aaa", "bbb"]})
        assert updated["unregistered_commits"] == ["aaa", "bbb"]

    def test_raises_when_no_state(self, tmp_path, mock_daemon):
        """No enforcement state in daemon → raises RuntimeError."""
        from _protocol_cache import update_cache
        with pytest.raises(RuntimeError):
            update_cache(str(tmp_path), {"stall": 1})

    def test_raises_when_daemon_unreachable(self, tmp_path):
        """No daemon running → raises RuntimeError."""
        from _protocol_cache import update_cache
        with pytest.raises(RuntimeError):
            update_cache(str(tmp_path), {"stall": 1})


class TestProtocolTrackerUpdatePatterns:
    """Verify protocol_tracker write patterns work with daemon cache."""

    def test_stall_increment(self, tmp_path, mock_daemon):
        """Stall counter increments atomically via update_cache."""
        from _protocol_cache import empty_cache, read_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 4})
        assert updated["stall"] == 4

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["stall"] == 4

    def test_commit_registration(self, tmp_path, mock_daemon):
        """Commit hash appended and stall reset via update_cache."""
        from _protocol_cache import empty_cache, read_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        cache["unregistered_commits"] = ["aaa"]
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {
            "unregistered_commits": ["aaa", "bbb"],
            "stall": 0,
        })
        assert updated["unregistered_commits"] == ["aaa", "bbb"]
        assert updated["stall"] == 0

    def test_sleep_double_stall(self, tmp_path, mock_daemon):
        """Sleep command gets double stall penalty via update_cache."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 5})
        assert updated["stall"] == 5

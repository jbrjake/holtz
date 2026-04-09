"""Regression test for issue #46: dynamic path construction bypass.

Verifies that enforcement state cannot be modified by writing to the
filesystem, because the state now lives in daemon memory.
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestIssue46Regression:
    """Enforcement state survives filesystem tampering."""

    def test_filesystem_write_does_not_affect_daemon_state(self, tmp_path, mock_daemon):
        """Writing enforcement-cache.json on disk does not change daemon state.

        This is the exact attack from issue #46: an agent uses pathlib to
        construct the path dynamically and overwrites the cache file. With
        daemon-backed state, the file is irrelevant.
        """
        from _protocol_cache import empty_cache, read_cache, write_cache

        # Seed legitimate state in daemon
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["active"] = True
        write_cache(str(tmp_path), cache)

        # Simulate the attack: write a forged cache file to disk
        cache_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        cache_dir.mkdir(parents=True, exist_ok=True)
        forged = {"active": False, "state": "finalized", "stall": 0}
        (cache_dir / "enforcement-cache.json").write_text(json.dumps(forged))

        # Read from daemon — should still show fix_loop, not finalized
        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["active"] is True

    def test_state_inaccessible_without_daemon(self, tmp_path):
        """Without a running daemon, there is no enforcement state to read.

        Even if a cache file exists on disk, read_cache returns None
        because it only reads from the daemon.
        """
        from _protocol_cache import read_cache

        # Put a file on disk (simulating leftover from old version)
        cache_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        cache_dir.mkdir(parents=True, exist_ok=True)
        old_cache = {"active": True, "state": "fix_loop"}
        (cache_dir / "enforcement-cache.json").write_text(json.dumps(old_cache))

        # read_cache ignores the file — daemon is not running
        assert read_cache(str(tmp_path)) is None

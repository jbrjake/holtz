"""Tests for sleep detection in protocol_tracker.py."""
from __future__ import annotations

import contextlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

# Load _is_sleep_cmd from protocol_tracker without relying on sys.path ordering.
# test_fence_masking_agreement.py inserts hooks/ (top-level) before
# enforcement/hooks/, caching the wrong _common in sys.modules.
# We use importlib.util.spec_from_file_location to load the correct enforcement
# _common directly by path, then temporarily install it before loading
# protocol_tracker, and restore everything afterward.

ENFORCEMENT_HOOKS = Path(__file__).parent.parent / "enforcement" / "hooks"


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Load a module from an absolute path, setting __file__ correctly."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_tracker_module() -> ModuleType:
    """Load protocol_tracker with correct sibling imports; returns the module."""
    saved: dict[str, object] = {}

    # Temporarily override _common in sys.modules with the enforcement version
    saved["_common"] = sys.modules.get("_common")
    enforcement_common = _load_module_from_path(
        "_common_enforcement_tmp", ENFORCEMENT_HOOKS / "_common.py"
    )
    sys.modules["_common"] = enforcement_common

    # Stub out other sibling modules if not already present
    stubs: dict[str, list[str]] = {
        "_protocol_cache": ["empty_cache", "is_git_commit", "is_sahjhan_cmd",
                            "parse_status_text", "read_cache", "write_cache"],
        "_resolve": ["sahjhan_binary"],
    }
    for mod_name, attrs in stubs.items():
        if mod_name not in sys.modules:
            stub = ModuleType(mod_name)
            for attr in attrs:
                setattr(stub, attr, None)
            sys.modules[mod_name] = stub
            saved[mod_name] = None  # mark as not previously present

    try:
        tracker = _load_module_from_path(
            "protocol_tracker_for_sleep_test", ENFORCEMENT_HOOKS / "protocol_tracker.py"
        )
        return tracker
    finally:
        # Restore sys.modules to its original state
        for mod_name, original in saved.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original  # type: ignore[assignment]


_tracker = _load_tracker_module()
_is_sleep_cmd = _tracker._is_sleep_cmd
_parse_commit_hash = _tracker._parse_commit_hash


class TestParseCommitHash:
    """BH-016: _parse_commit_hash must handle root-commit and detached HEAD."""

    def test_normal_commit(self):
        assert _parse_commit_hash("[dev 628c9be] fix: something") == "628c9be"

    def test_root_commit(self):
        assert _parse_commit_hash("[main (root-commit) 7d97832] initial") == "7d97832"

    def test_detached_head(self):
        assert _parse_commit_hash("[(HEAD detached) abc1234] fix") == "abc1234"

    def test_no_match(self):
        assert _parse_commit_hash("no commit output here") == "unknown"

    def test_branch_with_slash(self):
        assert _parse_commit_hash("[feat/foo 9fb6e9a] feat: bar") == "9fb6e9a"


class TestSleepDetection:
    def test_sleep_above_threshold(self):
        assert _is_sleep_cmd("sleep 25") is True

    def test_sleep_at_threshold(self):
        assert _is_sleep_cmd("sleep 5") is False

    def test_sleep_below_threshold(self):
        assert _is_sleep_cmd("sleep 2") is False

    def test_sleep_leading_segment(self):
        """sleep as the first segment of a chained command is detected."""
        assert _is_sleep_cmd("sleep 30 && echo done") is True

    def test_sleep_trailing_segment(self):
        """sleep as a later segment of a chained command is detected."""
        assert _is_sleep_cmd("echo done && sleep 30") is True

    def test_no_sleep(self):
        assert _is_sleep_cmd("echo hello") is False

    def test_sleep_in_unrelated_context(self):
        """The word 'sleep' in a non-sleep command should not match."""
        assert _is_sleep_cmd("grep sleep config.py") is False

    def test_sleep_with_float(self):
        assert _is_sleep_cmd("sleep 10.5") is True

    def test_sleep_1s(self):
        """Short sleeps (<=5s) are fine — used for legitimate polling."""
        assert _is_sleep_cmd("sleep 1") is False


class TestStallPenalty:
    """Integration tests: main() applies +2 stall penalty for sleep commands."""

    def _run_main_with_event(self, cmd: str, initial_cache: dict) -> dict:
        """Run _tracker.main() with a mocked stdin event and cache, return final cache."""
        event = {
            "tool_name": "Bash",
            "cwd": "/fake/cwd",
            "tool_input": {"command": cmd},
            "tool_response": {"exit_code": 0, "output": ""},
        }

        captured_cache: dict = {}

        def fake_write_cache(cwd: str, cache: dict) -> None:
            captured_cache.update(cache)

        with (
            patch.object(_tracker, "read_event", return_value=event),
            patch.object(_tracker, "read_cache", return_value=dict(initial_cache)),
            patch.object(_tracker, "write_cache", side_effect=fake_write_cache),
            patch.object(_tracker, "is_sahjhan_cmd", return_value=False),
            patch.object(_tracker, "is_git_commit", return_value=False),
            patch.object(_tracker, "exit_ok", side_effect=SystemExit(0)),contextlib.suppress(SystemExit)
        ):
            _tracker.main()

        return captured_cache

    def test_sleep_increments_stall_by_two(self):
        """sleep 30 bumps stall by 2 from baseline."""
        initial = {"stall": 0, "active": True}
        result = self._run_main_with_event("sleep 30", initial)
        assert result["stall"] == 2

    def test_sleep_increments_stall_by_two_from_nonzero(self):
        """stall penalty accumulates correctly from a non-zero baseline."""
        initial = {"stall": 3, "active": True}
        result = self._run_main_with_event("sleep 30", initial)
        assert result["stall"] == 5

    def test_chained_sleep_increments_stall_by_two(self):
        """echo done && sleep 30 is detected and gets the double stall penalty."""
        initial = {"stall": 0, "active": True}
        result = self._run_main_with_event("echo done && sleep 30", initial)
        assert result["stall"] == 2

    def test_normal_command_increments_stall_by_one(self):
        """Non-sleep, non-TDD commands increment stall by 1, not 2."""
        initial = {"stall": 0, "active": True}
        result = self._run_main_with_event("echo hello", initial)
        assert result["stall"] == 1

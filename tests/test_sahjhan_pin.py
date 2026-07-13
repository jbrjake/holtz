"""Regression guard for the sahjhan-pin drift footgun (v0.135.0).

The pinned sahjhan version drifted because it existed in two committed places:
`_resolve.SAHJHAN_VERSION` and the `bin/.sahjhan-version` marker. The marker
went stale while the resolver was bumped, and the mismatch shipped.

These tests lock the fix: the marker is untracked (single source of truth),
the current tree is self-consistent, and drift/re-tracking is detected.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKER_REL = "bin/.sahjhan-version"


def _load_check() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_sahjhan_pin.py"
    spec = importlib.util.spec_from_file_location("check_sahjhan_pin", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_sahjhan_pin"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_marker_is_not_git_tracked():
    """bin/.sahjhan-version must stay untracked — it is runtime state.

    If it becomes tracked again, a committed copy can drift from the pin in
    _resolve.py (exactly what happened on v0.135.0).
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", MARKER_REL],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert result.returncode != 0, (
        f"{MARKER_REL} is git-tracked again. It is runtime state and must be "
        f"untracked so it can never drift from _resolve.SAHJHAN_VERSION. "
        f"Fix: git rm --cached {MARKER_REL}"
    )


def test_current_tree_is_pin_consistent():
    """The real working tree passes the pin-consistency check."""
    check = _load_check()
    assert check.check() == [], (
        "sahjhan pin is inconsistent in the working tree: " + str(check.check())
    )


def test_drifted_marker_is_detected(tmp_path, monkeypatch):
    """A marker whose value != the pin is flagged."""
    check = _load_check()
    bad = tmp_path / ".sahjhan-version"
    bad.write_text("0.0.1\n")
    monkeypatch.setattr(check, "MARKER", bad)
    monkeypatch.setattr(check._resolve, "SAHJHAN_VERSION", "9.9.9")
    # No vendored binaries under tmp; only the marker-mismatch should fire.
    failures = check.check()
    assert any("0.0.1" in f and "9.9.9" in f for f in failures), failures


def test_retracked_marker_is_detected(monkeypatch):
    """If the real marker were tracked, check() reports it (guards check #1)."""
    check = _load_check()
    monkeypatch.setattr(check, "_is_git_tracked", lambda p: True)
    failures = check.check()
    assert any("git-tracked" in f for f in failures), failures

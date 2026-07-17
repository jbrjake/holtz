"""Tests for quiz_vault — the vault channel for the lens quiz bank (#73).

The bank lives only in the daemon vault (never on disk). These tests exercise
the store/read/append primitives against the mock daemon and the graceful
degradation lens_quiz relies on. State-gating itself (writable only in recon)
is enforced by the daemon and covered by sahjhan's vault_policy tests; here we
verify the Python channel plumbs data correctly and degrades on errors.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).parent.parent / "enforcement" / "hooks"


def _load_quiz_vault():
    """Load quiz_vault with enforcement/hooks/_common injected, then restore.

    Restoring sys.modules['_common'] is essential: leaving the enforcement
    _common registered as the bare '_common' pollutes other tests that expect
    hooks/_common.py (e.g. test_hooks, test_config_resolution).
    """
    old_common = sys.modules.get("_common")
    common_spec = importlib.util.spec_from_file_location(
        "enforcement_hooks._common", str(_HOOK_DIR / "_common.py")
    )
    common_mod = importlib.util.module_from_spec(common_spec)
    sys.modules["_common"] = common_mod
    common_spec.loader.exec_module(common_mod)
    try:
        spec = importlib.util.spec_from_file_location(
            "enforcement_hooks.quiz_vault", str(_HOOK_DIR / "quiz_vault.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if old_common is not None:
            sys.modules["_common"] = old_common
        else:
            sys.modules.pop("_common", None)
    return mod


_qv = _load_quiz_vault()
store_quiz_bank = _qv.store_quiz_bank
read_quiz_bank = _qv.read_quiz_bank
read_quiz_bank_safe = _qv.read_quiz_bank_safe
append_question = _qv.append_question
record_bank_generated = _qv.record_bank_generated


_Q1 = {
    "lens": "component",
    "q": "What does save() use?",
    "a": "B",
    "opts": ["shutil", "tempfile + os.replace", "open w", "json.dump"],
    "source": "src/thing.py::save",
    "keywords": ["save", "atomic", "thing"],
}
_Q2 = {**_Q1, "lens": "security", "q": "What is validated?"}


def test_store_read_round_trip(tmp_path, mock_daemon):
    store_quiz_bank([_Q1, _Q2], str(tmp_path))
    assert json.loads(mock_daemon.vault["quiz-bank"]) == [_Q1, _Q2]
    assert read_quiz_bank(str(tmp_path)) == [_Q1, _Q2]


def test_append_builds_bank_incrementally(tmp_path, mock_daemon):
    """append_question accumulates — the incremental staging path."""
    assert append_question(_Q1, str(tmp_path)) == 1
    assert append_question(_Q2, str(tmp_path)) == 2
    assert read_quiz_bank(str(tmp_path)) == [_Q1, _Q2]


def test_append_first_question_handles_not_found(tmp_path, mock_daemon):
    """The first append reads an empty vault (not_found) and starts fresh."""
    assert "quiz-bank" not in mock_daemon.vault
    assert append_question(_Q1, str(tmp_path)) == 1
    assert read_quiz_bank(str(tmp_path)) == [_Q1]


def test_read_safe_returns_empty_when_absent(tmp_path, mock_daemon):
    """No bank yet → [] (lens_quiz degrades to 'no quiz' rather than crash)."""
    assert read_quiz_bank_safe(str(tmp_path)) == []


def test_read_safe_returns_empty_when_daemon_down(tmp_path, monkeypatch):
    monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", str(tmp_path / "dead.sock"))
    assert read_quiz_bank_safe(str(tmp_path)) == []


def test_read_raises_when_absent(tmp_path, mock_daemon):
    with pytest.raises(RuntimeError):
        read_quiz_bank(str(tmp_path))


def test_record_bank_generated_emits_counts(tmp_path, mock_daemon):
    store_quiz_bank([_Q1, _Q2], str(tmp_path))
    record_bank_generated(str(tmp_path), run="4", auditor="holtz")
    events = [
        e for e in mock_daemon.recorded_events
        if e.get("event_type") == "quiz_bank_generated"
    ]
    assert len(events) == 1
    fields = events[0]["fields"]
    assert fields["question_count"] == "2"
    assert fields["lens_count"] == "2"  # component + security
    assert fields["run"] == "4"

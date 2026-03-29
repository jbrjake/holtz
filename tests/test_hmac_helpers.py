"""Tests for HMAC event provenance helpers."""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
from pathlib import Path
from types import ModuleType

# Load enforcement/hooks/_common.py directly by path to avoid sys.path conflicts
# with hooks/_common.py (same filename, different directories).
ENFORCEMENT_HOOKS = Path(__file__).parent.parent / "enforcement" / "hooks"


def _load_enforcement_common() -> ModuleType:
    """Load enforcement/hooks/_common.py directly, bypassing sys.path."""
    path = ENFORCEMENT_HOOKS / "_common.py"
    spec = importlib.util.spec_from_file_location("_common_enforcement", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_enforcement_common = _load_enforcement_common()


def test_compute_event_proof_deterministic(tmp_path):
    """Same inputs produce same proof."""
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    compute_event_proof = _enforcement_common.compute_event_proof

    fields = {"project": "holtz", "run": "25", "auditor": "holtz", "perspective": "component"}
    proof1 = compute_event_proof("quiz_answered", fields, str(key_path))
    proof2 = compute_event_proof("quiz_answered", fields, str(key_path))
    assert proof1 == proof2
    assert len(proof1) == 64  # SHA-256 hex digest


def test_compute_event_proof_field_order_independent(tmp_path):
    """Field ordering must not affect the proof (sorted internally)."""
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    compute_event_proof = _enforcement_common.compute_event_proof

    fields_a = {"z_field": "last", "a_field": "first"}
    fields_b = {"a_field": "first", "z_field": "last"}
    assert compute_event_proof("test_event", fields_a, str(key_path)) == \
           compute_event_proof("test_event", fields_b, str(key_path))


def test_compute_event_proof_matches_manual(tmp_path):
    """Proof must match manual HMAC-SHA256 computation."""
    key = b"known-key"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    compute_event_proof = _enforcement_common.compute_event_proof

    fields = {"auditor": "holtz", "project": "test"}
    proof = compute_event_proof("my_event", fields, str(key_path))

    # Manual computation
    payload = "my_event\0auditor=holtz\0project=test"
    expected = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    assert proof == expected


def test_compute_event_proof_different_types_differ(tmp_path):
    """Different event types produce different proofs."""
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    compute_event_proof = _enforcement_common.compute_event_proof

    fields = {"project": "holtz"}
    proof_a = compute_event_proof("event_a", fields, str(key_path))
    proof_b = compute_event_proof("event_b", fields, str(key_path))
    assert proof_a != proof_b

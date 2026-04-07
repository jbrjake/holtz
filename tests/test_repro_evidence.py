"""Tests for check_repro_evidence.py."""
from __future__ import annotations

from enforcement.scripts.check_repro_evidence import check_repro_evidence


def test_investigation_file_exists(tmp_path):
    """Investigation file present — evidence sufficient."""
    inv = tmp_path / "investigations" / "BH-042.md"
    inv.parent.mkdir(parents=True)
    inv.write_text("## Reproduction Attempts\n\n- Ran test 100x, 0 failures\n")
    assert check_repro_evidence("BH-042", str(tmp_path)) is True


def test_no_investigation_file_fails(tmp_path):
    """No investigation file and no evidence — fails."""
    assert check_repro_evidence("BH-042", str(tmp_path)) is False


def test_empty_investigation_file_fails(tmp_path):
    """Empty investigation file is not evidence."""
    inv = tmp_path / "investigations" / "BH-042.md"
    inv.parent.mkdir(parents=True)
    inv.write_text("")
    assert check_repro_evidence("BH-042", str(tmp_path)) is False


def test_invalid_finding_id_raises():
    """Invalid finding ID format raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Invalid finding ID"):
        check_repro_evidence("BOGUS", "/tmp")

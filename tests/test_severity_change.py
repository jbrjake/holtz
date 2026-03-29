"""Tests for check_severity_change.py."""
from __future__ import annotations

from enforcement.scripts.check_severity_change import check_downgrade


def test_no_downgrade_passes():
    """Same severity — no evidence needed."""
    result = check_downgrade(
        original_severity="MEDIUM",
        resolved_severity="MEDIUM",
        evidence_path=None,
    )
    assert result is True


def test_downgrade_with_evidence_passes(tmp_path):
    """Downgrade with valid evidence path passes."""
    evidence = tmp_path / "evidence.md"
    evidence.write_text("Code at file.py:42 shows this is actually LOW.")
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="MEDIUM",
        evidence_path=str(evidence),
    )
    assert result is True


def test_downgrade_without_evidence_fails():
    """Downgrade without evidence path fails."""
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="LOW",
        evidence_path=None,
    )
    assert result is False


def test_downgrade_with_nonexistent_evidence_fails():
    """Downgrade with nonexistent evidence file fails."""
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="MEDIUM",
        evidence_path="/nonexistent/evidence.md",
    )
    assert result is False


def test_upgrade_passes():
    """Upgrading severity never requires evidence."""
    result = check_downgrade(
        original_severity="LOW",
        resolved_severity="HIGH",
        evidence_path=None,
    )
    assert result is True


def test_unknown_original_severity_raises():
    """BH-009: Unknown original severity must raise, not silently map to rank 0."""
    import pytest
    with pytest.raises(ValueError, match="Unknown original severity"):
        check_downgrade(
            original_severity="TYPO",
            resolved_severity="LOW",
            evidence_path=None,
        )


def test_unknown_resolved_severity_raises():
    """Unknown resolved severity must raise, not silently map to rank 0."""
    import pytest
    with pytest.raises(ValueError, match="Unknown resolved severity"):
        check_downgrade(
            original_severity="HIGH",
            resolved_severity="BOGUS",
            evidence_path=None,
        )

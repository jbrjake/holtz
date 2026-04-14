"""Tests for check_severity_change.py."""
from __future__ import annotations

import subprocess
import sys

import pytest

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
    with pytest.raises(ValueError, match="Unknown resolved severity"):
        check_downgrade(
            original_severity="HIGH",
            resolved_severity="BOGUS",
            evidence_path=None,
        )


# ── CLI main() tests (subprocess E2E) ──

_SCRIPT = "enforcement/scripts/check_severity_change.py"


@pytest.mark.hook_e2e
class TestMainCLI:
    """Test the main() entry point via subprocess — the actual interface sahjhan calls."""

    def test_no_args_prints_usage_and_exits_1(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def test_same_severity_exits_0(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "HIGH", "HIGH"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

    def test_upgrade_exits_0(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "LOW", "HIGH"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

    def test_downgrade_without_evidence_exits_1(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "HIGH", "LOW"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "FAIL" in result.stderr
        assert "evidence_path" in result.stderr

    def test_downgrade_with_valid_evidence_exits_0(self, tmp_path):
        evidence = tmp_path / "evidence.md"
        evidence.write_text("Justified downgrade.\n")
        result = subprocess.run(
            [sys.executable, _SCRIPT, "HIGH", "LOW", str(evidence)],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

    def test_downgrade_with_nonexistent_evidence_exits_1(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "HIGH", "LOW", "/nonexistent/file.md"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "FAIL" in result.stderr

    def test_unknown_severity_exits_1(self):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "BOGUS", "LOW"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "Unknown" in result.stderr

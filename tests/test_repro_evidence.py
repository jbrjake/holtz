"""Tests for check_repro_evidence.py."""
from __future__ import annotations

import subprocess
import sys

import pytest
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
    with pytest.raises(ValueError, match="Invalid finding ID"):
        check_repro_evidence("BOGUS", "/tmp")


# ── CLI main() tests (subprocess E2E) ──

_SCRIPT = "enforcement/scripts/check_repro_evidence.py"


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

    def test_valid_finding_with_evidence_exits_0(self, tmp_path):
        inv = tmp_path / "investigations" / "BH-042.md"
        inv.parent.mkdir(parents=True)
        inv.write_text("## Reproduction Attempts\n\n- Ran test 100x\n")
        result = subprocess.run(
            [sys.executable, _SCRIPT, "BH-042", "--holtz-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_valid_finding_without_evidence_exits_1(self, tmp_path):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "BH-042", "--holtz-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "FAIL" in result.stderr

    def test_invalid_finding_id_exits_1(self, tmp_path):
        result = subprocess.run(
            [sys.executable, _SCRIPT, "BOGUS", "--holtz-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 1
        assert "Invalid finding ID" in result.stderr

    def test_justine_finding_id_accepted(self, tmp_path):
        inv = tmp_path / "investigations" / "BJ-001.md"
        inv.parent.mkdir(parents=True)
        inv.write_text("Investigation content\n")
        result = subprocess.run(
            [sys.executable, _SCRIPT, "BJ-001", "--holtz-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

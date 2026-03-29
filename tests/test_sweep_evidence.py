"""Tests for check_sweep_evidence.py — final sweep read threshold."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

SCRIPT = "enforcement/scripts/check_sweep_evidence.py"


def _make_transcript(tmp_path, read_count: int) -> str:
    """Create a fake session JSONL with N distinct file reads."""
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    for i in range(read_count):
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": f"src/file_{i}.py"},
                    }
                ]
            },
        }
        lines.append(json.dumps(entry))
    transcript.write_text("\n".join(lines))
    return str(transcript)


def test_below_threshold_fails(tmp_path):
    """Fewer than min_reads distinct reads should fail."""
    transcript = _make_transcript(tmp_path, 10)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "30", "--transcript", transcript],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_above_threshold_passes(tmp_path):
    """Meeting min_reads should pass."""
    transcript = _make_transcript(tmp_path, 35)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "30", "--transcript", transcript],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_duplicate_reads_not_double_counted(tmp_path):
    """Reading the same file twice counts as one distinct read."""
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    for _ in range(40):
        entry = {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "src/same.py"}}]
            },
        }
        lines.append(json.dumps(entry))
    transcript.write_text("\n".join(lines))
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "2", "--transcript", str(transcript)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0  # only 1 distinct file

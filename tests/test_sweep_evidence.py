"""Tests for check_sweep_evidence.py — final sweep read threshold."""
from __future__ import annotations

import json
import subprocess
import sys

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


def test_sweep_boundary_only_counts_post_sweep_reads(tmp_path):
    """BH-006: Only reads after the sweep boundary should count.

    A session with 40 reads before the sweep and 5 after should report 5,
    not 45. The old code counted all reads and would incorrectly pass.
    """
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    transcript = tmp_path / "transcript.jsonl"
    lines = []
    # 40 reads BEFORE the sweep (should not count)
    for i in range(40):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": f"src/pre_{i}.py"}}
            ]},
        }))
    # Sweep boundary marker
    lines.append(json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "sahjhan transition final_sweep_start"}}
        ]},
    }))
    # 5 reads AFTER the sweep (should count)
    for i in range(5):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": f"src/post_{i}.py"}}
            ]},
        }))
    transcript.write_text("\n".join(lines))

    assert count_distinct_reads(str(transcript), sweep_only=True) == 5
    assert count_distinct_reads(str(transcript), sweep_only=False) == 45


def test_no_sweep_boundary_counts_all(tmp_path):
    """With no sweep boundary marker, all reads are counted (fallback)."""
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    transcript = _make_transcript(tmp_path, 20)
    assert count_distinct_reads(str(transcript), sweep_only=True) == 20


def test_no_transcript_fails(tmp_path, monkeypatch):
    """No --transcript and no CLAUDE_SESSION_TRANSCRIPT env var should fail."""
    monkeypatch.delenv("CLAUDE_SESSION_TRANSCRIPT", raising=False)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "1"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "No transcript found" in result.stderr


def test_nonexistent_transcript_returns_zero(tmp_path):
    """Non-existent transcript path returns 0 reads."""
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    assert count_distinct_reads("/nonexistent/path.jsonl") == 0


def test_flat_tool_use_format_reads(tmp_path):
    """Reads in flat tool_use format (not nested message.content) are counted."""
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    transcript = tmp_path / "transcript.jsonl"
    lines = []
    for i in range(5):
        lines.append(json.dumps({
            "type": "tool_use",
            "name": "Read",
            "input": {"file_path": f"src/flat_{i}.py"},
        }))
    transcript.write_text("\n".join(lines))
    assert count_distinct_reads(str(transcript), sweep_only=False) == 5


def test_flat_format_sweep_boundary(tmp_path):
    """Sweep boundary in flat tool_use format is detected."""
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    transcript = tmp_path / "transcript.jsonl"
    lines = []
    # 10 reads before sweep
    for i in range(10):
        lines.append(json.dumps({
            "type": "tool_use", "name": "Read",
            "input": {"file_path": f"src/pre_{i}.py"},
        }))
    # Sweep boundary in flat format
    lines.append(json.dumps({
        "type": "tool_use", "name": "Bash",
        "input": {"command": "sahjhan transition final_sweep_start"},
    }))
    # 3 reads after sweep
    for i in range(3):
        lines.append(json.dumps({
            "type": "tool_use", "name": "Read",
            "input": {"file_path": f"src/post_{i}.py"},
        }))
    transcript.write_text("\n".join(lines))
    assert count_distinct_reads(str(transcript), sweep_only=True) == 3


def test_env_var_transcript_discovery(tmp_path, monkeypatch):
    """CLAUDE_SESSION_TRANSCRIPT env var is used when --transcript is omitted."""
    transcript = _make_transcript(tmp_path, 35)
    monkeypatch.setenv("CLAUDE_SESSION_TRANSCRIPT", transcript)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "30"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_malformed_jsonl_lines_skipped(tmp_path):
    """Malformed JSONL lines are skipped without crashing."""
    sys.path.insert(0, "enforcement/scripts")
    from check_sweep_evidence import count_distinct_reads

    transcript = tmp_path / "transcript.jsonl"
    lines = [
        "not valid json",
        "",
        json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/ok.py"}}
            ]},
        }),
        "{broken json",
    ]
    transcript.write_text("\n".join(lines))
    assert count_distinct_reads(str(transcript), sweep_only=False) == 1

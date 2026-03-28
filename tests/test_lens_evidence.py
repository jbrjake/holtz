"""Tests for lens sweep evidence checking."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))

from lens_evidence import check_artifact, check_transcript  # noqa: E402


def _make_reads(*paths: str) -> list[dict]:
    """Create JSONL-format transcript events with Read tool_use blocks."""
    blocks = [
        {"type": "tool_use", "name": "Read", "input": {"file_path": p}}
        for p in paths
    ]
    return [{"type": "assistant", "message": {"content": blocks}}]


def _make_text(text: str) -> dict:
    """Create a JSONL-format assistant text event."""
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def test_check_transcript_sufficient():
    """Transcript with >=5 reads and keywords passes."""
    transcript = _make_reads(*[f"src/mod{i}.py" for i in range(6)])
    transcript.append(_make_text("The except clause catches OSError and TimeoutExpired"))
    result = check_transcript(transcript, keywords=["except", "OSError"], lens="error-propagation")
    assert result["pass"]
    assert result["read_count"] >= 5


def test_check_transcript_insufficient_reads():
    """Transcript with <5 reads fails."""
    transcript = _make_reads("src/mod1.py")
    transcript.append(_make_text("The except clause catches OSError"))
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert not result["pass"]
    assert "files read" in result["reason"]


def test_check_transcript_no_keywords():
    """Transcript with reads but no lens keywords fails."""
    transcript = _make_reads(*[f"src/mod{i}.py" for i in range(6)])
    transcript.append(_make_text("The code looks fine."))
    result = check_transcript(transcript, keywords=["except", "raise", "OSError"], lens="error-propagation")
    assert not result["pass"]
    assert "keyword" in result["reason"].lower()


def test_check_transcript_skips_docs():
    """Reads of docs/ paths are not counted."""
    transcript = _make_reads(*[f"docs/holtz/file{i}.md" for i in range(10)])
    transcript.append(_make_text("The except clause catches OSError"))
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert not result["pass"]
    assert result["read_count"] == 0


def test_check_transcript_skips_quiz_bank():
    """Reads of quiz-bank paths are not counted (anti-cheat)."""
    transcript = _make_reads("enforcement/quiz-bank.json")
    transcript.append(_make_text("except OSError raise"))
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert result["read_count"] == 0


def test_check_transcript_counts_enforcement_source():
    """Reads of enforcement source code ARE counted (BH-007)."""
    transcript = _make_reads(*[f"enforcement/hooks/hook{i}.py" for i in range(6)])
    transcript.append(_make_text("The except clause catches OSError"))
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert result["pass"]
    assert result["read_count"] == 6


def test_check_transcript_degraded_mode():
    """Degraded mode (plain content string) counts keywords but not reads."""
    transcript = [{"type": "assistant", "content": "The except clause catches OSError"}]
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation", min_reads=0)
    assert result["pass"]
    assert result["keyword_hits"] >= 1


def test_check_artifact_exists(tmp_path):
    """Artifact file with content passes."""
    artifact = tmp_path / "lens-error-propagation.md"
    artifact.write_text("## error-propagation\n\n- primer.py:56 catches OSError\n")
    result = check_artifact(str(artifact))
    assert result["pass"]


def test_check_artifact_missing(tmp_path):
    """Missing artifact fails."""
    result = check_artifact(str(tmp_path / "nonexistent.md"))
    assert not result["pass"]


def test_check_artifact_too_small(tmp_path):
    """Artifact under 50 bytes fails."""
    artifact = tmp_path / "lens-tiny.md"
    artifact.write_text("ok")
    result = check_artifact(str(artifact))
    assert not result["pass"]


def test_parse_transcript_jsonl(tmp_path):
    """Parse JSONL transcript into list of events."""
    from lens_evidence import parse_transcript_jsonl
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "tool_use", "tool_name": "Read"}) + "\n"
        + json.dumps({"type": "assistant", "content": "hello"}) + "\n"
        + "bad json line\n"
    )
    events = parse_transcript_jsonl(str(transcript))
    assert len(events) == 2

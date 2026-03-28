"""Evidence checking for lens sweep subagents.

Parses subagent transcripts (JSONL) and output artifacts to verify
real work was done. All checks are Python regex — zero LLM token cost.
"""
from __future__ import annotations

import json
import os


def check_transcript(
    events: list[dict],
    keywords: list[str],
    lens: str,
    min_reads: int = 5,
) -> dict:
    """Check a parsed transcript for evidence of real lens work.

    Returns {"pass": bool, "read_count": int, "keyword_hits": int, "reason": str}
    """
    read_count = 0
    keyword_hits = 0
    assistant_text = ""

    for event in events:
        if event.get("tool_name") == "Read":
            path = event.get("tool_input", {}).get("file_path", "")
            parts = path.replace("\\", "/").split("/")
            if not any(p in ("docs", "enforcement") or "quiz-bank" in p for p in parts):
                read_count += 1
        if event.get("type") == "assistant":
            assistant_text += " " + event.get("content", "")

    lower_text = assistant_text.lower()
    for kw in keywords:
        if kw.lower() in lower_text:
            keyword_hits += 1

    passed = read_count >= min_reads and keyword_hits >= 1
    reason = ""
    if read_count < min_reads:
        reason = f"{read_count} files read. Blocked."
    elif keyword_hits < 1:
        reason = "0 lens keywords found. Blocked."

    return {"pass": passed, "read_count": read_count, "keyword_hits": keyword_hits, "reason": reason}


def check_artifact(artifact_path: str, min_bytes: int = 50) -> dict:
    """Check that a lens audit artifact exists with minimum content."""
    if not os.path.isfile(artifact_path):
        return {"pass": False, "reason": f"Artifact not found: {artifact_path}"}
    size = os.path.getsize(artifact_path)
    if size < min_bytes:
        return {"pass": False, "reason": f"Artifact too small: {size} bytes"}
    return {"pass": True, "reason": ""}


def parse_transcript_jsonl(path: str) -> list[dict]:
    """Parse a JSONL transcript file into a list of events."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events

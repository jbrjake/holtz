#!/usr/bin/env python3
"""SubagentStop lens quiz hook — three-phase gate for lens sweep subagents.

Phase 1: Evidence check — verifies real file reads and lens keywords.
Phase 2: Quiz — poses 5 multiple-choice questions from quiz bank.
Phase 3: Score — grades answers, allows on >=4/5 or after 3 failures.

Non-lens subagents (no LENS: prefix in last_assistant_message) pass through.
Degrades gracefully if sahjhan binary or quiz bank is unavailable.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _resolve import sahjhan_binary  # noqa: E402
from lens_evidence import (  # noqa: E402
    check_artifact,
    check_transcript,
    parse_transcript_jsonl,
)

from _common import (  # noqa: E402
    _active_ledger,
    exit_stop_allow,
    exit_stop_block,
    read_event,
)

# ── Constants ──

MAX_QUIZ_ATTEMPTS = 3
PASS_THRESHOLD = {5: 4, 4: 3, 3: 3, 2: 2, 1: 1}  # questions -> min correct
MAX_STALE_QUESTIONS = 2  # if more than this are stale, quiz is invalid

# ── Pure functions (tested directly) ──

_LENS_PREFIX_RE = re.compile(r"^LENS:\s*(\S+)", re.MULTILINE)
_ANSWERS_RE = re.compile(
    r"LENS:\s*(\S+)\s+ANSWERS:\s*([A-Da-d](?:\s*,\s*[A-Da-d])*)",
    re.MULTILINE,
)


def parse_lens_name(message: str) -> str | None:
    """Extract lens name from LENS: prefix in message."""
    m = _LENS_PREFIX_RE.search(message)
    return m.group(1) if m else None


def parse_answers(message: str) -> tuple[str, list[str]] | None:
    """Extract (lens_name, [answers]) from 'LENS: <name> ANSWERS: A,B,C,D,A'.

    Returns None if format doesn't match.
    """
    m = _ANSWERS_RE.search(message)
    if not m:
        return None
    lens = m.group(1)
    raw = m.group(2)
    answers = [a.strip().upper() for a in raw.split(",")]
    if len(answers) != 5:
        return None
    return (lens, answers)


def select_questions(bank: list[dict], lens: str) -> list[dict]:
    """Select up to 5 questions for a given lens from the bank."""
    matching = [q for q in bank if q.get("lens") == lens]
    return matching[:5]


def format_quiz_questions(questions: list[dict], lens: str) -> str:
    """Format quiz questions into compact block text.

    Output:
        Quiz. Format: LENS: error-propagation ANSWERS: A,B,C,D,A
        Q1: primer.py L56 catches? A) OSError,TimeoutExpired B) ...
        Q2: ...
    """
    lines = [f"Quiz. Format: LENS: {lens} ANSWERS: A,B,C,D,A"]
    for i, q in enumerate(questions, 1):
        opts = q["opts"]
        opt_str = " ".join(
            f"{chr(65 + j)}) {opts[j]}" for j in range(len(opts))
        )
        lines.append(f"Q{i}: {q['q']} {opt_str}")
    return "\n".join(lines)


def questions_hash(questions: list[dict]) -> str:
    """Stable SHA-256 hash of question content for ledger event."""
    payload = json.dumps(
        [{"q": q["q"], "a": q["a"]} for q in questions],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_answer_freshness(
    question: dict, cwd: str
) -> bool:
    """Check if a quiz question's source file still contains the expected answer.

    Returns True if the answer is still valid (or if we can't verify).
    Returns False if the source has changed and the answer is stale.
    """
    source = question.get("source", "")
    if ":" not in source:
        return True  # can't verify without line number

    parts = source.rsplit(":", 1)
    filepath = os.path.join(cwd, parts[0])
    if not os.path.isfile(filepath):
        return False  # file deleted — answer is stale

    try:
        line_no = int(parts[1])
    except ValueError:
        return True  # can't parse line number

    try:
        with open(filepath) as f:
            file_lines = f.readlines()
    except OSError:
        return True  # can't read — assume fresh

    # Check if any keyword from the correct answer option appears near the line
    answer_idx = ord(question["a"]) - ord("A")
    if answer_idx < 0 or answer_idx >= len(question["opts"]):
        return True

    answer_text = question["opts"][answer_idx].lower()
    # Check a window of lines around the source line
    start = max(0, line_no - 3)
    end = min(len(file_lines), line_no + 3)
    window = "".join(file_lines[start:end]).lower()

    # If the answer text has commas, check each part
    answer_parts = [p.strip() for p in answer_text.split(",")]
    return any(part in window for part in answer_parts)


def score_answers(
    questions: list[dict],
    answers: list[str],
    cwd: str,
) -> tuple[int, int]:
    """Score answers against quiz bank with staleness check.

    Returns (correct, total) where total may be < len(questions) if
    stale questions were dropped.
    """
    correct = 0
    total = 0
    for q, given in zip(questions, answers, strict=False):
        if not verify_answer_freshness(q, cwd):
            continue  # drop stale question
        total += 1
        if given.upper() == q["a"].upper():
            correct += 1
    return correct, total


# ── Sahjhan interaction helpers ──


def _run_sahjhan(
    binary: str,
    config_dir: str,
    cwd: str,
    ledger: str | None,
    args: list[str],
) -> subprocess.CompletedProcess[str] | None:
    """Run a sahjhan command, returning None on any failure."""
    cmd = [binary, "--config-dir", config_dir]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(args)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    return None


def _get_run_number(binary: str, config_dir: str, cwd: str, ledger: str | None) -> str:
    """Get current run number from sahjhan status."""
    result = _run_sahjhan(binary, config_dir, cwd, ledger, ["status", "--json"])
    if result and result.returncode == 0:
        with contextlib.suppress(json.JSONDecodeError):
            status = json.loads(result.stdout)
            return str(status.get("run", "0"))
    return "0"


def _query_events(
    binary: str,
    config_dir: str,
    cwd: str,
    ledger: str | None,
    event_type: str,
    perspective: str,
) -> list[dict]:
    """Query sahjhan for events of a given type and perspective."""
    result = _run_sahjhan(
        binary, config_dir, cwd, ledger,
        ["query", "--type", event_type, "--field", f"perspective={perspective}", "--json"],
    )
    if result and result.returncode == 0:
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(result.stdout)
    return []


def _record_event(
    binary: str,
    config_dir: str,
    cwd: str,
    ledger: str | None,
    event_type: str,
    fields: dict[str, str],
) -> None:
    """Record an event in the sahjhan ledger."""
    args = ["event", event_type]
    for k, v in fields.items():
        args.extend(["--field", f"{k}={v}"])
    _run_sahjhan(binary, config_dir, cwd, ledger, args)


# ── Main hook logic ──


def main() -> None:
    event = read_event()
    message = event.get("last_assistant_message", "")

    # Non-lens subagents pass through
    lens = parse_lens_name(message)
    if not lens:
        exit_stop_allow()
    assert lens is not None  # for mypy: exit_stop_allow calls sys.exit

    # Setup
    cwd = event.get("cwd", os.getcwd())
    binary = sahjhan_binary()
    config_dir = os.path.join(cwd, "enforcement")
    quiz_bank_path = os.path.join(cwd, "enforcement", "quiz-bank.json")

    # Graceful degradation: no binary → allow
    if not os.path.isfile(binary):
        exit_stop_allow()

    ledger = _active_ledger(cwd)
    run = _get_run_number(binary, config_dir, cwd, ledger)

    # Common fields for all events
    base_fields = {
        "project": os.path.basename(cwd),
        "run": run,
        "auditor": "holtz",
        "perspective": lens,
    }

    # ── Phase 1: Evidence check ──

    transcript_path = event.get("agent_transcript_path")
    if transcript_path and os.path.isfile(transcript_path):
        events_list = parse_transcript_jsonl(transcript_path)
    else:
        # Degrade: synthesize minimal events from last_assistant_message
        events_list = [{"type": "assistant", "content": message}]

    # Load quiz bank for keywords (or use empty list)
    bank: list[dict] = []
    if os.path.isfile(quiz_bank_path):
        with contextlib.suppress(json.JSONDecodeError, OSError), open(quiz_bank_path) as f:
            bank = json.load(f)

    questions = select_questions(bank, lens)
    keywords = []
    for q in questions:
        keywords.extend(q.get("keywords", []))
    keywords = list(set(keywords)) if keywords else [lens]

    evidence = check_transcript(events_list, keywords=keywords, lens=lens)
    if not evidence["pass"]:
        exit_stop_block(evidence["reason"])

    # Also check artifact if transcript was available
    artifact_path = os.path.join(cwd, "docs", "holtz", "audit", f"lens-{lens}.md")
    artifact = check_artifact(artifact_path)
    if not artifact["pass"]:
        exit_stop_block(artifact["reason"])

    # ── Phase 2 & 3: Quiz flow ──

    # Graceful degradation: no quiz bank → allow (evidence check was enough)
    if not questions:
        exit_stop_allow()

    # Check if quiz was already posed for this perspective
    posed_events = _query_events(
        binary, config_dir, cwd, ledger, "quiz_posed", lens
    )

    if not posed_events:
        # Phase 2: Pose the quiz
        qhash = questions_hash(questions)
        _record_event(binary, config_dir, cwd, ledger, "quiz_posed", {
            **base_fields, "questions_hash": qhash
        })
        quiz_text = format_quiz_questions(questions, lens)
        exit_stop_block(quiz_text)

    # Phase 3: Score answers
    parsed = parse_answers(message)
    if not parsed:
        exit_stop_block(
            f"Could not parse answers. Format: LENS: {lens} ANSWERS: A,B,C,D,A"
        )
    assert parsed is not None  # for mypy: exit_stop_block calls sys.exit
    _, given_answers = parsed
    correct, total = score_answers(questions, given_answers, cwd)

    # Check staleness
    if total < len(questions) - MAX_STALE_QUESTIONS:
        exit_stop_block(
            f"Too many stale questions ({len(questions) - total}/{len(questions)}). "
            "Quiz bank must be regenerated."
        )

    threshold = PASS_THRESHOLD.get(total, max(1, total - 1))

    if correct >= threshold:
        _record_event(binary, config_dir, cwd, ledger, "quiz_answered", {
            **base_fields,
            "score": f"{correct}/{total}",
            "pass": "true",
        })
        exit_stop_allow()

    # Failed — check attempt count
    failed_events = _query_events(
        binary, config_dir, cwd, ledger, "quiz_failed", lens
    )
    attempt = len(failed_events) + 1  # this is the current (failing) attempt

    _record_event(binary, config_dir, cwd, ledger, "quiz_failed", {
        **base_fields, "score": f"{correct}/{total}"
    })

    if attempt >= MAX_QUIZ_ATTEMPTS:
        _record_event(binary, config_dir, cwd, ledger, "quiz_exhausted", {
            **base_fields
        })
        exit_stop_allow()

    exit_stop_block(
        f"{correct}/{total}. Rejected. Read the code. "
        f"(attempt {attempt}/{MAX_QUIZ_ATTEMPTS})"
    )


if __name__ == "__main__":
    main()

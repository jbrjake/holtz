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

from _resolve import ensure_sahjhan  # noqa: E402
from lens_evidence import (  # noqa: E402
    check_artifact,
    check_transcript,
    parse_transcript_jsonl,
)

from _common import (  # noqa: E402
    _daemon_request,
    _get_daemon_socket_path,
    exit_stop_allow,
    exit_stop_block,
    mask_fenced_blocks,
    read_event,
    record_authed_event,
    resolve_config_dir,
)

# ── Vault helpers ──


def store_quiz_bank(bank: list[dict], cwd: str | None = None) -> None:
    """Store quiz bank data in the sahjhan daemon vault.

    Called during audit initialization to load the quiz bank into
    daemon memory. After this, the file-based quiz bank is not needed.
    """
    import base64
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(bank).encode()).decode()
    _daemon_request(sock_path, {"op": "vault_store", "name": "quiz-bank", "data": data})


# ── Constants ──

MAX_QUIZ_ATTEMPTS = 3
PASS_THRESHOLD = {5: 4, 4: 3, 3: 3, 2: 2, 1: 1}  # questions -> min correct
MAX_STALE_QUESTIONS = 2  # if more than this are stale, quiz is invalid

# ── Pure functions (tested directly) ──

_LENS_PREFIX_RE = re.compile(r"^LENS:\s*(\S+)", re.MULTILINE)
_ANSWERS_RE = re.compile(
    r"^LENS:\s*(\S+)\s+ANSWERS:\s*([A-Da-d](?:\s*,\s*[A-Da-d])*)",
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
    answers = [a.strip().upper() for a in raw.split(",") if a.strip()]
    if not answers or len(answers) > 5:
        return None
    return (lens, answers)


def select_questions(bank: list[dict], lens: str) -> list[dict]:
    """Select up to 5 deterministic questions for a given lens from the bank.

    Uses a seeded RNG so the same questions are selected on both the pose
    and score invocations within a single session (same bank + lens).
    """
    import random
    matching = [q for q in bank if q.get("lens") == lens]
    if len(matching) <= 5:
        return matching
    # Sort by question text for stable ordering before sampling
    matching.sort(key=lambda q: q.get("q", ""))
    rng = random.Random(f"{lens}:{len(matching)}")
    return rng.sample(matching, 5)


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


def _extract_symbol_body(file_content: str, symbol: str) -> str | None:
    """Extract the body of a function/class/constant from file content by symbol name.

    Handles 'ClassName.method', 'function_name', and 'CONSTANT_NAME'.
    Returns the relevant source region as a string, or None if not found.
    """
    lines = file_content.split("\n")

    # For dotted symbols like ClassName.method, search for 'def method' inside 'class ClassName'
    if "." in symbol:
        class_name, method_name = symbol.split(".", 1)
        class_pattern = re.compile(rf"^class\s+{re.escape(class_name)}\b")
        method_pattern = re.compile(rf"^\s+(?:async\s+)?def\s+{re.escape(method_name)}\b")
        in_class = False
        method_start = None
        for i, line in enumerate(lines):
            if class_pattern.match(line):
                in_class = True
            elif in_class and method_pattern.match(line):
                method_start = i
                break
            elif in_class and re.match(r"^class\s", line):
                in_class = False  # left the class
        if method_start is not None:
            return _extract_def_body(lines, method_start)
        return None

    # For UPPER_CASE names or _UPPER_CASE, treat as constants/attributes
    if re.match(r"^_?[A-Z][A-Z_0-9]+$", symbol):
        pattern = re.compile(rf"^\s*{re.escape(symbol)}\s*=")
        for i, line in enumerate(lines):
            if pattern.match(line):
                start = max(0, i - 2)
                end = min(len(lines), i + 6)
                return "\n".join(lines[start:end])

    # For function/class names (including async def)
    pattern = re.compile(rf"^(?:async\s+)?(?:def|class)\s+{re.escape(symbol)}\b")
    for i, line in enumerate(lines):
        if pattern.match(line):
            return _extract_def_body(lines, i)

    return None


def _extract_def_body(lines: list[str], start: int) -> str:
    """Extract a function/class body starting at the def/class line."""
    if start >= len(lines):
        return ""
    # Get indentation of the def line
    def_line = lines[start]
    def_indent = len(def_line) - len(def_line.lstrip())
    body_lines = [def_line]
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped:
            body_lines.append(line)
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= def_indent:
            break  # dedented past the function — done
        body_lines.append(line)
    return "\n".join(body_lines)


def verify_answer_freshness(
    question: dict, cwd: str
) -> bool:
    """Check if a quiz question's source symbol still contains the expected answer.

    Source format: 'file.py::symbol_name' (symbol-anchored, survives line shifts)
    or legacy 'file.py:line_no' (line-anchored, deprecated).

    Returns True if the answer is still valid (or if we can't verify).
    Returns False if the source has changed and the answer is stale.
    """
    source = question.get("source", "")
    if not source:
        return True

    # Symbol-anchored format: file.py::symbol
    if "::" in source:
        filepath_part, symbol = source.split("::", 1)
        filepath = os.path.join(cwd, filepath_part)
        if not os.path.isfile(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return True
        body = _extract_symbol_body(content, symbol)
        if body is None:
            return False  # symbol no longer exists
        return _check_answer_in_text(question, body)

    # Legacy line-anchored format: file.py:line_no
    if ":" not in source:
        return True

    parts = source.rsplit(":", 1)
    filepath = os.path.join(cwd, parts[0])
    if not os.path.isfile(filepath):
        return False

    try:
        line_no = int(parts[1])
    except ValueError:
        return True

    try:
        with open(filepath, encoding="utf-8") as f:
            file_lines = f.readlines()
    except OSError:
        return True

    start = max(0, (line_no - 1) - 3)
    end = min(len(file_lines), (line_no - 1) + 4)
    window = "".join(file_lines[start:end])
    return _check_answer_in_text(question, window)


def _check_answer_in_text(question: dict, text: str) -> bool:
    """Check if the correct answer's keywords appear in the given text."""
    answer_key = question.get("a", "")
    if not answer_key or len(answer_key) != 1:
        return False
    answer_idx = ord(answer_key) - ord("A")
    if answer_idx < 0 or answer_idx >= len(question.get("opts", [])):
        return True

    answer_text = question["opts"][answer_idx].lower()
    text_lower = text.lower()

    # Split on commas and common connectors so "tempfile + os.replace" becomes
    # ["tempfile", "os.replace"] rather than one unsplittable phrase.
    answer_parts = re.split(r"[,+/&]|\band\b|\bor\b|\bvia\b|\bthen\b", answer_text)
    answer_parts = [p.strip() for p in answer_parts if p.strip()]
    if not answer_parts:
        return False
    if all(len(p) < 3 for p in answer_parts):
        return all(part in text_lower for part in answer_parts)
    long_parts = [p for p in answer_parts if len(p) >= 3]
    return bool(long_parts) and any(part in text_lower for part in long_parts)


def score_answers(
    questions: list[dict],
    answers: list[str],
    cwd: str,
) -> tuple[int, int]:
    """Score answers against quiz bank with staleness check.

    Returns (correct, total) where total may be < len(questions) if
    stale questions were dropped.  Returns (-1, -1) on count mismatch
    (distinguishable from all-stale which returns (0, 0)).
    """
    correct = 0
    total = 0
    if len(questions) != len(answers):
        return -1, -1  # unevaluable: count mismatch
    for q, given in zip(questions, answers, strict=True):
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
    args: list[str],
) -> subprocess.CompletedProcess[str] | None:
    """Run a sahjhan command, returning None on any failure."""
    cmd = [binary, "--config-dir", config_dir]
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


def _get_run_number(cwd: str) -> str:
    """Get current run number from sahjhan active-ledger marker."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-ledger")
    try:
        with open(active_file, encoding="utf-8") as f:
            return f.read().strip().replace("run-", "") or "0"
    except OSError:
        return "0"


def _query_events(
    binary: str,
    config_dir: str,
    cwd: str,
    event_type: str,
    perspective: str,
) -> list[dict]:
    """Query sahjhan for events of a given type and perspective."""
    result = _run_sahjhan(
        binary, config_dir, cwd,
        ["query", "--type", event_type, "--field", f"perspective={perspective}", "--json"],
    )
    if result and result.returncode == 0:
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(result.stdout)
    return []


# ── Main hook logic ──


def main() -> None:
    event = read_event()
    message = event.get("last_assistant_message", "")

    # BH-008 run 28: mask fenced blocks before regex matching (PAT-001)
    # Prevents LENS: prefix inside code blocks from triggering the quiz gate
    masked_message = mask_fenced_blocks(message)

    # Non-lens subagents pass through
    lens = parse_lens_name(masked_message)
    if not lens:
        exit_stop_allow()
    assert lens is not None  # for mypy: exit_stop_allow calls sys.exit

    # Setup
    cwd = event.get("cwd", os.getcwd())
    binary = ensure_sahjhan()
    config_dir, _ = resolve_config_dir(cwd)

    # Graceful degradation: no binary → allow
    if binary is None:
        exit_stop_allow()

    run = _get_run_number(cwd)

    # Common fields for all events
    base_fields = {
        "project": os.path.basename(cwd),
        "run": run,
        "auditor": "holtz",
        "perspective": lens,
    }

    # ── Phase 1: Evidence check ──

    transcript_path = event.get("agent_transcript_path")
    transcript_available = bool(transcript_path and os.path.isfile(transcript_path))
    if transcript_available:
        events_list = parse_transcript_jsonl(transcript_path)
        # BH-016: check_transcript counts reads from session-JSONL format
        # (nested message.content blocks with tool_use entries). If the transcript
        # is in flat hook-event format (tool_name at top level), check_transcript
        # cannot parse it — degrade to min_reads=0 to avoid permanent blocking.
        # Session-JSONL format (no top-level tool_name) IS processable — keep it.
        has_flat_events = any("tool_name" in e for e in events_list)
        if has_flat_events:
            transcript_available = False
            events_list = [{"type": "assistant", "content": message}]
    else:
        # Degrade: synthesize minimal events from last_assistant_message.
        # In this mode we cannot verify file reads, so min_reads is set to 0
        # to avoid permanently blocking subagents whose transcript is unavailable.
        events_list = [{"type": "assistant", "content": message}]

    # Load quiz bank from daemon vault (secrets never on disk)
    # Graceful degradation: catch daemon-unavailable errors (OSError covers
    # socket failures; RuntimeError covers daemon-returned errors; KeyError
    # covers missing "data" field when vault is unpopulated).
    # Data corruption (binascii.Error, json.JSONDecodeError) is NOT caught —
    # corrupt vault data should crash the hook visibly, not silently disable
    # the quiz gate.
    bank: list[dict] = []
    with contextlib.suppress(OSError, RuntimeError, KeyError):
        import base64
        sock_path = _get_daemon_socket_path(cwd)
        resp = _daemon_request(sock_path, {"op": "vault_read", "name": "quiz-bank"})
        bank = json.loads(base64.b64decode(resp["data"]))

    questions = select_questions(bank, lens)
    keywords = []
    for q in questions:
        keywords.extend(q.get("keywords", []))
    keywords = list(set(keywords)) if keywords else [lens]

    # When transcript is unavailable, skip the read_count gate — we cannot
    # observe tool calls, so penalising for them inverts graceful degradation.
    min_reads = 5 if transcript_available else 0
    evidence = check_transcript(events_list, keywords=keywords, lens=lens, min_reads=min_reads)
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
        binary, config_dir, cwd, "quiz_posed", lens
    )

    if not posed_events:
        # Phase 2: Pose the quiz
        qhash = questions_hash(questions)
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            record_authed_event("quiz_posed", {
                **base_fields, "questions_hash": qhash
            }, cwd)
        quiz_text = format_quiz_questions(questions, lens)
        exit_stop_block(quiz_text)

    # Phase 3: Score answers (use masked_message for PAT-001 defense, BH-008)
    parsed = parse_answers(masked_message)
    if not parsed:
        exit_stop_block(
            f"Could not parse answers. Format: LENS: {lens} ANSWERS: A,B,C,D,A"
        )
    assert parsed is not None  # for mypy: exit_stop_block calls sys.exit
    # BH-009 run 28: verify lens name consistency between parsers
    parsed_lens, given_answers = parsed
    if parsed_lens != lens:
        exit_stop_block(
            f"Lens mismatch: header says '{lens}' but answer line says '{parsed_lens}'. "
            f"Use: LENS: {lens} ANSWERS: A,B,C,D,A"
        )
    correct, total = score_answers(questions, given_answers, cwd)

    # Answer count mismatch: score_answers returns (-1, -1)
    if correct == -1:
        exit_stop_block(
            f"Answer count mismatch: got {len(given_answers)} answers for "
            f"{len(questions)} questions. Provide exactly {len(questions)} answers."
        )

    # Check staleness — also handle total=0 (all questions stale)
    if total == 0 or total < len(questions) - MAX_STALE_QUESTIONS:
        exit_stop_block(
            f"Too many stale questions ({len(questions) - total}/{len(questions)}). "
            "Quiz bank must be regenerated."
        )

    threshold = PASS_THRESHOLD.get(total, max(1, total - 1))

    if correct >= threshold:
        # IDP-001: Guard against duplicate quiz_answered on hook retry
        already_answered = _query_events(
            binary, config_dir, cwd, "quiz_answered", lens
        )
        if not already_answered:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                record_authed_event("quiz_answered", {
                    **base_fields,
                    "score": f"{correct}/{total}",
                    "pass": "true",
                }, cwd)
        exit_stop_allow()

    # Failed — check attempt count
    failed_events = _query_events(
        binary, config_dir, cwd, "quiz_failed", lens
    )
    attempt = len(failed_events) + 1  # this is the current (failing) attempt

    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        record_authed_event("quiz_failed", {
            **base_fields, "score": f"{correct}/{total}"
        }, cwd)

    if attempt >= MAX_QUIZ_ATTEMPTS:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            record_authed_event("quiz_exhausted", {
                **base_fields
            }, cwd)
        exit_stop_allow()

    exit_stop_block(
        f"{correct}/{total}. Rejected. Read the code. "
        f"(attempt {attempt}/{MAX_QUIZ_ATTEMPTS})"
    )


if __name__ == "__main__":
    main()

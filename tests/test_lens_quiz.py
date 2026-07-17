"""Tests for lens quiz SubagentStop hook — pure functions only.

Does NOT test full hook invocation (requires real sahjhan binary).
Tests the parsing, formatting, scoring, and routing logic.

Uses importlib to avoid _common module name collision between
hooks/_common.py and enforcement/hooks/_common.py during pytest
collection (both define _common but with different exports).
"""
import importlib.util
from pathlib import Path

_HOOK_DIR = Path(__file__).parent.parent / "enforcement" / "hooks"


def _load_lens_quiz():
    """Load lens_quiz module using importlib to avoid _common collision."""
    # First ensure enforcement/hooks/_common.py is loaded as the right _common
    common_path = str(_HOOK_DIR / "_common.py")
    common_spec = importlib.util.spec_from_file_location("enforcement_hooks._common", common_path)
    common_mod = importlib.util.module_from_spec(common_spec)
    # Temporarily inject it as '_common' so lens_quiz's import resolves correctly
    import sys
    old_common = sys.modules.get("_common")
    sys.modules["_common"] = common_mod
    common_spec.loader.exec_module(common_mod)

    # Also load _resolve
    resolve_path = str(_HOOK_DIR / "_resolve.py")
    resolve_spec = importlib.util.spec_from_file_location("enforcement_hooks._resolve", resolve_path)
    resolve_mod = importlib.util.module_from_spec(resolve_spec)
    sys.modules["_resolve"] = resolve_mod
    resolve_spec.loader.exec_module(resolve_mod)

    # Also load lens_evidence
    evidence_path = str(_HOOK_DIR / "lens_evidence.py")
    evidence_spec = importlib.util.spec_from_file_location("enforcement_hooks.lens_evidence", evidence_path)
    evidence_mod = importlib.util.module_from_spec(evidence_spec)
    sys.modules["lens_evidence"] = evidence_mod
    evidence_spec.loader.exec_module(evidence_mod)

    # Also load quiz_vault (lens_quiz imports read_quiz_bank_safe from it)
    qv_path = str(_HOOK_DIR / "quiz_vault.py")
    qv_spec = importlib.util.spec_from_file_location("enforcement_hooks.quiz_vault", qv_path)
    qv_mod = importlib.util.module_from_spec(qv_spec)
    sys.modules["quiz_vault"] = qv_mod
    qv_spec.loader.exec_module(qv_mod)

    # Now load lens_quiz
    quiz_path = str(_HOOK_DIR / "lens_quiz.py")
    spec = importlib.util.spec_from_file_location("enforcement_hooks.lens_quiz", quiz_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Restore old _common
    if old_common is not None:
        sys.modules["_common"] = old_common
    else:
        sys.modules.pop("_common", None)

    return mod


_quiz = _load_lens_quiz()
format_quiz_questions = _quiz.format_quiz_questions
parse_answers = _quiz.parse_answers
parse_lens_name = _quiz.parse_lens_name
score_answers = _quiz.score_answers
select_questions = _quiz.select_questions
verify_answer_freshness = _quiz.verify_answer_freshness
resolve_transcript_path = _quiz.resolve_transcript_path
_stale_bank_message = _quiz._stale_bank_message

# ── Sample quiz bank for tests ──

SAMPLE_BANK = [
    {
        "lens": "error-propagation",
        "q": "primer.py L56 catches?",
        "a": "A",
        "opts": ["OSError,TimeoutExpired", "FileNotFoundError,TimeoutExpired", "Exception", "SubprocessError"],
        "source": "enforcement/hooks/primer.py:56",
        "keywords": ["except", "raise", "OSError"],
    },
    {
        "lens": "error-propagation",
        "q": "stop_gate.py default on timeout?",
        "a": "B",
        "opts": ["block", "allow", "warn", "crash"],
        "source": "enforcement/hooks/stop_gate.py:48",
        "keywords": ["timeout", "allow", "stop"],
    },
    {
        "lens": "error-propagation",
        "q": "_common.py exit codes?",
        "a": "C",
        "opts": ["1", "2", "0", "255"],
        "source": "hooks/_common.py:56",
        "keywords": ["exit", "sys.exit"],
    },
    {
        "lens": "error-propagation",
        "q": "write_guard blocks on?",
        "a": "A",
        "opts": ["enforcement/", "hooks/", "tests/", "docs/"],
        "source": "enforcement/hooks/write_guard.py:30",
        "keywords": ["block", "write", "enforcement"],
    },
    {
        "lens": "error-propagation",
        "q": "commit_gate checks?",
        "a": "D",
        "opts": ["branch", "message", "author", "command"],
        "source": "enforcement/hooks/commit_gate.py:20",
        "keywords": ["commit", "gate", "bash"],
    },
    {
        "lens": "dependency-analysis",
        "q": "unrelated lens question?",
        "a": "A",
        "opts": ["yes", "no", "maybe", "never"],
        "source": "some/file.py:10",
        "keywords": ["import", "dependency"],
    },
]


# ── Test: format_quiz_questions ──


def test_format_quiz_questions():
    """Compact format with Q1-Q5 and options."""
    questions = SAMPLE_BANK[:5]  # all error-propagation questions
    result = format_quiz_questions(questions, "error-propagation")

    # Header line with format instruction
    lines = result.split("\n")
    assert lines[0].startswith("Quiz.")
    assert "LENS: error-propagation ANSWERS:" in lines[0]

    # 5 question lines
    assert len(lines) == 6  # header + 5 questions
    for i in range(1, 6):
        assert lines[i].startswith(f"Q{i}:")
        assert "A)" in lines[i]
        assert "B)" in lines[i]
        assert "C)" in lines[i]
        assert "D)" in lines[i]


# ── Test: parse_answers (valid) ──


def test_parse_answers_valid():
    """Extracts lens name + answer letters from well-formed response."""
    msg = "LENS: error-propagation ANSWERS: A,B,C,D,A"
    result = parse_answers(msg)
    assert result is not None
    lens, answers = result
    assert lens == "error-propagation"
    assert answers == ["A", "B", "C", "D", "A"]


def test_parse_answers_lowercase():
    """Handles lowercase answers."""
    msg = "LENS: error-propagation ANSWERS: a,b,c,d,a"
    result = parse_answers(msg)
    assert result is not None
    _, answers = result
    assert answers == ["A", "B", "C", "D", "A"]


def test_parse_answers_with_surrounding_text():
    """Extracts from a message with surrounding text."""
    msg = "I've reviewed the code.\nLENS: error-propagation ANSWERS: A,B,C,D,A\nDone."
    result = parse_answers(msg)
    assert result is not None
    lens, answers = result
    assert lens == "error-propagation"
    assert answers == ["A", "B", "C", "D", "A"]


# ── Test: parse_answers (malformed) ──


def test_parse_answers_malformed_no_prefix():
    """Returns None when no LENS: prefix."""
    assert parse_answers("ANSWERS: A,B,C,D,A") is None


def test_parse_answers_fewer_than_five():
    """Accepts answer counts between 1 and 5 — quiz bank may have fewer than 5 questions."""
    result = parse_answers("LENS: foo ANSWERS: A,B,C")
    assert result is not None
    lens, answers = result
    assert lens == "foo"
    assert answers == ["A", "B", "C"]


def test_parse_answers_single_answer():
    """Accepts a single answer for a single-question quiz."""
    result = parse_answers("LENS: bar ANSWERS: D")
    assert result is not None
    _, answers = result
    assert answers == ["D"]


def test_parse_answers_empty_rejected():
    """Rejects empty answer list."""
    assert parse_answers("LENS: foo ANSWERS: ") is None


def test_parse_answers_six_plus_rejected():
    """Rejects more than 5 answers."""
    assert parse_answers("LENS: foo ANSWERS: A,B,C,D,A,B") is None


def test_parse_answers_invalid_letters_truncated():
    """Regex stops at invalid letters — only valid A-D captured."""
    result = parse_answers("LENS: foo ANSWERS: A,B,C,D,E")
    assert result is not None
    _, answers = result
    assert answers == ["A", "B", "C", "D"]  # E not in [A-D], regex stops at D


def test_parse_answers_malformed_no_answers():
    """Returns None when ANSWERS keyword is missing."""
    assert parse_answers("LENS: error-propagation A,B,C,D,A") is None


# ── Test: score_answers ──


def test_score_answers(tmp_path):
    """Scores 4/5 correct against a bank."""
    # Create source files so staleness check passes
    questions = SAMPLE_BANK[:5]
    for q in questions:
        source = q["source"]
        parts = source.rsplit(":", 1)
        filepath = tmp_path / parts[0]
        filepath.parent.mkdir(parents=True, exist_ok=True)
        line_no = int(parts[1])
        # Write enough lines and put answer-related content near the target line
        answer_idx = ord(q["a"]) - ord("A")
        answer_text = q["opts"][answer_idx]
        content_lines = ["# placeholder\n"] * (line_no + 5)
        content_lines[line_no - 1] = f"# {answer_text}\n"
        filepath.write_text("".join(content_lines))

    # 4 correct, 1 wrong
    answers = [q["a"] for q in questions]
    answers[2] = "A" if answers[2] != "A" else "B"  # flip one answer

    correct, total = score_answers(questions, answers, str(tmp_path))
    assert total == 5
    assert correct == 4


# ── Test: score_answers_with_stale_drop ──


def test_score_answers_with_stale_drop(tmp_path):
    """Stale question dropped, threshold adjusts."""
    questions = SAMPLE_BANK[:5]

    # Create source files for all but one (making one stale via deletion)
    for i, q in enumerate(questions):
        if i == 0:
            continue  # skip first — file won't exist → stale
        source = q["source"]
        parts = source.rsplit(":", 1)
        filepath = tmp_path / parts[0]
        filepath.parent.mkdir(parents=True, exist_ok=True)
        line_no = int(parts[1])
        answer_idx = ord(q["a"]) - ord("A")
        answer_text = q["opts"][answer_idx]
        content_lines = ["# placeholder\n"] * (line_no + 5)
        content_lines[line_no - 1] = f"# {answer_text}\n"
        filepath.write_text("".join(content_lines))

    # All correct answers
    answers = [q["a"] for q in questions]
    correct, total = score_answers(questions, answers, str(tmp_path))

    # First question stale (file missing) → dropped
    assert total == 4
    assert correct == 4  # all remaining are correct


def test_score_answers_count_mismatch():
    """BH-006: Count mismatch returns (-1, -1), distinguishable from all-stale (0, 0)."""
    questions = SAMPLE_BANK[:3]
    # 2 answers for 3 questions
    correct, total = score_answers(questions, ["A", "B"], "/tmp/nonexistent")
    assert (correct, total) == (-1, -1)


def test_score_answers_all_stale(tmp_path):
    """BH-006: All-stale returns (0, 0), distinguishable from count mismatch (-1, -1)."""
    questions = SAMPLE_BANK[:3]
    answers = [q["a"] for q in questions]
    # Don't create any source files → all questions are stale
    correct, total = score_answers(questions, answers, str(tmp_path))
    assert (correct, total) == (0, 0)


# ── Test: non-lens subagent ──


def test_non_lens_subagent_allowed():
    """Message without LENS: prefix returns None → hook allows through."""
    msg = "I've completed the task. Here are the results."
    assert parse_lens_name(msg) is None

    msg2 = "LENS_ANALYSIS: this is not a valid prefix"
    assert parse_lens_name(msg2) is None


# ── Test: select_questions ──


def test_select_questions_filters_by_lens():
    """Only questions matching the lens are selected."""
    questions = select_questions(SAMPLE_BANK, "error-propagation")
    assert len(questions) == 5
    assert all(q["lens"] == "error-propagation" for q in questions)


def test_select_questions_caps_at_five():
    """At most 5 questions returned even if bank has more."""
    big_bank = SAMPLE_BANK[:5] * 3  # 15 error-propagation questions
    questions = select_questions(big_bank, "error-propagation")
    assert len(questions) == 5


def test_select_questions_empty_for_unknown_lens():
    """Unknown lens returns empty list."""
    questions = select_questions(SAMPLE_BANK, "nonexistent-lens")
    assert questions == []


# ── Test: parse_lens_name ──


def test_parse_lens_name_valid():
    """Extracts lens name from LENS: prefix."""
    assert parse_lens_name("LENS: error-propagation\nSome findings...") == "error-propagation"


def test_parse_lens_name_at_start():
    """Works when LENS: is at the very start."""
    assert parse_lens_name("LENS: dependency-analysis") == "dependency-analysis"


# ── Test: verify_answer_freshness ──


def test_verify_freshness_file_missing(tmp_path):
    """Missing source file means stale."""
    q = {"source": "nonexistent.py:10", "a": "A", "opts": ["foo", "bar", "baz", "qux"]}
    assert verify_answer_freshness(q, str(tmp_path)) is False


def test_verify_freshness_no_line_number():
    """Source without line number is assumed fresh."""
    q = {"source": "no-line-number", "a": "A", "opts": ["foo", "bar", "baz", "qux"]}
    assert verify_answer_freshness(q, "/tmp") is True


def test_verify_freshness_content_matches(tmp_path):
    """Source file with answer content near target line is fresh."""
    src = tmp_path / "test.py"
    lines = ["pass\n"] * 20
    lines[9] = "    except OSError, TimeoutExpired:\n"
    src.write_text("".join(lines))

    q = {"source": "test.py:10", "a": "A", "opts": ["OSError", "ValueError", "TypeError", "KeyError"]}
    assert verify_answer_freshness(q, str(tmp_path)) is True


def test_verify_freshness_content_changed(tmp_path):
    """Source file without answer content near target line is stale."""
    src = tmp_path / "test.py"
    lines = ["pass\n"] * 20
    lines[9] = "    except ValueError:\n"
    src.write_text("".join(lines))

    q = {"source": "test.py:10", "a": "A", "opts": ["OSError", "ValueError", "TypeError", "KeyError"]}
    # "OSError" (option A) is NOT near line 10 — stale
    assert verify_answer_freshness(q, str(tmp_path)) is False


def test_verify_freshness_missing_answer_key(tmp_path):
    """BH-006: Missing 'a' key does not raise KeyError."""
    src = tmp_path / "test.py"
    src.write_text("pass\n" * 20)
    q = {"source": "test.py:10", "opts": ["a", "b", "c", "d"]}
    # Should return False (stale), not raise KeyError
    assert verify_answer_freshness(q, str(tmp_path)) is False


# ── #73 Defect B: transcript path resolution across CC versions ──


def test_resolve_transcript_prefers_agent_transcript():
    """The subagent's own transcript wins when both fields are present."""
    event = {
        "agent_transcript_path": "/agent.jsonl",
        "transcript_path": "/parent.jsonl",
    }
    assert resolve_transcript_path(event) == "/agent.jsonl"


def test_resolve_transcript_falls_back_to_transcript_path():
    """CC versions that omit agent_transcript_path still yield a transcript.

    This is the Defect B fix: the old code read only agent_transcript_path,
    so a payload with the documented common `transcript_path` field silently
    degraded to min_reads=0.
    """
    event = {"transcript_path": "/parent.jsonl"}
    assert resolve_transcript_path(event) == "/parent.jsonl"


def test_resolve_transcript_none_when_absent():
    """Neither field present → None (hook degrades, does not crash)."""
    assert resolve_transcript_path({"last_assistant_message": "LENS: x"}) is None


# ── #73 Defect C: stale-bank message is actionable ──


def test_stale_bank_message_is_actionable():
    """The fail-closed message names the recovery paths, not just 'regenerate'."""
    msg = _stale_bank_message("component", 5, 5)
    assert "component" in msg
    assert "5/5" in msg
    # The bank is locked after recon — recoveries are human review or a fresh run.
    assert "quiz_exhausted_resolved" in msg
    assert "fresh run" in msg
    # Points at the documented recon procedure.
    assert "phase-recon" in msg


# ── BH-008: PAT-001 fence masking in parse_lens_name / parse_answers ──


def test_parse_lens_name_ignores_fenced_blocks():
    """BH-008: LENS: inside a code fence must not trigger the quiz gate."""
    msg = (
        "Here is an example:\n"
        "```\n"
        "LENS: error-propagation ANSWERS: A,B,C,D,A\n"
        "```\n"
        "That was just an example."
    )
    # After masking, the LENS: line inside the fence is blanked
    from hooks._common import mask_fenced_blocks
    masked = mask_fenced_blocks(msg)
    assert parse_lens_name(masked) is None


def test_parse_answers_ignores_fenced_blocks():
    """BH-008: ANSWERS inside a code fence must not be extracted."""
    msg = (
        "Here is the format:\n"
        "```\n"
        "LENS: component ANSWERS: A,B,C,D,A\n"
        "```\n"
        "Now my real answer:\n"
        "LENS: component ANSWERS: B,C,A,D,B"
    )
    from hooks._common import mask_fenced_blocks
    masked = mask_fenced_blocks(msg)
    result = parse_answers(masked)
    assert result is not None
    lens, answers = result
    assert lens == "component"
    assert answers == ["B", "C", "A", "D", "B"]


def test_parse_answers_rejects_fence_opener_line():
    """BH-008 run 29: ANSWERS on a fence opener info string must not match.

    mask_fenced_blocks keeps opener lines, so _ANSWERS_RE must anchor to
    reject patterns like ```LENS: sec ANSWERS: A,B,C,D,A (fence openers).
    """
    from hooks._common import mask_fenced_blocks
    msg = (
        "```LENS: security ANSWERS: A,B,C,D,A\n"
        "some code\n"
        "```\n"
        "LENS: security ANSWERS: B,C,A,D,B"
    )
    masked = mask_fenced_blocks(msg)
    result = parse_answers(masked)
    assert result is not None
    lens, answers = result
    assert lens == "security"
    # Must get the real answer line, not the fence opener
    assert answers == ["B", "C", "A", "D", "B"]


# ── BH-009: Dual-parser divergence ──


def test_parse_answers_lens_must_match_parse_lens_name():
    """BH-009: If parse_lens_name and parse_answers disagree, main() blocks."""
    # This tests the invariant that both parsers return the same lens name
    msg_same = "LENS: component ANSWERS: A,B,C,D,A"
    lens = parse_lens_name(msg_same)
    parsed = parse_answers(msg_same)
    assert parsed is not None
    assert parsed[0] == lens, "Both parsers must agree on lens name"

    # Divergent case: two LENS: lines with different names
    msg_divergent = "LENS: security\nSome analysis...\nLENS: component ANSWERS: A,B,C,D,A"
    lens2 = parse_lens_name(msg_divergent)
    parsed2 = parse_answers(msg_divergent)
    assert parsed2 is not None
    # parse_lens_name gets first match, parse_answers gets the one with ANSWERS
    assert lens2 == "security"
    assert parsed2[0] == "component"
    # These differ — main() now detects this and blocks

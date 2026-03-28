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

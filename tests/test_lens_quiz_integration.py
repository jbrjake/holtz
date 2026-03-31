"""Integration tests for the lens quiz enforcement flow.

Tests the full pipeline: quiz bank → evidence check → quiz formatting → scoring.
Does NOT require sahjhan binary — tests pure Python logic only.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "scripts"))
# Use importlib for enforcement/hooks to avoid _common collision
import importlib.util

_HOOK_DIR = REPO_ROOT / "enforcement" / "hooks"


def _load_module(name, path):
    """Load a module from enforcement/hooks/ avoiding _common collision."""
    spec = importlib.util.spec_from_file_location(f"enforcement_hooks.{name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    # Ensure enforcement _common is loaded first
    import sys as _sys
    if "_common" not in _sys.modules or not hasattr(_sys.modules["_common"], "_active_ledger"):
        common_spec = importlib.util.spec_from_file_location("enforcement_hooks._common", str(_HOOK_DIR / "_common.py"))
        common_mod = importlib.util.module_from_spec(common_spec)
        _sys.modules["_common"] = common_mod
        common_spec.loader.exec_module(common_mod)
        resolve_spec = importlib.util.spec_from_file_location("enforcement_hooks._resolve", str(_HOOK_DIR / "_resolve.py"))
        resolve_mod = importlib.util.module_from_spec(resolve_spec)
        _sys.modules["_resolve"] = resolve_mod
        resolve_spec.loader.exec_module(resolve_mod)
    # Ensure lens_evidence is loaded so lens_quiz can import it
    if "lens_evidence" not in _sys.modules:
        evidence_spec = importlib.util.spec_from_file_location(
            "enforcement_hooks.lens_evidence", str(_HOOK_DIR / "lens_evidence.py")
        )
        evidence_mod = importlib.util.module_from_spec(evidence_spec)
        _sys.modules["lens_evidence"] = evidence_mod
        evidence_spec.loader.exec_module(evidence_mod)
    spec.loader.exec_module(mod)
    return mod


def test_full_quiz_flow_pass(tmp_path):
    """Full flow: valid quiz bank → sufficient evidence → quiz → correct answers → pass."""
    from generate_quiz_bank import validate_quiz_bank
    evidence_mod = _load_module("lens_evidence", _HOOK_DIR / "lens_evidence.py")
    quiz_mod = _load_module("lens_quiz", _HOOK_DIR / "lens_quiz.py")

    # Step 1: Create and validate quiz bank.
    # Sources omit line numbers so verify_answer_freshness returns True unconditionally
    # (no ":" in source → fresh by convention). This keeps the test focused on the
    # integration flow rather than file-content staleness.
    bank = [
        {"lens": "error-propagation", "q": "primer.py L56 catches?", "a": "A",
         "opts": ["OSError,TimeoutExpired", "FileNotFoundError", "Exception", "SubprocessError"],
         "source": "enforcement/hooks/primer.py", "keywords": ["except", "raise", "OSError"]},
        {"lens": "error-propagation", "q": "bash_guard catches?", "a": "B",
         "opts": ["Exception", "OSError,TimeoutExpired", "FileNotFoundError", "RuntimeError"],
         "source": "enforcement/hooks/bash_guard.py", "keywords": ["except", "OSError", "bash"]},
        {"lens": "error-propagation", "q": "stop_gate exits via?", "a": "C",
         "opts": ["exit_ok", "exit_warn", "exit_stop_block", "exit_block"],
         "source": "enforcement/hooks/stop_gate.py", "keywords": ["exit", "stop", "block"]},
        {"lens": "error-propagation", "q": "write_guard blocks?", "a": "A",
         "opts": ["MANAGED_FILES", "all docs/", "enforcement/", "*.md"],
         "source": "enforcement/hooks/write_guard.py", "keywords": ["MANAGED", "block", "write"]},
        {"lens": "error-propagation", "q": "primer injects via?", "a": "D",
         "opts": ["exit_ok", "exit_block", "exit_stop_block", "exit_warn"],
         "source": "enforcement/hooks/primer.py", "keywords": ["exit", "warn", "context"]},
    ]
    # validate_quiz_bank requires line numbers in source — use a separate valid bank for
    # validation only (with line numbers), then use the no-line-number bank for scoring.
    bank_for_validation = [
        {**q, "source": q["source"] + ":1"} for q in bank
    ]
    errors = validate_quiz_bank(bank_for_validation)
    assert errors == [], f"Quiz bank validation failed: {errors}"

    # Step 2: Check evidence (simulated transcript in JSONL format)
    transcript = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": f"src/mod{i}.py"}}
        ]}}
        for i in range(6)
    ] + [
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "The except clause in primer.py catches OSError and TimeoutExpired at line 56"}
        ]}}
    ]
    evidence = evidence_mod.check_transcript(transcript, keywords=["except", "OSError"], lens="error-propagation")
    assert evidence["pass"], f"Evidence check failed: {evidence['reason']}"

    # Step 3: Select and format questions
    selected = quiz_mod.select_questions(bank, "error-propagation")
    assert len(selected) == 5
    quiz_text = quiz_mod.format_quiz_questions(selected, "error-propagation")
    assert "Q1:" in quiz_text
    assert "Q5:" in quiz_text
    assert "LENS: error-propagation ANSWERS:" in quiz_text

    # Step 4: Parse correct answers
    answer_msg = "LENS: error-propagation ANSWERS: A,B,C,A,D"
    lens_name, answers = quiz_mod.parse_answers(answer_msg)
    assert lens_name == "error-propagation"
    assert answers == ["A", "B", "C", "A", "D"]

    # Step 5: Score — all 5 correct (answers match bank exactly).
    # cwd doesn't matter since sources have no line numbers → always fresh.
    correct, total = quiz_mod.score_answers(selected, answers, str(tmp_path))
    assert total == 5
    assert correct == 5


def test_full_quiz_flow_fail(tmp_path):
    """Full flow: wrong answers → fail score."""
    quiz_mod = _load_module("lens_quiz", _HOOK_DIR / "lens_quiz.py")

    # Sources without line numbers → verify_answer_freshness returns True unconditionally,
    # so all 5 questions stay active and total=5.
    bank = [
        {"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b", "c", "d"],
         "source": "f1.py", "keywords": ["test", "x", "y"]},
        {"lens": "component", "q": "test2?", "a": "B", "opts": ["a", "b", "c", "d"],
         "source": "f2.py", "keywords": ["test", "x", "y"]},
        {"lens": "component", "q": "test3?", "a": "C", "opts": ["a", "b", "c", "d"],
         "source": "f3.py", "keywords": ["test", "x", "y"]},
        {"lens": "component", "q": "test4?", "a": "D", "opts": ["a", "b", "c", "d"],
         "source": "f4.py", "keywords": ["test", "x", "y"]},
        {"lens": "component", "q": "test5?", "a": "A", "opts": ["a", "b", "c", "d"],
         "source": "f5.py", "keywords": ["test", "x", "y"]},
    ]
    # All wrong answers
    wrong = ["B", "A", "A", "A", "B"]
    correct, total = quiz_mod.score_answers(bank, wrong, str(tmp_path))
    assert total == 5
    assert correct == 0


def test_evidence_rejects_zero_reads():
    """Evidence check rejects a transcript with 0 source file reads (read-count gate)."""
    evidence_mod = _load_module("lens_evidence", _HOOK_DIR / "lens_evidence.py")
    transcript = [
        {"type": "assistant", "content": "Everything looks fine. No issues found."},
    ]
    evidence = evidence_mod.check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert not evidence["pass"]
    assert "0 files read" in evidence["reason"]


def test_evidence_rejects_no_keywords():
    """BH-011: Evidence check rejects transcript with reads but no lens keywords."""
    evidence_mod = _load_module("lens_evidence", _HOOK_DIR / "lens_evidence.py")
    # 5 reads but no keyword hits — this is the actual rubber-stamp case
    transcript = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": f"src/file_{i}.py"}},
            {"type": "text", "text": "Looks good to me."},
        ]}} for i in range(5)
    ]
    evidence = evidence_mod.check_transcript(transcript, keywords=["except", "raise", "catch"], lens="error-propagation")
    assert not evidence["pass"]
    assert "keyword" in evidence["reason"].lower()


def test_quiz_bank_validation_catches_bad_entries():
    """Quiz bank validator rejects entries with wrong format."""
    from generate_quiz_bank import validate_quiz_bank
    bad_bank = [
        {"lens": "component", "q": "test?", "a": "E", "opts": ["a", "b"],
         "source": "f.py", "keywords": ["x"]},
    ]
    errors = validate_quiz_bank(bad_bank)
    # Expects: wrong opts count, bad answer, missing line number, too few keywords
    assert len(errors) >= 3


def test_artifact_check_integration(tmp_path):
    """Artifact check verifies lens output file exists and has content."""
    evidence_mod = _load_module("lens_evidence", _HOOK_DIR / "lens_evidence.py")

    # No artifact
    result = evidence_mod.check_artifact(str(tmp_path / "lens-missing.md"))
    assert not result["pass"]

    # Good artifact
    artifact = tmp_path / "lens-error-propagation.md"
    artifact.write_text("## error-propagation\n\n- primer.py:56 catches OSError,TimeoutExpired\n- bash_guard.py:56 catches OSError,TimeoutExpired\n")
    result = evidence_mod.check_artifact(str(artifact))
    assert result["pass"]


def test_record_authed_event_missing_session_key(tmp_path):
    """record_authed_event raises FileNotFoundError when session.key is absent.

    BH-007: lens_quiz.py must wrap these calls with suppress(OSError) so a
    missing session key degrades gracefully instead of crashing the hook.
    """
    common_mod = _load_module("_common", _HOOK_DIR / "_common.py")
    import pytest
    # No session.key → compute_event_proof should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        common_mod.compute_event_proof(
            "quiz_posed",
            {"project": "holtz", "run": "1"},
            key_path=str(tmp_path / "nonexistent" / "session.key"),
        )


def test_score_answers_count_mismatch():
    """BH-006: Answer count mismatch returns (-1, -1), distinguishable from all-stale."""
    quiz_mod = _load_module("lens_quiz", _HOOK_DIR / "lens_quiz.py")
    bank = [
        {"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b", "c", "d"],
         "source": "f1.py", "keywords": ["test", "x", "y"]},
        {"lens": "component", "q": "test2?", "a": "B", "opts": ["a", "b", "c", "d"],
         "source": "f2.py", "keywords": ["test", "x", "y"]},
    ]
    # 3 answers for 2 questions
    correct, total = quiz_mod.score_answers(bank, ["A", "B", "C"], "/tmp")
    assert (correct, total) == (-1, -1)

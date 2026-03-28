"""Tests for quiz bank validation."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "scripts"))


def test_quiz_bank_schema():
    """Quiz bank entries have required fields."""
    from generate_quiz_bank import validate_quiz_bank
    entry = [{"lens": "error-propagation", "q": "primer.py L56 catches?", "a": "A",
              "opts": ["OSError,TimeoutExpired", "FileNotFoundError", "Exception", "SubprocessError"],
              "source": "enforcement/hooks/primer.py:56",
              "keywords": ["except", "raise", "OSError"]}]
    assert validate_quiz_bank(entry) == []


def test_rejects_wrong_option_count():
    """Rejects entries with != 4 options."""
    from generate_quiz_bank import validate_quiz_bank
    bad = [{"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b"],
            "source": "f.py:1", "keywords": ["x", "y", "z"]}]
    assert len(validate_quiz_bank(bad)) > 0


def test_rejects_bad_answer():
    """Rejects entries with answer not in A-D."""
    from generate_quiz_bank import validate_quiz_bank
    bad = [{"lens": "component", "q": "test?", "a": "E", "opts": ["a", "b", "c", "d"],
            "source": "f.py:1", "keywords": ["x", "y", "z"]}]
    assert len(validate_quiz_bank(bad)) > 0


def test_rejects_missing_source_line():
    """Rejects entries without line number in source."""
    from generate_quiz_bank import validate_quiz_bank
    bad = [{"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b", "c", "d"],
            "source": "f.py", "keywords": ["x", "y", "z"]}]
    assert len(validate_quiz_bank(bad)) > 0


def test_rejects_too_few_keywords():
    """Rejects entries with <3 keywords."""
    from generate_quiz_bank import validate_quiz_bank
    bad = [{"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b", "c", "d"],
            "source": "f.py:1", "keywords": ["x"]}]
    assert len(validate_quiz_bank(bad)) > 0


def test_rejects_missing_fields():
    """Rejects entries with missing required fields."""
    from generate_quiz_bank import validate_quiz_bank
    bad = [{"lens": "component", "q": "test?"}]
    assert len(validate_quiz_bank(bad)) > 0


def test_live_quiz_bank_valid():
    """BH-017: Live quiz bank file passes all validation rules."""
    import json

    from generate_quiz_bank import validate_quiz_bank

    quiz_bank_path = REPO_ROOT / "enforcement" / "quiz-bank.json"
    if not quiz_bank_path.exists():
        import pytest
        pytest.skip("No live quiz-bank.json present")
    with open(quiz_bank_path, encoding="utf-8") as f:
        bank = json.load(f)
    errors = validate_quiz_bank(bank)
    assert errors == [], f"Live quiz bank has validation errors: {errors}"

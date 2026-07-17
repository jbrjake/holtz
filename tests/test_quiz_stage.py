"""Unit tests for quiz_stage.py — the recon quiz-staging CLI (#73).

Exercises the validation core (build_question) and the marker output the
courier (quiz_capture.py) keys on. Pure logic — no daemon.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parent.parent / "skills" / "holtz" / "scripts" / "quiz_stage.py"


def _load():
    spec = importlib.util.spec_from_file_location("quiz_stage", str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_qs = _load()
build_question = _qs.build_question


def _ns(**kw) -> argparse.Namespace:
    base = {
        "lens": "component",
        "question": "What does save() use?",
        "answer": "B",
        "option": ["shutil", "tempfile + os.replace", "open w", "json.dump"],
        "source": "src/thing.py::save",
        "keyword": ["save", "atomic", "thing"],
        "finalize": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


def test_build_question_valid():
    q = build_question(_ns())
    assert q["lens"] == "component"
    assert q["a"] == "B"
    assert len(q["opts"]) == 4
    assert q["source"] == "src/thing.py::save"
    assert len(q["keywords"]) == 3


def test_answer_lowercased_and_validated():
    q = build_question(_ns(answer="d"))
    assert q["a"] == "D"


@pytest.mark.parametrize(
    "kw, msg",
    [
        ({"lens": ""}, "--lens"),
        ({"question": "  "}, "--question"),
        ({"answer": "E"}, "A-D"),
        ({"option": ["a", "b", "c"]}, "4 non-empty"),
        ({"option": ["a", "b", "c", ""]}, "4 non-empty"),
        ({"source": "no-anchor"}, "anchor"),
        ({"keyword": ["only", "two"]}, "3 --keyword"),
        ({"answer": "D", "option": ["a", "b", "c", "d"]}, None),  # D within 4 opts → ok
    ],
)
def test_build_question_validation(kw, msg):
    ns = _ns(**kw)
    if msg is None:
        build_question(ns)  # should not raise
        return
    with pytest.raises(ValueError) as exc:
        build_question(ns)
    assert msg in str(exc.value)


def _run_cli(*args) -> str:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, timeout=10,
    ).stdout


def test_cli_emits_question_marker():
    out = _run_cli(
        "--lens", "security", "--question", "What is validated?", "--answer", "A",
        "--option", "path", "--option", "b", "--option", "c", "--option", "d",
        "--source", "src/x.py::validate",
        "--keyword", "validate", "--keyword", "path", "--keyword", "security",
    )
    assert out.startswith("QUIZ-QUESTION:")
    payload = json.loads(out[len("QUIZ-QUESTION:"):].strip())
    assert payload["lens"] == "security"
    assert payload["a"] == "A"


def test_cli_finalize_marker():
    out = _run_cli("--finalize")
    assert out.strip() == "QUIZ-BANK-FINALIZE:"

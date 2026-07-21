"""E2e tests for quiz_capture.py — the PostToolUse quiz-staging courier (#73).

Runs the hook as a subprocess (the interface Claude Code actually uses),
feeding it realistic PostToolUse events and asserting it appends staged
questions to the daemon vault. Uses the mock daemon (which implements vault
ops); daemon-side state gating is covered by sahjhan's vault_policy tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_HOOK = REPO_ROOT / "enforcement" / "hooks" / "quiz_capture.py"


def _run(event: dict, cwd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=15,
        cwd=cwd,
        env=env,
    )
    return result.returncode, result.stdout + result.stderr


def _target_source(cwd: Path) -> None:
    """Write a target source file whose save() body carries the answer keywords."""
    src = cwd / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "thing.py").write_text(
        "import tempfile, os\n\n\n"
        "def save(self, path):\n"
        "    fd = tempfile.mkstemp()\n"
        "    os.replace(tmp, path)\n",
        encoding="utf-8",
    )


_QUESTION = {
    "lens": "component",
    "q": "How does save() write atomically?",
    "a": "B",
    "opts": ["shutil.copy2", "tempfile + os.replace", "open() mode w", "json.dump direct"],
    "source": "src/thing.py::save",
    "keywords": ["save", "atomic", "thing"],
}


def _bash_event(output: str, cwd: str) -> dict:
    """Build a realistic Claude Code 2.x Bash PostToolUse event.

    CC 2.x delivers Bash stdout under ``tool_response.stdout`` — there is no
    ``output`` key and no ``exit_code`` (verified live on 2.1.x). Tests use the
    real shape so a regression to reading ``.output`` (the #75 bug) fails here
    instead of passing against a synthetic payload the runtime never sends.
    """
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "python3 quiz_stage.py ..."},
        "tool_response": {
            "stdout": output,
            "stderr": "",
            "interrupted": False,
            "isImage": False,
            "noOutputExpected": False,
        },
        "cwd": cwd,
    }


def test_captures_question_into_vault(tmp_path, mock_daemon):
    _target_source(tmp_path)
    marker = "QUIZ-QUESTION: " + json.dumps(_QUESTION, separators=(",", ":"))
    code, _ = _run(_bash_event(marker, str(tmp_path)), str(tmp_path))
    assert code == 0
    assert "quiz-bank" in mock_daemon.vault
    stored = json.loads(mock_daemon.vault["quiz-bank"])
    assert stored == [_QUESTION]


def test_captures_from_legacy_output_field(tmp_path, mock_daemon):
    """Pre-2.x Claude Code delivered stdout under ``tool_response.output``.

    The shape-tolerant read must still capture from that legacy field so the
    courier keeps working across Claude Code versions (#75 fallback path).
    """
    _target_source(tmp_path)
    marker = "QUIZ-QUESTION: " + json.dumps(_QUESTION, separators=(",", ":"))
    legacy_event = {
        "tool_name": "Bash",
        "tool_input": {"command": "python3 quiz_stage.py ..."},
        "tool_response": {"exit_code": 0, "output": marker},
        "cwd": str(tmp_path),
    }
    code, _ = _run(legacy_event, str(tmp_path))
    assert code == 0
    stored = json.loads(mock_daemon.vault["quiz-bank"])
    assert stored == [_QUESTION]


def test_multiple_questions_accumulate(tmp_path, mock_daemon):
    _target_source(tmp_path)
    q2 = {**_QUESTION, "lens": "security", "q": "second?"}
    for q in (_QUESTION, q2):
        marker = "QUIZ-QUESTION: " + json.dumps(q, separators=(",", ":"))
        _run(_bash_event(marker, str(tmp_path)), str(tmp_path))
    stored = json.loads(mock_daemon.vault["quiz-bank"])
    assert len(stored) == 2


def test_finalize_records_quiz_bank_generated(tmp_path, mock_daemon):
    _target_source(tmp_path)
    # Stage one, then finalize.
    marker = "QUIZ-QUESTION: " + json.dumps(_QUESTION, separators=(",", ":"))
    _run(_bash_event(marker, str(tmp_path)), str(tmp_path))
    _run(_bash_event("QUIZ-BANK-FINALIZE:", str(tmp_path)), str(tmp_path))
    generated = [
        e for e in mock_daemon.recorded_events
        if e.get("event_type") == "quiz_bank_generated"
    ]
    assert len(generated) == 1
    assert generated[0]["fields"]["question_count"] == "1"


def test_stale_question_is_dropped(tmp_path, mock_daemon):
    """A question whose source is absent from the target is not staged."""
    # No source file written → verify_answer_freshness fails → dropped.
    marker = "QUIZ-QUESTION: " + json.dumps(_QUESTION, separators=(",", ":"))
    code, _ = _run(_bash_event(marker, str(tmp_path)), str(tmp_path))
    assert code == 0
    assert "quiz-bank" not in mock_daemon.vault


def test_non_bash_event_is_noop(tmp_path, mock_daemon):
    _target_source(tmp_path)
    event = {
        "tool_name": "Write",
        "tool_response": {"output": "QUIZ-QUESTION: " + json.dumps(_QUESTION)},
        "cwd": str(tmp_path),
    }
    code, _ = _run(event, str(tmp_path))
    assert code == 0
    assert "quiz-bank" not in mock_daemon.vault


def test_no_marker_is_noop(tmp_path, mock_daemon):
    code, _ = _run(_bash_event("ordinary command output\n", str(tmp_path)), str(tmp_path))
    assert code == 0
    assert "quiz-bank" not in mock_daemon.vault

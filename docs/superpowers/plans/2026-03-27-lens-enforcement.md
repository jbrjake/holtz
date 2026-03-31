# Lens Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent rubber-stamped lens sweeps by enforcing evidence of real code reading (transcript check), quiz-based comprehension testing (multiple-choice from quiz bank), and psychological priming.

**Architecture:** SubagentStop hook manages a three-phase gate (evidence → quiz → score) for lens subagents, backed by Sahjhan ledger events and enforcement directory isolation. Fallback architecture uses PreToolUse on Bash if SubagentStop blocking is unsupported.

**Tech Stack:** Python hooks, Sahjhan TOML config, JSON quiz bank, shell scripts

**Spec:** `docs/superpowers/specs/2026-03-27-lens-enforcement-design.md`

---

### Task 0: Empirical Test — SubagentStop Blocking Semantics

**Files:**
- Create: `tests/test_subagent_stop_blocking.py` (throwaway test script)

This task determines whether Section 3 or 3b of the spec is implemented. Must be done first.

- [ ] **Step 1: Write a minimal SubagentStop hook that blocks**

Create `enforcement/hooks/_test_stop_block.py`:
```python
#!/usr/bin/env python3
"""Throwaway test: does SubagentStop blocking resume the subagent?"""
import json, sys
event = json.loads(sys.stdin.read())
msg = event.get("last_assistant_message", "")
if "QUIZ_ANSWER" in msg:
    # Subagent answered — allow stop
    print(json.dumps({"decision": "allow"}))
else:
    # First stop — block with a quiz
    print(json.dumps({"decision": "block", "reason": "TEST: Reply with exactly QUIZ_ANSWER: B"}))
sys.exit(0)
```

- [ ] **Step 2: Register it temporarily in settings.local.json**

Add to SubagentStop hooks:
```json
{ "type": "command", "command": "python enforcement/hooks/_test_stop_block.py" }
```

- [ ] **Step 3: Dispatch a test subagent and observe**

```
Agent(prompt="Read enforcement/hooks/primer.py and summarize it in one sentence.", model="haiku")
```

Observe:
- Does the subagent receive "TEST: Reply with exactly QUIZ_ANSWER: B"?
- Does it respond with QUIZ_ANSWER: B?
- Does SubagentStop fire a second time?
- Does the subagent successfully stop on the second attempt?

- [ ] **Step 4: Record the result**

If blocking works: proceed with Task 1-9 (Section 3 path).
If blocking doesn't work: skip Tasks 6-7, implement Task 6b (Section 3b fallback) instead.

- [ ] **Step 5: Clean up**

Remove `enforcement/hooks/_test_stop_block.py`. Remove the temporary SubagentStop entry from settings.local.json.

---

### Task 1: Bootstrap Hook — Block Read on enforcement/

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py`
- Modify: `hooks/hooks.json`
- Modify: `.claude/settings.local.json`
- Test: `tests/test_sahjhan_integration.py`

- [ ] **Step 1: Write failing test — Read to enforcement/ should be blocked**

In `tests/test_sahjhan_integration.py`, add to `TestBootstrapHook`:
```python
def test_blocks_read_enforcement_directory(self):
    """Bootstrap blocks Read tool calls to enforcement/ paths."""
    event = {
        "tool_name": "Read",
        "tool_input": {"file_path": os.path.join(REPO_ROOT, "enforcement", "quiz-bank.json")},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert code == 0
    assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "block"

def test_allows_read_non_enforcement(self):
    """Bootstrap allows Read to non-enforcement paths."""
    event = {
        "tool_name": "Read",
        "tool_input": {"file_path": os.path.join(REPO_ROOT, "docs", "holtz", "audit", "test.md")},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert code == 0
    perm = output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    assert perm == "allow"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_read_enforcement_directory -v`
Expected: FAIL — bootstrap currently allows Read

- [ ] **Step 3: Update bootstrap hook code**

In `enforcement/hooks/_sahjhan_bootstrap.py`, the `main()` function checks `tool_input.file_path` against PROTECTED paths. It currently only fires for Write/Edit because of the hook matcher. The code itself doesn't check `tool_name` — it just checks paths. So the code needs NO changes. Only the registration needs updating.

- [ ] **Step 4: Add Read matcher to hooks.json**

In `hooks/hooks.json`, add a new PreToolUse entry:
```json
{
  "matcher": "Read",
  "hooks": [
    {
      "type": "command",
      "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_sahjhan_bootstrap.py\""
    }
  ]
}
```

- [ ] **Step 5: Add Read matcher to settings.local.json**

In `.claude/settings.local.json`, add to PreToolUse array:
```json
{
  "matcher": "Read",
  "hooks": [
    {
      "type": "command",
      "command": "python enforcement/hooks/_sahjhan_bootstrap.py"
    }
  ]
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook -v`
Expected: ALL PASS

- [ ] **Step 7: Run full suite**

Run: `python -m pytest --tb=short -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py hooks/hooks.json .claude/settings.local.json tests/test_sahjhan_integration.py
git commit -m "feat(enforcement): extend bootstrap to block Read on enforcement/ paths

Quiz bank isolation requires preventing Read tool calls to
enforcement/quiz-bank.json. The bootstrap hook code already checks
file_path against PROTECTED — only the matcher registration needed
updating to include Read alongside Write|Edit."
```

---

### Task 2: Sahjhan Event Schemas

**Files:**
- Modify: `enforcement/events.toml`
- Test: `tests/test_enforcement_config.py`

- [ ] **Step 1: Write failing test — new event types parseable**

In `tests/test_enforcement_config.py`, the existing `test_all_events_have_valid_fields` iterates all events in events.toml. Adding the new events to the TOML is sufficient — the test auto-discovers them. Add a targeted test:

```python
def test_quiz_event_types_exist(self):
    """All quiz-related event types are defined in events.toml."""
    required = ["quiz_bank_generated", "quiz_posed", "quiz_answered", "quiz_failed", "quiz_exhausted", "quiz_exhausted_resolved"]
    for name in required:
        assert name in events, f"Missing event type: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enforcement_config.py::test_quiz_event_types_exist -v`
Expected: FAIL — events don't exist yet

- [ ] **Step 3: Add event schemas to events.toml**

Append to `enforcement/events.toml`:

```toml
[events.quiz_bank_generated]
description = "Quiz bank generated during recon"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "question_count", type = "string", pattern = "^\\d+$" },
    { name = "lens_count", type = "string", pattern = "^\\d+$" },
]

[events.quiz_posed]
description = "Quiz questions posed to lens subagent"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "perspective", type = "string" },
    { name = "questions_hash", type = "string", pattern = "^[0-9a-f]{64}$" },
]

[events.quiz_answered]
description = "Lens subagent answered quiz"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "perspective", type = "string" },
    { name = "score", type = "string", pattern = "^[0-5]/[0-5]$" },
    { name = "pass", type = "string", pattern = "^(true|false)$" },
]

[events.quiz_failed]
description = "Lens subagent failed quiz"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "perspective", type = "string" },
    { name = "score", type = "string", pattern = "^[0-5]/[0-5]$" },
]

[events.quiz_exhausted]
description = "Lens subagent exhausted quiz attempts"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "perspective", type = "string" },
]

[events.quiz_exhausted_resolved]
description = "Human reviewed an exhausted quiz"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "perspective", type = "string" },
    { name = "resolution", type = "string", pattern = "^human_reviewed$" },
]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_enforcement_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/events.toml tests/test_enforcement_config.py
git commit -m "feat(enforcement): add quiz event schemas to events.toml

Six new event types for lens enforcement: quiz_bank_generated,
quiz_posed, quiz_answered, quiz_failed, quiz_exhausted,
quiz_exhausted_resolved."
```

---

### Task 3: Sahjhan Gate Additions

**Files:**
- Modify: `enforcement/transitions.toml`
- Test: `tests/test_enforcement_config.py`

- [ ] **Step 1: Write failing test for quiz gates**

In `tests/test_enforcement_config.py`, add:
```python
def test_perspective_clean_has_quiz_gate(self):
    """set complete perspective transition requires quiz_answered."""
    # Find the transition
    for t in transitions:
        if t.get("command") == "set complete perspective":
            gate_strs = [json.dumps(g) for g in t.get("gates", [])]
            assert any("quiz_answered" in g for g in gate_strs), \
                "set complete perspective missing quiz_answered gate"
            return
    raise AssertionError("set complete perspective transition not found")

def test_converge_has_quiz_exhaustion_gate(self):
    """converge transition checks for unresolved quiz_exhausted."""
    for t in transitions:
        if t.get("command") == "converge":
            gate_strs = [json.dumps(g) for g in t.get("gates", [])]
            assert any("quiz_exhausted" in g for g in gate_strs), \
                "converge missing quiz_exhausted gate"
            return
    raise AssertionError("converge transition not found")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_enforcement_config.py::test_perspective_clean_has_quiz_gate -v`
Expected: FAIL — gate not yet added

- [ ] **Step 3: Add quiz gate to `set complete perspective`**

In `enforcement/transitions.toml`, find the `set complete perspective` transition (the one with `from = "fix_loop"`, `to = "perspective_clean"`). Add after the existing gates:

```toml
    # Lens quiz must pass before perspective can be marked clean
    { type = "command_succeeds", cmd = "sahjhan query \"SELECT count(*) >= 1 FROM events WHERE type='quiz_answered' AND pass='true' AND perspective={{current_perspective}}\" | grep -q true" },
```

- [ ] **Step 2: Add quiz exhaustion gate to `converge`**

In `enforcement/transitions.toml`, find the `converge` transition (from `final_sweep`, to `final_sweep_clean`). Add:

```toml
    # No unresolved quiz exhaustions
    { type = "query", sql = "SELECT count(*) = 0 FROM events e WHERE e.type='quiz_exhausted' AND e.perspective NOT IN (SELECT r.perspective FROM events r WHERE r.type='quiz_exhausted_resolved')", expect = "true" },
```

- [ ] **Step 3: Run config tests**

Run: `python -m pytest tests/test_enforcement_config.py -v`
Expected: ALL PASS (TOML parses correctly)

- [ ] **Step 4: Commit**

```bash
git add enforcement/transitions.toml tests/test_enforcement_config.py
git commit -m "feat(enforcement): add quiz gates to perspective and convergence transitions

set complete perspective now requires quiz_answered(pass=true) for the
current perspective. converge now requires no unresolved quiz_exhausted
events."
```

---

### Task 4: Quiz Bank Generator Script

**Files:**
- Create: `enforcement/scripts/generate_quiz_bank.py`
- Create: `tests/test_quiz_bank.py`

- [ ] **Step 1: Write failing test — generator produces valid quiz bank**

```python
"""Tests for quiz bank generation."""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "scripts"))


def test_quiz_bank_schema():
    """Quiz bank entries have required fields."""
    # Minimal test with a hand-crafted entry
    entry = {
        "lens": "error-propagation",
        "q": "primer.py L56 catches?",
        "a": "A",
        "opts": ["OSError,TimeoutExpired", "FileNotFoundError", "Exception", "SubprocessError"],
        "source": "enforcement/hooks/primer.py:56",
        "keywords": ["except", "raise", "OSError"],
    }
    assert len(entry["opts"]) == 4
    assert entry["a"] in "ABCD"
    assert ":" in entry["source"]
    assert len(entry["keywords"]) >= 3


def test_quiz_bank_validates():
    """validate_quiz_bank rejects bad entries."""
    from generate_quiz_bank import validate_quiz_bank

    good = [{"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b", "c", "d"], "source": "f.py:1", "keywords": ["x", "y", "z"]}]
    assert validate_quiz_bank(good) == []

    bad_opts = [{"lens": "component", "q": "test?", "a": "A", "opts": ["a", "b"], "source": "f.py:1", "keywords": ["x", "y", "z"]}]
    errors = validate_quiz_bank(bad_opts)
    assert len(errors) > 0

    bad_answer = [{"lens": "component", "q": "test?", "a": "E", "opts": ["a", "b", "c", "d"], "source": "f.py:1", "keywords": ["x", "y", "z"]}]
    errors = validate_quiz_bank(bad_answer)
    assert len(errors) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_quiz_bank.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create directory and implement generator**

```bash
mkdir -p enforcement/scripts
```

Create `enforcement/scripts/generate_quiz_bank.py`:

```python
#!/usr/bin/env python3
"""Generate a quiz bank for lens enforcement.

Called by a sonnet subagent during Step 3 (recon summary).
Reads source files and produces 5 multiple-choice questions per lens.

Usage: python generate_quiz_bank.py --project-root <path> --output <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = {"lens", "q", "a", "opts", "source", "keywords"}
VALID_ANSWERS = set("ABCD")


def validate_quiz_bank(entries: list[dict]) -> list[str]:
    """Validate quiz bank entries. Returns list of error strings."""
    errors = []
    for i, entry in enumerate(entries):
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            errors.append(f"Entry {i}: missing fields {missing}")
            continue
        if len(entry["opts"]) != 4:
            errors.append(f"Entry {i}: need 4 options, got {len(entry['opts'])}")
        if entry["a"] not in VALID_ANSWERS:
            errors.append(f"Entry {i}: answer '{entry['a']}' not in A-D")
        if ":" not in entry["source"]:
            errors.append(f"Entry {i}: source missing line number")
        if len(entry["keywords"]) < 3:
            errors.append(f"Entry {i}: need ≥3 keywords, got {len(entry['keywords'])}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a quiz bank file")
    parser.add_argument("--input", required=True, help="Path to quiz-bank.json")
    args = parser.parse_args()

    with open(args.input) as f:
        bank = json.load(f)

    errors = validate_quiz_bank(bank)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Quiz bank valid: {len(bank)} questions")


if __name__ == "__main__":
    main()
```

> **Note:** The actual question generation is done by the sonnet subagent reading source files and writing JSON. This script validates the output. The subagent dispatch prompt (in SKILL.md) provides the format and constraints.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_quiz_bank.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/scripts/generate_quiz_bank.py tests/test_quiz_bank.py
git commit -m "feat(enforcement): add quiz bank validator script

Validates quiz bank JSON: 4 options per question, answer in A-D,
source has line number, ≥3 keywords. Called after sonnet subagent
generates the bank during recon Step 3."
```

---

### Task 5: Evidence Checker Module

**Files:**
- Create: `enforcement/hooks/lens_evidence.py`
- Create: `tests/test_lens_evidence.py`

- [ ] **Step 1: Write failing test — transcript parsing**

```python
"""Tests for lens sweep evidence checking."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))

from lens_evidence import check_transcript, check_artifact


def test_check_transcript_sufficient():
    """Transcript with ≥5 reads and keywords passes."""
    transcript = [
        {"type": "tool_use", "tool_name": "Read", "tool_input": {"file_path": f"src/mod{i}.py"}}
        for i in range(6)
    ] + [
        {"type": "assistant", "content": "The except clause catches OSError and TimeoutExpired"}
    ]
    result = check_transcript(transcript, keywords=["except", "OSError"], lens="error-propagation")
    assert result["pass"]
    assert result["read_count"] >= 5


def test_check_transcript_insufficient_reads():
    """Transcript with <5 reads fails."""
    transcript = [
        {"type": "tool_use", "tool_name": "Read", "tool_input": {"file_path": "src/mod1.py"}},
        {"type": "assistant", "content": "The except clause catches OSError"},
    ]
    result = check_transcript(transcript, keywords=["except"], lens="error-propagation")
    assert not result["pass"]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_lens_evidence.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement evidence checker**

Create `enforcement/hooks/lens_evidence.py`:

```python
"""Evidence checking for lens sweep subagents.

Parses subagent transcripts (JSONL) and output artifacts to verify
real work was done. All checks are Python regex — zero LLM token cost.
"""
from __future__ import annotations

import json
import os
import re


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
            # Don't count reads of docs or enforcement (could be cheating)
            if not any(skip in path for skip in ["docs/", "enforcement/", "quiz-bank"]):
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
        reason = f"0 lens keywords found. Blocked."

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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_lens_evidence.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/lens_evidence.py tests/test_lens_evidence.py
git commit -m "feat(enforcement): add lens evidence checker module

Python-only transcript parsing and artifact verification. Checks
≥5 source file reads, lens-vocabulary keywords, and artifact
existence. Zero LLM token cost."
```

---

### Task 6: SubagentStop Quiz Hook (Primary Path)

> **Skip this task if Task 0 showed SubagentStop blocking doesn't work. Do Task 6b instead.**

**Files:**
- Create: `enforcement/hooks/lens_quiz.py`
- Modify: `hooks/hooks.json` (add SubagentStop entry)
- Modify: `.claude/settings.local.json` (add SubagentStop entry)
- Create: `tests/test_lens_quiz.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the SubagentStop lens quiz hook."""
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))


def test_phase_detection_no_quiz():
    """First stop: no quiz_posed event → Phase 1/2."""
    from lens_quiz import detect_phase
    # Mock sahjhan query returning 0 quiz_posed events
    assert detect_phase("error-propagation", run="0", cwd="/tmp") in ("evidence", "quiz")


def test_format_quiz_block():
    """Quiz block reason is compact and parseable."""
    from lens_quiz import format_quiz_questions
    questions = [
        {"q": "primer.py L56 catches?", "opts": ["A1", "A2", "A3", "A4"]},
        {"q": "stop_gate uses?", "opts": ["B1", "B2", "B3", "B4"]},
    ]
    text = format_quiz_questions(questions, "error-propagation")
    assert "LENS: error-propagation ANSWERS:" in text
    assert "Q1:" in text
    assert "Q2:" in text


def test_parse_answers():
    """Parse ANSWERS line from subagent message."""
    from lens_quiz import parse_answers
    msg = "LENS: error-propagation ANSWERS: A,B,C,D,A"
    lens, answers = parse_answers(msg)
    assert lens == "error-propagation"
    assert answers == ["A", "B", "C", "D", "A"]


def test_parse_answers_malformed():
    """Malformed answer returns None."""
    from lens_quiz import parse_answers
    lens, answers = parse_answers("some random text")
    assert lens is None
    assert answers is None


def test_score_answers():
    """Score answers against quiz bank."""
    from lens_quiz import score_answers
    bank = [
        {"lens": "error-propagation", "a": "A", "source": "f.py:1"},
        {"lens": "error-propagation", "a": "B", "source": "f.py:2"},
        {"lens": "error-propagation", "a": "C", "source": "f.py:3"},
        {"lens": "error-propagation", "a": "D", "source": "f.py:4"},
        {"lens": "error-propagation", "a": "A", "source": "f.py:5"},
    ]
    # 4/5 correct
    correct, total = score_answers(["A", "B", "C", "A", "A"], bank, skip_stale=False)
    assert correct == 4
    assert total == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_lens_quiz.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the quiz hook**

Create `enforcement/hooks/lens_quiz.py`:

```python
#!/usr/bin/env python3
"""SubagentStop hook — lens quiz enforcement.

Three-phase gate for lens sweep subagents:
1. Evidence check (transcript parsing)
2. Quiz (pose 5 multiple-choice questions)
3. Score (parse answers, record result)

All state lives in the Sahjhan ledger. This hook is stateless.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _resolve import sahjhan_binary  # noqa: E402
from lens_evidence import check_artifact, check_transcript, parse_transcript_jsonl  # noqa: E402


QUIZ_BANK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "quiz-bank.json",
)


def read_event() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        return {}


def allow() -> None:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def parse_answers(msg: str) -> tuple[str | None, list[str] | None]:
    """Extract lens name and answers from LENS: X ANSWERS: A,B,C,D,A format."""
    m = re.search(r"LENS:\s*(\S+)\s+ANSWERS:\s*([A-D](?:,[A-D])*)", msg)
    if not m:
        return None, None
    return m.group(1), m.group(2).split(",")


def format_quiz_questions(questions: list[dict], lens: str) -> str:
    """Format quiz questions for the block reason text."""
    lines = [f"Quiz. Format: LENS: {lens} ANSWERS: A,B,C,D,A"]
    for i, q in enumerate(questions, 1):
        opts = " ".join(f"{chr(65+j)}) {o}" for j, o in enumerate(q["opts"]))
        lines.append(f"Q{i}: {q['q']} {opts}")
    return "\n".join(lines)


def score_answers(
    answers: list[str],
    bank_questions: list[dict],
    skip_stale: bool = True,
    project_root: str = ".",
) -> tuple[int, int]:
    """Score answers against quiz bank. Returns (correct, total)."""
    correct = 0
    total = 0
    for ans, q in zip(answers, bank_questions):
        if skip_stale:
            src = os.path.join(project_root, q["source"].rsplit(":", 1)[0])
            if not os.path.isfile(src):
                continue  # File deleted — skip
        total += 1
        if ans == q["a"]:
            correct += 1
    return correct, total


def run_sahjhan(*args: str, cwd: str = ".") -> subprocess.CompletedProcess:
    binary = sahjhan_binary()
    config_dir = os.path.join(cwd, "enforcement")
    cmd = [binary, "--config-dir", config_dir] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=cwd)


def _get_run_number(cwd: str) -> str:
    """Get current run number from sahjhan status."""
    result = run_sahjhan("status", "--json", cwd=cwd)
    if result.returncode == 0:
        try:
            status = json.loads(result.stdout)
            return str(status.get("run_number", "0"))
        except json.JSONDecodeError:
            pass
    return "0"


def count_quiz_failures(perspective: str, cwd: str) -> int:
    """Count quiz_failed events for this perspective in current run."""
    result = run_sahjhan(
        "query",
        f"SELECT count(*) FROM events WHERE type='quiz_failed' AND perspective='{perspective}'",
        cwd=cwd,
    )
    if result.returncode != 0:
        return 0
    # Parse tabular output — last non-empty line is the value
    lines = [ln.strip() for ln in result.stdout.strip().split("\n") if ln.strip() and not ln.startswith("-")]
    return int(lines[-1]) if lines else 0


def has_quiz_posed(perspective: str, cwd: str) -> bool:
    """Check if quiz has already been posed for this perspective."""
    result = run_sahjhan(
        "query",
        f"SELECT count(*) FROM events WHERE type='quiz_posed' AND perspective='{perspective}'",
        cwd=cwd,
    )
    if result.returncode != 0:
        return False
    lines = [ln.strip() for ln in result.stdout.strip().split("\n") if ln.strip() and not ln.startswith("-")]
    return int(lines[-1]) > 0 if lines else False


def detect_phase(perspective: str, run: str, cwd: str) -> str:
    """Determine which phase to execute based on ledger state."""
    if not has_quiz_posed(perspective, cwd):
        return "quiz"  # Evidence check + quiz
    return "score"


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())
    msg = event.get("last_assistant_message", "")

    # Only process lens sweep subagents (identified by LENS: prefix)
    if "LENS:" not in msg and not any(
        f"lens-{lens}" in msg.lower()
        for lens in ["component", "integration", "security"]
    ):
        allow()

    # Extract lens name
    lens_match = re.search(r"LENS:\s*(\S+)", msg)
    if not lens_match:
        allow()  # Not a lens subagent

    perspective = lens_match.group(1)

    # Load quiz bank
    quiz_bank_path = os.path.realpath(QUIZ_BANK_PATH)
    if not os.path.isfile(quiz_bank_path):
        allow()  # No quiz bank — quiz enforcement not active

    with open(quiz_bank_path) as f:
        bank = json.load(f)

    lens_questions = [q for q in bank if q["lens"] == perspective]
    if not lens_questions:
        allow()  # No questions for this lens

    # Check circuit breaker
    failures = count_quiz_failures(perspective, cwd)
    if failures >= 3:
        # Record exhaustion — allow stop (convergence gate blocks, not us)
        run_sahjhan(
            "event", "quiz_exhausted",
            "--field", "project=holtz",
            "--field", f"run={_get_run_number(cwd)}",
            "--field", "auditor=holtz",
            "--field", f"perspective={perspective}",
            cwd=cwd,
        )
        allow()  # NOT block — spec requires stop allowed after 3 strikes
        return

    phase = detect_phase(perspective, _get_run_number(cwd), cwd)

    if phase == "quiz":
        # Phase 1: Evidence check (if transcript available)
        transcript_path = event.get("agent_transcript_path")
        if transcript_path and os.path.isfile(transcript_path):
            events = parse_transcript_jsonl(transcript_path)
            keywords = lens_questions[0].get("keywords", [])
            evidence = check_transcript(events, keywords, perspective)
            if not evidence["pass"]:
                block(evidence["reason"])
                return

        # Phase 1b: Check artifact exists
        artifact_path = os.path.join(cwd, "docs", "holtz", "audit", f"lens-{perspective}.md")
        artifact = check_artifact(artifact_path)
        if not artifact["pass"]:
            block(artifact["reason"])
            return

        # Phase 2: Pose quiz
        selected = lens_questions[:5]
        questions_hash = hashlib.sha256(
            json.dumps([q["q"] for q in selected]).encode()
        ).hexdigest()

        run_sahjhan(
            "event", "quiz_posed",
            "--field", "project=holtz",
            "--field", f"run={_get_run_number(cwd)}",
            "--field", "auditor=holtz",
            "--field", f"perspective={perspective}",
            "--field", f"questions_hash={questions_hash}",
            cwd=cwd,
        )

        quiz_text = format_quiz_questions(selected, perspective)
        block(quiz_text)

    elif phase == "score":
        # Phase 3: Score answers
        lens, answers = parse_answers(msg)
        if not answers or len(answers) != 5:
            block(f"Bad answer format. Use: LENS: {perspective} ANSWERS: A,B,C,D,A")
            return

        selected = lens_questions[:5]
        correct, total = score_answers(answers, selected, project_root=cwd)

        threshold = 4 if total == 5 else 3
        passed = correct >= threshold

        if passed:
            run_sahjhan(
                "event", "quiz_answered",
                "--field", "project=holtz",
                "--field", f"run={_get_run_number(cwd)}",
                "--field", "auditor=holtz",
                "--field", f"perspective={perspective}",
                "--field", f"score={correct}/{total}",
                "--field", "pass=true",
                cwd=cwd,
            )
            allow()
        else:
            run_sahjhan(
                "event", "quiz_failed",
                "--field", "project=holtz",
                "--field", f"run={_get_run_number(cwd)}",
                "--field", "auditor=holtz",
                "--field", f"perspective={perspective}",
                "--field", f"score={correct}/{total}",
                cwd=cwd,
            )
            block(f"{correct}/{total}. Rejected. Read the code.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Register in hooks.json and settings.local.json**

In `hooks/hooks.json`, add/update SubagentStop entry:
```json
"SubagentStop": [
  {
    "matcher": "",
    "hooks": [
      { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/subagent_findings_check.py\"" },
      { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/lens_quiz.py\"" }
    ]
  }
]
```

In `.claude/settings.local.json`, update the existing SubagentStop entry to add the quiz hook (do NOT replace the existing `subagent_findings_check.py` entry — append to the hooks array):
```json
"SubagentStop": [
  {
    "matcher": "",
    "hooks": [
      { "type": "command", "command": "python hooks/subagent_findings_check.py" },
      { "type": "command", "command": "python enforcement/hooks/lens_quiz.py" }
    ]
  }
]
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_lens_quiz.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full suite**

Run: `python -m pytest --tb=short -q && ruff check .`
Expected: all pass, all clean

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/lens_quiz.py hooks/hooks.json .claude/settings.local.json tests/test_lens_quiz.py
git commit -m "feat(enforcement): add SubagentStop lens quiz hook

Three-phase gate: evidence check (transcript parsing), quiz (5
multiple-choice questions), score (parse answers, record to ledger).
All state in Sahjhan ledger. Hook is stateless."
```

---

### Task 6b: Fallback Quiz Hook (if SubagentStop blocking unsupported)

> **Only implement this if Task 0 showed SubagentStop blocking doesn't work.**

**Files:**
- Create: `enforcement/hooks/lens_quiz_fallback.py`
- Modify: `enforcement/hooks/commit_gate.py` (or create separate PreToolUse hook)

This task implements Section 3b: a PreToolUse hook on Bash that intercepts `sahjhan event iteration_complete` commands and poses the quiz via `additionalContext` + block.

- [ ] **Step 1: Write failing test**

```python
def test_blocks_iteration_complete_without_quiz(self):
    """PreToolUse blocks sahjhan event iteration_complete when no quiz passed."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "sahjhan event iteration_complete --field perspective=error-propagation"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("lens_quiz_fallback.py", event)
    assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "block"
    # Should include quiz questions in additionalContext
    context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "Q1:" in context

def test_allows_iteration_complete_with_quiz_passed(self):
    """PreToolUse allows iteration_complete when quiz_answered(pass=true) exists."""
    # Requires mock sahjhan that returns quiz_answered for this perspective
    # (use mock binary pattern from TestPrimerWithMockBinary)
    pass  # Full implementation uses mock binary
```

- [ ] **Step 2: Implement the fallback hook**

Create `enforcement/hooks/lens_quiz_fallback.py` — a PreToolUse hook on Bash that:
1. Checks if the command matches `sahjhan.*iteration_complete`
2. If no match: allow
3. Extracts perspective from the `--field perspective=X` argument
4. Queries ledger: does `quiz_answered(pass=true)` exist for this perspective?
5. If yes: allow
6. If no: reads quiz bank, formats questions, returns `permissionDecision: "block"` with quiz in `additionalContext`
7. On next call: parses the model's answer from the prior Bash attempt's context (stored in `_protocol_cache.py` as `pending_quiz`), scores it, records result

Uses the same `format_quiz_questions`, `parse_answers`, `score_answers` functions from `lens_quiz.py` (factor these into `lens_evidence.py` or a shared module).

- [ ] **Step 3: Register in hooks.json and settings.local.json**

Add to PreToolUse Bash matcher:
```json
{ "type": "command", "command": "python enforcement/hooks/lens_quiz_fallback.py" }
```

- [ ] **Step 4: Run tests and commit**

```bash
git add enforcement/hooks/lens_quiz_fallback.py tests/test_lens_quiz_fallback.py hooks/hooks.json .claude/settings.local.json
git commit -m "feat(enforcement): add fallback quiz hook for PreToolUse on Bash

Fallback for when SubagentStop blocking is unsupported. Intercepts
sahjhan event iteration_complete and poses quiz via additionalContext."
```

---

### Task 7: Primer Injection Update

**Files:**
- Modify: `enforcement/hooks/primer.py`

- [ ] **Step 1: Write failing test for lens priming**

In `tests/test_sahjhan_integration.py`, add to `TestPrimerWithMockBinary`:

```python
def test_injects_lens_priming_in_audit(self, tmp_path):
    """Primer injects lens priming when in audit state with active perspective."""
    cwd = self._setup(tmp_path, {
        "current_state": "audit",
        "terminal": False,
        "run_number": 1,
        "current_perspective": "error-propagation",
        "available_transitions": ["audit_complete"],
    })
    event = {"user_message": "continue", "cwd": str(cwd)}
    code, output, _ = run_enforcement_hook(
        "primer.py", event, cwd=str(cwd), env=_mock_env(tmp_path)
    )
    context = output.get("additionalContext", "")
    assert "error-propagation" in context
    assert "Quiz on exit" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestPrimerWithMockBinary::test_injects_lens_priming_in_audit -v`
Expected: FAIL — primer doesn't inject lens priming yet

- [ ] **Step 3: Add lens context to primer output**

In `primer.py`, after building the `context` string (around line 99), add:

```python
# Add lens priming if in audit/fix_loop with active perspective
if current_state in ("audit", "fix_loop") and perspective != "unknown":
    context += f"\nLens: {perspective}. Quiz on exit. Failures restart."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestPrimer tests/test_sahjhan_integration.py::TestPrimerWithMockBinary -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/primer.py
git commit -m "feat(enforcement): add lens priming to primer hook

Injects terse lens context when in audit/fix_loop state:
'Lens: {name}. Quiz on exit. Failures restart.'"
```

---

### Task 8: SKILL.md Lens Checklists

**Files:**
- Modify: `skills/holtz/references/lens-registry.md`
- Modify: `skills/holtz/SKILL.md` (Step 14 section, subagent dispatch template)

- [ ] **Step 1: Rewrite lens-registry.md with executable checklists**

For each of the 13 lenses, replace the current four-field format with numbered steps including grep commands and graph queries. Example for error-propagation:

```markdown
## error-propagation
**Focus:** How errors flow through the system
**Entry checklist:**
1. `grep -rn "except\|raise\|catch\|throw" <source>` — list all error sites
2. For each: trace the path upstream. Where is it caught? What does the caller see?
3. Flag: bare `except:`, swallowed exceptions (`pass` after except), error type changes across module boundaries
4. Check impact graph: `assumes` edges where one side expects an exception type the other doesn't throw
5. Write observations to `docs/holtz/audit/lens-error-propagation.md` with file:line for each
**Failure modes:** Silent failures, error masking, inconsistent error contracts
**Keywords:** except, raise, catch, throw, Error, Exception, try, finally
```

- [ ] **Step 2: Update SKILL.md Step 14 — subagent dispatch template**

Update the lens subagent dispatch prompt in Step 14 to include priming and quiz instructions:

```
Agent(subagent_type="general-purpose", model="sonnet", prompt="
LENS SWEEP: {{perspective}}

Last sweep: rubber-stamped. Findings missed. You're being quizzed on exit.

Read the lens checklist from skills/holtz/references/lens-registry.md for {{perspective}}.
Follow each numbered step. Write all observations to docs/holtz/audit/lens-{{perspective}}.md.

When you finish, your final message MUST begin with: LENS: {{perspective}}
When quizzed, respond ONLY with: LENS: {{perspective}} ANSWERS: A,B,C,D,A

Recon summary: docs/holtz/recon/step3-recon-summary.md
")
```

- [ ] **Step 3: Add quiz bank generation to Step 3**

In SKILL.md Step 3 (Recon Summary), add instructions to dispatch a quiz bank generator subagent:

```
After writing the recon summary, dispatch a quiz bank generator:

Agent(model="sonnet", prompt="
Generate a quiz bank for lens enforcement.
Read source files in <project> and generate 5 multiple-choice questions per lens (13 lenses).
Questions must be SHORT (under 15 words), derived from actual code facts (function signatures,
exception types, import relationships, config values, README claims).
Each question has exactly 4 options, 1 correct answer (A-D).
Write output as JSON to enforcement/quiz-bank.json using this format:
[{\"lens\": \"...\", \"q\": \"...\", \"a\": \"A\", \"opts\": [...], \"source\": \"file.py:line\", \"keywords\": [...]}]
Then validate: python enforcement/scripts/generate_quiz_bank.py --input enforcement/quiz-bank.json
")
```

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/references/lens-registry.md skills/holtz/SKILL.md
git commit -m "feat(skill): add executable lens checklists, quiz bank generation, and priming

Replace prose lens descriptions with numbered steps and grep commands.
Add quiz bank generation to Step 3 recon. Add priming and quiz
instructions to Step 14 lens subagent dispatch template."
```

---

### Task 9: Dev-Mode Hook Registration Safety Net

**Files:**
- Modify: `scripts/install-hooks.sh`
- Create: `enforcement/hooks/verify_hooks.py`
- Create: `enforcement/hooks-manifest.json`

- [ ] **Step 1: Create hooks manifest**

Create `enforcement/hooks-manifest.json`:
```json
{
  "required_hooks": {
    "PreToolUse": ["_sahjhan_bootstrap.py", "write_guard.py", "commit_gate.py"],
    "PostToolUse": ["bash_guard.py", "protocol_tracker.py"],
    "UserPromptSubmit": ["primer.py"],
    "Stop": ["stop_gate.py"],
    "SubagentStop": ["lens_quiz.py"]
  }
}
```

- [ ] **Step 2: Write failing test for verify_hooks**

```python
def test_verify_hooks_detects_missing(tmp_path):
    """verify_hooks exits 1 when required hooks are missing."""
    # Create a minimal settings.local.json with no hooks
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"hooks": {}}')
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "enforcement" / "hooks" / "verify_hooks.py"),
         "--settings", str(settings)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "missing" in result.stderr.lower()
```

- [ ] **Step 3: Implement verify_hooks.py**

```python
#!/usr/bin/env python3
"""Verify all required enforcement hooks are registered.

Exit 0 if all hooks in hooks-manifest.json are present in settings.
Exit 1 with missing hooks listed on stderr.
"""
import argparse
import json
import os
import sys

MANIFEST = os.path.join(os.path.dirname(__file__), "..", "hooks-manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", default=os.path.join(os.getcwd(), ".claude", "settings.local.json"))
    args = parser.parse_args()

    with open(MANIFEST) as f:
        manifest = json.load(f)

    if not os.path.isfile(args.settings):
        print("ERROR: No settings file found", file=sys.stderr)
        sys.exit(1)

    with open(args.settings) as f:
        settings = json.load(f)

    hooks = settings.get("hooks", {})
    missing = []

    for event_type, required_scripts in manifest["required_hooks"].items():
        registered = []
        for entry in hooks.get(event_type, []):
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                registered.append(cmd)

        for script in required_scripts:
            if not any(script in cmd for cmd in registered):
                missing.append(f"{event_type}/{script}")

    if missing:
        print(f"ERROR: Missing hooks: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print(f"Hook verification: all {sum(len(v) for v in manifest['required_hooks'].values())} required hooks present.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_verify_hooks.py -v`

- [ ] **Step 5: Extend install-hooks.sh**

Add a section that generates the hooks portion of `.claude/settings.local.json` from `hooks/hooks.json`, preserving the existing `permissions` block.

- [ ] **Step 4: Test and commit**

```bash
git add enforcement/hooks/verify_hooks.py enforcement/hooks-manifest.json scripts/install-hooks.sh
git commit -m "feat(enforcement): add hook registration safety net

hooks-manifest.json lists required hooks. verify_hooks.py checks
registration at run_start. install-hooks.sh generates dev-mode
settings from plugin hooks.json."
```

---

### Task 10: Integration Test — Full Quiz Flow

**Files:**
- Create: `tests/test_lens_quiz_integration.py`

- [ ] **Step 1: Write end-to-end test**

Test the full flow: generate quiz bank → dispatch mock subagent event → SubagentStop evidence check → quiz posed → answers scored → events recorded in ledger.

Use `tmp_path` with mock sahjhan binary (from the existing mock pattern in `test_sahjhan_integration.py`).

- [ ] **Step 2: Run and verify**

Run: `python -m pytest tests/test_lens_quiz_integration.py -v`

- [ ] **Step 3: Run full suite**

Run: `python -m pytest --tb=short -q && ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`

- [ ] **Step 4: Update README metrics and commit**

```bash
git commit -m "test(enforcement): add lens quiz integration tests"
```

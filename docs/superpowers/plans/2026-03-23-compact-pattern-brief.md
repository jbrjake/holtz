# Compact Pattern Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a compact representation of `patterns-brief.md` that's small enough for subagents to load quickly but informative enough for reliable pattern recognition. Includes an empirical testing phase to determine the right format through actual subagent trials.

**Architecture:** A Python script (`pattern_brief_compact.py`) reads `patterns-brief.md` and produces compact output in a configurable format. Three candidate formats are tested empirically during development by dispatching actual subagents with each format + synthesized code samples, then checking whether the subagent correctly identifies the matching pattern. This is a dev-time refinement loop, not CI — it runs during implementation to lock in the right format.

**Tech Stack:** Python 3.11+, pytest, existing `markdown_utils.py`

**Key constraint:** The compact format must be empirically validated — not just theoretically small. A format that saves 80% of tokens but causes subagents to miss 30% of pattern matches is worse than the full brief.

---

### Task 1: Parse patterns-brief.md into structured entries

**Files:**
- Create: `skills/holtz/scripts/pattern_brief_compact.py`
- Test: `tests/test_pattern_brief_compact.py`

Parse the patterns-brief format (defined in SKILL.md Phase 5) into structured data. Each entry has: pattern ID, name, run/date, "what to look for" text, detection heuristic, and example.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for pattern_brief_compact.py."""

import pattern_brief_compact as pbc


SAMPLE_BRIEF = """\
# Holtz Pattern Brief

> Read this before starting any audit work. These patterns were discovered
> in prior audits of this project. Check for them in the code you're reviewing.

## PAT-001: missing-edge-case-handling (Run 3, 2026-03-10)
**What to look for:** Functions with early return on happy path that lack guards for null, empty, or boundary inputs. The error path exists but is never reached.
**Detection heuristic:** `grep -rn 'if.*return' --include='*.py' | grep -v 'None\\|empty\\|boundary'`
**Example:** A validation function returns True for valid input but has no branch for empty string — callers assume empty string is valid.

## PAT-002: dual-parser-divergence (Run 5, 2026-03-15)
**What to look for:** Two or more functions that parse, extract, or deserialize from the same data format with different edge-case handling. One handles quoting/escaping, the other does not.
**Detection heuristic:** Find pairs of parse/extract/decode functions targeting the same format. Compare their handling of empty input, special characters, and nested structures.
**Example:** A report generator and a data validator both parse key-value text — one strips quotes, the other preserves them.

## PAT-003: code-fence-unaware-parsing (Run 5, 2026-03-15)
**What to look for:** Regex or string matching applied to document content without first masking or stripping fenced/quoted/literal blocks. Content inside code blocks matches patterns meant for the document layer.
**Detection heuristic:** `grep -rn 're\\.search.*content' --include='*.py'` then check: is there a mask/strip step before the regex?
**Example:** A heading extractor matches `# comment` inside a code block as a real heading.
"""


def test_parse_brief_entries():
    """Parse patterns-brief format into structured entries."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    assert len(entries) == 3
    assert entries[0].pattern_id == "PAT-001"
    assert entries[0].name == "missing-edge-case-handling"
    assert entries[0].run == "Run 3"
    assert "early return" in entries[0].what_to_look_for
    assert "grep" in entries[0].detection_heuristic
    assert "validation function" in entries[0].example


def test_parse_brief_empty():
    """Empty or header-only brief returns no entries."""
    header_only = "# Holtz Pattern Brief\n\n> Read this before starting.\n"
    entries = pbc.parse_brief(header_only)
    assert len(entries) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_pattern_brief_compact.py::test_parse_brief_entries -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create pattern_brief_compact.py with parser**

```python
#!/usr/bin/env python3
"""
Holtz Pattern Brief Compactor

Reads patterns-brief.md and produces compact representations for subagent
consumption. Multiple output formats available; default determined by
empirical testing.

Usage:
  python pattern_brief_compact.py [path-to-patterns-brief.md]
  python pattern_brief_compact.py [path] --format oneliner|twoliner|structured
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatternEntry:
    pattern_id: str
    name: str
    run: str
    date: str
    what_to_look_for: str
    detection_heuristic: str
    example: str


def parse_brief(content: str) -> list[PatternEntry]:
    """Parse patterns-brief.md into structured entries."""
    entries = []
    # Match ## PAT-NNN: name (Run N, YYYY-MM-DD)
    header_re = re.compile(
        r'^## (PAT-\d+): (.+?) \((Run \d+), (\d{4}-\d{2}-\d{2})\)\s*$',
        re.MULTILINE,
    )
    matches = list(header_re.finditer(content))

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]

        def _extract(field: str) -> str:
            m = re.search(
                rf'\*\*{field}:\*\*\s*(.*?)(?=\n\*\*|\n##|\Z)',
                block,
                re.DOTALL,
            )
            return m.group(1).strip() if m else ""

        entries.append(PatternEntry(
            pattern_id=match.group(1),
            name=match.group(2),
            run=match.group(3),
            date=match.group(4),
            what_to_look_for=_extract("What to look for"),
            detection_heuristic=_extract("Detection heuristic"),
            example=_extract("Example"),
        ))

    return entries
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_pattern_brief_compact.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/scripts/pattern_brief_compact.py tests/test_pattern_brief_compact.py
git commit -m "feat(scripts): add pattern brief parser for compact output"
```

---

### Task 2: Implement three candidate compact formats

**Files:**
- Modify: `skills/holtz/scripts/pattern_brief_compact.py`
- Test: `tests/test_pattern_brief_compact.py`

Three formats to test empirically:

**Format A: "oneliner"** — one line per pattern, pipe-delimited. Minimum context.
```
PAT-001 | missing-edge-case-handling | Functions with early return on happy path, no guard on null/empty/boundary
PAT-002 | dual-parser-divergence | Two+ parsers for same format with different edge-case handling
```

**Format B: "twoliner"** — two lines per pattern: description + detection heuristic. Moderate context.
```
PAT-001: missing-edge-case-handling — Functions with early return on happy path, no guard on null/empty/boundary
  Detect: `grep -rn 'if.*return' | grep -v 'None\|empty\|boundary'`

PAT-002: dual-parser-divergence — Two+ parsers for same format with different edge-case handling
  Detect: Find pairs of parse/extract/decode functions for same format, compare edge-case handling
```

**Format C: "structured"** — three lines per pattern: description + heuristic + one-sentence example. Maximum context in compact form.
```
## PAT-001: missing-edge-case-handling
Look for: Functions with early return on happy path, no guard on null/empty/boundary
Detect: `grep -rn 'if.*return' | grep -v 'None\|empty\|boundary'`
e.g.: validation function returns True for valid input, no branch for empty string

## PAT-002: dual-parser-divergence
Look for: Two+ parsers for same format with different edge-case handling
Detect: Find pairs of parse/extract/decode functions, compare edge cases
e.g.: report generator and data validator both parse KV text, one strips quotes, other doesn't
```

- [ ] **Step 1: Write the failing tests**

```python
def test_format_oneliner():
    """Oneliner format: one pipe-delimited line per pattern."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="oneliner")
    lines = [l for l in output.strip().split('\n') if l.strip() and not l.startswith('#')]
    assert len(lines) == 3
    assert "PAT-001" in lines[0]
    assert "|" in lines[0]
    # Each line is under 200 chars (enforced for readability)
    assert all(len(l) < 200 for l in lines)


def test_format_twoliner():
    """Twoliner format: description + detection on two lines."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="twoliner")
    assert "PAT-001" in output
    assert "Detect:" in output
    # Roughly 2 non-empty lines per entry + 1 blank separator
    content_lines = [l for l in output.strip().split('\n') if l.strip()]
    assert len(content_lines) >= 6  # 3 entries × 2 lines


def test_format_structured():
    """Structured format: header + look for + detect + example."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="structured")
    assert "## PAT-001" in output
    assert "Look for:" in output
    assert "Detect:" in output
    assert "e.g.:" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_pattern_brief_compact.py -k "format_" -v`
Expected: FAIL — `format_compact` does not exist

- [ ] **Step 3: Implement format_compact**

```python
def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, preserving whole words."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len].rsplit(' ', 1)[0]
    return truncated + "..."


def _compress_heuristic(heuristic: str) -> str:
    """Compress a detection heuristic to a single actionable line."""
    # If it's a grep command, keep the grep
    if '`' in heuristic:
        m = re.search(r'`([^`]+)`', heuristic)
        if m:
            return m.group(0)
    # Otherwise, take the first sentence
    first_sentence = heuristic.split('.')[0].strip()
    return _truncate(first_sentence, 120)


def _compress_example(example: str) -> str:
    """Compress an example to a single sentence."""
    # Take first sentence, truncate
    first_sentence = example.split('.')[0].strip()
    if first_sentence.startswith('A ') or first_sentence.startswith('The '):
        first_sentence = first_sentence[0].lower() + first_sentence[1:]
    return _truncate(first_sentence, 100)


def format_compact(entries: list[PatternEntry], *, fmt: str = "structured") -> str:
    """Format parsed entries into a compact representation.

    Args:
        entries: Parsed pattern entries.
        fmt: Output format — "oneliner", "twoliner", or "structured".

    Returns:
        Compact markdown string.
    """
    if not entries:
        return "# Pattern Brief (compact)\n\nNo patterns recorded.\n"

    header = f"# Pattern Brief (compact, {len(entries)} patterns)\n\n"
    blocks = []

    for entry in entries:
        wtlf = _truncate(entry.what_to_look_for, 150)
        heuristic = _compress_heuristic(entry.detection_heuristic)
        example = _compress_example(entry.example)

        if fmt == "oneliner":
            blocks.append(f"{entry.pattern_id} | {entry.name} | {wtlf}")

        elif fmt == "twoliner":
            blocks.append(
                f"{entry.pattern_id}: {entry.name} — {wtlf}\n"
                f"  Detect: {heuristic}"
            )

        elif fmt == "structured":
            blocks.append(
                f"## {entry.pattern_id}: {entry.name}\n"
                f"Look for: {wtlf}\n"
                f"Detect: {heuristic}\n"
                f"e.g.: {example}"
            )

        else:
            raise ValueError(f"Unknown format: {fmt!r}")

    separator = "\n" if fmt == "oneliner" else "\n\n"
    return header + separator.join(blocks) + "\n"
```

- [ ] **Step 4: Run format tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_pattern_brief_compact.py -k "format_" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/scripts/pattern_brief_compact.py tests/test_pattern_brief_compact.py
git commit -m "feat(scripts): implement three candidate compact formats for pattern brief"
```

---

### Task 3: CI-safe structural tests

**Files:**
- Create: `tests/test_pattern_brief_compact_structure.py`

These are fast deterministic tests for CI — they verify that each format preserves the structural requirements for pattern identification without making LLM calls.

- [ ] **Step 1: Write structural tests**

```python
"""Structural tests for compact pattern brief formats (CI-safe, no LLM calls)."""

import pattern_brief_compact as pbc
from test_pattern_brief_compact import SAMPLE_BRIEF


def test_all_formats_contain_all_pattern_ids():
    """Every pattern ID must appear in every format's output."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt)
        for entry in entries:
            assert entry.pattern_id in output, f"{fmt}: missing {entry.pattern_id}"


def test_twoliner_and_structured_contain_heuristics():
    """Twoliner and structured formats must include detection heuristics."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt)
        assert output.count("Detect:") == len(entries), f"{fmt}: missing Detect lines"


def test_structured_contains_all_fields():
    """Structured format has Look for + Detect + e.g. for each entry."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="structured")
    assert output.count("Look for:") == len(entries)
    assert output.count("Detect:") == len(entries)
    assert output.count("e.g.:") == len(entries)


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def test_all_formats_smaller_than_full():
    """Every compact format must be smaller than the full brief."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    full_size = _approx_tokens(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        compact = pbc.format_compact(entries, fmt=fmt)
        assert _approx_tokens(compact) < full_size, f"{fmt} not smaller"


def test_size_ordering():
    """oneliner < twoliner < structured in output size."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    sizes = {fmt: len(pbc.format_compact(entries, fmt=fmt))
             for fmt in ("oneliner", "twoliner", "structured")}
    assert sizes["oneliner"] < sizes["twoliner"] < sizes["structured"]


def test_key_terms_preserved_across_formats():
    """Each format preserves the distinctive terms that distinguish patterns."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt).lower()
        # PAT-001 must mention edge cases / boundaries / null
        assert any(t in output for t in ['early return', 'edge case', 'boundary', 'null']), \
            f"{fmt}: PAT-001 lost distinguishing terms"
        # PAT-002 must mention parsers / format divergence
        assert any(t in output for t in ['parser', 'format', 'deserialize', 'diverge']), \
            f"{fmt}: PAT-002 lost distinguishing terms"
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_pattern_brief_compact_structure.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_pattern_brief_compact_structure.py
git commit -m "test(scripts): add CI-safe structural tests for compact formats"
```

---

### Task 4: Dev-time subagent evaluation loop

**This task is NOT automated. It's a procedure the implementing developer follows during development to empirically test each format with actual subagent calls. The results determine which format becomes the default.**

The idea: for each candidate format, dispatch a subagent with the compact brief + a synthesized code sample. Check whether the subagent correctly identifies the pattern. Iterate on the format until recognition is reliable.

**Eval cases** (synthesized code that should/shouldn't match known patterns):

```python
# These live in the plan as reference data, not as a committed file.
# The developer uses them as prompts when dispatching test subagents.

EVAL_CASES = [
    {
        "name": "true_positive_edge_case",
        "expected": "PAT-001",
        "code": """
def validate_email(email):
    if '@' in email and '.' in email.split('@')[1]:
        return True
    return False
""",
    },
    {
        "name": "true_positive_dual_parser",
        "expected": "PAT-002",
        "code": """
def load_config(text):
    config = {}
    for line in text.split('\\n'):
        key, val = line.split('=', 1)
        config[key] = val
    return config

def parse_settings(text):
    settings = {}
    for line in text.strip().split('\\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, val = line.partition('=')
        settings[key.strip()] = val.strip().strip('"')
    return settings
""",
    },
    {
        "name": "true_negative_clean",
        "expected": "none",
        "code": """
def calculate_total(items):
    if not items:
        return 0.0
    subtotal = sum(item.price * item.quantity for item in items)
    return round(subtotal * 1.08, 2)
""",
    },
    {
        "name": "true_positive_fence_unaware",
        "expected": "PAT-003",
        "code": """
import re
def find_todos(document):
    return re.findall(r'TODO:.*$', document, re.MULTILINE)
""",
    },
]
```

- [ ] **Step 1: Generate compact output for each format**

Run the script for each format and capture output:

```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz
python -c "
import sys; sys.path.insert(0, 'skills/holtz/scripts')
import pattern_brief_compact as pbc
# Use the sample brief from the test file or a real patterns-brief.md
brief = open('tests/test_pattern_brief_compact.py').read()
# Extract SAMPLE_BRIEF... or just use a real file if available
"
```

Or more practically: after Task 2 is committed, use the CLI to generate each format's output and save to temp files for reference.

- [ ] **Step 2: Test each format by dispatching subagents**

For each of the 3 formats × 4 eval cases (12 combinations), dispatch a subagent:

```
Agent(model="sonnet", prompt="You are a code auditor scanning for known bug patterns.

Here are the patterns to check for:

{paste compact output for this format here}

---

Review this code and report if any of the above patterns apply.
If a pattern matches, state which pattern ID and why.
If no patterns match, say 'No patterns match.'

```
{paste eval case code here}
```")
```

Use `model: sonnet` because that's what Phase 2/3 subagents typically run on.

**Run all 4 cases for one format in parallel** (they're independent). Then move to the next format.

- [ ] **Step 3: Score the results**

For each subagent response, record:

| Format | Case | Expected | Subagent said | Correct? | Notes |
|--------|------|----------|---------------|----------|-------|
| oneliner | true_positive_edge_case | PAT-001 | ? | ? | |
| oneliner | true_positive_dual_parser | PAT-002 | ? | ? | |
| oneliner | true_negative_clean | none | ? | ? | |
| oneliner | true_positive_fence_unaware | PAT-003 | ? | ? | |
| twoliner | ... | ... | ... | ... | |
| structured | ... | ... | ... | ... | |

**What to look for:**
- **False negatives** (subagent misses a pattern) — the dangerous failure mode. If a format produces false negatives, it needs more context.
- **False positives** (subagent sees a pattern that isn't there) — annoying but manageable. A few false positives on the compact brief are acceptable since Holtz/Justine verify findings.
- **Confidence of identification** — does the subagent say "this clearly matches PAT-001" or "this might match PAT-001"? Higher confidence = better format.

- [ ] **Step 4: Iterate if needed**

If a format fails (false negatives on true positives):
1. Look at what information was lost in compression
2. Adjust `_truncate` lengths, `_compress_heuristic` logic, or `_compress_example` logic
3. Re-run the failing cases with the adjusted format
4. Repeat until the format passes all cases reliably

Common adjustments:
- `_truncate` max_len too short → key distinguishing terms cut off
- `_compress_heuristic` only extracting first grep → multiple heuristics needed
- `_compress_example` losing the critical detail that distinguishes from similar patterns

- [ ] **Step 5: Select winner and record rationale**

Pick the smallest format that passes all eval cases. Record in a comment at the top of `pattern_brief_compact.py`:

```python
# Default format selected by empirical testing (YYYY-MM-DD):
# - oneliner: {pass/fail, notes}
# - twoliner: {pass/fail, notes}
# - structured: {pass/fail, notes}
# Winner: {format} — {rationale}
DEFAULT_FORMAT = "structured"  # or whatever won
```

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/pattern_brief_compact.py
git commit -m "feat(scripts): set default compact format based on subagent eval results"
```

---

### Task 5: Add CLI and integrate with SKILL.md

**Files:**
- Modify: `skills/holtz/scripts/pattern_brief_compact.py` (add `main()`)
- Modify: `skills/holtz/SKILL.md:172-193` (Phase 2-3 subagent brief)
- Modify: `skills/holtz/references/justine-skill.md:195-220` (Justine subagent brief)

- [ ] **Step 1: Add CLI main function**

```python
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Compact pattern brief for subagents")
    parser.add_argument("path", nargs="?", default="docs/holtz/patterns-brief.md",
                        help="Path to patterns-brief.md")
    parser.add_argument("--format", choices=["oneliner", "twoliner", "structured"],
                        default="structured",  # or whatever won the eval
                        help="Compact format to use")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"No pattern brief found at {path}", file=sys.stderr)
        sys.exit(0)  # Not an error — brief may not exist on early runs

    content = path.read_text()
    entries = parse_brief(content)
    if not entries:
        print("No patterns in brief", file=sys.stderr)
        sys.exit(0)

    print(format_compact(entries, fmt=args.format))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update SKILL.md Phase 2 subagent brief**

In Phase 2, step 3, the subagent brief currently says "(a) read `docs/holtz/patterns-brief.md` before starting". Change to:

```markdown
3. **Subagent brief:** Instruct each subagent to: (a) read the compact pattern brief by running `python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/pattern_brief_compact.py docs/holtz/patterns-brief.md` — if a finding matches a pattern ID, reference it in the punchlist item; if a pattern match seems likely but uncertain, read the full entry from `docs/holtz/patterns-brief.md` for that specific pattern ID, (b) check known patterns against the code being reviewed, ...
```

Apply the same change to Phase 3 step 2 and to justine-skill.md's subagent brief.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/scripts/pattern_brief_compact.py skills/holtz/SKILL.md skills/holtz/references/justine-skill.md
git commit -m "feat(scripts): add CLI for compact brief, update skill subagent briefs"
```

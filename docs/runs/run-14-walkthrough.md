# Holtz Run 14: Full Walkthrough

> **What you're reading:** The complete trace of Holtz's 14th audit of his own codebase, including reasoning, commands, findings, and fixes. This was a full adversarial self-play audit — Holtz and Justine auditing in parallel, merging findings, then Holtz running the TDD fix loop.
>
> **Token usage:** 207,110 tokens in the main context + 141,876 tokens in Justine's parallel subagent = 348,986 total across 2 execution contexts. All token counts are real, extracted from `~/.claude/` session logs.
>
> **Result:** 8 findings (6 MEDIUM, 2 LOW), all resolved. 2 real code bugs found and fixed. 3 tests added. Pattern library predicted both bugs before any code was read.

---

## Context

This codebase is Holtz himself — the Claude Code plugin that performs these audits. After 13 prior runs, the codebase has 321 tests, 67% coverage, clean lints, and a mature test suite. The challenge: find what 13 previous audit runs missed.

**Starting state:**
- 21 Python files, 8,545 lines
- 321 tests passing, 0 failing, 0 skipped
- Ruff clean, mypy clean
- Impact graph: 37 nodes, 35 edges
- 3 known patterns: PAT-001 (code-fence-unaware parsing), PAT-002 (incomplete isolation), PAT-003 (regex convention violation)

---

## Phase 0: Recon (~45K tokens)

Recon maps the codebase before a single line of code is read. 8 steps, each written to disk immediately (context can compact at any time — files are Holtz's durable memory).

<details>
<summary><strong>Step 0a: Project overview</strong></summary>

Scanned all 21 Python files. Key observation: **no source code has changed since run 13** — all 5 recent commits are docs/config only. This means the audit is primarily testing whether pattern heuristics catch things that human review missed.

```
skills/holtz/scripts/
  convergence_check.py    (429 lines) — convergence tracking, test runner detection
  impact_graph.py         (435 lines) — knowledge graph operations
  markdown_utils.py       (81 lines)  — code fence state machine
  pattern_brief_compact.py (168 lines) — newest module, pattern brief parser
  validate_punchlist.py   (584 lines) — punchlist parsing, validation, filtering

hooks/                     (339 lines) — 4 enforcement hooks + shared utilities
tests/                     (6,509 lines) — 8 test files + fixtures
```

`pattern_brief_compact.py` is the newest module with 4 changes in 50 commits. This becomes relevant later.
</details>

<details>
<summary><strong>Step 0c: Test baseline</strong></summary>

```
321 passed in 2.63s

Coverage:
  markdown_utils.py       100%
  validate_punchlist.py    80%  (CLI main uncovered)
  convergence_check.py     85%
  impact_graph.py          65%  (CLI entry points)
  pattern_brief_compact.py 78%
  hooks/*                   0%  (tested via subprocess — coverage can't trace)
```
</details>

<details>
<summary><strong>Step 0d-0f: Lint, churn, skipped tests</strong></summary>

- **Ruff:** All checks passed
- **Mypy:** No issues in 10 files
- **Git churn (50 commits):** validate_punchlist.py (7 changes), pattern_brief_compact.py (4), hooks (14 total)
- **Skipped tests:** None. All 321 active.
</details>

<details>
<summary><strong>Impact graph reconciliation</strong></summary>

The graph persists across runs. Reconciliation before each audit:

1. **Prune missing files:** 0 nodes removed (all files still exist)
2. **Drift check:** 1 function shifted — `validate_punchlist::validate` moved from line 360 to 374 (updated in graph)
3. **Stats:** 37 nodes, 35 edges (10 imports, 5 calls, 9 `assumes`, 1 `diverges_from`, 10 `tests`)

The `assumes` edges are the interesting ones. They encode implicit contracts between modules — things like "both `parse_punchlist` and `count_items` split on `### BH-NNN:` headers in masked content." When Holtz fixes one function, blast radius analysis walks these edges to check whether the assumption still holds.
</details>

<details>
<summary><strong>Architecture drift detection</strong></summary>

Compared current module dependencies against the baseline established in run 8:

| Module | Depends On | Status |
|--------|-----------|--------|
| validate_punchlist.py | markdown_utils.py | matches baseline |
| convergence_check.py | markdown_utils.py | matches baseline |
| impact_graph.py | (standalone) | matches baseline |
| hooks/*.py | _common.py | matches baseline |

No dependency reversals. No boundary erosion. No layering breaches. Architecture stable.
</details>

<details>
<summary><strong>Global pattern library scan (6 seed patterns)</strong></summary>

Each seed pattern has an executable detection heuristic — a grep command or structural check that fires during recon. Results:

| Pattern | Heuristic | Result |
|---------|-----------|--------|
| code-fence-unaware-parsing | `grep` for regex on `content`/`body`/`text` vars | No hits |
| **regex-newline-leak** | `grep` for `\s` with quantifier | **2 HITS in pattern_brief_compact.py** |
| dual-parser-divergence | Find duplicate parse/extract functions | 5 functions, all distinct formats |
| incomplete-layer-isolation | Find abstraction layers with bypasses | No layers detected |
| missing-edge-case-handling | Manual review per module | Deferred to Phase 3 |
| doc-spec-drift | Claim-by-claim comparison | Deferred to Phase 1 |

**The regex-newline-leak heuristic flagged `pattern_brief_compact.py` lines 41 and 53.** This is the only source module still using `\s` in regex — the rest of the codebase converted to `[ \t]` after PAT-003 was discovered in run 11.
</details>

<details>
<summary><strong>Recommendation escalation (scanning 13 prior summaries)</strong></summary>

Recommendations that appear in 2+ prior audit summaries get escalated to punchlist items. Holtz tracks what he told you to fix. If you didn't fix it, it stops being a suggestion.

**Scanned:** Runs 2-13 + 3 Justine summaries (16 files total)

**Escalated:**
1. **"README metrics test incomplete"** — appeared in runs 9, 10, 13, and Justine run 1 (4 appearances). The test `test_readme_metrics_match_actual` extracts all 9 fields but only asserts on test count. → **BH-001**
2. **"\\s convention check not in CI"** — appeared in run 11 and Justine run 11 (2 appearances). No automated check prevents `\s` regression. → **BH-002**

**Not escalated (addressed):**
- "Add mypy" — now configured and clean
- "pytest-cov" — now installed and working
- "CI configuration" — `.github/workflows/ci.yml` exists
- "_field_names recomputation" — hoisted to module-level constant
- "validate() redundant masking" — `masked_content` now passed as parameter
</details>

### Predictive Recon (~52K tokens)

After recon completes, Holtz synthesizes 6 input sources into ranked predictions of where bugs are most likely hiding. These get written to disk and checked against actual findings at the end of the run.

| # | Confidence | Target | Predicted Issue | Basis |
|---|-----------|--------|-----------------|-------|
| 1 | **HIGH** | `pattern_brief_compact.py:53` | `\s*` after `**Field:**` matches `\n`, causing `(.*?)` to capture next field's content when field is empty | Pattern library heuristic + PAT-003 adjacency + only module using `\s` |
| 2 | MEDIUM | `pattern_brief_compact.py:41` | `\s*$` in header regex — CRLF edge case | Heuristic hit, but `$`+MULTILINE constrains to single line |
| 3 | MEDIUM | `pattern_brief_compact.py` | `parse_brief()` applies regex directly to content without masking code fences | No `mask_code_fences` call before `finditer` |
| 4 | **HIGH** | `README.md` "What's inside" | README counts may be stale; test only validates 1 of 9 fields | 4 appearances in prior summaries |
| 5 | LOW | `hooks/` | 0% coverage is subprocess testing artifact | Single signal, not a real gap |

---

## Justine Dispatch (~52K tokens in main context)

After Phase 0, Holtz dispatches Justine as a background subagent. She inherits the raw recon data but runs her own synthesis and predictions independently. Same inputs, different methodology (breadth-first vs depth-first), different conclusions.

```
Agent(subagent_type="holtz:justine", run_in_background=true, ...)
```

Justine runs for ~15 minutes, uses 142K tokens, makes 109 tool calls. She produces her own punchlist, impact graph, and predictions. Holtz doesn't see her findings until the merge — that's the point.

**Justine's results (received later):** 5 findings, 3 MEDIUM + 2 LOW. 0/5 predictions confirmed. Her assessment: "This codebase is clean... the defensive coding patterns held up under adversarial testing."

She was wrong about one thing. She noted the `\s` convention violation and called it "functionally harmless." She tested CRLF handling and cross-entry bleeding. She tested the *wrong edge cases*. The *right* edge cases — empty field values and code-fenced headers — she never tried.

---

## Phase 1: Doc-to-Implementation Audit (~78K tokens)

Every testable claim in the documentation checked against reality. Predicted areas first (Prediction 4).

<details>
<summary><strong>README "What's inside" verification</strong></summary>

| Claim | README | Actual | Status |
|-------|--------|--------|--------|
| Skills | 1 | 1 | VERIFIED |
| Agents | 3 | 3 | VERIFIED |
| Reference docs | 17 | 17 | VERIFIED |
| Examples | 1 | 1 | VERIFIED |
| Python scripts | 5 | 5 | VERIFIED |
| Seed patterns | 6 | 6 | VERIFIED |
| Enforcement hooks | 4 | 4 | VERIFIED |
| Tests | 321 | 321 | VERIFIED |
| Lines | 8,500 | 8,545 | VERIFIED (rounds) |

Prediction 4: **UNCONFIRMED** — counts are currently correct. But BH-001 remains valid: the test only checks 1 of these 9 fields.
</details>

<details>
<summary><strong>Architecture invariants</strong></summary>

| Invariant | Status |
|-----------|--------|
| Field extraction uses masked boundaries, original extraction | VERIFIED |
| `mask_code_fences` preserves line count | VERIFIED |
| `count_items` and `parse_punchlist` split on `B[HJ]-NNN` headers in masked content | VERIFIED |
| `save_history` and `ImpactGraph.save` use atomic writes (tempfile + rename) | VERIFIED |
| Test runner parsers return `None` for unparseable output | VERIFIED (14 return-None paths) |
</details>

**Result: 0 new findings.** All claims verified.

---

## Phase 2: Test Quality Audit (~110K tokens)

Every test file scored against 12 anti-patterns across 3 tiers. A subagent audited the 4 large test files (5,381 lines total) while Holtz focused on the predicted area.

<details>
<summary><strong>Subagent results: 4 large test files</strong></summary>

- **test_validate_punchlist.py** (2,578 lines): 1 cosmetic flag (Copy-Paste Archipelago in legacy tests)
- **test_convergence_check.py** (1,289 lines): 1 cosmetic flag (parametrizable runner tests)
- **test_impact_graph.py** (983 lines): 0 flags. Strongest file — systematic coverage, corruption handling, stress tests
- **test_hooks.py** (531 lines): 0 flags. Clean subprocess integration testing

No real quality concerns in the mature test files.
</details>

**The predicted area — `test_pattern_brief_compact.py`:**

- 76 lines, 5 tests, all using well-formed `SAMPLE_BRIEF` with every field populated
- **Anti-pattern #5 (Happy Path Tourist):** No test for empty field values. No test for code-fenced pattern headers. These are exactly the edge cases that Predictions 1 and 3 say will trigger bugs.

**Finding: BH-003** — parse_brief has no edge case tests for empty fields or code fences (MEDIUM, test/shallow)

---

## Phase 3: Adversarial Code Audit (~140K tokens)

Source modules reviewed for bugs, error paths, boundary conditions. Predicted areas first.

### The moment of confirmation

**Testing Prediction 1 (HIGH confidence):**

```python
brief = '## PAT-001: test (Run 1, 2026-03-20)\n**What to look for:**\n**Detection heuristic:** `grep foo`\n'
entries = parse_brief(brief)
# entries[0].what_to_look_for == '**Detection heuristic:** `grep foo`'
# Expected: ''
```

**BUG CONFIRMED.** When a field has no value on its line, `\s*` consumed the newline and `(.*?)` with DOTALL captured the next field's entire content including its bold marker. The empty field silently stole content from the next field.

**Testing Prediction 3 (MEDIUM confidence):**

```python
brief = '## PAT-001: real (Run 1, 2026-03-20)\n...\n```\n## PAT-999: fake (Run 99, 2099-01-01)\n```\n'
entries = parse_brief(brief)
# len(entries) == 2 — PAT-999 inside code fence matched as real entry
```

**BUG CONFIRMED.** `parse_brief()` applied the header regex directly to content without masking. A pattern header inside a code example was matched as a real entry.

Both bugs are PAT-001/PAT-003 family — the same root cause classes that have appeared in runs 1, 2, 4, 6, and 11. The pattern library predicted them before a line of code was read.

**Findings:**
- **BH-004** — parse_brief field extraction leaks across fields on empty values (MEDIUM, bug/logic)
- **BH-005** — parse_brief matches pattern headers inside code fences (MEDIUM, bug/logic)

A subagent audited the remaining 9 source modules. 21 observations, 18 INFO/LOW. 3 concerns raised — 2 verified as false positives (correct behavior), 1 confirmed as negligible (hook `--graph=path` syntax).

---

## Pre-Phase 4: Adversarial Merge (~160K tokens)

Holtz and Justine audited independently. Now their findings merge.

### Classification

| Classification | Count | Items |
|----------------|-------|-------|
| **Agreement** | 2 | BH-001 (README metrics) + BJ-002; BH-002 (\\s convention) + BJ-004 |
| **Holtz-only** | 3 | BH-003 (test gap), BH-004 (regex leak), BH-005 (fence-unaware) |
| **Justine-only** | 3 | BH-006 (README ambiguity), BH-007 (hook paths), BH-008 (stall message) |
| **Severity disagreements** | 0 | — |
| **Contradictions** | 0 | — |

### Blind spot analysis

- **Holtz's blind spots:** Missed README line count ambiguity and hook design concerns. His depth-first focus on `pattern_brief_compact.py` meant breadth-level issues in hooks and README phrasing were overlooked.
- **Justine's blind spots:** Missed the actual code bugs. She found the `\s` convention violation and called it "functionally harmless" — she tested CRLF and cross-entry bleeding (wrong edge cases) instead of empty fields and code fences (right edge cases). Breadth-first found the symptom. Depth-first found the disease.

### Impact graph merge

- Holtz: 37 nodes, 35 edges
- Justine: 12 nodes, 12 edges
- Merged: **50 nodes, 50 edges**

**Merged worklist: 8 items (6 MEDIUM, 2 LOW)**

---

## Phase 4: TDD Fix Loop (~195K tokens)

Every fix starts with a failing test. Not after. Before.

### Commit 1: `f1b715b` — BH-003 + BH-004 + BH-005

**Step 1: Write the failing tests**

```python
def test_parse_brief_empty_field_value():
    """Field with no value on its line returns empty string, not next field's content."""
    brief = "## PAT-001: test-pattern (Run 1, 2026-03-20)\n**What to look for:**\n..."
    entries = pbc.parse_brief(brief)
    assert entries[0].what_to_look_for == ""  # FAILS: gets next field's content

def test_parse_brief_ignores_code_fenced_headers():
    """Pattern headers inside code fences are not matched as real entries."""
    brief = "...```\n## PAT-999: fake (Run 99, 2099-01-01)\n```\n..."
    assert "PAT-999" not in [e.pattern_id for e in pbc.parse_brief(brief)]  # FAILS
```

```
FAILED test_parse_brief_empty_field_value — got "**Detection heuristic:** ..."
FAILED test_parse_brief_ignores_code_fenced_headers — PAT-999 matched
2 failed, 5 deselected
```

**Step 2: Minimal fix**

```python
# Before (buggy)
header_re = re.compile(r'^## (PAT-\d+): (.+?) \((Run \d+), ...\)\s*$', re.MULTILINE)
matches = list(header_re.finditer(content))  # matches inside code fences

def _extract(field, _block=block):
    m = re.search(rf'\*\*{field}:\*\*\s*(.*?)(?=\n\*\*|\n##|\Z)', _block, re.DOTALL)
    #                                 ^^^ \s* matches \n on empty fields

# After (fixed)
from markdown_utils import mask_code_fences
_, masked = mask_code_fences(content)  # mask before matching
matches = list(header_re.finditer(masked))  # safe from code fence headers

def _extract(field, _block=block):
    m = re.search(rf'\*\*{field}:\*\*[ \t]*(.*?)(?=\n\*\*|\n##|\Z)', _block, re.DOTALL)
    #                                 ^^^^^^ [ \t]* stays on same line
```

```
322 passed in 2.61s ✓
```

### Commit 2: `e5e8b5b` — BH-001 + BH-002 + BH-006

Expanded `test_readme_metrics_match_actual` from 1 assertion to 10 (all 9 fields + line count with ±100 tolerance). Added `test_no_backslash_s_in_source_regex` to enforce the `[ \t]` convention. Updated README from "321 tests across 8,500 lines" to "324 tests across 8,600 lines of code".

```
324 passed in 2.67s | ruff clean | mypy clean ✓
```

### Commit 3: `cfcf762` — BH-007 + BH-008

Documented that hook `in` path matching is a design decision (Claude Code provides absolute or cwd-relative paths, making these specific path components safe). Changed stall detection from "STALLED" to "REGRESSING" when open items are growing.

```
324 passed in 2.66s | ruff clean | mypy clean ✓
```

---

## Convergence (~210K tokens)

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 321 | **324** |
| Tests failing | 0 | 0 |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Coverage | 67% | 67% |
| Punchlist open | — | **0** |
| Punchlist resolved | — | **8** |

### Prediction accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 2 | 1 | 50% |
| MEDIUM | 2 | 1 | 50% |
| LOW | 1 | 0 | 0% |
| **Total** | **5** | **2** | **40%** |

- Prediction 1 (HIGH, regex-newline-leak): **CONFIRMED** via BH-004
- Prediction 2 (MEDIUM, CRLF in header regex): UNCONFIRMED — `\s*$` correctly handles CRLF
- Prediction 3 (MEDIUM, code-fence-unaware): **CONFIRMED** via BH-005
- Prediction 4 (HIGH, README counts stale): UNCONFIRMED — counts were correct
- Prediction 5 (LOW, hook coverage): UNCONFIRMED — subprocess testing is adequate

### Token usage (real, from session history)

Context window size at each milestone, extracted from `~/.claude/` session logs:

| Phase | Context Window | Output Tokens | Wall Clock (UTC) |
|-------|---------------|---------------|-----------------|
| Session start | 31,707 | 25 | 05:20:47 |
| Phase 0 complete | 103,136 | — | 05:41:22 |
| Justine dispatched | 104,084 | 4 | 05:41:39 |
| Phase 1 complete | 131,282 | — | 05:46:05 |
| Phase 2 complete (BH-003) | 142,164 | — | 05:49:51 |
| Both bugs confirmed | 144,218 | — | 05:50:27 |
| Phase 3 complete | 155,261 | 2 | 05:56:57 |
| Merge complete | 174,760 | 2 | 06:00:30 |
| Fix loop: first commit | 190,661 | — | 06:04:24 |
| All 8 items fixed | 191,404 | — | 06:04:41 |
| **Run 14 converged** | **207,110** | **478** | **06:09:16** |

| Execution Context | Context Window | Output Tokens | Tool Calls | Duration |
|-------------------|---------------|---------------|------------|----------|
| **Holtz (main)** | **207,110** | ~73K total | 381 turns | ~49 min |
| **Justine (parallel subagent)** | **141,876** | — | 109 calls | ~15 min |
| **Total** | **348,986** | — | **490 turns** | — |

*Context window = input_tokens + cache_creation_input_tokens + cache_read_input_tokens per API call.
This is the number displayed in the Claude Code status bar.*

---

## Commits

```
f1b715b fix(scripts): mask code fences and fix \s regex in parse_brief
e5e8b5b fix(tests): expand README metrics test to validate all 9 fields
cfcf762 fix(hooks,scripts): document path matching design, distinguish stall vs regress
34eedec docs: complete Holtz run 14 — 8 findings, all resolved
```

28 files changed, 1,806 insertions, 322 deletions.

---

## What the pattern library caught

Both real bugs (BH-004 and BH-005) were in `pattern_brief_compact.py` — the newest and least-audited module in the codebase. Both are from known pattern families:

- **PAT-001 (code-fence-unaware parsing):** First discovered in run 1. Appeared in runs 1, 2, 4, and 6 with different disguises. Run 14 found it in a new module that was added after run 11 fixed the last instance. Same root cause, 5th manifestation.

- **PAT-003 (regex convention violation):** Discovered in run 11 when Justine's breadth-first scan caught 3 instances of `\s` where `[ \t]` was the project convention. Run 14 found `\s` in the newest module — the one added after run 11 enforced the convention everywhere else.

The pattern library's detection heuristic (`grep -rnP '\\s[*+?]'`) flagged both violations during recon, before Holtz read a single line of source code. The predictions said where to look. The reproduction tests proved the bugs were real. The pattern library is what makes each run smarter than the last.

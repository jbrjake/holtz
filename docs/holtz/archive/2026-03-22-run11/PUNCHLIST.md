# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 265 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 2    | 0        | 0        |
| LOW      | 5    | 0        | 0        |

## Patterns

## Items

### BH-001: Automate README metrics — recurring recommendation unaddressed
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** README.md:36
**Status:** OPEN

**Problem:** The recommendation "Automate README metrics" has appeared in 2 consecutive audit summaries (runs 9 and 10) without being implemented. Run 10's summary explicitly states "Will be escalated in run 11 if unaddressed." The README test count (265) and line count (8,118) have required manual updates in runs 9 and 10 after code changes caused drift.

**Evidence:** Run 9 SUMMARY.md: "Automate README metrics — Consider a CI step or pre-commit hook that validates test count and line count against README.md. First appearance." Run 10 SUMMARY.md: "Automate README metrics — test count and line count drift on every change. Second appearance (also in run 9). Will be escalated in run 11 if unaddressed."

**Discovery Chain:** Prior summary scan → "Automate README metrics" found in runs 9 and 10 → 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [ ] README metrics are validated automatically (CI step, pre-commit hook, or test)
- [ ] Validation: `grep -c "265 tests across 8,118 lines" README.md` matches and is checked automatically

**Validation Command:**
```bash
grep "265 tests" README.md && python -m pytest tests/ --co -q 2>/dev/null | tail -1
```

### BH-002: README says 13 reference docs, actual is 14
**Severity:** LOW
**Category:** doc/drift
**Location:** README.md:36
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 36 states "13 reference docs" but there are 14 .md files in `skills/holtz/references/`. The `recommendation-escalation.md` file was added but the README count was not updated.

**Evidence:** `ls skills/holtz/references/*.md | wc -l` returns 14. README says "13 reference docs". The 14th file is `recommendation-escalation.md`, added to support the recommendation escalation protocol.

**Discovery Chain:** Phase 1 component count verification → `ls` returns 14 reference docs → README says 13 → `recommendation-escalation.md` not counted in last README update

**Acceptance Criteria:**
- [ ] README reference doc count matches actual
- [ ] Validation: count matches

**Validation Command:**
```bash
grep "14 reference docs" README.md
```

### BH-003: artifact_verification.py regex fails on quoted paths with spaces
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/artifact_verification.py:29`
**Status:** OPEN
**Determinism:** theoretical
**Predicted:** Prediction 2 (confidence: MEDIUM)
**Lens:** component

**Problem:** The `--graph` path extraction regex `r'--graph\s+["\']?([^"\'\s]+)["\']?'` claims to handle quoted paths (the `["\']?` groups exist for this purpose) but the capture group `([^"\'\s]+)` stops at whitespace, so `--graph "docs/my project/impact-graph.json"` captures only `docs/my`.

**Evidence:** The regex character class `[^"\'\s]+` excludes spaces. For input `--graph "path with spaces/graph.json"`, the capture stops at the first space after `path`. The comment on line 28 says "handles quoted and unquoted paths" but the regex only handles quoted paths without spaces.

**Discovery Chain:** Adversarial hook audit → regex review → capture group excludes `\s` → quoted paths with spaces truncated → comment claim inaccurate

**Acceptance Criteria:**
- [ ] Regex correctly extracts paths from `--graph "path with spaces/file.json"`
- [ ] Existing unquoted path extraction still works
- [ ] Test covers the quoted-path-with-spaces case

**Validation Command:**
```bash
python -c "import re; m = re.search(r'--graph\s+[\"\\x27]([^\"\\x27]+)[\"\\x27]|--graph\s+(\S+)', '--graph \"docs/my project/graph.json\"'); print(m.group(1) or m.group(2))"
```

### BH-004: impact_graph_gate.py substring path match is order-dependent
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/impact_graph_gate.py:33-36`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** component

**Problem:** The gate uses substring matching where `"docs/holtz/audit/"` is a substring of `"docs/holtz/justine/audit/"`. The justine check (line 33) must come before the holtz check (line 35) — if reordered, justine audit writes would check the wrong graph file. This ordering dependency is undocumented and fragile.

**Evidence:** `"docs/holtz/audit/" in "docs/holtz/justine/audit/notes.md"` evaluates to `True`. The code works correctly because the justine check comes first in the if/elif chain, but there is no comment explaining why the order matters.

**Discovery Chain:** Adversarial hook audit → substring analysis → `"docs/holtz/audit/"` matches justine paths too → order-dependent correctness → no comment documenting this

**Acceptance Criteria:**
- [ ] Comment added explaining the ordering dependency
- [ ] OR refactored to use non-overlapping checks

**Validation Command:**
```bash
grep -A1 "justine/audit" hooks/impact_graph_gate.py | head -4
```

### BH-005: status_staleness_gate.py TOCTOU race on STATUS.md deletion
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `hooks/status_staleness_gate.py:56-60`
**Status:** OPEN
**Determinism:** intermittent
**Predicted:** Prediction 2 (confidence: MEDIUM)
**Lens:** error-propagation

**Problem:** If STATUS.md is deleted between the `os.path.isfile()` check (line 56) and `os.path.getmtime()` call (line 60), an unhandled `FileNotFoundError` crashes the hook. The crash produces exit code 1 (warn), which is acceptable but accidental — not an intentional degradation path.

**Evidence:** Lines 56-60: `if not os.path.isfile(status_path): exit_ok()` followed by `mtime = os.path.getmtime(status_path)`. No try/except around `getmtime`. The known limitation comment (lines 52-55) documents the deletion *bypass* but not the crash on race.

**Discovery Chain:** Adversarial hook audit → TOCTOU pattern between isfile and getmtime → FileNotFoundError unhandled → crash exit code 1 = accidental warn

**Acceptance Criteria:**
- [ ] `getmtime` wrapped in try/except for `OSError`
- [ ] On `FileNotFoundError`, hook calls `exit_ok()` (consistent with "file doesn't exist" logic)

**Validation Command:**
```bash
grep -A5 "os.path.getmtime" hooks/status_staleness_gate.py
```

### BH-006: update_risk accepts NaN delta, silently sets risk_score to 1.0
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:211-212`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 3 (confidence: MEDIUM)
**Lens:** component

**Problem:** When `update_risk()` receives `float('nan')` as delta, the arithmetic produces NaN but Python's `min(1.0, nan)` returns `1.0` (NaN comparisons always return False, so `min` returns its first arg). The result is `max(0.0, 1.0) = 1.0`. The node's risk_score is silently set to 1.0 regardless of its current value. The CLI exposes this directly: `python impact_graph.py update_risk node nan` is accepted by argparse.

**Evidence:** `python -c "print(max(0.0, min(1.0, float('nan'))))"` returns `1.0`. Any call to `update_risk(node_id, float('nan'))` silently sets risk_score to 1.0 instead of returning an error.

**Discovery Chain:** Adversarial code audit → float edge case analysis → NaN propagation through min/max → silent risk_score reset to 1.0

**Acceptance Criteria:**
- [ ] `update_risk` rejects NaN and inf delta values with an error
- [ ] Test verifies NaN rejection

**Validation Command:**
```bash
source .venv/bin/activate && python -c "import math; from impact_graph import ImpactGraph; g = ImpactGraph('/tmp/test.json'); g.add_node('x', 'function', 'f.py'); r = g.update_risk('x', float('nan')); print('error' in r)"
```

### BH-007: CLI --top accepts negative integers with counterintuitive results
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:323`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 3 (confidence: MEDIUM)
**Lens:** component

**Problem:** The `risk_hotspots` CLI subcommand accepts negative `--top` values without validation. Due to Python's negative slice semantics, `--top -1` on a 10-node graph returns 9 nodes (via `nodes[:-1]`), and `--top -10` returns 0 nodes. The user asked for a negative count and silently gets a different positive count.

**Evidence:** `python -c "print(list(range(10))[:-1])"` returns `[0, 1, 2, 3, 4, 5, 6, 7, 8]` — 9 items for --top -1.

**Discovery Chain:** CLI argument audit → --top has no lower bound → negative int accepted → Python slice semantics produce counterintuitive count

**Acceptance Criteria:**
- [ ] `--top` validated to be non-negative, or clamped to 0
- [ ] Test verifies negative --top handling

**Validation Command:**
```bash
source .venv/bin/activate && python -c "from impact_graph import ImpactGraph; g = ImpactGraph('/tmp/test.json'); print(len(g.risk_hotspots(top=-1)))"
```

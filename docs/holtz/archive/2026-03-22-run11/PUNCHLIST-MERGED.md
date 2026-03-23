# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 265 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 0    | 5        | 0        |
| LOW      | 0    | 8        | 0        |

## Patterns

## Pattern: PAT-003: regex-convention-violation
**Instances:** BH-009, BH-011, BH-013
**Root Cause:** \s used in regex where [ \t] is project convention. Established after initial dev; not all sites updated.
**Systemic Fix:** Replace \s with [ \t] in all non-line-start positions. Add grep check to CI.
**Detection Rule:** `grep -rnP '\\s[*+?]' --include='*.py' skills/ hooks/ | grep -v '^\s*#'`

## Items

### BH-001: Automate README metrics — recurring recommendation unaddressed
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** README.md:36
**Status:** RESOLVED
**Found by:** Holtz only
<!-- Was: Holtz BH-001 -->

**Problem:** The recommendation "Automate README metrics" has appeared in 2 consecutive audit summaries (runs 9 and 10) without being implemented.

**Evidence:** Run 9 and 10 SUMMARY.md both contain this recommendation. Run 10 explicitly states "Will be escalated in run 11 if unaddressed."

**Discovery Chain:** Prior summary scan → "Automate README metrics" found in runs 9 and 10 → 2+ appearances triggers escalation

**Acceptance Criteria:**
- [ ] README metrics validated automatically (CI step, pre-commit hook, or test)
- [ ] Validation: metric check runs on CI

**Validation Command:**
```bash
grep "265 tests" README.md && python -m pytest tests/ --co -q 2>/dev/null | tail -1
```

### BH-002: README says 13 reference docs, actual is 14
**Severity:** LOW
**Category:** doc/drift
**Location:** README.md:36
**Status:** RESOLVED
**Found by:** Holtz only
**Predicted:** Prediction 1 (confidence: HIGH)
<!-- Was: Holtz BH-002 -->

**Problem:** README says "13 reference docs" but there are 14. recommendation-escalation.md was not counted.

**Evidence:** `ls skills/holtz/references/*.md | wc -l` returns 14.

**Discovery Chain:** Phase 1 count verification → ls returns 14 → README says 13

**Acceptance Criteria:**
- [ ] README reference doc count matches actual

**Validation Command:**
```bash
grep "14 reference docs" README.md
```

### BH-003: artifact_verification.py regex fails on quoted paths with spaces
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/artifact_verification.py:29`
**Status:** RESOLVED
**Determinism:** theoretical
**Found by:** Holtz only
**Predicted:** Prediction 2 (confidence: MEDIUM)
<!-- Was: Holtz BH-003 -->

**Problem:** The regex `([^"\'\s]+)` stops at spaces, so `--graph "path with spaces/file.json"` captures only `path`.

**Evidence:** The capture group excludes whitespace. Practically safe since Holtz paths don't contain spaces.

**Discovery Chain:** Adversarial hook audit → regex review → capture excludes spaces → quoted-path truncation

**Acceptance Criteria:**
- [ ] Regex correctly handles quoted paths with spaces
- [ ] Test covers the case

**Validation Command:**
```bash
python -c "import re; m = re.search(r'--graph\s+[\"\\x27]([^\"\\x27]+)[\"\\x27]|--graph\s+(\S+)', '--graph \"docs/my project/graph.json\"'); print(m.group(1) or m.group(2))"
```

### BH-004: impact_graph_gate substring match order-dependent
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/impact_graph_gate.py:33-36`
**Status:** RESOLVED
**Found by:** Holtz only
<!-- Was: Holtz BH-004 -->

**Problem:** `"docs/holtz/audit/"` is substring of `"docs/holtz/justine/audit/"`. Justine check must come first. Undocumented ordering dependency.

**Evidence:** Reordering the if/elif breaks justine gating.

**Discovery Chain:** Adversarial hook audit → substring analysis → order-dependent correctness → no comment

**Acceptance Criteria:**
- [ ] Comment explaining ordering dependency, or refactored to non-overlapping checks

**Validation Command:**
```bash
grep -A1 "justine/audit" hooks/impact_graph_gate.py | head -4
```

### BH-005: status_staleness_gate TOCTOU race on STATUS.md deletion
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `hooks/status_staleness_gate.py:56-60`
**Status:** RESOLVED
**Determinism:** intermittent
**Found by:** Holtz only
**Predicted:** Prediction 2 (confidence: MEDIUM)
<!-- Was: Holtz BH-005 -->

**Problem:** If STATUS.md deleted between isfile (line 56) and getmtime (line 60), unhandled FileNotFoundError crashes the hook.

**Evidence:** No try/except around getmtime.

**Discovery Chain:** TOCTOU pattern → isfile/getmtime gap → FileNotFoundError unhandled

**Acceptance Criteria:**
- [ ] getmtime wrapped in try/except OSError, calls exit_ok on FileNotFoundError

**Validation Command:**
```bash
grep -A5 "os.path.getmtime" hooks/status_staleness_gate.py
```

### BH-006: update_risk accepts NaN delta, silently sets risk_score to 1.0
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:211-212`
**Status:** RESOLVED
**Determinism:** deterministic
**Found by:** Holtz only
**Predicted:** Prediction 3 (confidence: MEDIUM)
<!-- Was: Holtz BH-006 -->

**Problem:** NaN delta doesn't propagate (Python min/max behavior) but silently sets risk_score to 1.0 regardless of current value. CLI accepts `nan` via argparse float().

**Evidence:** `max(0.0, min(1.0, float('nan'))) == 1.0`. The clamping prevents data corruption but produces wrong results silently.

**Discovery Chain:** Float edge case analysis → NaN through min/max → silent reset to 1.0

**Acceptance Criteria:**
- [ ] update_risk rejects NaN/inf delta with error
- [ ] Test verifies rejection

**Validation Command:**
```bash
source .venv/bin/activate && python -c "import math; from impact_graph import ImpactGraph; g = ImpactGraph('/tmp/t.json'); g.add_node('x','function','f.py'); r = g.update_risk('x', float('nan')); print('error' in r)"
```

### BH-007: CLI --top accepts negative integers with counterintuitive results
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:323`
**Status:** RESOLVED
**Determinism:** deterministic
**Found by:** Holtz only
**Predicted:** Prediction 3 (confidence: MEDIUM)
<!-- Was: Holtz BH-007 -->

**Problem:** `--top -1` on 10 nodes returns 9 nodes via Python negative slice semantics.

**Evidence:** `list(range(10))[:-1]` returns 9 items.

**Discovery Chain:** CLI argument audit → no lower bound → negative slice semantics

**Acceptance Criteria:**
- [ ] --top clamped to max(0, value) or validated

**Validation Command:**
```bash
source .venv/bin/activate && python -c "from impact_graph import ImpactGraph; g = ImpactGraph('/tmp/t.json'); print(len(g.risk_hotspots(top=-1)))"
```

### BH-008: impact_graph_gate enforcement scope narrower than documented requirement
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/impact_graph_gate.py:33`
**Status:** RESOLVED
**Found by:** Justine only
<!-- Was: Justine BJ-001 -->
**Severity disagreement:** Holtz=MEDIUM, Justine=HIGH

**Problem:** The hook only gates writes to `docs/holtz/audit/` but the HARD-GATE requires gating ALL Phase 1+ output including PUNCHLIST.md. Commented as "Known limitation" at line 30-32. Already documented in run 10 as BH-009.

**Evidence:** `else: exit_ok()` allows PUNCHLIST.md writes ungated.

**Discovery Chain:** SKILL.md HARD-GATE → hook only gates audit/ → PUNCHLIST.md bypasses

**Acceptance Criteria:**
- [ ] Hook also gates PUNCHLIST.md, PUNCHLIST-MERGED.md, and investigations/ writes
- [ ] Test verifies PUNCHLIST.md gating

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestImpactGraphGate -v
```

### BH-009: \s+ in Jest/Vitest/Cargo parser regexes violates [ \t] convention
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:143,163,180`
**Status:** RESOLVED
**Pattern:** PAT-003
**Found by:** Justine only
<!-- Was: Justine BJ-003 -->

**Problem:** Three test runner parsers use `\s` where project convention specifies `[ \t]`. Semantically wrong for horizontal whitespace, practically safe.

**Evidence:** Lines 143 (Jest), 163 (Vitest), 180 (Cargo) use `\s+` or `\s*`. Architecture baseline: "All regex in source uses `[ \t]` not `\s`."

**Discovery Chain:** Pattern library match (regex-newline-leak) → grep hit → baseline convention → violation confirmed

**Acceptance Criteria:**
- [ ] All three parsers use `[ \t]` instead of `\s`

**Validation Command:**
```bash
grep -n '\\s' skills/holtz/scripts/convergence_check.py | grep -v '^\s*#'
```

### BH-010: status_staleness_gate bypass on STATUS.md deletion
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/status_staleness_gate.py:56`
**Status:** RESOLVED
**Found by:** Justine only
<!-- Was: Justine BJ-002 -->
**Severity disagreement:** Holtz=MEDIUM, Justine=HIGH

**Problem:** Deleting STATUS.md mid-run disables all staleness enforcement. Documented as "Known limitation" at lines 53-55. Already documented in run 10 as BH-008.

**Evidence:** `if not os.path.isfile(status_path): exit_ok()` can't distinguish first-write from deletion.

**Discovery Chain:** Prior run 10 finding → code still has same bypass → deletion disables enforcement

**Acceptance Criteria:**
- [ ] Hook checks for sibling artifacts (recon/, PUNCHLIST.md) to distinguish first-write from deletion

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestStatusStalenessGate -v
```

### BH-011: \s+ in artifact_verification.py violates [ \t] convention
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/artifact_verification.py:29`
**Status:** RESOLVED
**Pattern:** PAT-003
**Found by:** Justine only
<!-- Was: Justine BJ-004 -->

**Problem:** `\s+` in `--graph\s+` regex violates project [ \t] convention. Harmless since shell commands are single-line.

**Evidence:** `hooks/artifact_verification.py:29`: `--graph\s+`.

**Discovery Chain:** Pattern library match → grep hit → convention violation

**Acceptance Criteria:**
- [ ] Regex uses `[ \t]+` instead of `\s+`

**Validation Command:**
```bash
grep -n '\\s' hooks/artifact_verification.py
```

### BH-012: detect_test_runner dict ordering as implicit priority
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:76`
**Status:** RESOLVED
**Found by:** Justine only
<!-- Was: Justine BJ-005 -->

**Problem:** Runner detection priority depends on dict insertion order (CPython 3.7+ guaranteed). Tests exist for pytest>jest and jest>vitest, but ordering dependency is undocumented and fragile.

**Evidence:** Reordering dict entries silently changes priority. Two tests verify ordering but don't prevent regression.

**Discovery Chain:** Prior run 9 finding → code unchanged → dict ordering is implicit priority

**Acceptance Criteria:**
- [ ] Comment explicitly documents that dict ordering IS the priority

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "priority" -v
```

### BH-013: \s in ENTITY_PATTERNS violates [ \t] convention (safe)
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/impact_graph.py:26-36`
**Status:** RESOLVED
**Pattern:** PAT-003
**Found by:** Justine only
<!-- Was: Justine BJ-008 -->

**Problem:** 9 regex patterns use `\s`. Applied per-line via splitlines(), so newlines can't match. Convention violation only.

**Evidence:** Lines 26-36 contain `\s`. Patterns applied at line 277 via `content.splitlines()`.

**Discovery Chain:** Grep found \s → checked usage → per-line via splitlines → safe but convention violation

**Acceptance Criteria:**
- [ ] Replace \s with [ \t] in ENTITY_PATTERNS

**Validation Command:**
```bash
grep -c '\\\\s' skills/holtz/scripts/impact_graph.py
```

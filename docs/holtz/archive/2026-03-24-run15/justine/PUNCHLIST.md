# Justine Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 595 pass, 9 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1 | 0 | 0 |
| HIGH | 5 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

## Pattern: PAT-001: Code-Fence-Unaware Parsing
**Instances:** BJ-002, BJ-003, BJ-004
**Root Cause:** Regex applied to full document content without masking code fences first. Fenced examples match patterns meant for the structural layer.
**Systemic Fix:** All STATUS.md/PUNCHLIST.md parsing should use mask_code_fences() from markdown_utils.py before applying field-extraction regex.
**Detection Rule:** `grep -rn 're\.\(search\|findall\).*content' hooks/`

## Items

### BJ-001: test_commit_msg_hook.py references deleted git-hooks/commit-msg
**Severity:** CRITICAL
**Category:** test/bogus
**Location:** `tests/test_commit_msg_hook.py:7`
**Status:** OPEN
**Predicted:** Prediction J3 (confidence: HIGH)
**Lens:** integration

**Problem:** `HOOK_PATH = Path(__file__).parent.parent / "git-hooks" / "commit-msg"` references a file deleted in commit b412c16. The hook was renamed to `git-hooks/post-commit`. All 9 version-bump tests create dangling symlinks, so the hook never fires and versions never bump. 9 of 18 tests fail. The remaining 9 ("NoBump" and "Guards") pass vacuously because they assert the version is unchanged, which is trivially true when no hook runs.

**Evidence:** Line 7: `HOOK_PATH = Path(__file__).parent.parent / "git-hooks" / "commit-msg"`. File `git-hooks/commit-msg` does not exist. `git-hooks/post-commit` is the actual hook. Test suite: 9 FAILED, 9 passed (vacuously).

**Discovery Chain:** 9 test failures in baseline → `HOOK_PATH` points to deleted file → symlink to nowhere → hook never fires → bump tests fail, no-bump tests pass vacuously

**Acceptance Criteria:**
- [ ] `HOOK_PATH` updated to `git-hooks/post-commit`
- [ ] Hook destination in `_setup_git_repo` changed from `commit-msg` to `post-commit`
- [ ] All 18 tests pass (9 bump tests verify correct versions, 9 no-bump tests verify unchanged versions)
- [ ] No-bump tests confirmed to pass because the hook correctly skips, not because the hook is absent

**Validation Command:**
```bash
python -m pytest tests/test_commit_msg_hook.py -v
```

### BJ-002: convergence_gate.py parses STATUS.md without masking code fences
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/convergence_gate.py:89`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Predicted:** Prediction J1 (confidence: HIGH)
**Lens:** integration

**Problem:** `re.search(r'\*\*Status:\*\*[ \t]*(.*)', content)` matches the first `**Status:**` in unmasked content. If a code fence containing `**Status:** CONVERGED` appears before the real `**Status:** IN PROGRESS` field, the gate reads CONVERGED and allows a premature stop. This is a gate bypass — the enforcement hook that exists to prevent premature stops can be bypassed by document content.

**Evidence:** Reproduction test: STATUS.md with a code fence example containing `**Status:** CONVERGED` before the real `**Status:** IN PROGRESS` field causes `re.search` to return CONVERGED. The gate then calls `exit_stop_allow()`, permitting a premature stop during an active audit.

**Discovery Chain:** code-fence-unaware-parsing pattern match → convergence_gate.py uses bare regex on content → reproduction confirms re.search returns fenced CONVERGED before real IN PROGRESS → gate bypass

**Acceptance Criteria:**
- [ ] STATUS.md content is fence-masked before field extraction regex runs
- [ ] Test: STATUS.md with `**Status:** CONVERGED` inside a code fence and `**Status:** IN PROGRESS` outside still blocks stop
- [ ] Test: STATUS.md with `**Phase:** 6` inside a code fence and `**Phase:** 4` outside still reads Phase 4

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergenceGate -v -k fence
```

### BJ-003: convergence_primer.py parses STATUS.md without masking code fences
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/convergence_primer.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Predicted:** Prediction J2 (confidence: HIGH)
**Lens:** integration

**Problem:** `_read_status_fields` uses bare `re.search` on unmasked STATUS.md content to extract Phase, Step, and Status fields. A code fence containing these fields before the real fields would inject wrong values into the resume context.

**Evidence:** Same regex pattern as BJ-002. `re.search(rf'\*\*{field}:\*\*[ \t]*(.*)', content)` iterates over (Phase, Step, Status) and matches the first occurrence. If a fenced example appears first, the primer injects misleading resume context.

**Discovery Chain:** Same root cause as BJ-002 → convergence_primer uses identical parsing → both hooks assume STATUS.md has no fenced examples before real fields

**Acceptance Criteria:**
- [ ] STATUS.md content is fence-masked before field extraction regex runs
- [ ] Test: STATUS.md with fenced `**Phase:** 6` before real `**Phase:** 4` reads Phase 4
- [ ] Test: Next Action extraction unaffected by fenced content

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergencePrimer -v -k fence
```

### BJ-004: Convergence hook tests lack code-fence adversarial cases
**Severity:** HIGH
**Category:** test/shallow
**Location:** `tests/test_hooks.py:588-827`
**Status:** OPEN
**Pattern:** PAT-001
**Predicted:** Prediction J6 (confidence: HIGH)
**Lens:** integration

**Problem:** All 24 convergence hook tests use clean markdown fixtures without code fences. The code-fence bypass vulnerability (BJ-002, BJ-003) is not tested. The tests verify correct behavior on well-formed input but never test the adversarial case that the hooks are supposed to protect against.

**Evidence:** Read all fixtures in `TestConvergenceGate._make_status` and `TestConvergencePrimer._make_status`. Both generate clean markdown: `**Phase:** N\n**Status:** VALUE`. No fixture includes triple-backtick code fences.

**Discovery Chain:** BJ-002/BJ-003 confirmed → checked test fixtures for adversarial cases → no code fence fixtures exist → tests pass on clean input, miss the bypass

**Acceptance Criteria:**
- [ ] At least one TestConvergenceGate test with `**Status:** CONVERGED` inside a code fence before the real Status field, asserting the hook still blocks
- [ ] At least one TestConvergencePrimer test with fenced fields before real fields, asserting the primer reads the real values
- [ ] Tests pass after BJ-002/BJ-003 fixes are applied

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -v -k fence
```

### BJ-005: README "13,302 lines of code" claim is stale
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:190`
**Status:** OPEN
**Predicted:** Prediction J4 (confidence: HIGH)
**Lens:** public-contract

**Problem:** README "What's inside" section claims "604 tests across 13,302 lines of code." The 604 test count is correct. The 13,302 line count is stale. Current Python line count is 15,662 (excluding .venv, docs/runs). No counting method yields 13,302 for the current codebase.

**Evidence:** `find . -name '*.py' -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/docs/runs/*' -not -path '*/docs/holtz/*' -exec wc -l {} + | tail -1` = 15,662 total. README line 190: "604 tests across 13,302 lines of code."

**Discovery Chain:** README claims 13,302 lines → direct measurement shows 15,662 Python lines → 18% drift → no counting method matches 13,302

**Acceptance Criteria:**
- [ ] Line count in README updated to reflect actual current count
- [ ] Counting method documented (which files are included/excluded) so future audits can reproduce

**Validation Command:**
```bash
grep -n "lines of code" README.md
```

### BJ-006: NoBump and Guards tests pass vacuously due to broken hook
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_commit_msg_hook.py:110-182`
**Status:** OPEN
**Predicted:** Prediction J7 (confidence: HIGH)
**Lens:** component

**Problem:** The 9 passing tests in `TestNoBump` and `TestGuards` assert that the version is unchanged after commits with non-bumping prefixes (docs, chore, refactor, etc.) or guard conditions. These tests pass, but they pass because the hook never fires (dangling symlink), not because the hook correctly identifies non-bumping commits. They are rubber stamps — they would pass even if the hook logic were completely wrong, because no hook runs at all.

**Evidence:** `TestNoBump.test_docs_no_bump` asserts `_get_version(repo) == "0.4.0"` after a `docs:` commit. This passes because `HOOK_PATH` points to `git-hooks/commit-msg` which doesn't exist, so no hook fires, so the version never changes. If the hook were installed correctly (pointing to `post-commit`), this test would STILL pass — but it would be testing the hook's skip logic rather than testing nothing.

**Discovery Chain:** BJ-001 shows hook is broken → NoBump tests assert "version unchanged" → this is trivially true when no hook fires → tests pass for the wrong reason → they are not testing what they claim to test

**Acceptance Criteria:**
- [ ] After BJ-001 fix, all NoBump tests still pass (confirming the hook correctly skips non-bumping commits)
- [ ] After BJ-001 fix, the Guards test still passes (confirming the hook correctly handles manual version edits)

**Validation Command:**
```bash
python -m pytest tests/test_commit_msg_hook.py::TestNoBump tests/test_commit_msg_hook.py::TestGuards -v
```

### BJ-007: convergence_gate._count_open_items inflated by code fence examples
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/convergence_gate.py:45-46`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Predicted:** Prediction J5 (confidence: MEDIUM)
**Lens:** data-flow

**Problem:** `_count_open_items` counts `**Status:** OPEN` and `**Status:** IN PROGRESS` via bare regex on unmasked punchlist content. Code fence examples containing these status fields inflate the count. The docstring explicitly notes this count is "informational, not decisional" — the gate decision is based on STATUS.md and SUMMARY.md existence, not this count.

**Evidence:** Reproduction test: punchlist with `**Status:** OPEN` inside a code fence and `**Status:** RESOLVED` outside returns open_count=1 when real open count is 0.

**Discovery Chain:** PAT-001 pattern scan → _count_open_items uses same bare regex → reproduction confirms inflation → but docstring says "informational, not decisional" → severity capped at MEDIUM

**Acceptance Criteria:**
- [ ] Either: mask code fences before counting, OR: document the limitation more prominently
- [ ] Test: punchlist with fenced `**Status:** OPEN` example does not inflate the reported count (if fix chosen)

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergenceGate -v -k count
```

### BJ-008: Architecture baseline drift — CLAUDE.md and convergence hooks not in baseline
**Severity:** LOW
**Category:** doc/drift
**Location:** `docs/holtz/architecture-baseline.md`
**Status:** OPEN
**Predicted:** Prediction J8 (confidence: HIGH)
**Lens:** contract

**Problem:** The architecture baseline (established 2026-03-22) states "No CLAUDE.md or ARCHITECTURE.md exists" but CLAUDE.md was added in d8e4064. The Module Dependencies table does not include convergence_gate.py or convergence_primer.py. These are structural drift items — the baseline no longer describes the actual project structure.

**Evidence:** Baseline line 13: "No CLAUDE.md or ARCHITECTURE.md exists." CLAUDE.md is at project root. Baseline Module Dependencies table (lines 50-61) has 8 entries; convergence_gate.py and convergence_primer.py are absent.

**Discovery Chain:** Holtz recon 0a noted drift → Justine verified by reading baseline → CLAUDE.md exists, 2 hooks missing from table → baseline is stale

**Acceptance Criteria:**
- [ ] Holtz updates baseline (Justine does not own this document per skill spec)

**Validation Command:**
```bash
grep -n "CLAUDE.md" docs/holtz/architecture-baseline.md
```

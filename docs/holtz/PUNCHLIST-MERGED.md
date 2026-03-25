# Holtz Punchlist (Merged)
> Generated: 2026-03-24 | Project: holtz | Baseline: 595 pass, 9 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 4 | 0 |
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 1 | 0 |

## Patterns

## Pattern: PAT-001: Code-Fence-Unaware Parsing
**Instances:** BH-003, BH-004, BH-005, BH-006
**Root Cause:** Regex applied to full document content without masking code fences first. Project convention (validate_punchlist.py, convergence_check.py) requires masking via mask_code_fences() before field extraction. New hooks didn't follow this convention.
**Systemic Fix:** Added mask_fenced_blocks() to _common.py and updated both convergence hooks to mask before field extraction.
**Detection Rule:** `grep -rn 're\.\(search\|findall\).*content' hooks/ | grep -v mask`

## Items

### BH-001: test_commit_msg_hook.py references deleted git-hooks/commit-msg
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_commit_msg_hook.py:7`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** Commit b412c16 replaced `git-hooks/commit-msg` with `git-hooks/post-commit` but did not update `test_commit_msg_hook.py`. Tests create a dangling symlink. All 9 version-bumping tests fail. The 9 no-bump tests pass vacuously.

**Evidence:** HOOK_PATH pointed to non-existent git-hooks/commit-msg. Hook installed as commit-msg instead of post-commit.

**Discovery Chain:** 9 test failures in baseline → all in test_commit_msg_hook.py → HOOK_PATH points to git-hooks/commit-msg → file deleted in b412c16, replaced by post-commit

**Acceptance Criteria:**
- [x] HOOK_PATH updated to `git-hooks/post-commit`
- [x] Hook destination changed from `commit-msg` to `post-commit`
- [x] All 18 tests pass
- [x] `python -m pytest tests/test_commit_msg_hook.py -q` shows 0 failures

**Validation Command:**
```bash
python -m pytest tests/test_commit_msg_hook.py --tb=short -q
```

**Resolution:** Updated HOOK_PATH to git-hooks/post-commit, hook destination to post-commit, updated Guards test to match post-commit behavior (bumps from disk version instead of skipping). 18/18 pass.

### BH-002: No test for REGRESSING label in stall detection
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `skills/holtz/scripts/convergence_check.py:371`
**Status:** RESOLVED

**Problem:** Stall detection distinguishes STALLED from REGRESSING but only the STALLED path was tested.

**Evidence:** `label = "REGRESSING" if open_items > first_open else "STALLED"` — no test for the REGRESSING case.

**Discovery Chain:** Run 14 recommendation → grep for REGRESSING in tests → no assertion found → untested code path

**Acceptance Criteria:**
- [x] A test exists where open items grow across 4+ iterations
- [x] The test asserts "REGRESSING" appears in the message (not "STALLED")
- [x] The test verifies the open item count is reported in the message

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "regress" --tb=short -q
```

**Resolution:** Added test_regressing_detection_when_open_items_grow with 4 iterations of growing open items (2→3→4→5). Asserts REGRESSING label and "5 items remain open".

### BH-003: convergence_gate.py parses STATUS.md without masking code fences
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/convergence_gate.py:89`
**Status:** RESOLVED
**Pattern:** PAT-001

**Problem:** Used bare regex on STATUS.md without masking code fences. Inconsistent with project convention.

**Evidence:** hooks/convergence_gate.py did not import mask_code_fences.

**Discovery Chain:** Global pattern library: code-fence-unaware-parsing → convergence_gate.py uses bare regex → project convention requires masking

**Acceptance Criteria:**
- [x] Import mask_fenced_blocks and mask STATUS.md content before regex
- [x] Test: STATUS.md with fenced `**Status:** CONVERGED` before real `**Status:** IN PROGRESS` still blocks

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergenceGate -v -k fence
```

**Resolution:** Added mask_fenced_blocks() to _common.py. convergence_gate.py now masks content before field extraction and item counting.

### BH-004: convergence_primer.py parses STATUS.md without masking code fences
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/convergence_primer.py:33`
**Status:** RESOLVED
**Pattern:** PAT-001

**Problem:** Same as BH-003 but for the primer hook.

**Evidence:** hooks/convergence_primer.py did not import mask_fenced_blocks.

**Discovery Chain:** Same root cause as BH-003

**Acceptance Criteria:**
- [x] Import mask_fenced_blocks and mask STATUS.md content before regex
- [x] Test: fenced fields before real fields yields correct values

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergencePrimer -v -k fence
```

**Resolution:** convergence_primer.py now masks content before field extraction.

### BH-005: Convergence hook tests lack code-fence adversarial fixtures
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_hooks.py:588-827`
**Status:** RESOLVED
**Pattern:** PAT-001

**Problem:** All 24 convergence hook tests used clean markdown fixtures. No adversarial fence cases.

**Evidence:** No triple-backtick code fences in any fixture.

**Discovery Chain:** BH-003/BH-004 found → test fixtures checked → no adversarial cases

**Acceptance Criteria:**
- [x] At least one convergence_gate test with fenced `**Status:** CONVERGED` + real `**Status:** IN PROGRESS` → blocks
- [x] At least one convergence_primer test with fenced fields + real fields → reads real values

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -v -k fence
```

**Resolution:** Added 3 adversarial tests: test_fence_does_not_bypass_gate, test_fence_does_not_inflate_open_count, test_fence_does_not_mislead_primer. All pass.

### BH-006: _count_open_items informational count inflated by code fences
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/convergence_gate.py:45-46`
**Status:** RESOLVED
**Pattern:** PAT-001

**Problem:** _count_open_items counted via bare regex. Developer documented as "informational, not decisional."

**Evidence:** Docstring line 31 documented the limitation.

**Discovery Chain:** PAT-001 scan → _count_open_items uses bare regex → docstring documented limitation

**Acceptance Criteria:**
- [x] Mask code fences before counting
- [x] Test: punchlist with fenced `**Status:** OPEN` example does not inflate count

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestConvergenceGate -v -k count
```

**Resolution:** _count_open_items now masks content via mask_fenced_blocks() before counting. Adversarial test confirms fenced items are not counted.

### BH-007: convergence_check.py CLI silently accepts nonexistent punchlist paths
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:394`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** `main()` uses bare `sys.argv[1]` with no argument parsing. Flags like `--punchlist` are treated as filenames. When the resulting path doesn't exist, the script warns to stderr but proceeds with an empty punchlist — 0 open items. An empty punchlist + passing tests will eventually declare false convergence, allowing Holtz to stop while real items remain open.

Additionally, the default path is `docs/holtz/PUNCHLIST.md` but after Justine merge the worklist is `PUNCHLIST-MERGED.md`. There's no logic to prefer the merged punchlist when it exists.

**Evidence:**
```python
# convergence_check.py:394
punchlist_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/holtz/PUNCHLIST.md")
```
Running `convergence_check.py --punchlist docs/holtz/PUNCHLIST-MERGED.md` sets path to `--punchlist` (non-existent file), silently falls back to empty punchlist, and records a poisoned history entry showing 0 open items.

**Discovery Chain:** Ran convergence_check with `--punchlist` flag → script treated it as filename → "punchlist not found" warning → empty punchlist recorded → would eventually declare false convergence → realized the convergence tool itself has a silent data integrity bug

**Acceptance Criteria:**
- [ ] Script uses argparse or equivalent for CLI argument parsing
- [ ] Unknown flags cause an error exit, not silent fallback
- [ ] When no path is provided, prefer PUNCHLIST-MERGED.md over PUNCHLIST.md if the merged file exists
- [ ] Non-existent punchlist path causes a hard error (exit 1), not a warning + empty fallback
- [ ] Tests verify all four conditions

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "cli" --tb=short -q
```

### BH-008: SKILL.md lacks convergence verification gate — process allows self-declared convergence
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `skills/holtz/SKILL.md` Phase 6
**Status:** RESOLVED

**Problem:** The SKILL.md convergence protocol says "Run convergence_check.py. If CONVERGED, write SUMMARY.md and stop." But there is no hard gate requiring convergence_check.py to actually return exit code 0 before SUMMARY.md can be written. The auditor can run convergence_check.py, see it return exit code 1 ("not converged"), and write SUMMARY.md anyway — which is exactly what happened in this run.

The convergence gate hook (`hooks/convergence_gate.py`) blocks premature *stops* but not premature *SUMMARY.md writes*. An auditor who writes SUMMARY.md before convergence is not stopped by any enforcement mechanism — and once SUMMARY.md exists, the convergence gate allows the stop.

**Evidence:** Run 15: convergence_check.py returned exit 1 ("not enough data points"). Auditor wrote SUMMARY.md anyway. Convergence gate saw SUMMARY.md and allowed the stop. No mechanism prevented this.

**Discovery Chain:** Auditor declared convergence without convergence_check passing → convergence gate allowed stop because SUMMARY.md existed → realized the gate checks for SUMMARY.md existence but not whether convergence was actually verified → the gate trusts an artifact that the auditor controls

**Acceptance Criteria:**
- [ ] SKILL.md Phase 6 includes explicit language: "convergence_check.py MUST return exit 0 before SUMMARY.md is written. If it returns non-zero, do NOT write SUMMARY.md — update STATUS.md and tell the user to /clear."
- [ ] Add to Rationalization Red Flags: "All items are resolved, I can skip convergence" → "Convergence requires the checker to say so. Resolved items can introduce new issues."
- [ ] Consider: convergence gate could verify HISTORY.json shows a CONVERGED entry, not just that SUMMARY.md exists

**Validation Command:**
```bash
grep -n "convergence_check.py MUST" skills/holtz/SKILL.md
```

### BH-009: SKILL.md does not specify exact convergence_check.py invocation
**Severity:** HIGH
**Category:** doc/drift
**Location:** `skills/holtz/SKILL.md` Phase 6
**Status:** RESOLVED

**Problem:** SKILL.md says "Run convergence_check.py" but does not specify the exact command, argument format, or how to pass the punchlist path. The script uses bare `sys.argv[1]` (positional arg), but there's no documentation of this interface. The auditor invented `--punchlist` and `--run-tests` flags that don't exist, causing silent data corruption.

Additionally, after a Justine merge, the worklist is PUNCHLIST-MERGED.md but the script defaults to PUNCHLIST.md. The SKILL.md Phase 6 "Filtered reads in convergence loop" section references `<punchlist-path>` without specifying how this maps to the convergence_check.py invocation.

**Evidence:** SKILL.md Phase 6 says:
```
1. Run `convergence_check.py`. If **CONVERGED**, write `docs/holtz/SUMMARY.md` and stop.
```
No argument specification. convergence_check.py takes `sys.argv[1]` as the punchlist path. The mismatch between SKILL.md's vague instruction and the script's undocumented interface caused 2 poisoned history entries.

**Discovery Chain:** Auditor called convergence_check.py with invented flags → flags silently treated as filenames → SKILL.md doesn't specify the correct invocation → no way for a fresh-context auditor to know the right command without reading source code

**Acceptance Criteria:**
- [ ] SKILL.md Phase 6 specifies the exact convergence_check.py invocation, including punchlist path argument
- [ ] Example: `python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/convergence_check.py docs/holtz/PUNCHLIST-MERGED.md` (or PUNCHLIST.md if no merge)
- [ ] The convergence boundary protocol section includes the full command

**Validation Command:**
```bash
grep -n "convergence_check.py" skills/holtz/SKILL.md | grep -v "^#"
```

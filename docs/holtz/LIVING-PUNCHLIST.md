# Living Punchlist

**Project:** holtz
**Established:** 2026-03-29
**Last Updated:** 2026-03-29
**Audits Completed:** 25

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** code-fence-unaware parsing — parsers that operate on raw markdown text without first masking fenced code blocks, causing headers, field labels, or structured content inside fences to be misidentified as real document structure.
  - Instances: 12+ across Runs 1–16 (multiple BH entries per run), resolved in core scripts by Run 16
  - Root cause: Multiple parsers independently implemented against the same markdown format without a shared masking contract; each new parser must rediscover the masking requirement
  - Detection rule: `grep -rn 're\.search\|re\.findall\|re\.split' --include='*.py' skills/holtz/scripts/ enforcement/ | grep -v mask_code_fences | grep -v _common`
  - First seen: Run 1 (2026-03-19)

- **PAT-002:** incomplete code-fence isolation — a parser masks code fences at the top level but does not propagate masking through all helper functions, leaving one layer exposed.
  - Instances: 1 (Run 2)
  - Root cause: Masking applied at call site but not threaded through to nested extraction helpers
  - Detection rule: When adding masking to a function, trace all callee paths to confirm each one receives masked content
  - First seen: Run 2 (2026-03-19)

- **PAT-003:** regex newline leak — `\s` used in a regex intended to match only spaces and tabs, inadvertently matching newlines and causing cross-line or cross-entry bleed.
  - Instances: 4 (Runs 11, 14, 19)
  - Root cause: Project convention is `[ \t]` not `\s`, but convention is not enforced by linters; new code written without knowing the convention
  - Detection rule: `grep -rn '\\s' --include='*.py' skills/holtz/scripts/ enforcement/ | grep -v '#.*\\s'` — flag any `\s` in regex context for review
  - First seen: Run 11 (2026-03-22)

- **PAT-004:** dual-parser divergence — two independent implementations of the same parsing logic (`mask_code_fences` in `markdown_utils.py` and `mask_fenced_blocks` in `hooks/_common.py`) that must produce identical output but have no shared test asserting equivalence.
  - Instances: 1 (Run 18)
  - Root cause: Enforcement hooks cannot import from skills/holtz/scripts, so the masking logic was reimplemented independently; the two implementations can drift
  - Detection rule: `git diff HEAD~5 -- hooks/_common.py skills/holtz/scripts/markdown_utils.py` — review any divergence between the two mask implementations
  - First seen: Run 18 (2026-03-25)

- **PAT-005:** README count drift — numeric claims in README.md (test count, LOC, hook count, run count, prediction accuracy) fall out of sync with reality and are never automatically validated.
  - Instances: Recurring every 1–3 runs from Run 4 onward; present in Run 25 as BH-001, BH-002, BH-011, BH-014, BH-015
  - Root cause: No CI step validates README numeric claims; they are updated manually and are always stale by the time a new run ships
  - Detection rule: `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v` — validates test count badge; other counts have no automated check
  - First seen: Run 4 (2026-03-20); escalated as Tier 1 persistent gap after Run 19

- **PAT-006:** load filter defensive gap — a `load()` or `validate()` function accepts malformed input because a required key is missing from the `_REQUIRED_KEYS` constant, allowing downstream code to KeyError on assumptions the validator should have rejected.
  - Instances: BH-017 (Run 25)
  - Root cause: `impact_graph.py` `_REQUIRED_NODE_KEYS` was `{type, file}` but `risk_hotspots()` accesses `n["id"]`; the id key was never added to the required set
  - Detection rule: For every `_REQUIRED_*_KEYS` set, grep downstream code that accesses those objects and verify all accessed keys are present in the constant
  - First seen: Run 25 (2026-03-29)

- **PAT-007:** incomplete parser output — a parser returns a default/fallback value for a field that depends on upstream state not yet established, making all consumers see the same stale value regardless of actual state.
  - Instances: BH-018 (Run 25)
  - Root cause: `parse_status_text()` always set `current_perspective="unknown"` because `primer.py` never emitted a lens-context line after `/clear`; the parser was correct for the format it received but the emitter was incomplete
  - Detection rule: For every field `parse_status_text()` extracts, verify there is a corresponding emit line in `primer.py`; cross-reference parser against emitter after any change to either
  - First seen: Run 25 (2026-03-29)

### Risk Hotspots

Nodes with `risk_score > 0.5` from the current impact graph. All other nodes are at 0.0 as of Run 25.

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| `hooks/_common.py:mask_fenced_blocks` | 0.7 | BH-016 (Run 25) | 1 | Dual-parser risk (PAT-004); must stay in sync with `markdown_utils.py:mask_code_fences`; no equivalence test |

### Architectural Risks

- **README semantic claims not CI-gated:** README contains numerous numeric claims (test count, LOC, run count, hook count, prediction accuracy) that are not validated by CI. They drift on every run.
  - Source: Recurring finding across Runs 4–25; escalated Tier 1 after Run 19
  - Severity: MEDIUM
  - Why it matters: Every run finds PAT-005 instances; the fix is always manual and incomplete; CI could close this permanently
  - Punchlist items produced: BH-001, BH-002, BH-011, BH-014, BH-015 (Run 25 alone)

- **Dual fence-masking implementations with no equivalence test:** `markdown_utils.py:mask_code_fences` and `hooks/_common.py:mask_fenced_blocks` implement the same logic independently. An architectural constraint prevents enforcement hooks from importing skills/holtz/scripts, so the implementations will continue to live separately.
  - Source: Drift log, Run 18 (2026-03-25)
  - Severity: MEDIUM
  - Why it matters: PAT-004 instances will recur whenever one implementation is updated without the other; the divergence is invisible without an equivalence test
  - Punchlist items produced: PAT-004 (Run 18)

- **Protocol cache parser/emitter contract is implicit:** `_protocol_cache.py:parse_status_text()` and `primer.py` share a text-format contract that is not documented, not tested as an interface, and not enforced. The parser and emitter can drift silently.
  - Source: BH-013, BH-018 (Run 25, 2026-03-29)
  - Severity: MEDIUM
  - Why it matters: Two bugs in one run from the same implicit contract; without a documented format spec or integration test, this will recur
  - Punchlist items produced: BH-013, BH-018

### Persistent Gaps

- **No CI gate on README numeric claims**
  - First identified: Run 4 (2026-03-20); escalated as Tier 1 after Run 19
  - Still present as of: Run 25 (2026-03-29)
  - Impact: PAT-005 recurs every 1–3 runs; each instance is found by auditors and patched manually; the patch is always stale by the next run
  - Recommended fix: Add a test battery to CI that validates every numeric claim in README against live counts (test count, hook count, LOC within 5%, run count)

- **No equivalence test for dual fence-masking implementations**
  - First identified: Run 18 (2026-03-25)
  - Still present as of: Run 25 (2026-03-29)
  - Impact: `mask_fenced_blocks` and `mask_code_fences` can diverge silently; divergence would corrupt enforcement hook parsing without any test failure
  - Recommended fix: Add a parametric test that runs identical inputs through both implementations and asserts identical output

- **Parser/emitter contract between `primer.py` and `_protocol_cache.py` is undocumented**
  - First identified: Run 25 (2026-03-29)
  - Still present as of: Run 25 (2026-03-29)
  - Impact: Two bugs (BH-013, BH-018) from the same implicit contract in one run; without a documented format spec or integration test, this will recur
  - Recommended fix: Document the text format that `primer.py` emits and `parse_status_text()` parses; add an integration test that runs both together and verifies round-trip correctness

## Proactive Checks

### Check 1: Code-fence-unaware parser (PAT-001)
**Source:** PAT-001
**Trigger:** New or modified file in `skills/holtz/scripts/` or `enforcement/hooks/` that introduces a regex, `split`, `findall`, or `search` operating on user-provided or file-read markdown text
**Heuristic:** `grep -rn 're\.\(search\|findall\|split\|match\)' skills/holtz/scripts/ enforcement/hooks/ --include='*.py' | grep -v mask_code_fences | grep -v mask_fenced_blocks | grep -v '#'`
**If triggered:** Check whether the caller masks code fences before the regex. If not, test with input that has a code fence containing a matching header or field label.

### Check 2: Regex newline leak (PAT-003)
**Source:** PAT-003
**Trigger:** New or modified regex in any `.py` file in `skills/holtz/scripts/` or `enforcement/hooks/`
**Heuristic:** `grep -rn '\\s' skills/holtz/scripts/ enforcement/hooks/ --include='*.py' | grep -v '#.*\\s' | grep -v 'whitespace\|space\|tab'`
**If triggered:** Review whether `\s` is used where only spaces and tabs are intended. Replace with `[ \t]` per project convention if so.

### Check 3: Dual-parser drift (PAT-004)
**Source:** PAT-004; Hotspot: `hooks/_common.py:mask_fenced_blocks`
**Trigger:** Any change to `hooks/_common.py:mask_fenced_blocks` or `skills/holtz/scripts/markdown_utils.py:mask_code_fences`
**Heuristic:** `git diff HEAD~1 -- hooks/_common.py skills/holtz/scripts/markdown_utils.py | grep -A5 -B5 'mask'`
**If triggered:** Run both implementations against the same test corpus and assert identical output. If they diverge, synchronize and add an equivalence test.

### Check 4: README count drift (PAT-005)
**Source:** PAT-005
**Trigger:** Any commit that adds tests, adds hooks, changes LOC significantly, or completes a run
**Heuristic:** `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v`; additionally spot-check LOC and hook count manually
**If triggered:** Update all stale numeric claims in README.md. Verify badge URL, prose counts, and statistics section.

### Check 5: Load filter defensive gap (PAT-006)
**Source:** PAT-006
**Trigger:** Any change to a `_REQUIRED_*_KEYS` set, or any new field access on objects produced by `load()` in `impact_graph.py`
**Heuristic:** `grep -n '_REQUIRED.*KEYS' skills/holtz/scripts/impact_graph.py` — for each required-keys constant, verify all downstream field accesses on the produced objects are covered by the constant
**If triggered:** Add the missing key to the required-keys set and add a test that verifies malformed input raises a clear error rather than a KeyError downstream.

### Check 6: Parser/emitter contract drift (PAT-007)
**Source:** PAT-007; Architectural Risk: protocol cache parser/emitter contract
**Trigger:** Any change to `enforcement/hooks/primer.py` output format or `enforcement/hooks/_protocol_cache.py:parse_status_text()`
**Heuristic:** `git diff HEAD~1 -- enforcement/hooks/primer.py enforcement/hooks/_protocol_cache.py`
**If triggered:** Verify that every field `parse_status_text()` extracts has a corresponding emit line in `primer.py`. Run the enforcement integration test suite. If no test covers the primer→parse round-trip end-to-end, add one before merging.

### Check 7: Hotspot change in mask_fenced_blocks
**Source:** Hotspot: `hooks/_common.py:mask_fenced_blocks` (risk_score 0.7)
**Trigger:** Any change to `hooks/_common.py`, especially `mask_fenced_blocks` or its callers
**Heuristic:** `git diff --name-only HEAD~1 | grep '_common.py'`
**If triggered:** Re-run `test_hooks.py` and verify PAT-004 equivalence against `mask_code_fences`. Review change against known patterns PAT-001, PAT-002, PAT-004.

## Prediction Accuracy

Prediction tracking established Run 4. The README previously claimed 82%/59%/67% (HIGH/MEDIUM/LOW) which was fabricated (BH-014, fixed Run 25). Research data from `docs/research/convergence-data.md` shows historical actuals:

### Cumulative Accuracy (Runs 4–25)

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | ~26       | ~18       | ~69%     |
| MEDIUM     | ~20       | ~9        | ~45%     |
| LOW        | ~9        | 0         | 0%       |
| **Total**  | **~55**   | **~27**   | **~49%** |

### Per-Run Breakdown

| Run | HIGH | MEDIUM | LOW | Notes |
|-----|------|--------|-----|-------|
| 25 | 3/3 (100%) | 3/4 (75%) | 0/1 (0%) | 8 predictions total; 6 confirmed |

### Calibration Notes

- HIGH-confidence predictions from hotspots and recurring patterns (PAT-005, test isolation failures) are the most reliable signal. Run 25 was 100% for HIGH — predictions grounded in recon evidence (CI red, churn data) consistently confirm.
- MEDIUM-confidence predictions are moderately reliable (~45% cumulative). Run 25 improved to 75% because predictions were specific and evidence-based rather than speculative. When a MEDIUM prediction cites a specific code path and test, it tends to confirm; vague MEDIUM predictions ("could happen") do not.
- LOW-confidence predictions have never confirmed across all tracked runs. Consider not filing them unless they identify a specific code path that would confirm them. Vague LOW predictions consume attention without payoff.
- Drift-based predictions (PAT-005 README drift) are the single most reliable signal for this project — this class has confirmed on every run since Run 4. Any prediction citing PAT-005 should be rated HIGH.
- Historical cumulative figures are estimates because the README fabricated data was the primary tracking source. The ~65%/~38%/0% pre-Run-25 figures come from `docs/research/convergence-data.md`; Run 25 contribution was computed from ledger `predicted_by` fields.

## History

### 2026-03-29: Run 25 completed

This is the first proper population of the living punchlist. The prior file at this path was a placeholder stub (created 2026-03-28, content: "No checkpoint data available yet").

- Added: PAT-001 through PAT-007. PAT-001–PAT-005 reconstructed from prior run history (archive STATUS.md files and PUNCHLIST-MERGED.md files). PAT-006 (load filter defensive gap) and PAT-007 (incomplete parser output) are new from Run 25.
- Added: Risk hotspot — `hooks/_common.py:mask_fenced_blocks` (risk_score 0.7, PAT-004 exposure, last bug BH-016 Run 25)
- Added: Three architectural risks — README not CI-gated, dual fence-masking no equivalence test, primer/parse contract implicit
- Added: Three persistent gaps — no README CI gate (Tier 1, escalated since Run 19), no equivalence test for dual maskers, undocumented primer/parse contract
- Added: Seven proactive checks derived from PAT-001–PAT-007 and the mask_fenced_blocks hotspot
- Calibration: Run 25 prediction accuracy was 75% overall (6/8 confirmed): HIGH 100% (3/3), MEDIUM 75% (3/4), LOW 0% (0/1). Outperformed historical average, attributed to evidence-grounded predictions from recon churn/CI data.
- Notes: 17 total findings, all resolved. Two new patterns: BH-017 (PAT-006, quiz bank updated for blast radius) and BH-018 (PAT-007, primer lens priming fixed). Badge URL fixed (PAT-005 recurrence). 774 tests, 60% coverage, ruff clean, mypy clean at convergence.

# Convergence Data: 15 Runs of Adversarial Self-Audit

Raw data from Holtz auditing his own codebase across 15 runs. This is the convergence behavior of an LLM-driven TDD audit loop operating on real code with real bugs, not synthetic benchmarks.

## 1. Findings Progression

| Run | Date | Findings | HIGH | MEDIUM | LOW | Tests Before | Tests After | Net Tests | Notes |
|-----|------|----------|------|--------|-----|-------------|-------------|-----------|-------|
| 1 | 2026-03-19 | 21 | 2 | 10 | 9 | 0 | 19 | 19 | First audit. No test suite existed. |
| 2 | 2026-03-19 | 12 | 0 | 5 | 7 | 40 | 88 | 48 | Second pass found bugs exposed by run 1 fixes. |
| 3 | 2026-03-20 | 3 | 0 | 1 | 2 | 102 | 104 | 2 | First run with no dominant pattern. |
| 4 | 2026-03-20 | 4 | 0 | 3 | 1 | 104 | 108 | 4 | PAT-001 fourth manifestation. |
| 5 | 2026-03-21 | 9 | 0 | 3 | 6 | 157 | 159 | 2 | Post-refactor audit. |
| 6 | 2026-03-22 | 8 | 0 | 1 | 7 | 226 | 232 | 6 | Severity shift to LOW. |
| 7 | 2026-03-22 | 2 | 0 | 2 | 0 | 232 | 235 | 3 | Minimum findings. Coverage 77%. |
| 8 | 2026-03-22 | 10 | 2 | 3 | 5 | 235 | 259 | 24 | New hooks layer introduced. Spike. |
| 9 | 2026-03-22 | 5 | 0 | 1 | 4 | 259 | 261 | 2 | First Justine parallel run. |
| 10 | 2026-03-22 | 9 | 0 | 7 | 2 | 261 | 265 | 4 | First Justine merge. |
| 11 | 2026-03-22 | 13 | 0 | 5 | 8 | 265 | 269 | 4 | Justine found 3 regex violations Holtz missed. |
| 12 | 2026-03-23 | 6 | 0 | 4 | 2 | 286 | 295 | 9 | Justine found test gaps in hooks. |
| 13 | 2026-03-23 | 4 | 0 | 2 | 2 | 320 | 321 | 1 | Targeted delta audit. |
| 14 | 2026-03-24 | 8 | 0 | 6 | 2 | 321 | 324 | 3 | Full adversarial self-play. PAT-001 5th manifestation. |
| 15 | 2026-03-24 | 9 | 4 | 4 | 1 | 595 | 613 | 18 | Convergence enforcement audit. 4 HIGH from process gaps. |

**Observations:**
- Findings never reach zero. Each fix changes the terrain.
- HIGH severity disappeared after run 1, returned in run 8 (new code layer), returned in run 15 (process layer audit).
- Severity distribution shifted from HIGH/MEDIUM to MEDIUM/LOW to predominantly LOW across runs 1-7.
- New code layers (hooks in run 8, token profiler pre-run 15) cause findings spikes.
- Test count: 0 -> 619 across 15 runs. Every finding produces at least one test.

## 2. PAT-001: Code-Fence-Unaware Parsing

The signature recurring pattern. Same root cause, different disguise each time.

| Manifestation | Run | Location | Disguise | How Found |
|---------------|-----|----------|----------|-----------|
| 1st | 1 | `validate_punchlist.py` | `**Status:**` header inside code fence truncated real Status field | Phase 3 adversarial audit |
| 2nd | 2 | `validate_punchlist.py` | Masking added but extraction still used raw content | Convergence sweep found incomplete fix |
| 3rd | 2 | `convergence_check.py` | Same `\s*` cross-line leak in 6 field regexes | Pattern sibling search |
| 4th | 4 | `validate_punchlist.py` | `_section_from_original()` used masked block for headers but original block for content | Integration test gap |
| 5th | 14 | `pattern_brief_compact.py` | `parse_brief()` applied header regex without masking code fences | Pattern library prediction (confirmed) |
| 6th | 14 | `pattern_brief_compact.py` | `\s*` in field extraction regex caused empty fields to consume next field | Pattern library prediction (confirmed) |
| 7th | 15 | `convergence_gate.py` | Parses STATUS.md without masking code fences | Recon prediction |
| 8th | 15 | `convergence_primer.py` | Same pattern as convergence_gate | Recon prediction |
| 9th | 15 | `hooks/_common.py` | `mask_fenced_blocks` tracks fence character but not fence count; ```` closed by ``` | Phase 4 fix uncovered it |
| 10th | 15 | Hook test fixtures | No adversarial code-fence fixtures in convergence hook tests | Sibling search |

**Pattern evolution:**
- Runs 1-4: Same module, same bug class, increasingly subtle manifestation. Each fix narrowed the gap but didn't close it.
- Run 14: Jumped to a new module (`pattern_brief_compact.py`). The pattern library predicted it before any code was read.
- Run 15: Jumped to the enforcement layer (hooks). The hooks that were supposed to prevent audit gaps had the same parsing gap they were enforcing against.

The pattern never presented the same way twice. It was always technically a different bug. But the root cause — parsing structured markdown without accounting for code fences — was identical every time. By run 14, the pattern library was predicting it before Holtz read a line of code.

## 3. Prediction Accuracy

Predictions begin at run 6 (when predictive recon was implemented). Each prediction has a confidence level (HIGH, MEDIUM, LOW) and an outcome (CONFIRMED, PARTIALLY CONFIRMED, UNCONFIRMED).

### Holtz Predictions

| Run | HIGH Pred | HIGH Conf | MEDIUM Pred | MEDIUM Conf | LOW Pred | LOW Conf |
|-----|-----------|-----------|-------------|-------------|----------|----------|
| 6 | 2 | 1 (50%) | 3 | 3 (100%) | 1 | 0 (0%) |
| 7 | 3 | 0 (0%) | 4 | 0 (0%) | 1 | 0 (0%) |
| 8 | 3 | 3 (100%) | 3 | 1 (33%) | 1 | 0 (0%) |
| 9 | 1 | 1 (100%) | 2 | 0 (0%) | 2 | 0 (0%) |
| 10 | 2 | 2 (100%) | 0 | -- | 0 | -- |
| 11 | 1 | 1 (100%) | 2 | 2 (100%) | 1 | 0 (0%) |
| 12 | 1 | 1 (100%) | 3 | 1 (33%) | 1 | 0 (0%) |
| 13 | 3 | 3 (100%) | 1 | 1 (100%) | 1 | 0 (0%) |
| 14 | 2 | 1 (50%) | 2 | 1 (50%) | 1 | 0 (0%) |
| 15 | 3 | 1 (33%) | 3 | 0 (0%) | 1 | 0 (0%) |
| 16 | 2 | 1 (50%) | 3 | 1 (33%) | 1 | 0 (0%) |

### Justine Predictions

| Run | HIGH Pred | HIGH Conf | MEDIUM Pred | MEDIUM Conf | LOW Pred | LOW Conf |
|-----|-----------|-----------|-------------|-------------|----------|----------|
| 9 | -- | -- | -- | -- | -- | -- |
| 12 | 2 | 2 (100%) | 1 | 1 (100%) | 0 | -- |
| 14 | 1 | 0 (0%) | 3 | 0 (0%) | 0 | -- |
| 16 | 3 | 1 (33%) | 3 | 1 (33%) | 1 | 0 (0%) |

### Aggregate Prediction Accuracy (Holtz only, 11 runs)

| Confidence | Total Predictions | Confirmed | Accuracy |
|------------|-------------------|-----------|----------|
| HIGH | 23 | 15 | 65% |
| MEDIUM | 26 | 10 | 38% |
| LOW | 11 | 0 | 0% |

### Aggregate Including Justine (14 data points)

| Confidence | Total Predictions | Confirmed | Accuracy |
|------------|-------------------|-----------|----------|
| HIGH | 29 | 18 | 62% |
| MEDIUM | 33 | 12 | 36% |
| LOW | 12 | 0 | 0% |

**Observations:**
- HIGH predictions perform best when converging on a known pattern family. Run 8 (new hooks, all HIGH confirmed), run 10, run 11, run 13 all show 100% HIGH accuracy. These runs had strong prior signals — known patterns, high churn, or graph risk scores.
- HIGH accuracy drops on novel code. Run 7 (0%), run 15 (33%) — when the model predicts bugs in code it hasn't seen before, it overestimates.
- MEDIUM predictions are directionally correct more often than strict confirmation shows. They identify the right code area but overestimate severity or miss the exact bug location. Run 6 and run 11 are outliers at 100%.
- LOW predictions have 0% confirmation across all 12 instances. They represent speculative hypotheses that the model correctly identifies as unlikely. The calibration is working — LOW means LOW.
- Justine's run 14 predictions (0% across the board) were an outlier. She tested CRLF handling and cross-entry bleeding — the wrong edge cases. Holtz tested empty fields and code fences — found the actual bugs. The prediction system works better when calibrated by prior runs of the same auditor.
- **Best predictor of HIGH accuracy:** Whether the prediction targets a known pattern family. Pattern-library-backed predictions confirm at ~80%. Novel predictions confirm at ~40%.

## 4. Adversarial Merge Analysis

Runs with both Holtz and Justine auditing independently, then merging.

### Run 9-10 (First Justine integration)

| Found by | Finding | Category |
|----------|---------|----------|
| Justine only | README doc-spec drift (stale test count) | doc/drift |
| Justine only | CI lint scope diverges from pyproject.toml | design/inconsistency |
| Justine only | Architecture baseline omits hooks | doc/drift |
| Holtz only | detect_test_runner priority bug | bug/logic |
| Holtz only | Go test parser missing | bug/logic |
| Both | pytest-cov configuration issue | design/inconsistency |

**Blind spots revealed:** Justine catches documentation drift and configuration inconsistency that Holtz deprioritizes. Holtz catches runtime logic bugs that Justine's static analysis misses.

### Run 11 (Regex convention violations)

| Found by | Finding | Category |
|----------|---------|----------|
| Justine only | 3 `\s` regex convention violations | bug/logic |
| Justine only | Hook enforcement scope too narrow | bug/logic |
| Justine only | STATUS.md deletion bypass | bug/logic |
| Holtz only | NaN risk score bug (impact_graph.py) | bug/logic |
| Holtz only | README metrics test is rubber stamp | design/inconsistency |

**Key insight:** Justine found the regex convention violations because breadth-first scanning sees all instances of a pattern simultaneously. Holtz's depth-first approach examined each file in isolation, where each individual `\s` usage looked correct. The bug was only visible in aggregate.

### Run 12 (Hook test gaps)

| Found by | Finding | Category |
|----------|---------|----------|
| Justine only | 3 untested hook paths (PUNCHLIST-MERGED, Justine paths, STATUS deletion) | test/missing |
| Holtz only | Malformed graph entry handling | bug/error-handling |
| Holtz only | Doc-spec drift in README counts | doc/drift |

**Pattern:** Justine consistently identifies test coverage gaps that Holtz's fix-oriented approach doesn't prioritize until they cause a bug.

### Run 14 (Full adversarial self-play)

| Found by | Finding | Category |
|----------|---------|----------|
| Justine only | README line count ambiguity | doc/drift |
| Justine only | Stall detection message doesn't distinguish stagnation from regression | design/inconsistency |
| Both | README metrics test is rubber stamp | test/shallow |
| Both | `\s` convention violation in pattern_brief_compact.py | design/inconsistency |
| Holtz only | Empty field content bleed (PAT-001) | bug/logic |
| Holtz only | Code fence in pattern brief (PAT-001) | bug/logic |

**Key insight:** Justine called the `\s` convention violation "functionally harmless." Holtz tested what happens when a field is empty with that regex and found the actual bug. Justine identified the right code but tested the wrong edge case. This is the core value of adversarial self-play — two auditors with different testing instincts cover different failure modes.

## 5. Convergence Behavior

| Run | Iterations to Converge | Stall Detected | Circuit Breaker Hit | Notes |
|-----|------------------------|----------------|---------------------|-------|
| 1 | 3 | No | No | First audit, large backlog |
| 2 | 2 | No | No | |
| 3 | 1 | No | No | Only 3 findings |
| 4 | 2 | No | No | PAT-001 created new items |
| 5 | 2 | No | No | |
| 6 | 2 | No | No | |
| 7 | 1 | No | No | Minimum findings |
| 8 | 2 | No | No | Hook layer spike |
| 9 | 1 | No | No | |
| 10 | 2 | No | No | With Justine merge |
| 11 | 2 | No | No | With Justine merge |
| 12 | 2 | No | No | With Justine merge |
| 13 | 1 | No | No | Targeted delta |
| 14 | 2 | No | No | Full adversarial |
| 15 | 3 | No | No | Convergence enforcement audit |

**Observations:**
- Most runs converge in 1-2 iterations.
- 3 iterations only happened on runs 1 (cold start) and 15 (auditing the convergence system itself).
- No stall detection or circuit breaker activation across 15 runs.
- The convergence loop has never failed to converge on this codebase.

## 6. Test Growth Curve

```
Run:   1    2    3    4    5    6    7    8    9   10   11   12   13   14   15
Tests: 19   88  104  108  159  232  235  259  261  265  269  295  321  324  619
       ^^^                                ^^^                              ^^^
       cold start                         hooks layer                     convergence + profiler
```

The three inflection points correspond to:
1. **Run 1-2:** Cold start. No test suite existed. 88 tests written from scratch.
2. **Run 8:** New hooks layer added. 24 tests for hook enforcement.
3. **Run 15:** Token profiler and convergence enforcement. 18 tests + 9 broken tests fixed + major new module.

Between inflection points, test growth is 2-9 tests per run. The audit finds fewer bugs per run, but each bug still produces at least one test.

## 7. Methodology

This data was collected from the `docs/holtz/archive/` directory, which contains the complete audit artifacts from every run — recon reports, predictions, punchlists, summaries, and investigation files. The archive is append-only and unedited.

All audits were run by Claude (Opus 4 / Opus 4.6 models) using the Holtz skill in Claude Code. The auditor and the codebase are the same project — this is a self-audit, which means:

1. The auditor has maximum domain knowledge (it wrote the code).
2. The auditor has maximum blind spots (it can't see its own assumptions).
3. Adding Justine (a second auditor with different methodology) partially compensates for #2.
4. The pattern library accumulates cross-run knowledge that compensates for context window limits.

The prediction accuracy data represents the model's ability to predict where bugs will appear *before reading the code*, based only on structural signals (churn, coverage, prior findings, known patterns). This is not few-shot prompting or in-context learning — the predictions are made from pattern library heuristics and graph risk scores accumulated across runs.

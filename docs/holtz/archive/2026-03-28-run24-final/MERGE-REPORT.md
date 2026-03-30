# Adversarial Self-Play Merge Report

**Date:** 2026-03-28
**Run:** 25
**Holtz findings:** 10 total items (BH-001 through BH-010)
**Justine findings:** 7 total items (BJ-001 through BJ-007)
**Merged total:** 17 items (BH-001 through BH-017)

## Counts by Classification

| Classification    | Count |
|-------------------|-------|
| AGREEMENT         | 1     |
| HOLTZ-ONLY        | 9     |
| JUSTINE-ONLY      | 6     |
| CONTRADICTION     | 0     |
| **Merged total**  | **16 unique bugs** (17 items: 1 agreement merges 2 original items) |

> Note: BH-001 (Holtz) and BJ-001 (Justine) both found README doc/drift at the same location — these merge to a single item (BH-002 in merged list). The 10 + 7 = 17 original items collapse to 16 unique bugs after deduplication.

## Agreement

**1 item** found by both auditors.

| Merged ID | Holtz original | Justine original | Notes |
|-----------|---------------|------------------|-------|
| BH-002 | BH-001 (LOW) | BJ-001 (HIGH) | Severity disagreement: used HIGH. Justine's scope was broader (also caught anti-pattern count and run count). |

**Severity disagreements:** 1 item — BH-001 rated LOW by Holtz, BJ-001 rated HIGH by Justine. Merged as HIGH (higher severity wins).

## Holtz-only

**9 items** — findings from Holtz that Justine did not independently surface.

| Merged ID | Original ID | Title | Severity |
|-----------|-------------|-------|----------|
| BH-001 | BH-007 | sahjhan status --json not supported, all hooks degraded | HIGH |
| BH-004 | BH-002 | README says 10 hooks, actual 9 | MEDIUM |
| BH-005 | BH-003 | lens_evidence.py and verify_hooks.py not registered in hooks.json | MEDIUM |
| BH-006 | BH-008 | lens_quiz verify_answer_freshness KeyError on missing "a" key | MEDIUM |
| BH-007 | BH-009 | lens_quiz cross-lens answer injection | MEDIUM |
| BH-011 | BH-010 | _sahjhan_bootstrap cp/mv bypass | MEDIUM |
| BH-012 | BH-004 | subagent_findings_check.py 0% test coverage | LOW |
| BH-013 | BH-005 | lens_quiz select_questions latent ordering bug | LOW |
| BH-014 | BH-006 | Impact graph stale nodes | LOW |

## Justine-only

**6 items** — findings from Justine that Holtz did not independently surface.

| Merged ID | Original ID | Title | Severity |
|-----------|-------------|-------|----------|
| BH-003 | BJ-002 | 5 tests use source-code string matching instead of behavioral testing | HIGH |
| BH-008 | BJ-003 | primer.py uses two different sources for run_number | MEDIUM |
| BH-009 | BJ-004 | Quiz bank validator does not check for empty option strings | MEDIUM |
| BH-010 | BJ-008 | lens_evidence check_transcript excludes enforcement code reads | MEDIUM |
| BH-015 | BJ-005 | _sahjhan_bootstrap redirect detection false positive | LOW |
| BH-016 | BJ-006 | Protocol cache TOML parser fragile | LOW |
| BH-017 | BJ-007 | lens_quiz questions_hash not validated at scoring | LOW |

## Severity Disagreements

**1 item** — listed with both ratings.

- **BH-002:** Holtz=LOW (doc/drift, scoped to LOC count), Justine=HIGH (doc/drift, broader scope including run count and anti-pattern count). Using HIGH.

## Contradictions

**0 items** — no contradictions detected. No item in either punchlist explicitly stated that a finding from the other auditor was "not a bug" or "correct behavior."

Note on BH-010 vs BJ-005 (near-miss, not a contradiction): Both concern `_sahjhan_bootstrap.py`, but they are different bugs with different categories:
- BH-010 (Holtz): `bug/security` — cp/mv commands bypass the protected-path check (false negative)
- BJ-005 (Justine): `bug/logic` — redirect detection produces false positives (over-blocking)
These are independent defects at the same file. Per the merge protocol, different categories = not the same bug. Both are carried forward independently.

## Blind Spot Analysis

### Holtz's blind spots (what Justine found that Holtz missed)

Justine found 6 items Holtz missed. Pattern analysis:

1. **Test anti-pattern (BH-003 / BJ-002, HIGH):** Justine's contract lens audit caught the source-code-string-matching test pattern. Holtz's test quality audit did not flag this class of Inspector Clouseau / Rubber Stamp anti-pattern. Holtz likely checked test coverage and structure but not whether tests were behavioral vs. structural.

2. **Data-flow divergence (BH-008 / BJ-003, MEDIUM):** Justine's data-flow lens traced `run_number` through two code paths in primer.py and identified the field name mismatch (`run_number` vs `run`). Holtz audited lens_quiz.py deeply (finding BH-008, BH-009) but did not trace the same data-flow path through primer.py.

3. **Input validation gap (BH-009 / BJ-004, MEDIUM):** Justine found that the quiz bank validator skips content validation of option strings. Holtz found a related KeyError on missing "a" key (BH-006) but did not look upstream at the validator's completeness.

4. **Boundary filter over-exclusion (BH-010 / BJ-008, MEDIUM):** Justine spotted that the `"enforcement"` exclusion in lens_evidence.py check_transcript was too broad. Holtz's lens_evidence coverage did not extend to this edge case.

5. **False-positive in bootstrap (BH-015 / BJ-005, LOW):** Holtz found the cp/mv bypass (false negative). Justine found the false positive (over-blocking). Holtz's security lens focused on what was NOT blocked; Justine's security lens also checked what was incorrectly blocked.

6. **TOML parser fragility (BH-016 / BJ-006, LOW) and hash validation gap (BH-017 / BJ-007, LOW):** Infrastructure-level robustness issues that require reading helper modules in depth. Holtz's audit prioritized the primary enforcement flow.

**Summary:** Justine's breadth-first approach surfaced test quality issues, upstream validation gaps, and data-flow divergences that Holtz's depth-first focus on the enforcement logic missed.

### Justine's blind spots (what Holtz found that Justine missed)

Holtz found 9 items Justine missed. Pattern analysis:

1. **Critical integration failure (BH-001 / BH-007, HIGH):** The `sahjhan status --json` bug is the most consequential finding — it degrades the entire enforcement layer. Justine did not catch this. Justine's recon may not have run the status command directly, or her audit focused on in-process hook logic rather than the CLI integration boundary.

2. **Manifest registration gaps (BH-005 / BH-003, MEDIUM):** Holtz cross-referenced hooks.json against the enforcement/hooks/ directory and found lens_evidence.py and verify_hooks.py unregistered. Justine's audit did not include a manifest completeness check.

3. **Quiz logic bugs — KeyError and cross-lens injection (BH-006, BH-007 / BH-008, BH-009, MEDIUM):** Holtz found two bugs inside lens_quiz.py through deep adversarial code review. Justine found related issues (BJ-004 upstream validator, BJ-007 hash gap) but did not reach the KeyError or cross-lens injection bugs inside the scoring functions.

4. **Security bypass via cp/mv (BH-011 / BH-010, MEDIUM):** Holtz found that cp/mv commands bypass the bootstrap protection. Justine found the false-positive side of the same file but did not audit the false-negative side.

5. **Coverage and latent defects (BH-012, BH-013 / BH-004, BH-005, LOW):** 0% test coverage on subagent_findings_check.py and the latent ordering bug in select_questions are findings requiring targeted coverage analysis and adversarial reasoning about edge cases. Justine's breadth-first pass did not reach these.

6. **Stale impact graph (BH-014 / BH-006, LOW):** Infrastructure maintenance finding. Justine's audit did not include an impact graph audit.

**Summary:** Holtz's depth-first, adversarial approach found the critical integration failure, manifest gaps, deep quiz logic bugs, and a security bypass that Justine's breadth-first sweep missed.

## Post-Merge Fix Ownership

Holtz owns the merged punchlist and runs the fix loop (Steps 10-16) on all 17 items in `docs/holtz/PUNCHLIST-MERGED.md`.

## Archiving

Archiving of Justine's output files (`docs/holtz/justine/`) is deferred. Files remain in place at:
- `docs/holtz/justine/PUNCHLIST.md` — Justine's Run 25 findings (source of BJ-001 through BJ-007)
- `docs/holtz/justine/STATUS.md` (if present)

Archiving should occur after Holtz completes the fix loop, per the standard post-merge sequence in `skills/holtz/references/merge-protocol.md`.

# Justine Audit Summary

**Project:** holtz v0.72.0
**Run:** 27
**Date:** 2026-03-29
**Auditor:** Justine (breadth-first adversarial)

## Totals

| Metric | Value |
|--------|-------|
| Findings total | 10 |
| CRITICAL | 2 |
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 1 |
| Open | 10 |
| Resolved | 0 |
| Deferred | 0 |
| Tests at start | 847 |
| Tests at end | 847 |
| Coverage at start | 76% |

## Finding Summary

### CRITICAL (2)
- **BJ-001:** _sahjhan_bootstrap.py Bash write bypass via dd, wget, python -c, xargs, find -exec. Five confirmed bypass vectors that allow modifying protected enforcement infrastructure via Bash commands.
- **BJ-002:** Bash redirects to Sahjhan-managed files (STATUS.md, PUNCHLIST.md, SUMMARY.md) bypass both write_guard.py and _sahjhan_bootstrap.py. The integration seam between the two guards leaves Sahjhan-rendered files unprotected from Bash writes.

### HIGH (3)
- **BJ-003:** README claims stale: "Twenty-six runs" (actual: 27), "19,129 lines of code" (actual: 23,585).
- **BJ-007:** README claims four non-existent lenses (concurrency, resource-lifecycle, idempotency, observability not in lens-registry.md), wrong anti-pattern count (17 claimed vs 12 actual), wrong reference doc count (24 claimed vs 17 actual).
- **BJ-008:** CI pipeline does not enforce the 60% coverage gate -- pytest runs without --cov flags.

### MEDIUM (4)
- **BJ-004:** _protocol_cache.py `(OSError, Exception)` catch masks programming errors, returning default 13 perspectives.
- **BJ-005:** subagent_findings_check.py regex only matches .md files, missing JSON and extensionless audit artifacts.
- **BJ-006:** score_answers returns (0,0) for both count mismatch and all-stale scenarios, leading to wrong error messages.
- **BJ-009:** Multi-redirect Bash commands bypass the redirect check because only the first `>` or `>>` is examined.

### LOW (1)
- **BJ-010:** hooks/subagent_findings_check.py has 0% metric coverage because subprocess-based tests don't contribute to --cov.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 3         | 100%     |
| MEDIUM     | 3         | 3         | 100%     |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **7**     | **6**     | **86%**  |

HIGH predictions were all confirmed because each had a single strong signal backed by code inspection. The cold security-critical files (P1, P3) and broad exception catches (P2) were direct pattern matches. MEDIUM predictions were confirmed because the code issues were visible in a single read-through. The LOW prediction (P7 -- shell construct bypass) was correctly calibrated as speculative.

## Patterns

### Observation: Allowlist-Based Command Filtering

BJ-001, BJ-002, and BJ-009 share a root cause: the _sahjhan_bootstrap.py hook uses an allowlist of known write commands (sed, perl, patch, cp, mv, install, tee, redirect) to detect Bash writes to protected paths. Shell is infinitely expressive. An allowlist will always be incomplete.

The architecturally stronger approach is post-hoc verification (as bash_guard.py already does with manifest verify), combined with making the managed files read-only at the filesystem level or using a purpose-built filesystem watcher. The current preventive guard gives a false sense of security -- it catches the obvious cases and misses everything else.

### Observation: README as Living Document

BJ-003 and BJ-007 are instances of PAT-005 (badge/metrics drift). The README contains concrete numeric claims (test count, LOC, run count, lens count, anti-pattern count, reference doc count) that go stale with every code change. This is a systemic issue that will recur on every run.

## Recommendations

1. **Rethink write protection architecture.** The allowlist approach in _sahjhan_bootstrap.py is fundamentally limited. Consider: (a) extending bash_guard.py's post-hoc manifest verification to block on violation instead of just detecting, (b) filesystem-level protection (chmod), or (c) accepting the current detect-and-flag model as sufficient for the threat model.

2. **Add missing lens definitions.** Protocol.toml declares 13 perspectives but lens-registry.md only defines 9. Either add definitions for concurrency, resource-lifecycle, idempotency, and observability, or reduce the protocol set to match the registry.

3. **Automate README metrics.** Badge values and prose metrics could be generated from code analysis rather than manually maintained. This would eliminate the PAT-005 recurrence pattern.

## Test Quality Assessment

The test suite is solid. No Rubber Stamp or Permissive Validator anti-patterns found. Tests consistently check actual computed values, not just structure or types. The assertion density is healthy. The main gap is coverage measurement (subprocess-based tests don't contribute to --cov metrics) and the missing CI coverage gate.

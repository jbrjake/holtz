# Holtz Audit Summary

**Project:** holtz (self-audit)
**Date:** 2026-03-19
**Auditor:** Holtz, applied to himself

## Before / After

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 40 | 88 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Findings | — | 12 |
| Resolved | — | 12 |
| Deferred | — | 0 |

## Findings by Category

| Category | Count |
|----------|-------|
| bug/logic | 5 |
| bug/error-handling | 1 |
| test/missing | 3 |
| test/shallow | 1 |
| design/inconsistency | 1 |
| doc/drift | 1 |

## Pattern Identified

**PAT-001: Code-fence-unaware parsing** (4 instances: BH-001, BH-002, BH-003, BH-004)

The parsing layer operated on raw/normalized content without considering code fence boundaries. This manifested as:
- Field headers inside code fences poisoning extraction (BH-001)
- Phantom item headers corrupting boundary calculations (BH-002)
- Bold text wrongly terminating section capture (BH-003)
- Tilde fences not recognized (BH-004)

Systemic fix: masked gating for all field detection, line-number mapping for boundary correlation, tilde fence support in the masking layer.

## Key Fixes

1. **BH-001/BH-002 (HIGH):** The validator's dual masked/normalized parsing had two complementary bugs. Field extraction from original_block wasn't gated on masked header existence, and boundary mapping used ID-based indexing that included phantom headers. Both fixed: masked gating + line-number mapping.

2. **BH-003 (MEDIUM):** Section regex `(?!\*\*\w)` stopped at any bold text, not just field headers. Changed to `(?!\*\*[A-Z][\w ]*:\*\*)` to match only `**FieldName:**` patterns.

3. **BH-006 (MEDIUM):** Go parser counted packages, not individual tests. Changed to `-v` flag with `--- PASS/FAIL/SKIP` parsing, excluding subtests. The fixture suite for this fix also exposed bugs in Jest, Cargo, Vitest, and Mocha parsers (crash output fell through to fallback instead of returning None, Vitest matched wrong summary line).

4. **BH-007 (MEDIUM):** Test runner output parsing returned `{passed: 0, failed: 0}` instead of `None` when output was unparseable, making crashes look like clean runs to the convergence checker.

5. **BH-005 (LOW):** pyproject.toml detection used substring matching, triggering on comments containing "pytest". Now checks for TOML section headers.

## Test Fixtures

Created `tests/runner_fixtures.py` with realistic output for all 6 supported test runners, each themed as a whimsical fictional project:

| Runner | Fictional Project | Theme |
|--------|------------------|-------|
| pytest | The Cheese Shop | Artisanal cheese inventory REST API |
| jest | Flavortown Jukebox | Music recommendation engine |
| vitest | Quantum Tacos | Physics simulation for optimal taco construction |
| cargo | Crab Rave Orchestrator | Distributed task scheduler in Rust |
| go | Haunted Elevator | Building simulation with unpredictable floors |
| mocha | Sock Puppet Theatre | WebSocket-based puppet show platform |

Each runner has fixtures for: all pass, mixed results, and crash/unparseable output. Go additionally has subtest and package-level fixtures.

## Recommendations

1. The primary risk surface is the markdown parsing in `validate_punchlist.py` — every new field extraction should use the `_section_from_original` pattern (gate on masked, extract from original).

2. No linter or type checker is configured. Adding mypy would catch type issues at development time.

3. The runner fixture suite can be extended as new runner output formats are encountered — the whimsical naming convention makes them easy to identify and maintain.

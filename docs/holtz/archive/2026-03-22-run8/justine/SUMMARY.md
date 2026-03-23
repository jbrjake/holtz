# Justine Audit Summary

**Project:** holtz (Claude Code plugin for adversarial bug identification)
**Date:** 2026-03-22
**Auditor:** Justine (breadth-first, parallel dispatch)
**Baseline:** 235 tests passing, 0 failing, 0 skipped, 0.27s runtime
**Punchlist:** docs/holtz/justine/PUNCHLIST.md
**Impact Graph:** docs/holtz/justine/impact-graph.json (11 nodes, 13 edges)

## Findings Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 4 |
| LOW | 2 |
| **Total** | **12** |

### By Category

| Category | Count |
|----------|-------|
| bug/logic | 5 |
| design/inconsistency | 3 |
| test/missing | 1 |
| test/integration-gap | 1 |
| bug/security | 1 |
| bug/error-handling | 1 |

## Critical Finding

**BH-101: impact_graph_gate.py gates a path nobody writes to.** The hook that enforces the "impact graph must exist before audit writes" HARD-GATE checks for writes to `docs/holtz/audit/` and `docs/holtz/justine/audit/`. Neither path is used by the protocol. All punchlist, recon, and findings writes go to `docs/holtz/` and `docs/holtz/justine/` directly. The gate is a complete no-op. The HARD-GATE requirement exists because the impact graph was never created for 10+ consecutive runs despite advisory instructions -- this hook was supposed to enforce what instructions could not. It does not work. Severity: CRITICAL because it defeats the stated purpose of the hook system.

## Primary Theme: Untested Hooks Subsystem

The hooks/ directory was added in a single commit and has:
- Zero test coverage (BH-102)
- 7 ruff lint errors (BH-106)
- A gate that protects a nonexistent path (BH-101)
- Dead code in artifact verification (BH-103)
- An overly broad STATUS.md exemption (BH-104)
- No code-fence awareness in subagent checks (BH-105)
- No integration tests validating the event contract (BH-110)
- Not included in ruff or mypy configuration (BH-108, BH-109)

These are all instances of PAT-001 (Untested hooks subsystem): the entire hooks layer was shipped without the quality gates applied to the rest of the codebase.

## Secondary Finding: Parser Prefix Hardcoding

**BH-112: Both validate_punchlist.py and convergence_check.py are hardcoded to the BH- prefix.** The architecture-baseline.md documents that Justine uses `BJ-NNN`, but neither parser recognizes that prefix. Justine's punchlist output would be invisible to the tooling. This was discovered empirically during this audit when the initial BJ-prefixed punchlist failed validation with "No punchlist items found."

## Tertiary Finding: Broken Default Configuration

**BH-107: pyproject.toml references pytest-cov but it is not installed.** Running `pytest` without `--override-ini` fails immediately. Anyone cloning the repo gets a broken test command out of the box.

## Test Quality Assessment

The existing test suite (235 tests across 5 files) is well-constructed:
- **No Rubber Stamp patterns detected.** All assertions check values, not just types/shapes.
- **No Permissive Validator patterns detected.** Assertions use exact equality or specific string matching.
- **Good integration tests.** The test_integration.py file validates cross-parser agreement between validate_punchlist and convergence_check.
- **Comprehensive edge case coverage.** Code-fence immunity, CRLF handling, phantom items, bold continuation lines, empty sections, corrupt JSON, binary files.

The test quality gap is entirely in hooks/ (zero coverage) and the BJ- prefix (untested path).

## Patterns Identified

### PAT-001: Untested hooks subsystem
8 of 12 findings trace to the hooks/ directory being shipped without the quality processes applied to the rest of the codebase (no tests, no lint, no mypy, no ruff src inclusion).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 4 | 4 | 100% |
| MEDIUM | 3 | 3 | 100% |
| LOW | 1 | 0 | 0% |
| **Total** | **8** | **7** | **88%** |

The single unconfirmed prediction (P6: unbounded stdin read in _common.py) was correctly classified as LOW confidence and the risk was assessed as acceptable given the plugin system context.

## Recommendations

1. **Write tests for hooks/ before any further changes.** The entire hooks subsystem is unverified. BH-101 (no-op gate) would have been caught by a single test that checks whether the gate blocks a punchlist write.

2. **Fix the impact_graph_gate path filter.** This is the highest priority fix. The gate should check for writes to PUNCHLIST.md and findings files, not a nonexistent `audit/` subdirectory. Recon files should be exempt (Phase 0 runs before the graph exists).

3. **Generalize parsers to accept BJ- prefix.** Change the item header regex in both validate_punchlist.py and convergence_check.py from `BH-\d+` to `B[HJ]-\d+` (or a configurable pattern). Add tests.

4. **Either install pytest-cov or remove it from addopts.** A broken default command is worse than no coverage reporting.

5. **Add hooks/ to ruff and mypy configuration.** The hooks are Python code in the project. They should be linted and type-checked with the same rules.

## Convergence

Convergence reached in 1 iteration. Single-pass audit across all areas under all lenses found 12 items. Final sweep found no additional issues. The scripts/ and tests/ directories are mature and well-tested. The hooks/ directory accounts for 8 of 12 findings and is the primary risk area.

Justine's role ends here. Holtz handles the merge and fix loop.

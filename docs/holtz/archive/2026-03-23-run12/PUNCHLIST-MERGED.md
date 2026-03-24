# Holtz Punchlist (Merged)
> Generated: 2026-03-23 | Project: holtz | Baseline: 286 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 2 | 0 |

## Patterns

## Items

### BH-001: README "What's inside" counts stale after Justine refactor
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:164`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 164 claims "2 skills, 2 agents, 14 reference docs, ... 286 tests across 8,200 lines" but after the Justine internal-only refactor: skills is now 1 (skills/justine/ removed), test count changed, line count changed.

**Evidence:**
- `ls skills/*/SKILL.md` → only `skills/holtz/SKILL.md` (1 skill, not 2)
- Test count changed from 286 to 295
- Line count changed from 8,200 to ~7,800

**Discovery Chain:** Justine refactor (bc165b2) moved files from skills/justine/ to skills/holtz/references/ → skills count decreased → README line 164 not updated

**Acceptance Criteria:**
- [x] README "What's inside" line reflects actual counts
- [x] test_readme_metrics_match_actual regex handles singular/plural

**Validation Command:**
```bash
grep "skill.*, .* agents, .* reference docs" README.md
```

**Resolution:** Updated README line 164 to "1 skill, 2 agents, 14 reference docs, ... 295 tests across 7,800 lines". Updated test regex to accept singular forms.

### BH-002: subagent_findings_check.py docstring references legacy exit codes
**Severity:** LOW
**Category:** doc/drift
**Location:** `hooks/subagent_findings_check.py:12`
**Status:** RESOLVED

**Problem:** Docstring says "Uses exit 1 (warn) not exit 2 (block)" but the hook was modernized to use JSON output format. All hooks now exit 0.

**Evidence:** Lines 6, 11: references to "exit 1" and "exit 2" in docstring.

**Discovery Chain:** read subagent_findings_check.py during Phase 2 → docstring mentions exit codes → code uses JSON functions that exit 0 → docstring stale

**Acceptance Criteria:**
- [x] Docstring accurately describes the modern output format
- [x] No references to legacy exit code semantics

**Validation Command:**
```bash
grep -n "exit 1\|exit 2\|exit code" hooks/subagent_findings_check.py
```

**Resolution:** Updated docstring to say "Warns but does not block" and "exit_warn" instead of legacy exit code references.

### BH-003: impact_graph.py load() does not validate individual edge/node entries
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/impact_graph.py:50-65`
**Status:** RESOLVED
**Determinism:** deterministic
**Predicted:** Prediction 4 (confidence: MEDIUM)
**Lens:** error-propagation

**Problem:** `load()` validates top-level structure but not individual entries. Malformed edge/node entries missing required keys crash downstream methods with `KeyError`.

**Evidence:** `load()` lines 59-62 check `isinstance(nodes, dict)` and `isinstance(edges, list)` but do not validate entry contents.

**Discovery Chain:** global pattern heuristic (missing-edge-case-handling) flagged impact_graph.py → read load() → found top-level validation but no per-entry validation → confirmed KeyError on malformed entries

**Acceptance Criteria:**
- [x] `load()` filters out malformed edge entries (missing source/target/type keys)
- [x] `load()` filters out malformed node entries (missing required keys)
- [x] Tests verify that loading a graph with malformed entries doesn't crash
- [x] Tests verify that valid entries survive filtering alongside malformed ones

**Validation Command:**
```bash
python -m pytest tests/test_impact_graph.py -v --tb=short -k "malformed"
```

**Resolution:** Added `_REQUIRED_EDGE_KEYS` and `_REQUIRED_NODE_KEYS` class constants. `load()` now filters entries with dict comprehensions that check `isinstance(v, dict)` and required key presence. 3 tests added: malformed edges, malformed nodes, mixed valid/invalid.

### BH-004: Missing test for PUNCHLIST-MERGED.md gate path in impact_graph_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/impact_graph_gate.py:34`
**Status:** RESOLVED
**Lens:** contract

**Problem:** The `holtz_files` tuple includes `"docs/holtz/PUNCHLIST-MERGED.md"` as a gated path but no test exercises it.

**Evidence:** `grep -r "PUNCHLIST-MERGED" tests/` returned zero results.

**Discovery Chain:** Justine read impact_graph_gate.py line 34 → identified PUNCHLIST-MERGED.md in holtz_files → grepped tests → zero matches → untested path confirmed

**Acceptance Criteria:**
- [x] Test sends file_path ending in `docs/holtz/PUNCHLIST-MERGED.md` and verifies block when graph missing
- [x] Test verifies allow when graph exists

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "punchlist_merged" -v
```

**Resolution:** Added `test_blocks_punchlist_merged_when_graph_missing` and `test_allows_punchlist_merged_when_graph_exists` to TestImpactGraphGate.

### BH-005: Missing test for STATUS.md-deleted-mid-run block in status_staleness_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/status_staleness_gate.py:55-64`
**Status:** RESOLVED
**Lens:** contract

**Problem:** The hook blocks writes when STATUS.md is missing but sibling artifacts exist, but no test exercises this path.

**Evidence:** Only the allow case (no artifacts) was tested.

**Discovery Chain:** Justine read status_staleness_gate.py lines 55-64 → identified conditional block on artifact existence → grepped tests → zero matches → untested block path confirmed

**Acceptance Criteria:**
- [x] Test where STATUS.md is absent but `docs/holtz/recon/` exists → hook blocks
- [x] Test where STATUS.md is absent but `docs/holtz/PUNCHLIST.md` exists → hook blocks

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "status_missing" -v
```

**Resolution:** Added `test_blocks_when_status_missing_but_recon_exists` and `test_blocks_when_status_missing_but_punchlist_exists` to TestStatusStalenessGate.

### BH-006: Missing test for Justine PUNCHLIST.md gate path in impact_graph_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/impact_graph_gate.py:35`
**Status:** RESOLVED
**Lens:** contract

**Problem:** The Justine PUNCHLIST.md endswith check is not tested. Only the audit/ directory path is tested.

**Evidence:** No test sends `docs/holtz/justine/PUNCHLIST.md` as file_path.

**Discovery Chain:** Justine read impact_graph_gate.py line 35 → two-condition OR for justine paths → test only covers audit/ path → endswith(justine_files) untested

**Acceptance Criteria:**
- [x] Test sends file_path `docs/holtz/justine/PUNCHLIST.md` and verifies it checks Justine's graph
- [x] Test verifies both block (graph missing) and allow (graph present)

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "justine_punchlist" -v
```

**Resolution:** Added `test_blocks_justine_punchlist_when_graph_missing` and `test_allows_justine_punchlist_when_graph_exists` to TestImpactGraphGate.

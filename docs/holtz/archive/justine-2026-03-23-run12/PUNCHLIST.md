# Holtz Punchlist
> Generated: 2026-03-23 | Project: holtz | Baseline: 286 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM | 3 | 0 | 0 |

## Patterns

## Items

### BJ-001: Missing test for PUNCHLIST-MERGED.md gate path in impact_graph_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/impact_graph_gate.py:34`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** The `holtz_files` tuple includes `"docs/holtz/PUNCHLIST-MERGED.md"` as a gated path that requires `docs/holtz/impact-graph.json` to exist before writes are allowed. No test in `test_hooks.py` exercises this specific file path. If the string were misspelled or the logic were broken for this path specifically, no test would catch it. The existing `test_blocks_audit_write_when_graph_missing` test uses `docs/holtz/audit/1.md`, which takes a different code path (`"docs/holtz/audit/" in normalized`).

**Evidence:** `grep -r "PUNCHLIST-MERGED" tests/` returns zero results. The `holtz_files` tuple at line 34 contains `"docs/holtz/PUNCHLIST-MERGED.md"` but no test sends a file_path containing this string.

**Discovery Chain:** read impact_graph_gate.py line 34 → identified PUNCHLIST-MERGED.md in holtz_files tuple → grepped tests for PUNCHLIST-MERGED → zero matches → untested code path confirmed

**Acceptance Criteria:**
- [ ] Test exists that sends a file_path ending in `docs/holtz/PUNCHLIST-MERGED.md` and verifies it is blocked when the graph is missing
- [ ] Test verifies the correct graph path (`docs/holtz/impact-graph.json`) is required for this file

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "punchlist_merged" -v
```

### BJ-002: Missing test for STATUS.md-deleted-mid-run block path in status_staleness_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/status_staleness_gate.py:55-64`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** The `status_staleness_gate.py` hook has a code path (lines 55-64) that blocks writes when `STATUS.md` does not exist BUT sibling artifacts (a `recon/` directory or `PUNCHLIST.md` file) do exist -- indicating STATUS.md was deleted mid-run rather than never created. No test exercises this path. The test `test_allows_when_no_status_exists` only tests the allow case (no artifacts exist), not the block case. If the artifact detection logic were broken, no test would catch it.

**Evidence:** `grep -r "artifacts exist\|recon_dir\|deleted mid" tests/` returns zero matches. The test `test_allows_when_no_status_exists` creates an empty tmp_path with no `recon/` dir and no `PUNCHLIST.md`, so it always takes the allow path.

**Discovery Chain:** read status_staleness_gate.py lines 55-64 → identified conditional block on artifact existence → grepped tests for artifact/recon_dir/deleted → zero matches → untested block path confirmed

**Acceptance Criteria:**
- [ ] Test exists where STATUS.md is absent but `docs/holtz/recon/` directory exists, and verifies the hook blocks
- [ ] Test exists where STATUS.md is absent but `docs/holtz/PUNCHLIST.md` exists, and verifies the hook blocks

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "status_missing_artifacts" -v
```

### BJ-003: Missing test for Justine PUNCHLIST.md gate path in impact_graph_gate
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/impact_graph_gate.py:35`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 3 (confidence: MEDIUM)

**Problem:** The `impact_graph_gate.py` hook has two conditions for Justine paths: `any(p in normalized for p in justine_paths)` (audit/ dir) and `normalized.endswith(justine_files)` (PUNCHLIST.md). The existing test `test_justine_audit_checks_justine_graph` only exercises the audit/ path with `docs/holtz/justine/audit/1.md`. The PUNCHLIST.md endswith check is not tested. If `justine_files` were misspelled or the `endswith` call were changed, no test would detect the regression.

**Evidence:** The test at line 233 sends `file_path="docs/holtz/justine/audit/1.md"`, which matches via `any(p in normalized for p in justine_paths)`. No test sends `file_path="docs/holtz/justine/PUNCHLIST.md"`.

**Discovery Chain:** read impact_graph_gate.py line 35 → identified two-condition OR for justine paths → test_justine_audit_checks_justine_graph only tests audit/ path → endswith(justine_files) untested

**Acceptance Criteria:**
- [ ] Test exists that sends `file_path` ending in `docs/holtz/justine/PUNCHLIST.md` and verifies it checks for `docs/holtz/justine/impact-graph.json`
- [ ] Test verifies both block (graph missing) and allow (graph present) behaviors

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -k "justine_punchlist" -v
```

# Audit 3: Code Audit

Audited 2026-03-23. Source files:
- `skills/holtz/scripts/impact_graph.py`
- `skills/holtz/scripts/convergence_check.py`
- `skills/holtz/scripts/validate_punchlist.py`
- `skills/holtz/scripts/markdown_utils.py`

All 240 tests pass at time of audit.

---

## Finding 1: Malformed edge entries from JSON cause KeyError crashes

**File:** `skills/holtz/scripts/impact_graph.py`, lines 50-65 (load), lines 122-123, 153, 183-188, 222, 235-236 (consumers)
**Severity:** MEDIUM
**Category:** bug/error-handling
**Determinism:** deterministic (given malformed input)

**Discovery chain:**
1. Observed that `load()` validates top-level structure (`nodes` must be dict, `edges` must be list) but does not validate individual entries within those containers.
2. Inferred that if an edge entry in JSON is missing required keys (`source`, `target`, `type`) or is a non-dict value (e.g., string, number), any method that iterates edges would crash.
3. Confirmed by loading JSON with `{"edges": [{"target": "a", "type": "calls"}]}` (missing `source`): `neighbors()` raises `KeyError: 'source'`. Similarly, `stats()` raises `KeyError: 'type'` when `type` is missing; non-dict edge entries (e.g., `"edges": ["not a dict"]`) raise `TypeError` in `stats()`.

**Impact:** Every method that iterates `self.edges` (`neighbors`, `blast_radius`, `add_edge` dedup loop, `stats`, `prune_node`) crashes on the first malformed entry. The graph becomes unusable until the JSON file is manually repaired.

**Root cause:** `load()` trusts that if `edges` is a list, its elements are well-formed dicts with all required keys. No per-entry validation or filtering.

---

## Finding 2: Malformed node entries from JSON cause KeyError crashes

**File:** `skills/holtz/scripts/impact_graph.py`, lines 50-65 (load), lines 204, 243, 259-266 (consumers)
**Severity:** MEDIUM
**Category:** bug/error-handling
**Determinism:** deterministic (given malformed input)

**Discovery chain:**
1. Same observation as Finding 1, applied to node values in the `nodes` dict.
2. If a node value is missing expected keys (`id`, `file`, `type`, `risk_score`), methods that access those keys crash.
3. Confirmed: `risk_hotspots()` raises `KeyError: 'id'` on a node missing that key. `prune_missing()` raises `KeyError: 'file'` on a node missing that key. `drift_check()` raises `KeyError: 'type'` and `KeyError: 'file'`.

**Impact:** Same as Finding 1 -- the graph becomes unusable. `risk_hotspots()` is particularly fragile because it sorts all nodes, so a single malformed node blocks the entire operation.

**Root cause:** Same as Finding 1. `load()` checks `isinstance(nodes, dict)` but not the structure of individual node values.

**Note on Findings 1 and 2:** These share a single root cause and a single fix. The `load()` method should either (a) validate and filter out malformed entries, or (b) catch `KeyError`/`TypeError` in each method that iterates edges/nodes. Option (a) is cleaner -- filter entries at load time and log a warning.

---

## Finding 3: `_get_punchlist` does not validate value types from history JSON

**File:** `skills/holtz/scripts/convergence_check.py`, lines 280-286 (\_get\_punchlist), lines 296, 300, 306, etc. (arithmetic consumers)
**Severity:** LOW
**Category:** bug/error-handling
**Determinism:** theoretical

**Discovery chain:**
1. Observed that `_get_punchlist()` extracts values from the punchlist dict via `pl.get(k, 0)` -- this provides defaults for missing keys but does not validate that present values are integers.
2. Inferred that if `HISTORY.json` is manually edited to contain non-integer values (e.g., `"OPEN": "three"`), `check_convergence()` would crash with `TypeError` on the first arithmetic operation.
3. Confirmed: `result['OPEN'] + result['IN PROGRESS']` raises `TypeError: can only concatenate str (not "int") to str`.

**Impact:** LOW because `HISTORY.json` is machine-written by `save_history()` which always writes integer values from `count_items()`. This can only be triggered by manual edits or external corruption of the file.

**Mitigating factor:** `load_history()` already guards against corrupt JSON (returns `[]`) and non-list top-level structure. The gap is only in per-entry field types within a structurally valid JSON file.

---

## Finding 4: `types=[]` treated identically to `types=None` in neighbors/blast_radius

**File:** `skills/holtz/scripts/impact_graph.py`, lines 150, 166
**Severity:** LOW
**Category:** bug/logic
**Determinism:** deterministic

**Discovery chain:**
1. Observed that `set(types) if types else None` evaluates to `None` when `types=[]` because empty lists are falsy in Python.
2. Inferred that a caller passing `types=[]` (meaning "filter to no edge types, return nothing") would instead get unfiltered results (all neighbors returned).
3. Confirmed: `neighbors("a", types=[])` returns all neighbors, same as `types=None`.

**Impact:** LOW. The existing tests explicitly document and accept this behavior. The CLI parser splits a comma-separated string, so `--type ""` would produce `[""]` (truthy, filters to no matches), not `[]`. Programmatic callers could hit this, but the test suite treats it as a design decision. Noting for completeness, not as an actionable bug.

---

## Files with no actionable findings

### `skills/holtz/scripts/markdown_utils.py`

The fence state machine is correctly implemented against the CommonMark spec:
- Backtick fence info strings reject backtick characters (`[^`]*$` in opener regex).
- Tilde fence info strings allow any characters including tildes (`.*$` in opener regex).
- Closing fences require same-type characters with at least the opening fence length.
- Closing fences reject trailing non-whitespace content (`[ \t]*$`).
- 0-3 space indentation is accepted for both opening and closing fences; 4+ spaces are not treated as fences.
- Unclosed fences correctly mask all content through EOF.
- Opening and closing fence lines themselves are correctly blanked.
- CRLF normalization happens before fence parsing.
- `has_unclosed_fence` correctly reports the fence state at document end.

No bugs found. 100% line coverage.

### `skills/holtz/scripts/validate_punchlist.py`

Thoroughly audited the following areas:
- **Section regex (`SECTION_RE`):** Correctly uses a known-field-name allowlist for terminators, preventing false truncation on arbitrary `**Bold:** text` in prose. Tested against inline bold, HTTP Status, etc.
- **Code fence isolation:** `parse_punchlist` uses `masked_block` for boundary detection and `original_block` for content extraction. Field headers inside code fences are invisible to boundary detection. Line-number mapping between masked and normalized content is correct because `mask_code_fences` preserves line count.
- **Validation command extraction:** Supports backtick and tilde fences of any length (3+), optional blank lines between header and fence, and CommonMark-correct fence length matching for closers. The close pattern requires at least `fence_len` characters of the same type.
- **Checkbox scoping:** Checkbox detection is scoped to the Acceptance Criteria section in the masked block, preventing false positives from checkboxes in other sections or inside code fences.
- **Discovery Chain detection:** Uses `re.MULTILINE` with `^` anchor to require the header at line start, preventing false positives from mid-line mentions.
- **CRLF handling:** CRLF normalization in `mask_code_fences` runs before all parsing, so all regex patterns can assume LF-only line endings.

No bugs found.

### `skills/holtz/scripts/convergence_check.py` (beyond Finding 3)

Audited the following areas beyond the theoretical Finding 3:
- **Test runner parsers:** Each runner's output parser handles the all-pass, mixed, all-fail, and crash cases. The parsers return `None` on unparseable output, not partial results. Go subtest exclusion uses `\w+[ (]` which correctly excludes `TestParent/SubTest` patterns.
- **Convergence logic:** The state machine correctly prevents false convergence on: empty punchlist history, deleted items (total decreased), items with unknown status, and test regressions across data gaps.
- **History file I/O:** Atomic write via temp file + `os.replace`. Handles corrupt JSON, non-list JSON, and missing file. `BaseException` catch in save ensures temp file cleanup even on `KeyboardInterrupt`.
- **Stall detection:** Correctly uses 4-entry window with `>=` comparison (non-decreasing open count = no progress).
- **Deletion detection:** Compares current total against previous max total, not just adjacent entries.

No additional bugs found.

---

## Summary

| # | File | Severity | Category | Determinism |
|---|------|----------|----------|-------------|
| 1 | impact_graph.py | MEDIUM | bug/error-handling | deterministic (malformed input) |
| 2 | impact_graph.py | MEDIUM | bug/error-handling | deterministic (malformed input) |
| 3 | convergence_check.py | LOW | bug/error-handling | theoretical |
| 4 | impact_graph.py | LOW | bug/logic | deterministic |

Findings 1 and 2 share a root cause (missing per-entry validation in `load()`) and should be fixed together. Finding 3 is low-risk due to the machine-written nature of the history file. Finding 4 is a documented design decision with test coverage; noting for completeness only.

No findings in `markdown_utils.py` or `validate_punchlist.py`.

# Pattern Heuristic Scan Results

Scan target: `skills/holtz/scripts/` and `hooks/`
Date: 2026-03-23

---

## 1. Dual Parser Divergence

**Heuristic run:** `grep -rnP '(def|function|func)\s+(parse|extract|decode|deserialize|read|load|from_)\w*'` across scripts/ and hooks/; regex pattern comparison across files.

**Result: MATCH**

Both `validate_punchlist.py` and `convergence_check.py` independently parse the same PUNCHLIST.md format:

- `validate_punchlist.py:85` — `re.compile(r'^### (B[HJ]-\d+):[ \t]*(.*)$', re.MULTILINE)` with full field extraction
- `convergence_check.py:44` — `re.compile(r'^### B[HJ]-\d+:', re.MULTILINE)` with status-only extraction
- Both extract `**Status:**` fields using identical regex: `r'\*\*Status:\*\*[ \t]*(OPEN|IN PROGRESS|RESOLVED|DEFERRED)'`
  - `validate_punchlist.py:133`
  - `convergence_check.py:51`

Both parsers use `mask_code_fences()` for fence awareness and handle the same edge cases for status extraction, so this is a **true positive for duplication** but **not currently divergent** -- they agree on behavior. The divergence risk is future: if one parser is updated and the other is not, results will silently differ. `convergence_check.py:count_items()` could call `parse_punchlist()` and count statuses from the returned items instead of re-implementing the parsing.

Additionally, `convergence_check.py:load_history()` and `impact_graph.py:ImpactGraph.load()` are independent JSON loaders, but they load different file formats (array vs object), so this is not a true dual-parser case.

---

## 2. Regex Newline Leak

**Heuristic run:** `grep -rnP '\\s[*+?]'` across scripts/ and hooks/ (Python files).

**Result: NO MATCH**

Zero instances of `\s` with quantifiers found in any script or hook file. All whitespace-matching regex patterns use `[ \t]` consistently (e.g., `[ \t]*` in validate_punchlist.py, convergence_check.py, artifact_verification.py). This appears to be a deliberate design choice -- the codebase has been cleaned of this pattern.

---

## 3. Doc-Spec Drift

**Heuristic run:** Compared documented defaults/values in `*.md` files against code defaults in `*.py` files; compared function signatures in docs vs code.

**Result: MATCH (minor)**

Locations with potential drift:

1. **STALENESS_WINDOW** -- `hooks/status_staleness_gate.py:21` defines `STALENESS_WINDOW = 300` (5 minutes). The SKILL.md and reference docs do not document this specific threshold. The code comment on line 19 self-documents it, but no external spec file mentions the value. If someone changes the threshold in code, no doc needs updating -- but no doc describes it for users either. Low-severity informational gap rather than active drift.

2. **DEFAULT_GRAPH_PATH** -- `impact_graph.py:21` defines `DEFAULT_GRAPH_PATH = Path("docs/holtz/impact-graph.json")`. This matches `skills/holtz/references/impact-graph-operations.md` and `skills/holtz/SKILL.md:159` which both reference `docs/holtz/impact-graph.json`. No drift detected here -- values are consistent.

3. **DRIFT_LINE_THRESHOLD** -- `impact_graph.py:22` defines `DRIFT_LINE_THRESHOLD = 10`. This value is not documented in any reference file. Low severity -- internal implementation detail.

4. **Punchlist valid categories** -- `validate_punchlist.py:57-62` defines `VALID_CATEGORIES` with 16 categories. Cross-referencing with `skills/holtz/references/punchlist-format.md` would reveal whether these match. The categories are not duplicated in docs that were scanned, so no active drift is detectable, but no external spec anchors them either.

Overall: no active contradiction found between docs and code. The drift risk is that several code constants lack corresponding spec documentation.

---

## 4. Code Fence Unaware Parsing

**Heuristic run:** `grep -rnP 're\.(search|findall|finditer|match)\(.*\b(content|body|text|document|source|raw|markdown|md_text)\b'` across scripts/ and hooks/.

**Result: MATCH (acknowledged/accepted)**

Locations:

1. **`hooks/subagent_findings_check.py:33`** -- `re.findall(r'docs/holtz/[^\s"\')\]]+\.md', message)` operates on raw `message` text without code-fence masking. This is explicitly acknowledged in the file's docstring (lines 9-12): "Path extraction operates on raw message text without code-fence masking. Paths mentioned in code examples may trigger false-positive warnings. This is acceptable because the hook only warns (exit 1) and false positives are preferable to missed findings." Accepted risk, not a latent bug.

2. **`convergence_check.py:96,99`** -- `re.search(r'^\[tool\.pytest[\].]', content, re.MULTILINE)` operates on raw `content` of `pyproject.toml` and `setup.cfg`. These are TOML/INI files, not markdown, so code-fence masking is not applicable. Not a true positive.

3. **`validate_punchlist.py` and `convergence_check.py`** -- both correctly use `mask_code_fences()` before applying structural regex to markdown content. These are examples of the pattern being handled correctly.

---

## 5. Missing Edge Case Handling

**Heuristic run:** `grep -rnP '\w+\[[\x27"][^\x27"]+[\x27"]\]'` for direct dict access; `grep -rnP '\w+\.\w+\.\w+\.\w+'` for chained attribute access.

**Result: MATCH**

Locations with direct dict key access (potential KeyError if data is malformed):

1. **`convergence_check.py:296`** -- `curr_pl["OPEN"] + curr_pl["IN PROGRESS"]` -- direct dict access on the return value of `_get_punchlist()`. However, `_get_punchlist()` (line 280-286) constructs the dict with all expected keys guaranteed present via explicit defaults: `{k: pl.get(k, 0) for k in default}`. So this is safe -- the upstream function guarantees the keys. Not a true positive.

2. **`convergence_check.py:346-347`** -- `snapshots_with_tests[0]["tests"]["failed"]` -- chained access assumes `"tests"` dict has a `"failed"` key. The list comprehension filter on line 342-343 checks `s.get("tests") and "failed" in s.get("tests", {})`, so `"failed"` is guaranteed present. Not a true positive.

3. **`impact_graph.py:90-93`** -- `node["type"] = ...`, `node["file"] = ...` -- these are write operations to a node that was just retrieved from `self.nodes[node_id]` after confirming `node_id in self.nodes`. Safe.

4. **`impact_graph.py:204`** -- `n["id"]` in sort key lambda. Nodes are created with `"id"` in `add_node()` (line 97), but `load()` accepts arbitrary JSON from disk. If the JSON file contains a node dict without an `"id"` key, `risk_hotspots()` would raise `KeyError`. **True positive** -- external data loaded from a JSON file could be malformed.

5. **`impact_graph.py:123`** -- `edge["source"]`, `edge["target"]`, `edge["type"]` -- edges loaded from JSON could be missing these keys. The `load()` method does `self.edges = edges if isinstance(edges, list) else []` but does not validate individual edge dicts. **True positive** -- malformed edge dicts from the JSON file could cause KeyError in `neighbors()`, `blast_radius()`, `add_edge()`, or `prune_node()`.

Chained attribute access: only 1 hit at `impact_graph.py:69` (`self.path.parent.mkdir`) -- this is a standard `pathlib` chain, not a null-risk pattern.

---

## 6. Incomplete Layer Isolation

**Heuristic run:** `grep -rnP '(class|def)\s+\w*(Manager|Service|Client|...|Adapter)\b'` for named abstraction layers; manual inspection of `_common.py` as a shared hook interface and `markdown_utils.py` as a shared parsing layer.

**Result: MATCH (partial)**

Two abstraction layers identified:

### Layer A: `hooks/_common.py` (hook I/O layer)

All 4 hook files import from `_common.py` and use its `exit_ok()`, `exit_warn()`, `exit_block()`, and `read_event()` functions. No hook bypasses this layer with raw `print(json.dumps(...))` or direct `sys.exit()` calls. **Fully isolated -- no bypass detected.**

### Layer B: `markdown_utils.py` (code-fence masking layer)

- `validate_punchlist.py` -- imports and uses `mask_code_fences()` and `has_unclosed_fence()`. Correct.
- `convergence_check.py` -- imports and uses `mask_code_fences()`. Correct.
- `hooks/subagent_findings_check.py` -- applies regex to raw message text **without** importing `markdown_utils`. This bypasses the masking layer. However, as noted under Pattern 4, this is explicitly documented as an accepted tradeoff in the file's docstring. **Acknowledged bypass, not an accidental omission.**

No hook file processes markdown punchlist content, so the masking layer is not needed there. The bypass in `subagent_findings_check.py` is for a different data type (assistant message text, not punchlist markdown).

**Verdict:** Both abstraction layers are respected by their intended consumers. The one bypass is documented and intentional.

---

## Summary

| # | Pattern | Result | Severity |
|---|---------|--------|----------|
| 1 | Dual Parser Divergence | MATCH -- convergence_check.py duplicates punchlist parsing from validate_punchlist.py | LOW (not yet divergent, future risk) |
| 2 | Regex Newline Leak | NO MATCH -- all patterns use `[ \t]` instead of `\s` | -- |
| 3 | Doc-Spec Drift | MATCH (minor) -- several code constants lack spec documentation | LOW (no active contradictions) |
| 4 | Code Fence Unaware Parsing | MATCH (acknowledged) -- subagent_findings_check.py skips masking by design | LOW (documented tradeoff) |
| 5 | Missing Edge Case Handling | MATCH -- impact_graph.py assumes well-formed JSON in loaded edges/nodes | MEDIUM (malformed JSON file causes KeyError) |
| 6 | Incomplete Layer Isolation | MATCH (partial) -- one documented bypass of markdown_utils layer | LOW (intentional) |

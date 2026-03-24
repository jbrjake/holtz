# Step 0h: Predictive Recon

**Run 14 — 2026-03-24**

## Input Sources

| Source | Signal |
|--------|--------|
| Pattern Brief | PAT-001 (code-fence-unaware), PAT-002 (incomplete isolation), PAT-003 (regex convention violation) — 3 known patterns |
| Impact Graph | 37 nodes, 9 `assumes` edges, 1 `diverges_from` edge, risk_score ceiling at 0.0 (post-convergence) |
| Git Churn | No source changes since run 13 |
| Prior Run 13 | 4 findings (2 MEDIUM, 2 LOW), all resolved. BH-001 was PAT-003 adjacent |
| Recon | `pattern_brief_compact.py` has 2 `\s` regex hits, only module violating convention |
| Global Patterns | regex-newline-leak heuristic hit on pattern_brief_compact.py lines 41, 53 |

## Predictions

### Prediction 1
**Target:** `skills/holtz/scripts/pattern_brief_compact.py:53` — `\s*` in field extraction regex
**Predicted Issue:** regex-newline-leak — `\s*` after `**Field:**` could match `\n`, causing `(.*?)` to capture from the next line when a field has an empty value
**Confidence:** HIGH
**Basis:** Global pattern library match (`regex-newline-leak.md`) + detection heuristic hit + PAT-003 adjacency (same convention violation class) + this is the only module still using `\s`
**Lens:** component
**Graph Support:** `pattern_brief_compact` node has no `assumes` edges — isolated module, low blast radius
**Outcome:** CONFIRMED — empty field causes content bleed from next field (BH-004)

### Prediction 2
**Target:** `skills/holtz/scripts/pattern_brief_compact.py:41` — `\s*$` in header regex
**Predicted Issue:** regex-newline-leak — `\s*` before `$` in header pattern. In MULTILINE mode, `$` matches end of line, but `\s*` preceding it could match trailing whitespace including `\r` in CRLF files
**Confidence:** MEDIUM
**Basis:** Detection heuristic hit, but the `^...$` anchors + MULTILINE constrain the match to a single line. Impact limited to CRLF edge case.
**Lens:** component
**Graph Support:** —
**Outcome:** UNCONFIRMED — `\s*$` in header regex correctly handles CRLF. Convention violation exists but is actually correct behavior for cross-platform compatibility.

### Prediction 3
**Target:** `pattern_brief_compact.py` — `parse_brief()` applies regex directly to content without masking
**Predicted Issue:** code-fence-unaware-parsing — if a pattern brief contains a code example with a `## PAT-NNN:` header inside a code fence, `parse_brief` would match it as a real entry
**Confidence:** MEDIUM
**Basis:** parse_brief uses `header_re.finditer(content)` without masking. Pattern brief format includes `**Example:**` sections that could contain fenced code with pattern headers.
**Lens:** component
**Graph Support:** No `assumes` edges, no callers in graph
**Outcome:** CONFIRMED — fake PAT-999 header inside code fence matched as real entry (BH-005)

### Prediction 4
**Target:** `README.md` "What's inside" line
**Predicted Issue:** doc-spec-drift — README counts may be stale for ref docs (claimed 17) and line count (claimed 8,500). Test only validates test count.
**Confidence:** HIGH
**Basis:** Recurring recommendation (4 appearances). `test_readme_metrics_match_actual` only checks test count. Ref doc count and line count are unchecked. README was updated in commit 30f4dfc.
**Lens:** public-contract
**Graph Support:** `README.md` diverges_from `validate_punchlist.py` edge exists
**Outcome:** UNCONFIRMED — README counts are currently correct (all 9 match). However, BH-001 (test only checks 1 of 9 fields) remains valid as a design/inconsistency finding.

### Prediction 5
**Target:** `hooks/` coverage
**Predicted Issue:** test/shallow — hooks show 0% coverage because test_hooks.py tests via subprocess. This means coverage-guided audit work will systematically overlook hook code.
**Confidence:** LOW
**Basis:** Single signal (coverage report). Hooks are tested functionally (531 lines in test_hooks.py). The 0% is a reporting artifact, not a real coverage gap. However, any NEW hook paths added without tests would be invisible to coverage.
**Lens:** integration
**Graph Support:** Hook nodes have `tests` edges in graph
**Outcome:**

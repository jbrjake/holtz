# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz | Run: 19 | Baseline: 639 pass, 1 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 0 |
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 2 | 0 |

## Patterns

(none yet)

## Items

### BH-001: README seed pattern count stale — "Fourteen" should be "Sixteen"
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:108`, `README.md:216`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (HIGH) — failing test, direct observation

**Problem:** README says "Fourteen seed patterns" (line 108) and "14 seed patterns" (line 216, What's inside section). Actual count is 16 — two new patterns added in recent commits: `numeric-precision-exhaustion` (92e9e5f) and `cross-language-dead-interface` (4e4cf0a). Line 108 also lists 14 pattern names by name, missing the two new ones. The test `test_readme_metrics_match_actual` is currently failing because of this mismatch.

**Evidence:**
- `ls skills/holtz/patterns/ | wc -l` → 16
- README line 108: "Fourteen seed patterns ship with the plugin: regex newline leaks, code-fence-unaware parsing, incomplete layer isolation, dual-parser divergence, missing edge case handling, doc-spec drift, concurrency violation, resource leak, uncontrolled amplification, error destruction, cache coherence failure, silent semantic mismatch, implicit ordering dependency, dead code latent path."
- Missing from list: numeric-precision-exhaustion, cross-language-dead-interface
- README line 216: "14 seed patterns"
- `test_readme_metrics_match_actual` FAILING

**Discovery Chain:** Step 2 subagent ran tests → `test_readme_metrics_match_actual` failed (expected 14, found 16) → confirmed 2 new patterns added in recent feat commits → README not updated

**Acceptance Criteria:**
- [ ] README line 108 says "Sixteen seed patterns" and lists all 16 by name
- [ ] README line 216 says "16 seed patterns"
- [ ] `test_readme_metrics_match_actual` passes

**Validation Command:**
```bash
python -m pytest tests/test_integration.py -k "test_readme_metrics_match_actual" -v
```

### BH-002: README lens count inconsistency — "nine" in two places, "thirteen" in another
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:38`, `README.md:146`, `README.md:114`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 2 (HIGH) — direct observation

**Problem:** The README has three references to the lens count with contradictory values:
- Line 38: "nine analytical lenses" (STALE)
- Line 146: "across all nine lenses — component, integration, security, error propagation, data flow, contract, semantic fidelity, temporal protocol, public contract" (STALE — lists only 9)
- Line 114: "The thirteen analytical lenses that ship are defaults" (CORRECT)

The lens registry has 13 lenses. 4 were added in commit b85a98a: concurrency, resource-lifecycle, idempotency, observability. Lines 38 and 146 were not updated.

**Evidence:**
- `grep '^## ' skills/holtz/references/lens-registry.md | wc -l` → 13
- Line 114 says "thirteen" (correct)
- Lines 38 and 146 say "nine" (stale)
- Line 146 lists 9 lenses by name, missing 4

**Discovery Chain:** Lens registry has 13 entries → README line 114 says "thirteen" (correct) → README line 38 says "nine" (stale) → README line 146 lists 9 names (stale) → internal inconsistency within same document

**Acceptance Criteria:**
- [ ] Line 38 says "thirteen analytical lenses"
- [ ] Line 146 lists all 13 lenses by name
- [ ] No internal inconsistency between lens count references

**Validation Command:**
```bash
grep -c "thirteen" README.md  # should match lines 38, 114, 146
```

### BH-003: README anti-pattern count stale — "twelve" should be "seventeen"
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:50`, `README.md:138`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 3 (MEDIUM) — direct comparison

**Problem:** README says "twelve anti-patterns across three tiers" (line 50) and "twelve anti-patterns" (line 138). The actual count is 17 — items 13-17 were added in commit 2a35821.

**Evidence:**
- `skills/holtz/references/anti-patterns.md` contains 17 numbered items (1-17)
- `git log --oneline -1 -- skills/holtz/references/anti-patterns.md` → `2a35821 feat(patterns): add 5 test antipatterns (items 13-17)`
- README lines 50, 138 both say "twelve"

**Discovery Chain:** anti-patterns.md has 17 numbered items → README says "twelve" in two locations → commit 2a35821 added items 13-17 → README not updated

**Acceptance Criteria:**
- [ ] Line 50 says "seventeen anti-patterns across three tiers"
- [ ] Line 138 says "seventeen anti-patterns"

**Validation Command:**
```bash
grep -n "twelve anti-patterns\|seventeen anti-patterns" README.md
```

### BH-004: README run counts and practice narrative stale — "Sixteen" should be "Eighteen"
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:160`, `README.md:190`, `README.md:192`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 4 (MEDIUM) — recurring drift class

**Problem:** README "What this looks like in practice" section says "Sixteen runs" (line 160), "After 16 runs: 619 tests across 13,800 lines" (line 190), and "across all 16 runs" (line 192). Actual: 18+ runs completed (Run 18 archived, Run 19 in progress). After Run 18: 640 tests across 13,900 lines of code. Runs 17 and 18 are not described in the narrative.

**Evidence:**
- `ls docs/holtz/archive/ | grep run | wc -l` → 17+ run archives exist
- Run 18 SUMMARY.md: 640 tests, 7 items found, 13,900+ lines
- README line 160: "Sixteen runs"
- README line 190: "After 16 runs: 619 tests across 13,800 lines"

**Discovery Chain:** docs/holtz/archive/ contains Run 18 → README says "Sixteen runs" → line 190 shows stale test/line counts → recurring drift (same class as Runs 14-18)

**Acceptance Criteria:**
- [ ] Line 160 updated to "Eighteen runs"
- [ ] Line 190 updated to "After 18 runs: 640 tests across 13,900 lines"
- [ ] Line 192 updated to "all 18 runs"
- [ ] Run 18 narrative added (or section indicates historical freeze point)

**Validation Command:**
```bash
grep -n "Sixteen runs\|16 runs\|Eighteen runs\|18 runs" README.md
```

### BH-005: Recommendation escalation — README semantic claim test coverage gap
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `tests/test_integration.py`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 6 (MEDIUM) — recommendation escalation (Runs 13+16)

**Problem:** README semantic claims beyond counts (feature descriptions, capability claims, convergence behavior) lack integration test coverage. `test_readme_metrics_match_actual` checks numeric counts (patterns, tests, coverage) but not semantic claims (lens descriptions, feature capabilities, step descriptions). This recommendation appeared in Run 13 ("README maintenance — consider integration test") and Run 16 ("Add README semantic claim test"). 2+ appearances triggers escalation per protocol.

**Evidence:**
- Run 13 SUMMARY.md: "README maintenance: Consider an integration test or hook that checks README counts match reality"
- Run 16 SUMMARY.md: "Add README semantic claim test. The integration test validates component counts but not descriptive claims"
- Current `test_readme_metrics_match_actual` checks: pattern count, test count, coverage — does NOT check lens count, anti-pattern count, hook count, etc.

**Discovery Chain:** Run 13 recommendation → Run 16 same recommendation → 2 appearances → escalation protocol → punchlist item

**Acceptance Criteria:**
- [ ] Integration test verifies lens count in README matches lens-registry.md
- [ ] Integration test verifies anti-pattern count in README matches anti-patterns.md
- [ ] Integration test verifies seed pattern count (already exists but should be comprehensive)

**Validation Command:**
```bash
python -m pytest tests/test_integration.py -k "readme" -v
```

### BH-006: token_profiler --pricing flag is a silent no-op
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/token_profiler/cli.py:326-415`, `scripts/token_profiler/analyze.py:297`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 7 (MEDIUM) — cold file unknown risk

**Problem:** The `--pricing` CLI flag loads a JSON pricing file (cli.py:328-330) into `custom_pricing`, which is then explicitly suppressed with `_ = custom_pricing` (line 414-415). The `pricing_fn` parameter in `build_session_profile` (analyze.py:297) is accepted but never called — dollar costs are always $0.0. A user passing `--pricing my-prices.json` would see zero-dollar costs with no indication their pricing file was ignored.

**Evidence:**
- `cli.py:326`: `# Load custom pricing (not yet integrated into full pipeline, but load it)`
- `cli.py:414-415`: `# Suppress unused variable warning for custom_pricing` / `_ = custom_pricing`
- `analyze.py:297`: `pricing_fn: PricingFn | None = None` — parameter accepted, never called in function body
- `grep -rn pricing_fn scripts/token_profiler/` shows only 2 hits (type alias + parameter), zero usage

**Discovery Chain:** Cold file audit of token_profiler → `pricing_fn` parameter unused in analyze.py → traced to CLI where `custom_pricing` is loaded then suppressed → confirmed dead feature path

**Acceptance Criteria:**
- [ ] Either integrate pricing_fn into build_session_profile to compute real dollar costs
- [ ] Or remove the --pricing flag and pricing_fn parameter to avoid misleading users
- [ ] Test verifies pricing is applied (or flag is removed)

**Validation Command:**
```bash
grep -rn "pricing_fn\|custom_pricing" scripts/token_profiler/
```

### BH-007: extract.py json.loads without error context at data boundary
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/extract.py:236`
**Status:** RESOLVED
**Lens:** error-propagation

**Problem:** `_read_jsonl` calls `json.loads(line)` with no exception handling. A malformed JSONL line produces a raw `JSONDecodeError` traceback with no indication of which file or which line number in the file is bad. This is a data ingestion boundary reading user-provided files.

**Evidence:**
```python
# extract.py:233-237
for line in f:
    line = line.strip()
    if line:
        records.append(json.loads(line))  # no try/except
```

**Discovery Chain:** Cold file audit → extract.py reads external JSONL files → json.loads at line 236 has no error wrapping → user sees raw traceback on corrupt input

**Acceptance Criteria:**
- [ ] Malformed JSONL line produces error with file path and line number
- [ ] Test verifies error message includes file context

**Validation Command:**
```bash
python -m pytest tests/ -k "jsonl" -v
```

### BH-008: artifact_verification.py uses \s instead of [ \t] (PAT-003)
**Severity:** LOW
**Category:** bug/convention
**Location:** `hooks/artifact_verification.py:25`
**Status:** RESOLVED
**Lens:** contract
**Pattern:** PAT-003

**Problem:** Line 25 uses `r'(?:^|[\s/])impact_graph\.py\b'` where `\s` matches newlines, carriage returns, form feeds in addition to spaces and tabs. Per project convention, horizontal whitespace should use `[ \t]`. In this context, `\s` could match a newline in a multi-line command string, causing a false-positive hook trigger.

**Evidence:**
```python
# artifact_verification.py:25
if not re.search(r'(?:^|[\s/])impact_graph\.py\b', command):
```
Convention: all regex in source uses `[ \t]` not `\s` for horizontal whitespace (architecture-baseline.md Conventions).

**Discovery Chain:** Cold file audit triggered PAT-003 detection heuristic → `\s` in artifact_verification.py:25 → matches newline in addition to space/tab → theoretical false-positive on multi-line commands

**Acceptance Criteria:**
- [ ] `\s` replaced with `[ \t]` in the regex
- [ ] Test verifies hook doesn't false-positive on multi-line command with impact_graph.py on a non-command line

**Validation Command:**
```bash
grep -rn '\\s' hooks/artifact_verification.py
```

### BH-009: analyze.py _parse_iso without error context
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/analyze.py:256-260`
**Status:** RESOLVED
**Lens:** error-propagation

**Problem:** `_parse_iso(turn.timestamp)` is called at lines 256, 257, 260 inside milestone application logic with no try/except. A malformed timestamp in the input data produces a raw ValueError that aborts the entire analysis pipeline with no indication of which turn had the bad timestamp.

**Evidence:**
```python
# analyze.py:256-260
start_dt = _parse_iso(ms["start_time"])
end_dt = _parse_iso(ms["end_time"])
for turn in turns:
    if turn.timestamp:
        turn_dt = _parse_iso(turn.timestamp)
```

**Discovery Chain:** Cold file audit → analyze.py calls _parse_iso on external timestamp data → no error wrapping → user sees raw ValueError on malformed timestamp

**Acceptance Criteria:**
- [ ] Malformed timestamp produces error with turn index and raw value
- [ ] Test verifies error message includes context

**Validation Command:**
```bash
python -m pytest tests/ -k "parse_iso" -v
```

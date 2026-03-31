# Phase 2: Test Quality — pattern_brief_compact tests

**Predicted areas audited first per 0h-predictions.md**

## test_pattern_brief_compact.py (76 lines, 5 tests)

**Red flags: 2 (decent)**

1. **Happy Path Tourist (#5)** — All 5 tests use well-formed SAMPLE_BRIEF with all fields present on same line. No tests for:
   - Empty field values (`**What to look for:**\n**Detection heuristic:**`)
   - Malformed headers (missing date, run, or parentheses)
   - Content with code fences containing fake `## PAT-NNN:` headers
   - CRLF line endings
   - Single-entry brief

2. **Copy-Paste Archipelago (#10)** — SAMPLE_BRIEF (26 lines) is duplicated verbatim between test_pattern_brief_compact.py and test_pattern_brief_compact_structure.py. Should be a shared fixture in conftest.py.

The missing edge case tests directly relate to Predictions 1 and 3: the `\s*` regex and code-fence-unaware parsing are untested.

## test_pattern_brief_compact_structure.py (83 lines, 5 tests)

**Red flags: 1 (decent)**

1. **Rubber Stamp (#11)** — Structural tests by design. They verify format contracts (all IDs present, size ordering, key terms) but not content correctness. This is intentional for CI-safe testing, so it's a design decision, not a quality issue.

## test_integration.py (252 lines)

Quick scan: `test_readme_metrics_match_actual` only asserts on `claimed_tests` (line 249) despite extracting all 9 fields from the regex match (line 230-234). This is the BH-001 finding — a partial test.

## test_markdown_utils.py (233 lines)

Quick scan: 0 red flags. Tests cover fence state machine thoroughly including edge cases (nested fences, mismatched chars, unclosed fences, empty lines inside fences).

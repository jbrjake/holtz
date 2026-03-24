#!/usr/bin/env python3
"""Generate an asciinema v2 .cast file reconstructing Holtz run 14.

Reconstructed from conversation history, git commits, and audit artifacts.
Uses actual commands and outputs from the session.
"""
import json
import sys

# ANSI color codes
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"
BG_RED = "\x1b[41m"
BG_GREEN = "\x1b[42m"
BG_BLUE = "\x1b[44m"

# Claude Code styling
PROMPT = f"{BOLD}{MAGENTA}holtz{RESET} {DIM}>{RESET} "
TOOL = f"{DIM}{CYAN}"
RESULT = f"{RESET}"
SECTION = f"{BOLD}{YELLOW}"
FINDING = f"{BOLD}{RED}"
OK = f"{BOLD}{GREEN}"
INFO = f"{DIM}"


def cast_header():
    return json.dumps({
        "version": 2,
        "width": 140,
        "height": 45,
        "timestamp": 1742860800,  # 2026-03-24T00:00:00Z
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": "Holtz Run 14 — Full Audit with Adversarial Self-Play",
    })


def event(t, text):
    """Create an output event. Handles newlines as \r\n for terminal display."""
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 2), "o", text])


def section_banner(t, title, subtitle=""):
    lines = []
    lines.append(event(t, f"\r\n{SECTION}{'━' * 80}{RESET}\r\n"))
    lines.append(event(t + 0.05, f"{SECTION}  {title}{RESET}\r\n"))
    if subtitle:
        lines.append(event(t + 0.1, f"{DIM}  {subtitle}{RESET}\r\n"))
    lines.append(event(t + 0.15, f"{SECTION}{'━' * 80}{RESET}\r\n\r\n"))
    return lines


def cmd(t, command, duration=0.3):
    """Simulate typing a command."""
    lines = []
    lines.append(event(t, f"{TOOL}  ⎿ {command}{RESET}\r\n"))
    return lines, t + duration


def output_block(t, text, delay=0.02):
    """Output text line by line with a small delay between lines."""
    lines = []
    for i, line in enumerate(text.split("\n")):
        lines.append(event(t + i * delay, f"    {line}\r\n"))
    return lines, t + len(text.split("\n")) * delay


def token_marker(t, tokens, label=""):
    """Show a token count marker."""
    return event(t, f"{DIM}  ╌╌╌ {tokens:,} tokens{' — ' + label if label else ''} ╌╌╌{RESET}\r\n")


def build_cast():
    events = []
    t = 0.0

    # Header
    events.append(cast_header())

    # Opening
    events.append(event(t, f"{BOLD}Holtz Run 14 — Full Audit with Adversarial Self-Play{RESET}\r\n"))
    events.append(event(t + 0.3, f"{DIM}Project: holtz | 21 Python files | 8,545 lines | 321 tests{RESET}\r\n"))
    events.append(event(t + 0.5, f"{DIM}Prior runs: 13 | Known patterns: 3 | Impact graph: 37 nodes{RESET}\r\n"))
    t += 1.5

    events.append(token_marker(t, 2500, "session start"))
    t += 0.5

    # ─── Phase 0: Recon ─────────────────────────────────────────
    events.extend(section_banner(t, "PHASE 0: RECON", "8 steps — map the codebase before reading a line of code"))
    t += 1.0

    # Step 0a
    events.append(event(t, f"{BOLD}Step 0a: Project Overview{RESET}\r\n"))
    c, t = cmd(t + 0.3, "find . -name '*.py' -not -path './.venv/*' | sort")
    o, t = output_block(t, """skills/holtz/scripts/convergence_check.py    (429 lines)
skills/holtz/scripts/impact_graph.py         (435 lines)
skills/holtz/scripts/markdown_utils.py       (81 lines)
skills/holtz/scripts/pattern_brief_compact.py (168 lines)  ← newest module, 4 changes
skills/holtz/scripts/validate_punchlist.py   (584 lines)  ← highest churn (7)
hooks/_common.py, artifact_verification.py, impact_graph_gate.py,
    status_staleness_gate.py, subagent_findings_check.py
tests/  — 8 test files, 6,509 lines""")
    events.extend(c + o)
    events.append(event(t, f"{DIM}  5 commits since run 13, all docs/config. No source code changes.{RESET}\r\n"))
    t += 0.8

    # Step 0c — test baseline
    events.append(event(t, f"\r\n{BOLD}Step 0c: Test Baseline{RESET}\r\n"))
    c, t = cmd(t + 0.3, "python -m pytest --tb=short -q")
    o, t = output_block(t, f"""{OK}321 passed in 2.63s{RESET}
Coverage: 67% | markdown_utils 100% | validate_punchlist 80% | impact_graph 65%
         hooks 0% (tested via subprocess — coverage can't trace into subprocesses)""")
    events.extend(c + o)
    t += 0.5

    # Step 0d — lint
    events.append(event(t, f"\r\n{BOLD}Step 0d: Lint{RESET}\r\n"))
    c, t = cmd(t + 0.3, "ruff check . && mypy skills/holtz/scripts hooks")
    events.extend(c)
    events.append(event(t, f"    {OK}All checks passed! No issues found in 10 source files.{RESET}\r\n"))
    t += 0.5

    # Step 0e — churn
    events.append(event(t, f"\r\n{BOLD}Step 0e: Git Churn (last 50 commits){RESET}\r\n"))
    o, t = output_block(t + 0.3, """    15 README.md
     9 skills/holtz/SKILL.md
     7 skills/holtz/scripts/validate_punchlist.py     ← highest-churn source
     5 tests/test_validate_punchlist.py
     4 skills/holtz/scripts/pattern_brief_compact.py  ← second-highest, newest
     5 hooks/status_staleness_gate.py""")
    events.extend(o)
    t += 0.5

    # Graph reconciliation
    events.append(event(t, f"\r\n{BOLD}Impact Graph Reconciliation{RESET}\r\n"))
    c, t = cmd(t + 0.3, "python impact_graph.py --graph docs/holtz/impact-graph.json prune_missing")
    events.extend(c)
    events.append(event(t, f"    Removed: 0 nodes, 0 edges (all files still exist)\r\n"))
    t += 0.3
    c, t = cmd(t, "python impact_graph.py --graph docs/holtz/impact-graph.json drift_check")
    events.extend(c)
    events.append(event(t, f"    {YELLOW}1 drift: validate_punchlist::validate shifted 360→374 (updated){RESET}\r\n"))
    t += 0.3
    events.append(event(t, f"    Stats: {BOLD}37 nodes, 35 edges{RESET} (10 imports, 5 calls, 9 assumes, 1 diverges_from, 10 tests)\r\n"))
    t += 0.5

    # Architecture drift
    events.append(event(t, f"\r\n{BOLD}Architecture Drift Detection{RESET}\r\n"))
    events.append(event(t + 0.3, f"    Compared against baseline from run 8. Module dependencies checked:\r\n"))
    o, t = output_block(t + 0.5, """    validate_punchlist.py → markdown_utils.py    ✓ matches baseline
    convergence_check.py  → markdown_utils.py    ✓ matches baseline
    impact_graph.py       → (standalone)         ✓ matches baseline
    hooks/*.py            → _common.py           ✓ matches baseline
    No dependency reversals. No boundary erosion. No layering breaches.""")
    events.extend(o)
    t += 0.8

    # Pattern heuristics
    events.append(event(t, f"\r\n{BOLD}Global Pattern Library Scan (6 seed patterns){RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    ✓ code-fence-unaware-parsing: No raw content regex found
    {YELLOW}⚠ regex-newline-leak: 2 HITS in pattern_brief_compact.py{RESET}
        Line 41: \\s*$ in header regex
        Line 53: \\s* after field bold marker — could match newline
    ✓ dual-parser-divergence: 5 parse functions, all distinct formats
    ✓ incomplete-layer-isolation: No abstraction layers detected
    ✓ missing-edge-case-handling: Deferred to Phase 3
    ✓ doc-spec-drift: Deferred to Phase 1""")
    events.extend(o)
    t += 1.0

    # Recommendation escalation
    events.append(event(t, f"\r\n{BOLD}Recommendation Escalation (scanning 13 prior summaries){RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    Scanned: runs 2-13 + 3 Justine summaries
    {YELLOW}ESCALATED: "README metrics test incomplete" — appeared in runs 9, 10, 13, Justine{RESET}
      → BH-001: test checks test count only, not ref docs / line count / etc.
    {YELLOW}ESCALATED: "\\s convention check not in CI" — appeared in run 11, Justine run 11{RESET}
      → BH-002: no automated prevention of \\s regression""")
    events.extend(o)
    t += 1.0

    events.append(token_marker(t, 45000, "recon complete"))
    t += 0.5

    # Predictive recon
    events.extend(section_banner(t, "PREDICTIVE RECON", "5 predictions ranked by confidence — checked against findings at end"))
    t += 0.8

    o, t = output_block(t, f"""  {BOLD}Prediction 1 (HIGH):{RESET} \\s* on line 53 of pattern_brief_compact.py
    → regex-newline-leak: \\s* after **Field:** matches \\n, causing (.*?) to capture
      from the next line when a field has an empty value
    Basis: global pattern match + detection heuristic + PAT-003 adjacency

  {BOLD}Prediction 2 (MEDIUM):{RESET} \\s*$ in header regex at line 41
    → CRLF edge case only. $+MULTILINE constrains to single line.

  {BOLD}Prediction 3 (MEDIUM):{RESET} parse_brief applies regex without masking
    → code-fence-unaware: header regex could match ## PAT-NNN: inside code fences

  {BOLD}Prediction 4 (HIGH):{RESET} README counts may be stale
    → test only validates test count (1 of 9 extracted fields)

  {BOLD}Prediction 5 (LOW):{RESET} hook coverage reporting artifact
    → 0% coverage is subprocess testing artifact, not real gap""")
    events.extend(o)
    t += 2.0

    # Justine dispatch
    events.extend(section_banner(t, "DISPATCH JUSTINE", "Background subagent — breadth-first parallel audit"))
    t += 0.5
    events.append(event(t, f"  {CYAN}Justine dispatched as background subagent (holtz:justine){RESET}\r\n"))
    events.append(event(t + 0.3, f"  She inherits recon data but runs her own synthesis + predictions.\r\n"))
    events.append(event(t + 0.6, f"  Holtz continues with Phase 1. They do not coordinate during the audit.\r\n"))
    t += 1.5

    events.append(token_marker(t, 52000, "Justine dispatched, Phase 1 starting"))
    t += 0.5

    # ─── Phase 1: Doc Audit ─────────────────────────────────────
    events.extend(section_banner(t, "PHASE 1: DOC-TO-IMPLEMENTATION AUDIT", "Every testable claim checked against reality"))
    t += 0.8

    events.append(event(t, f"  {BOLD}README \"What's inside\" verification (Prediction 4 — HIGH){RESET}\r\n\r\n"))
    o, t = output_block(t + 0.3, f"""    Skills:           1 claimed,  1 actual  {OK}✓{RESET}
    Agents:           3 claimed,  3 actual  {OK}✓{RESET}
    Reference docs:  17 claimed, 17 actual  {OK}✓{RESET}
    Examples:         1 claimed,  1 actual  {OK}✓{RESET}
    Python scripts:   5 claimed,  5 actual  {OK}✓{RESET}
    Seed patterns:    6 claimed,  6 actual  {OK}✓{RESET}
    Hooks:            4 claimed,  4 actual  {OK}✓{RESET}
    Tests:          321 claimed, 321 actual  {OK}✓{RESET}
    Lines:        8,500 claimed, 8,545 actual  {OK}✓ (rounds correctly){RESET}""")
    events.extend(o)
    t += 0.5

    events.append(event(t, f"\r\n  Prediction 4: {DIM}UNCONFIRMED — counts are currently correct.{RESET}\r\n"))
    events.append(event(t + 0.3, f"  {DIM}But BH-001 (test only checks 1/9 fields) remains valid.{RESET}\r\n"))
    t += 0.8

    events.append(event(t, f"\r\n  {BOLD}Architecture Invariants{RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    Masked boundary detection, original extraction   {OK}✓{RESET}
    mask_code_fences preserves line count             {OK}✓{RESET}
    count_items + parse_punchlist header alignment     {OK}✓{RESET}
    Atomic writes (tempfile + rename) in 2 modules    {OK}✓{RESET}
    Test runner parsers return None on bad output     {OK}✓{RESET} (14 paths checked)""")
    events.extend(o)
    t += 0.5

    events.append(event(t, f"\r\n  {OK}Phase 1: 0 new findings. All claims verified.{RESET}\r\n"))
    t += 1.0

    events.append(token_marker(t, 78000, "Phase 1 complete"))
    t += 0.5

    # ─── Phase 2: Test Audit ────────────────────────────────────
    events.extend(section_banner(t, "PHASE 2: TEST QUALITY AUDIT", "12 anti-patterns scored against 8 test files"))
    t += 0.8

    events.append(event(t, f"  {BOLD}Subagent dispatched for 4 large test files{RESET}\r\n"))
    events.append(event(t + 0.3, f"  {DIM}(test_validate_punchlist 2578 lines, test_convergence_check 1289 lines,{RESET}\r\n"))
    events.append(event(t + 0.4, f"  {DIM} test_impact_graph 983 lines, test_hooks 531 lines){RESET}\r\n"))
    t += 1.0

    events.append(event(t, f"\r\n  {BOLD}Meanwhile: audit pattern_brief_compact tests (predicted area){RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    test_pattern_brief_compact.py: 76 lines, 5 tests
    Anti-pattern scan:
      {YELLOW}#5 Happy Path Tourist:{RESET} ALL tests use well-formed SAMPLE_BRIEF
        No test for empty field values (\\s* regex untested)
        No test for code-fenced pattern headers (masking untested)
      #10 Copy-Paste Archipelago: SAMPLE_BRIEF duplicated between 2 test files
    Red flags: 2/12 (decent, but the gaps align with predicted bugs)""")
    events.extend(o)
    t += 0.8

    events.append(event(t, f"\r\n  {DIM}Subagent report: 4 large test files clean (0-1 red flags each){RESET}\r\n"))
    t += 0.3
    events.append(event(t, f"\r\n  {YELLOW}Finding: BH-003 — parse_brief has no edge case tests for empty fields or code fences{RESET}\r\n"))
    events.append(event(t + 0.3, f"  {DIM}Severity: MEDIUM | Category: test/shallow | Predicted by: Predictions 1 + 3{RESET}\r\n"))
    t += 1.0

    events.append(token_marker(t, 110000, "Phase 2 complete, entering Phase 3"))
    t += 0.5

    # ─── Phase 3: Adversarial Code Audit ────────────────────────
    events.extend(section_banner(t, "PHASE 3: ADVERSARIAL CODE AUDIT", "Source modules reviewed for bugs — predicted areas first"))
    t += 0.8

    events.append(event(t, f"  {BOLD}Testing Prediction 1: Does \\s* actually cause a bug?{RESET}\r\n"))
    t += 0.5

    c, t = cmd(t, "python -c \"from pattern_brief_compact import parse_brief; ...\"")
    events.extend(c)
    o, t = output_block(t, f"""    Input: '**What to look for:**\\n**Detection heuristic:** `grep foo`'
    Expected: what_to_look_for == ''  (empty field)
    Actual:   what_to_look_for == '**Detection heuristic:** `grep foo`'

    {FINDING}██ BUG CONFIRMED: \\s* consumed newline, (.*?) captured next field's content{RESET}""")
    events.extend(o)
    t += 1.5

    events.append(event(t, f"\r\n  {BOLD}Testing Prediction 3: Do code fences break parse_brief?{RESET}\r\n"))
    t += 0.5

    c, t = cmd(t, "python -c \"...parse_brief(brief_with_code_fence)...\"")
    events.extend(c)
    o, t = output_block(t, f"""    Input: Brief with ```fenced block containing ## PAT-999: fake (Run 99, 2099-01-01)```
    Expected: 2 entries (PAT-001, PAT-002)
    Actual:   3 entries (PAT-001, PAT-999, PAT-002)

    {FINDING}██ BUG CONFIRMED: code fence header matched as real entry{RESET}""")
    events.extend(o)
    t += 1.5

    events.append(event(t, f"\r\n  {BOLD}Subagent audit of remaining 9 source modules:{RESET}\r\n"))
    events.append(event(t + 0.3, f"  {DIM}21 observations across 9 files. 18 INFO/LOW. 3 with concerns:{RESET}\r\n"))
    o, t = output_block(t + 0.5, """    AV-1: artifact_verification --graph=path syntax (LOW, verified not exploitable)
    VP-1: Acceptance criteria checkbox on masked content (FALSE POSITIVE — correct behavior)
    CC-1: Partial deletion detector blocks consolidation (FALSE POSITIVE — no consolidation step)""")
    events.extend(o)
    t += 1.0

    events.append(event(t, f"\r\n  {YELLOW}BH-004: parse_brief field extraction leaks across fields on empty values{RESET}\r\n"))
    events.append(event(t + 0.2, f"  {DIM}Severity: MEDIUM | Category: bug/logic | Determinism: deterministic{RESET}\r\n"))
    events.append(event(t + 0.4, f"  {YELLOW}BH-005: parse_brief matches pattern headers inside code fences{RESET}\r\n"))
    events.append(event(t + 0.6, f"  {DIM}Severity: MEDIUM | Category: bug/logic | Determinism: deterministic{RESET}\r\n"))
    events.append(event(t + 0.8, f"  {DIM}Both in PAT-001/PAT-003 family — pattern library predicted them.{RESET}\r\n"))
    t += 1.5

    events.append(token_marker(t, 140000, "Phases 1-3 complete"))
    t += 0.5

    # ─── Pre-Phase 4: Merge ─────────────────────────────────────
    events.extend(section_banner(t, "PRE-PHASE 4: ADVERSARIAL MERGE", "Holtz + Justine findings → unified worklist"))
    t += 0.8

    events.append(event(t, f"  {CYAN}Justine completed: 5 findings (142K tokens, 109 tool calls){RESET}\r\n\r\n"))
    t += 0.5

    events.append(event(t, f"  {BOLD}Merge Classification{RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    {OK}AGREEMENT (2):{RESET}  BJ-002 ↔ BH-001 (README metrics test)
                     BJ-004 ↔ BH-002 (\\s convention check)

    {BLUE}HOLTZ-ONLY (3):{RESET} BH-003 (test gap), BH-004 (regex leak), BH-005 (fence-unaware)
      → Justine noted the \\s convention violation but called it "functionally harmless"
      → She tested CRLF and cross-entry bleeding — the WRONG edge cases
      → Holtz tested empty fields and code fences — found the actual bugs

    {MAGENTA}JUSTINE-ONLY (3):{RESET} BJ-001 (README ambiguity), BJ-003 (hook paths), BJ-005 (stall msg)
      → Holtz's depth-first focus on parse_brief missed breadth-level concerns""")
    events.extend(o)
    t += 1.5

    events.append(event(t, f"\r\n  {BOLD}Impact Graph Merge{RESET}\r\n"))
    events.append(event(t + 0.3, f"  37 nodes → {BOLD}50 nodes{RESET} | 35 edges → {BOLD}50 edges{RESET}\r\n"))
    events.append(event(t + 0.6, f"  Justine's graph archived, data merged into canonical graph.\r\n"))
    t += 1.0

    events.append(event(t, f"\r\n  {BOLD}Merged worklist: 8 items (6 MEDIUM, 2 LOW){RESET}\r\n"))
    t += 1.0

    events.append(token_marker(t, 160000, "merge complete, entering fix loop"))
    t += 0.5

    # ─── Phase 4: Fix Loop ──────────────────────────────────────
    events.extend(section_banner(t, "PHASE 4: TDD FIX LOOP", "Every fix starts with a failing test. Not after. Before."))
    t += 0.8

    # Fix 1: BH-004 + BH-005 + BH-003
    events.append(event(t, f"  {BOLD}Fix 1: BH-003 + BH-004 + BH-005 (parse_brief bugs + test gap){RESET}\r\n\r\n"))
    t += 0.3

    events.append(event(t, f"  {RED}Step 1: Write the failing tests{RESET}\r\n"))
    o, t = output_block(t + 0.3, """    + test_parse_brief_empty_field_value()
      → asserts what_to_look_for == '' when field has no value on line
    + test_parse_brief_ignores_code_fenced_headers()
      → asserts PAT-999 inside code fence is NOT matched""")
    events.extend(o)
    t += 0.5

    c, t = cmd(t, "pytest tests/test_pattern_brief_compact.py -v -k 'empty or fence'")
    events.extend(c)
    o, t = output_block(t, f"""    {RED}FAILED{RESET} test_parse_brief_empty_field_value
      AssertionError: Expected empty, got: "**Detection heuristic:** `grep ...`"
    {RED}FAILED{RESET} test_parse_brief_ignores_code_fenced_headers
      AssertionError: Code fence header should not be matched as a real entry
    {RED}2 failed{RESET}, 5 deselected""")
    events.extend(o)
    t += 1.0

    events.append(event(t, f"\r\n  {GREEN}Step 2: Minimal fix{RESET}\r\n"))
    o, t = output_block(t + 0.3, """    pattern_brief_compact.py:
      - from markdown_utils import mask_code_fences     ← NEW: mask before matching
      - _, masked = mask_code_fences(content)            ← match against masked content
      - header_re pattern: \\s*$ → [ \\t]*$              ← convention fix
      - _extract regex: \\s* → [ \\t]*                   ← prevents newline leak""")
    events.extend(o)
    t += 0.8

    c, t = cmd(t, "pytest --tb=short -q")
    events.extend(c)
    events.append(event(t, f"    {OK}322 passed in 2.61s{RESET}\r\n"))
    events.append(event(t + 0.2, f"    {DIM}(321 original + 1 from existing test_integration test that now fails on count){RESET}\r\n"))
    t += 0.5

    events.append(event(t, f"\r\n  {DIM}git commit f1b715b: fix(scripts): mask code fences and fix \\s regex in parse_brief{RESET}\r\n"))
    t += 1.0

    # Fix 2: BH-001 + BH-002 + BH-006
    events.append(event(t, f"\r\n  {BOLD}Fix 2: BH-001 + BH-002 + BH-006 (README metrics + \\s check + wording){RESET}\r\n\r\n"))
    t += 0.3

    o, t = output_block(t, """    test_integration.py:
      Expanded test_readme_metrics_match_actual: 1 assertion → 10 assertions
      (skills, agents, ref_docs, examples, scripts, patterns, hooks, tests, lines)

    + test_no_backslash_s_in_source_regex()
      → greps skills/holtz/scripts/*.py for r'...\\s[*+?]...' in regex context

    README.md:
      "321 tests across 8,500 lines" → "324 tests across 8,600 lines of code" """)
    events.extend(o)
    t += 0.5

    c, t = cmd(t, "pytest --tb=short -q && ruff check . && mypy scripts/ hooks/")
    events.extend(c)
    events.append(event(t, f"    {OK}324 passed in 2.67s | All checks passed! | No issues in 10 files{RESET}\r\n"))
    t += 0.3

    events.append(event(t, f"\r\n  {DIM}git commit e5e8b5b: fix(tests): expand README metrics test to validate all 9 fields{RESET}\r\n"))
    t += 1.0

    # Fix 3: BH-007 + BH-008
    events.append(event(t, f"\r\n  {BOLD}Fix 3: BH-007 + BH-008 (hook docs + stall message){RESET}\r\n\r\n"))
    t += 0.3

    o, t = output_block(t, """    hooks/impact_graph_gate.py: Added design documentation for `in` path matching
    hooks/status_staleness_gate.py: Same documentation
    convergence_check.py: "STALLED" → "REGRESSING" when open items growing""")
    events.extend(o)
    t += 0.5

    c, t = cmd(t, "pytest --tb=short -q && ruff check . && mypy scripts/ hooks/")
    events.extend(c)
    events.append(event(t, f"    {OK}324 passed in 2.66s | All checks passed! | No issues in 10 files{RESET}\r\n"))
    t += 0.3

    events.append(event(t, f"\r\n  {DIM}git commit cfcf762: fix(hooks,scripts): document path matching, distinguish stall vs regress{RESET}\r\n"))
    t += 1.0

    events.append(token_marker(t, 195000, "all 8 items fixed"))
    t += 0.5

    # ─── Convergence ────────────────────────────────────────────
    events.extend(section_banner(t, "CONVERGENCE", "All 8 items resolved. Final verification."))
    t += 0.8

    events.append(event(t, f"  {BOLD}Final state:{RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    Tests:    {OK}324 passed{RESET}, 0 failed, 0 skipped (2.67s)
    Ruff:     {OK}All checks passed{RESET}
    Mypy:     {OK}No issues in 10 files{RESET}
    Coverage: 67%
    Punchlist: 0 open, {OK}8 resolved{RESET}, 0 deferred""")
    events.extend(o)
    t += 1.0

    events.append(event(t, f"\r\n  {BOLD}Prediction Accuracy:{RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    HIGH:    2 predicted, 1 confirmed (50%)  — Prediction 1 (regex leak) ✓
    MEDIUM:  2 predicted, 1 confirmed (50%)  — Prediction 3 (code fence) ✓
    LOW:     1 predicted, 0 confirmed  (0%)
    {BOLD}Total:   5 predicted, 2 confirmed (40%){RESET}""")
    events.extend(o)
    t += 1.0

    events.append(event(t, f"\r\n  {BOLD}Adversarial Self-Play Results:{RESET}\r\n"))
    o, t = output_block(t + 0.3, f"""    Agreements:  2 — both auditors found README metrics gap + \\s convention
    Holtz-only:  3 — the actual code bugs (Justine said "functionally harmless")
    Justine-only: 3 — README ambiguity, hook design, stall message quality

    Holtz's blind spots: README wording, hook design (breadth-level concerns)
    Justine's blind spots: Actual bugs (tested wrong edge cases)""")
    events.extend(o)
    t += 1.5

    events.append(event(t, f"\r\n  {BOLD}Commits:{RESET}\r\n"))
    o, t = output_block(t + 0.3, """    f1b715b fix(scripts): mask code fences and fix \\s regex in parse_brief
    e5e8b5b fix(tests): expand README metrics test to validate all 9 fields
    cfcf762 fix(hooks,scripts): document path matching, distinguish stall vs regress
    34eedec docs: complete Holtz run 14 — 8 findings, all resolved""")
    events.extend(o)
    t += 1.0

    events.append(token_marker(t, 210000, "run 14 complete"))
    t += 0.5

    # Summary box
    events.append(event(t, f"\r\n{BOLD}{'═' * 80}{RESET}\r\n"))
    events.append(event(t + 0.1, f"{BOLD}  HOLTZ RUN 14: CONVERGED{RESET}\r\n"))
    events.append(event(t + 0.2, f"  8 findings (6 MEDIUM, 2 LOW) — all resolved\r\n"))
    events.append(event(t + 0.3, f"  2 real bugs found and fixed with TDD\r\n"))
    events.append(event(t + 0.4, f"  3 tests added, 28 files changed\r\n"))
    events.append(event(t + 0.5, f"  Pattern library predicted both bugs before code was read\r\n"))
    events.append(event(t + 0.7, f"\r\n  {DIM}Main context: ~210K tokens | Justine subagent: ~142K tokens{RESET}\r\n"))
    events.append(event(t + 0.8, f"  {DIM}Total: ~352K tokens across 2 parallel execution contexts{RESET}\r\n"))
    events.append(event(t + 1.0, f"{BOLD}{'═' * 80}{RESET}\r\n"))
    t += 2.0

    return events


def main():
    events = build_cast()
    out = sys.stdout if len(sys.argv) < 2 else open(sys.argv[1], "w")
    for e in events:
        out.write(e + "\n")
    if out != sys.stdout:
        out.close()
        print(f"Written {len(events)} events to {sys.argv[1]}")


if __name__ == "__main__":
    main()

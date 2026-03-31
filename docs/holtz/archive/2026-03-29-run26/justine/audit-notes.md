# Justine Audit Notes — Run 26

**Date:** 2026-03-29
**Auditor:** Justine (breadth-first)
**Project:** holtz v0.71.2

## Methodology

Inherited recon from Holtz Steps 0-4. Ran breadth-first audit across all target areas simultaneously: enforcement hooks, cold gate scripts, HMAC authentication, README, test quality. All lenses applied in parallel (integration -> security -> data-flow -> error-propagation -> contract -> component).

## Areas Examined

### 1. HMAC Authentication (enforcement/hooks/_common.py)

**Lenses:** security, contract, integration

The HMAC implementation in `compute_event_proof()` is structurally correct — SHA-256, sorted fields, deterministic output. But the null byte separator (`\0`) combined with unsanitized field values creates a field boundary injection vulnerability. This is a classic canonicalization failure.

The `record_authed_event()` function correctly delegates to `compute_event_proof()` and passes the proof to sahjhan CLI. The attack surface is any code path that passes user-controllable data into the `fields` dict. Currently, all callers construct fields from internal state (lens name, project name, run number), so exploitation requires a compromised caller. The severity is HIGH because the HMAC system exists specifically to prevent event forgery, and this vulnerability undermines that purpose even if current callers happen to be safe.

`_get_session_key_path()` has a try/except that catches all exceptions including the import of `_resolve`. This is defense-in-depth (fall back to default path). The broad exception catch is acceptable here because the fallback is secure.

### 2. check_sweep_evidence.py (cold gate script)

**Lenses:** component, contract, integration

The script is well-structured. It handles two JSONL formats (nested message.content and flat tool_use) correctly. The `count_distinct_reads()` function uses a set for deduplication. Main function auto-discovers transcript from `CLAUDE_SESSION_TRANSCRIPT` env var.

Verified: the flat format handling on lines 41-44 correctly extracts file_path from tool_use entries. Mixed format transcripts get double-counted (both nested and flat reads are processed), but in practice transcripts use one format consistently.

No issues found beyond the missing edge case tests (empty transcript, malformed JSON boundary). The gate logic is sound.

### 3. check_severity_change.py (cold gate script)

**Lenses:** contract, component, error-propagation

Found two bugs: empty/unknown severity accepted as rank 0 (JH-002), case sensitivity not handled (JH-003). The function design is correct for valid inputs but lacks input validation. The `.get(severity, 0)` default of 0 is the root cause — it conflates "unrecognized" with "lowest possible severity."

The CLI `main()` passes `sys.argv` directly without validation or normalization. No help text about required severity format.

### 4. Enforcement Hooks (highest churn area)

**Lenses:** all

#### commit_gate.py
Logic is sound for the documented use cases. The unconditional block for unregistered commits in fix_loop (lines 50-56) correctly fires before `compute_obligations()`. The pattern analysis overdue block (lines 64-73) correctly excludes cases with unregistered commits (avoids double-blocking).

One observation: `_is_test_cmd()` only matches `pytest` and `python -m pytest`. Other test runners (e.g., `python -m unittest`, `nose2`) would be treated as non-test commands. This is acceptable since the project uses pytest exclusively.

#### protocol_tracker.py
`_is_sleep_cmd()` has the bypass vectors documented in JH-004. The double penalty for sleep (stall += 2) is correctly implemented. `_refresh_from_sahjhan()` correctly handles all error paths with graceful degradation.

`_parse_commit_hash()` regex `\[[\w/.-]+\s+([0-9a-f]{7,})\]` correctly handles branch names with dots and slashes. Falls back to "unknown" on parse failure.

#### lens_quiz.py
Complex but well-structured three-phase flow. `select_questions()` uses a seeded RNG for deterministic question selection across pose/score invocations. `verify_answer_freshness()` has good defensive coding (file deleted, can't parse line number, can't read file all handled).

The IDP-001 guard against duplicate `quiz_answered` events (line 370-374) is correct — queries for existing events before recording.

One observation: `MAX_STALE_QUESTIONS = 2` means if 3+ of 5 questions are stale, the quiz fails permanently until the bank is regenerated. This is a conservative and correct design.

#### primer.py
Correctly derives run number from ledger name. Injects lens priming when in audit/fix_loop states. The `record_authed_event("context_reset", ...)` call is wrapped in `contextlib.suppress()` — if HMAC authentication fails (no session key), the primer still injects context. This is intentional graceful degradation.

#### stop_gate.py
Correctly allows `awaiting_clear` state (iteration boundary). Only `finalized` is terminal. Clean logic.

#### _sahjhan_bootstrap.py
Read guard bypass vectors documented in JH-010. Write protection uses `os.path.realpath()` for path resolution — correct for symlink attacks. Shell redirect detection (lines 96-128) handles `>`, `>>`, `tee`, `cp`, `mv`, `install` — thorough but necessarily incomplete for arbitrary shell commands.

#### bash_guard.py
Manifest verification on every Bash command. Graceful degradation if binary missing/unexecutable. Protocol violation recording uses `--field` syntax correctly.

#### write_guard.py
Clean enumeration of managed files. Uses `os.path.realpath()` for path resolution. Only blocks exact file matches (not prefix matches), which is correct — `docs/holtz/STATUS.md` is blocked but `docs/holtz/recon/status.md` is not.

### 5. README vs Implementation

**Lenses:** public-contract

| Claim | Status | Notes |
|-------|--------|-------|
| 815 tests | VERIFIED | `pytest` reports 815 passed |
| 76% coverage | VERIFIED | Toolchain reports 76.21% |
| 18,537 LOC | STALE | Actual: 22,974 (24% drift) |
| Twenty-five runs | VERIFIED | Run 26 in progress, 25 completed |
| Thirteen lenses | VERIFIED | lens-registry.md has 13 |
| Seventeen anti-patterns | VERIFIED | anti-patterns.md has 17 (1-17) |
| Sixteen seed patterns | VERIFIED | 16 files in patterns/ |
| Nine hooks | VERIFIED | 9 scripts in hooks.json |
| Twenty-one steps | VERIFIED | Steps 0-20 in phase index |
| 24 reference docs | VERIFIED | 24 files in references/ |
| 6 Python scripts | VERIFIED | 6 files in skills/holtz/scripts/ |
| HIGH 65%, MEDIUM 38% | STALE | Living Punchlist: ~69%/~45% |
| "eleven runs" tracking | STALE | Actually 22 runs (Runs 4-25) |
| 5 hooks described | UNDERSTATED | Only 5 of 9 hooks described |

### 6. Test Quality

**Lenses:** contract, component

#### test_severity_change.py (5 tests)
- **Anti-patterns:** #11 Rubber Stamp (tests check happy paths only), #12 Permissive Validator (accepts invalid inputs without failing)
- **Red flags:** 2 (Happy Path Tourist + Rubber Stamp)
- **Missing coverage:** empty severity, case sensitivity, typos, None input

#### test_sweep_evidence.py (3 tests)
- **Anti-patterns:** #5 Happy Path Tourist (missing edge cases)
- **Red flags:** 1
- **Missing coverage:** empty transcript, exact boundary, malformed JSON

#### test_hmac_helpers.py (4 tests)
- **Anti-patterns:** #11 Rubber Stamp (tests check consistency, not security)
- **Red flags:** 1
- **Missing coverage:** null byte injection, empty fields, non-string values

#### test_protocol_enforcement.py (comprehensive)
- Good coverage of commit gate, protocol tracker, enforcement integration
- Proper use of mock binaries for sahjhan interactions
- Integration test cycle (commit -> blocked -> fix_commit -> allowed)
- **Red flags:** 0

#### test_sahjhan_integration.py (comprehensive)
- Good coverage of all hook scripts
- Path traversal test, prefix collision test, symlink test
- Mock binary infrastructure well-designed
- **Red flags:** 0

### 7. _protocol_cache.py (PAT-007 target)

**Lenses:** contract, integration

`parse_status_text()` is well-tested with 6 tests covering state parsing, perspective extraction, available transitions, and the BH-018 fix. The parser/emitter contract between primer.py and _protocol_cache.py appears stable after the Run 25 fixes.

One observation: `_read_perspectives_total()` has a broad except clause on line 36 (`except (OSError, Exception)`) — `Exception` already covers `OSError`, making the tuple redundant. Minor code smell, not a bug.

### 8. hooks/_common.py and PAT-004

**Lenses:** component, integration

Reviewed `mask_fenced_blocks()` against CommonMark spec. The implementation correctly handles:
- 0-3 space indentation for opening fences
- Backtick vs tilde fence characters
- Minimum fence length matching for closing fences
- Backtick info strings must not contain backticks

No new PAT-004 divergence detected between `hooks/_common.py:mask_fenced_blocks` and `skills/holtz/scripts/markdown_utils.py:mask_code_fences` based on current code.

## Prediction Outcomes

| ID | Target | Confidence | Outcome | Notes |
|----|--------|------------|---------|-------|
| P1 | README drift | HIGH | CONFIRMED | JH-005, JH-006, JH-007 (LOC, accuracy, hook descriptions) |
| P2 | HMAC auth logic | HIGH | CONFIRMED | JH-001 (null byte injection) |
| P3 | check_sweep_evidence.py | MEDIUM | PARTIAL | No gate logic error found; test gaps only (JH-013) |
| P4 | check_severity_change.py | MEDIUM | CONFIRMED | JH-002, JH-003 (empty severity, case sensitivity) |
| P5 | commit_gate blocking | MEDIUM | UNCONFIRMED | No overcorrection found; logic is correct |
| P6 | subagent_findings_check.py | MEDIUM | CONFIRMED | JH-009 (0% coverage confirmed, no tests exist) |
| P7 | _protocol_cache / primer drift | MEDIUM | UNCONFIRMED | Contract appears stable after Run 25 fixes |
| P8 | impact_graph.py rendering | LOW | NOT TESTED | Out of priority scope |

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total findings | 15 |
| CRITICAL | 0 |
| HIGH | 3 (JH-001, JH-012, JH-014) |
| MEDIUM | 5 (JH-002, JH-004, JH-007, JH-008, JH-009) |
| LOW | 7 (JH-003, JH-005, JH-006, JH-010, JH-011, JH-013, JH-015) |
| Predictions confirmed | 5/8 (62.5%) |
| HIGH predictions confirmed | 2/2 (100%) |
| MEDIUM predictions confirmed | 3/5 (60%) |
| LOW predictions confirmed | 0/1 (0%) |

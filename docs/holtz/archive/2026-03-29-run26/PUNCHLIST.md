
# Punchlist

**Protocol:** holtz v1.0.0
**Run:** 26
**State:** Finalized
**Ledger:** 230 events

## CRITICAL

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | bug/state | docs/holtz/.sahjhan/ledgers.toml | component | STATUS.md render falls back to default ledger — template references 'run' but no ledger named 'run' is registered. Named ledger is 'run-26'. STATUS.md may show stale or incorrect protocol state. | RESOLVED |
| BH-015 | bug/security | docs/holtz/.sahjhan/ledgers/*/session.key | security | HMAC enforcement bypass: session keys are readable by the AI agent. Agent can read the key via Read tool or xxd, compute HMAC proofs using enforcement/hooks/_common.py:compute_event_proof(), and record restricted events (context_reset, quiz_answered, etc.) without hook authorization. The entire restricted-event HMAC system provides zero protection against a motivated agent. | RESOLVED |
| BH-021 | bug/integration | enforcement/hooks/_common.py:42-60 | integration | _get_session_key_path ignores ledger parameter. Queries sahjhan config session-key-path without --ledger, always returning default ledger key. record_authed_event computes HMAC with default key but targets per-ledger run. Proof mismatch silently fails all restricted events (quiz_posed, quiz_answered, context_reset) for named ledger runs. | RESOLVED |
## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-005 | bug/logic | enforcement/hooks/_common.py:32-39 | integration | active-run marker file has never existed. _active_ledger() always returns None. Hooks write quiz/context events to default ledger, not run-specific ledger. Gate conditions on run-specific ledger cannot see hook events. | RESOLVED |
| BH-007 | bug/error-handling | enforcement/hooks/lens_quiz.py:344-395 | error-propagation | record_authed_event calls unprotected from FileNotFoundError when session.key is absent. primer.py wraps with suppress but lens_quiz.py does not. | RESOLVED |
| BH-008 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py | security | Read-guard bypass: sed -i, perl -pi, patch, python -c open() all write to protected enforcement/ paths without being blocked. | RESOLVED |
| BH-011 | test/bogus | tests/test_lens_quiz_integration.py:test_evidence_rejects_rubber_stamp | component | Test uses flat-format content against min_reads=5 threshold. Rejection is from read-count gate, not rubber-stamp detection. Wrong code path tested. | RESOLVED |
| BH-014 | bug/security | enforcement/hooks/_common.py:82 | security | HMAC null byte injection: field value containing null byte produces payload identical to one with additional fields. Enables HMAC collision/forgery. | RESOLVED |
| BH-022 | bug/design | enforcement/hooks/lens_quiz.py:118-158 | component | verify_answer_freshness checks if quiz answer keywords still appear at the source line number. But any fix that adds/removes lines shifts all downstream line numbers, invalidating quiz questions that haven't changed semantically. After a fix loop with multiple commits, enough questions go stale to permanently block convergence (>MAX_STALE_QUESTIONS). Line numbers are the wrong stability anchor — function names, class names, or content hashes would survive line shifts. | RESOLVED |
## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-002 | doc/drift | README.md:6,190,214 | public-contract | LOC figure 18537 is stale in 3 places. Actual: 22974 total or 7969 production-only. | RESOLVED |
| BH-003 | doc/drift | README.md:192 | public-contract | Research data staleness footnote says Runs 17-18 missing but actually Runs 17-25 are excluded. Misleading. | RESOLVED |
| BH-006 | bug/logic | enforcement/scripts/check_sweep_evidence.py:18-45 | component | count_distinct_reads counts ALL file reads in session transcript, not just final sweep reads. Any session with 30+ total reads passes the gate regardless of whether the final sweep read any files. | RESOLVED |
| BH-009 | bug/logic | enforcement/scripts/check_severity_change.py:25 | component | Unknown severity maps to rank 0. Any valid resolved severity ranks >= 1, so downgrade from typo/unknown severity silently passes without evidence. | RESOLVED |
| BH-010 | bug/logic | enforcement/hooks/lens_quiz.py:360-365 | component | Answer count mismatch returns (0,0) which triggers stale-questions error message. Wrong error message for wrong condition. | RESOLVED |
| BH-013 | test/shallow | tests/test_impact_graph.py:test_38_200_node_round_trip | component | While loop with bare try/except KeyError: pass suppresses production errors. If add_edge broke, test hangs instead of failing. | RESOLVED |
## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-004 | doc/drift | README.md:162 | public-contract | Run count says twenty-five but Run 26 is in progress. Stale. | RESOLVED |
| BH-012 | bug/logic | enforcement/hooks/_protocol_cache.py:165 | component | is_git_commit regex matches git commit inside echo, comments, and quoted strings. Can false-positive block echo commands in fix_loop. | RESOLVED |
| BH-099 | test/dummy | test | component | test render | RESOLVED |
| BH-016 | bug/logic | enforcement/hooks/protocol_tracker.py:57 | component | _parse_commit_hash regex fails on root commits and detached HEAD. Pattern requires [branch hash] but git outputs [main (root-commit) hash] which has parenthesized metadata. Returns 'unknown' instead of actual hash. | RESOLVED |
| BH-017 | bug/logic | skills/holtz/scripts/pattern_brief_compact.py:92-97 | component | _truncate() appends '...' without accounting for its 3-char length. Output exceeds max_len when truncating at word boundaries or when no spaces exist before max_len. | RESOLVED |
| BH-018 | bug/logic | enforcement/hooks/lens_quiz.py:156-157 | component | verify_answer_freshness uses 1-based line_no directly as 0-based index. Window starts one line late. Practical impact minimal due to ±3 line window. | RESOLVED |
| BH-019 | bug/integration | enforcement/hooks/protocol_tracker.py:85-88 | integration | protocol_tracker._refresh_from_sahjhan populates perspectives_done/total from parse_status_text but never writes current_perspective to cache. _protocol_cache.format_state_line reads cache['perspective'] which stays at default '?'. Status line shows '? 1/13' instead of active perspective name. | RESOLVED |
| BH-020 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:61-68 | security | Bash read-guard substring matching is case-sensitive. On case-insensitive filesystems (macOS default), alternate-case paths like QUIZ-BANK.JSON bypass the guard. Read tool guard is unaffected (uses os.path.realpath). Only quiz bank is at risk; session keys use structural guard. | RESOLVED |



# Punchlist

**Protocol:** holtz v1.0.0
**Run:** ?
**State:** Fix Loop (Step 10)
**Ledger:** 189 events

## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:6 | public-contract | Badge URL says 869_total but actual test count is 874. Alt text says 874 but shield URL is stale. PAT-005 recurrence. | RESOLVED |
| BH-004 | bug/security | enforcement/hooks/lens_quiz.py:48 | security | Quiz answer bypass via fence info string. _ANSWERS_RE lacks ^ anchor, so LENS:...ANSWERS: on a code fence opener line survives mask_fenced_blocks and matches. A subagent could embed answers in a fence info string to bypass quiz scoring. | RESOLVED |
| BH-016 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:98-112 | security | _bash_references_guarded uses literal substring matching for read guards. Shell glob patterns like 'cat docs/holtz/.sahjhan/s*.key' or 'cat docs/holtz/.sahjhan/*' bypass both the structural guard (no 'session.key' in command) and the literal guard (no '.sahjhan/session.key' substring). Attacker subagent could read session.key via glob expansion and forge HMAC proofs. | RESOLVED |
| BH-017 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:113 | security | Brace expansion bypass: _GLOB_CHARS omits '{' so 'cat .sahjhan/ses{sion.ke,x}y' evades the glob guard. Bash expands braces before exec, producing session.key. Incomplete fix for BH-016. | RESOLVED |
| BH-020 | process/audit-blind-spot | SKILL.md:rationalization-table | semantic-fidelity | Holtz applied the same band-aid fix (update stale number) for the third time (BH-002, BH-018, BH-019) without recognizing the PAT-005 recurrence pattern. Required user escalation to identify root cause. Pattern analysis at Step 11 should have caught this after BH-018 resolved — two instances of the same fix-class in one run triggers sibling search. The auditor skipped pattern analysis between BH-018 and convergence attempt. | RESOLVED |
| BH-021 | bug/schema | enforcement/transitions.toml:84 | contract | iteration_boundary gate SQL uses rowid (SQLite concept) instead of seq (DataFusion schema). Query fails at runtime blocking all iteration_boundary transitions. Introduced in commit 0da131f. | RESOLVED |
## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-002 | doc/drift | README.md:190,161 | public-contract | Run count inconsistent: line 161 says twenty-seven, line 190 says 28, actual completed runs is 28 (run 29 in progress). LOC claim 19766 is stale, actual Python LOC ~23626. | RESOLVED |
| BH-003 | doc/drift | README.md:104 | public-contract | Prediction accuracy claims 65%/38%/0% but living punchlist tracks ~69%/~45%/0%. Stale numbers from earlier research epoch. | RESOLVED |
| BH-005 | bug/logic | enforcement/hooks/_protocol_cache.py:197 | contract | is_sahjhan_cmd fails for bare platform binary names (sahjhan-aarch64-apple-darwin without path prefix). Third condition checks for /sahjhan- but not sahjhan- at start. Low impact — binary is always invoked with path. | RESOLVED |
| BH-006 | test/fragile | tests/test_sahjhan_integration.py:516 | component | Choose Your Own Adventure anti-pattern: or-disjunction lets test pass whether hook warned OR silently allowed a chained command. Should assert specifically for warning behavior. | RESOLVED |
| BH-007 | test/fragile | tests/test_token_profiler_integration.py:30 | component | Mystery Guest anti-pattern: hardcoded path to specific JSONL on one developer machine. Test skips if file absent but is a dead test in CI and for any other developer. | RESOLVED |
| BH-015 | bug/logic | enforcement/hooks/protocol_tracker.py:49 | component | _is_sleep_cmd regex only matches bare numeric seconds. sleep 1m (60s) parses as 1.0 < 5 → returns False. Bash sleep supports s/m/h/d suffixes. Gaming via suffixed sleep notation would bypass the double-stall penalty. | RESOLVED |
| BH-018 | doc/drift | README.md:6,190,214 | public-contract | LOC count claims 19910 in badge, narrative, and inventory but actual Python LOC is ~24418 (~23% stale). BH-002 recurrence. | RESOLVED |
| BH-019 | design/fragile | README.md:6,190,214 | public-contract | Exact LOC count hardcoded in 3 README locations goes stale every run. BH-002 and BH-018 both 'fixed' by updating the number. Root cause: exact counts in prose that drift on every code change. PAT-005 systemic recurrence. Fix: remove exact LOC from prose, keep test-enforced badge as single source of truth. | RESOLVED |



# Punchlist

**Protocol:** holtz v1.0.0
**Run:** ?
**State:** Finalized
**Ledger:** 110 events

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-003 | bug/state | bin/sahjhan (symlink), enforcement/hooks/_sahjhan_bootstrap.py:71 | integration | bin/sahjhan symlink is absolute (/Users/jonr/...) — tracked in git. CI resolves it to a non-existent machine-specific path. _sahjhan_bootstrap.py realpath comparison fails because PROTECTED 'bin/sahjhan' resolves to Jon's local path while the test input resolves to CI workspace path. | RESOLVED |
| BH-014 | doc/drift | README.md:104 | public-contract | Prediction accuracy statistics fabricated. README claims 82%/59%/67% for HIGH/MEDIUM/LOW across 7 runs. Research data shows 65%/38%/0% across 11 runs. No data slice produces claimed numbers. LOW=67% contradicts all data (actual: 0%). | RESOLVED |
## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:6,190,214 | public-contract | Test count badge and prose say 759, actual is 761. PAT-005 recurrence. | RESOLVED |
| BH-002 | doc/drift | README.md:190,214 | public-contract | LOC count says 21,120, actual is 21,756. PAT-005 recurrence. | RESOLVED |
| BH-004 | bug/logic | tests/test_integration.py:284-288 | component | test_readme_metrics_match_actual uses pytest --co -q, but -q suppresses the summary line. re.search returns None, causing AttributeError on .group(1). Fix: use --co without -q, or parse the line count differently. | RESOLVED |
| BH-005 | test/fragile | tests/test_sahjhan_integration.py:346-357 | integration | TestStopGate test_allows_without_sahjhan_binary and test_allows_without_active_run run without isolated cwd. Hook picks up live .sahjhan/ state from repo root and blocks. Tests are Mystery Guest (AP-15) and Schrodinger Test (AP-8). | RESOLVED |
| BH-006 | test/bogus | tests/test_sahjhan_integration.py:318-321,413-418 | component | Conditional assertions in test_violation_records_event and test_reset_records_event. If the log file doesn't exist or context_reset isn't in logged, tests pass with zero assertions. Inspector Clouseau (AP-4). | RESOLVED |
| BH-008 | bug/logic | enforcement/hooks/_sahjhan_bootstrap.py:43-58 | security | Bash redirect detection uses substring matching (p in command). False positives: echo mentioning protected path, cp reading from protected path. Defense-in-depth issue — primary path protection via realpath handles Write/Edit correctly. | RESOLVED |
| BH-011 | doc/drift | README.md:191,214 | public-contract | LOC count says 17,800, actual Python LOC is 21,909. PAT-005 recurrence. Two instances in 'After 25 runs' paragraph and 'What's inside' section. | RESOLVED |
| BH-013 | bug/logic | enforcement/hooks/_protocol_cache.py:120 | component | parse_status_text transition regex requires leading whitespace on already-stripped line | RESOLVED |
| BH-015 | doc/drift | README.md:174-175 | public-contract | Run 1 narrative mixes Run 1 and Run 2 data. Claims '12 issues' and '48 new tests' for Run 1. Research data: Run 1 had 21 findings/19 tests; Run 2 had 12 findings/48 tests. | RESOLVED |
| BH-016 | bug/logic | enforcement/hooks/lens_quiz.py:308-311 | integration | SEC-007 degrades session-JSONL format (processable by check_transcript) to min_reads=0, while keeping min_reads=5 for hook-event format (unprocessable). Logic inverted: read-count enforcement is always bypassed. | RESOLVED |
| BH-017 | bug/logic | skills/holtz/scripts/impact_graph.py:226 | component | risk_hotspots() uses n[id] but _REQUIRED_NODE_KEYS is {type, file} — load() allows nodes without id, causing KeyError in sort key | RESOLVED |
| BH-018 | bug/logic | enforcement/hooks/_protocol_cache.py:135 | component | parse_status_text sets current_perspective=unknown unconditionally — primer.py lens priming line never emits after /clear | RESOLVED |
## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-007 | test/shallow | tests/test_convergence_check.py:143,157,703 | component | Permissive Validator (AP-12): assert result \!= 'pytest' instead of assert result is None. Would pass with any non-pytest string as return value. | RESOLVED |
| BH-009 | bug/logic | enforcement/hooks/lens_quiz.py:153-161 | data-flow | verify_answer_freshness uses substring matching on comma-split answer parts. Short parts (1-2 chars) could match spuriously. Theoretical risk — current quiz bank uses multi-word options. | RESOLVED |
| BH-010 | design/coupling | enforcement/hooks/_common.py:1-29 | contract | Bridge re-exports 7 names from hooks/_common.py via importlib. No test validates the export list stays in sync. Future additions to source module break enforcement hooks silently. | RESOLVED |


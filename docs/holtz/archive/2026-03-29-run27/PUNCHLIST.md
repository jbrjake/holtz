
# Punchlist

**Protocol:** holtz v1.0.0
**Run:** 27
**State:** Fix Loop (Step 10)
**Ledger:** 106 events

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-002 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:142-153 | security | Redirect guard bypass: command.find(op) returns first occurrence of > or >>. A quoted > before the real redirect (e.g. echo '>' > enforcement/file) causes the guard to check the wrong position. Protected paths can be overwritten via shell redirect. | RESOLVED |
| BH-003 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:141-196 | security | Interpreter execution bypass: python -c open(), ruby -e, node -e can write to protected enforcement/ paths. BH-008 from run 26 listed python -c as a vector but fix only addressed sed/perl/patch. | RESOLVED |
## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:190,214 | public-contract | LOC count stale: 19,129 in README vs 23,585 actual (23% drift) | RESOLVED |
| BH-004 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:164-175 | security | Chained command bypass: cp/mv/install check uses cmd_stripped.startswith() which only matches at command start. Chained commands (true && cp file enforcement/) bypass the guard. | RESOLVED |
| BH-006 | bug/logic | enforcement/hooks/lens_quiz.py:276-277 | data-flow | score_answers returns (0,0) for both count mismatch and all-stale; caller cannot distinguish | RESOLVED |
| BH-007 | bug/logic | hooks/subagent_findings_check.py:33 | component | Regex only matches .md files; .json and other audit artifacts not checked | RESOLVED |
| BH-008 | test/integration-gap | .github/workflows/ci.yml:33 | integration | CI runs pytest without --cov; 60% coverage gate only enforced locally | RESOLVED |
## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-005 | test/bogus | tests/test_hooks.py:114-211 | component | 10 tautology tests: 5 exit-zero tests and 5 stderr-empty tests add zero mutation detection value. Exit code is 0 for all hook output paths. Sibling tests already cover substantive assertions. | RESOLVED |
| BH-009 | bug/error-handling | enforcement/hooks/_protocol_cache.py:35 | error-propagation | except (OSError, Exception) catches all non-system exceptions; masks programming errors | RESOLVED |
| BH-010 | test/missing | hooks/subagent_findings_check.py | component | 0% line coverage; subprocess tests dont count toward --cov measurement | RESOLVED |
| BH-011 | test/bogus | tests/test_hooks.py:114-211 | component | 10 tautology tests: exit-zero and stderr-empty checks add zero mutation signal | RESOLVED |
| BH-012 | bug/logic | skills/holtz/scripts/markdown_utils.py:79-81 | component | has_unclosed_fence returns True (false positive) when the document's last line is a closing fence with no trailing newline. _iterate_fences yields (i, True) for closing fences before resetting in_fence=False; consumer stores last yielded value. | RESOLVED |


# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 595 pass, 9 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 1 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 0 | 0 | 0 |

## Patterns

## Items

### BH-001: test_commit_msg_hook.py references deleted git-hooks/commit-msg
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_commit_msg_hook.py:7`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** Commit b412c16 replaced `git-hooks/commit-msg` with `git-hooks/post-commit` but did not update `test_commit_msg_hook.py`. The test file references `git-hooks/commit-msg` (line 7) which no longer exists. Tests create a dangling symlink, so the hook never fires. All 9 version-bumping tests pass the commit step but fail the assertion — versions don't bump.

**Evidence:**
```
HOOK_PATH = Path(__file__).parent.parent / "git-hooks" / "commit-msg"  # line 7 — file does not exist
hook_dest = hooks_dir / "commit-msg"  # line 25 — installs as commit-msg, not post-commit
```
`ls git-hooks/` shows only `post-commit`. No `commit-msg` file exists.

**Discovery Chain:** 9 test failures in baseline → all in test_commit_msg_hook.py → HOOK_PATH points to git-hooks/commit-msg → file deleted in b412c16, replaced by post-commit

**Acceptance Criteria:**
- [ ] All 9 version-bumping tests pass
- [ ] Tests reference `git-hooks/post-commit` and install as `post-commit` hook
- [ ] `python -m pytest tests/test_commit_msg_hook.py -q` shows 0 failures

**Validation Command:**
```bash
python -m pytest tests/test_commit_msg_hook.py --tb=short -q
```

### BH-002: No test for REGRESSING label in stall detection
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `skills/holtz/scripts/convergence_check.py:371`
**Status:** OPEN

**Problem:** The stall detection code distinguishes between STALLED (flat open items) and REGRESSING (growing open items) at line 371. The existing tests only verify the STALLED path (test_stall_detection_triggers, line 941). There is no test for the REGRESSING label when open items increase across iterations.

**Evidence:**
```python
# convergence_check.py:371
label = "REGRESSING" if open_items > first_open else "STALLED"
```
Grep for REGRESSING in test files returns zero matches in test assertions. The test at line 956 asserts `"STALLED" in message` but no test asserts `"REGRESSING" in message`.

**Discovery Chain:** Run 14 recommendation "Consider adding a stall-vs-regress test" → grep for REGRESSING in tests → no assertion found → untested code path

**Acceptance Criteria:**
- [ ] A test exists where open items grow across 4+ iterations
- [ ] The test asserts "REGRESSING" appears in the message (not "STALLED")
- [ ] The test verifies the open item count is reported in the message

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "regress" --tb=short -q
```

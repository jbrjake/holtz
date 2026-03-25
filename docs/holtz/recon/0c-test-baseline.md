# Step 0c: Test Baseline

**Date:** 2026-03-24
**Run:** 15

## Results
- **Passed:** 595
- **Failed:** 9
- **Skipped:** 0
- **Time:** 6.92s

## Failures (all in test_commit_msg_hook.py)
| Test | Expected | Actual | Issue |
|------|----------|--------|-------|
| test_feat_bumps_minor | 0.5.0 | 0.4.0 | Hook not installed |
| test_feat_with_scope_bumps_minor | 0.5.0 | 0.4.0 | Hook not installed |
| test_fix_bumps_patch | 0.5.1 | 0.5.0 | Hook not installed |
| test_perf_bumps_patch | 0.5.1 | 0.5.0 | Hook not installed |
| test_fix_with_scope_bumps_patch | 1.2.4 | 1.2.3 | Hook not installed |
| test_feat_bang_bumps_major | 2.0.0 | 1.2.3 | Hook not installed |
| test_fix_bang_bumps_major | 2.0.0 | 1.2.3 | Hook not installed |
| test_breaking_change_in_body_bumps_major | 2.0.0 | 1.2.3 | Hook not installed |
| test_feat_then_fix_then_feat | 0.5.0 | 0.4.0 | Hook not installed |

**Root cause:** Tests reference `git-hooks/commit-msg` (line 7) which was removed in commit b412c16. The actual hook is now `git-hooks/post-commit`. Tests create a dangling symlink, so the hook never fires and version never bumps.

## Coverage
| Module | Coverage |
|--------|----------|
| markdown_utils.py | 100% |
| profiler_plugin.py | 100% |
| convergence_check.py | 85% |
| validate_punchlist.py | 80% |
| pattern_brief_compact.py | 78% |
| impact_graph.py | 65% |
| hooks/ (all) | 0% |
| **Total** | **63%** |

**Note:** Hook coverage is 0% because hooks are tested via subprocess in test_hooks.py (coverage doesn't track subprocess execution). This is expected behavior, not a gap.

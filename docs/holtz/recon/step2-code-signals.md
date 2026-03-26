# Step 2: Code Signals — Run 21

Generated: 2026-03-26

---

## Git Churn (top 20 files, last 50 commits)

Command: `git log --pretty=format: --name-only -50 | sort | uniq -c | sort -rn | head -20`

| Commits | File |
|---------|------|
| 34 | .claude-plugin/plugin.json |
| 8 | skills/holtz/SKILL.md |
| 5 | README.md |
| 4 | tests/test_convergence_check.py |
| 3 | tests/test_integration.py |
| 3 | skills/holtz/scripts/convergence_check.py |
| 3 | skills/holtz/references/recon-procedures.md |
| 3 | scripts/token_profiler/cli.py |
| 2 | tests/test_fence_masking_agreement.py |
| 2 | skills/holtz/references/lens-registry.md |
| 2 | skills/holtz/patterns/concurrency-violation.md |
| 2 | hooks/convergence_gate.py |
| 2 | enforcement/transitions.toml |
| 2 | enforcement/states.toml |
| 2 | enforcement/hooks/write_guard.py |
| 2 | enforcement/hooks/stop_gate.py |
| 2 | enforcement/hooks/primer.py |
| 2 | enforcement/hooks/bash_guard.py |
| 2 | enforcement/hooks/_sahjhan_bootstrap.py |
| 2 | enforcement/events.toml |

**Observations:**

- `.claude-plugin/plugin.json` dominates with 34 of 50 commits — expected, it is auto-bumped by the post-commit hook on every feat/fix/perf commit. Not a real signal.
- The first real-code signal is `skills/holtz/SKILL.md` (8), reflecting active iteration on the plugin's functional specification.
- `skills/holtz/scripts/convergence_check.py` (3) and `scripts/token_profiler/cli.py` (3) are the only source `.py` files in the top 20. Both are high-traffic, user-facing entry points.
- Enforcement hooks cluster at 2 commits each — coordinated, likely introduced together as a system. None appear to have received independent follow-on fixes, which may mean they are stable or untested after initial landing.
- No test files other than `test_convergence_check.py` (4) and `test_integration.py` (3) show churn, consistent with the token profiler tests being a recent addition not yet reflected in the 50-commit window.

---

## Skipped / Disabled Tests

Command: `grep -rn "skip\|xfail\|@pytest.mark.skip\|TODO.*test" tests/ --include="*.py"`

**No permanently skipped or disabled tests found.**

- No `@pytest.mark.skip` decorators anywhere in `tests/`.
- No `@pytest.mark.xfail` decorators anywhere in `tests/`.
- No `@unittest.skip` decorators anywhere in `tests/`.

**One conditional runtime skip exists:**

- `tests/test_token_profiler_integration.py:41` — `pytest.skip("Run 14 session JSONL not available")` inside a fixture (`skip_if_no_session`). This is a data-availability guard: integration tests that require an actual session JSONL are skipped when the file is absent from the test environment. This is not a suppressed defect; it is an intentional environment gate.

**False positives in grep output:**
- All other occurrences of "skip" in test files are either fixture data strings (Go/Jest/Vitest output samples used to test the parser) or test function *names* that test the parsing of skipped counts (e.g., `test_vitest_all_skipped`, `test_jest_with_skipped`). These are correct, not gaps.

---

## Cold File Inventory

A file is "cold" if its basename does not appear in any `docs/holtz/archive/*/PUNCHLIST*.md` or `docs/holtz/archive/justine-*/PUNCHLIST*.md` finding.

**Total source files: 27** (in `skills/`, `hooks/`, `enforcement/`, `scripts/`)

### Warm files (14) — appeared in at least one prior PUNCHLIST

| File | Path |
|------|------|
| _common.py | enforcement/hooks/_common.py |
| _common.py | hooks/_common.py |
| subagent_findings_check.py | hooks/subagent_findings_check.py |
| analyze.py | scripts/token_profiler/analyze.py |
| cli.py | scripts/token_profiler/cli.py |
| extract.py | scripts/token_profiler/extract.py |
| pricing.py | scripts/token_profiler/pricing.py |
| viewer.py | scripts/token_profiler/viewer.py |
| convergence_check.py | skills/holtz/scripts/convergence_check.py |
| impact_graph.py | skills/holtz/scripts/impact_graph.py |
| markdown_utils.py | skills/holtz/scripts/markdown_utils.py |
| pattern_brief_compact.py | skills/holtz/scripts/pattern_brief_compact.py |
| validate_punchlist.py | skills/holtz/scripts/validate_punchlist.py |
| artifact_verification.py | hooks/artifact_verification.py (via punchlist mention) |

### Cold files (13) — never appeared in any PUNCHLIST finding

| File | Path | Notes |
|------|------|-------|
| _resolve.py | enforcement/hooks/_resolve.py | Enforcement helper, no prior audit coverage |
| _sahjhan_bootstrap.py | enforcement/hooks/_sahjhan_bootstrap.py | Bootstrap for Sahjhan engine, new/unaudited |
| bash_guard.py | enforcement/hooks/bash_guard.py | Bash command enforcement hook |
| primer.py | enforcement/hooks/primer.py | Primer enforcement hook |
| stop_gate.py | enforcement/hooks/stop_gate.py | Stop gate enforcement hook |
| write_guard.py | enforcement/hooks/write_guard.py | Write guard enforcement hook |
| generate-changelog.py | scripts/generate-changelog.py | Changelog generation script |
| session-to-cast.py | scripts/session-to-cast.py | Session cast converter utility |
| __init__.py | scripts/token_profiler/__init__.py | Package init (likely trivial) |
| __main__.py | scripts/token_profiler/__main__.py | CLI entry point |
| models.py | scripts/token_profiler/models.py | Data models for token profiler |
| plugin_protocol.py | scripts/token_profiler/plugin_protocol.py | Plugin protocol interface |
| report.py | scripts/token_profiler/report.py | Report generation module |
| profiler_plugin.py | skills/holtz/scripts/profiler_plugin.py | Profiler plugin integration |

**Cold file ratio: 14/27 = 52%**

**Highest-risk cold clusters:**
1. **enforcement/hooks/** — 5 of 7 enforcement hooks are cold. These are security-critical path files (bash_guard, write_guard, stop_gate, primer) that have never been audited. Combined with their low churn (2 commits each at initial landing), there is no evidence of post-landing review.
2. **scripts/token_profiler/models.py, plugin_protocol.py, report.py** — Core profiler data layer. The surface modules (analyze, cli, extract, viewer) are warm, but the underlying data contracts and report generation are cold.
3. **scripts/session-to-cast.py, scripts/generate-changelog.py** — Utility scripts with no test coverage and no prior audit mention.

---

## TODO / FIXME / HACK / XXX Comments

Command: `grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.py" skills/ hooks/ enforcement/ scripts/`

**One match found:**

- `scripts/token_profiler/report.py:30` — docstring containing the word `format` adjacent to a dollar amount description. This is a **false positive** (the grep matched on a substring of a docstring that does not contain TODO/FIXME/HACK/XXX explicitly — confirmed by re-reading the line, which is a `"""Format a dollar amount as $X.XXXX."""` docstring).

**Effective result: Zero actionable TODO/FIXME/HACK/XXX markers in production source.**

This is a positive signal for code hygiene but also a risk signal: either the codebase is genuinely clean of known debt markers, or authors are not using standard debt markers and known issues exist undocumented in comments. Given the cold file ratio above, the latter cannot be ruled out for the enforcement/ subsystem.

---

## Summary Signal Table

| Signal | Finding | Risk |
|--------|---------|------|
| Churn leader (real code) | `convergence_check.py`, `SKILL.md` | Low — expected active files |
| Enforcement hook churn | 2 commits each, all at same time | Medium — one-shot landing, no follow-on fixes |
| Skipped tests | 0 permanent, 1 conditional env guard | Low |
| Cold file ratio | 14/27 (52%) | High |
| Cold enforcement hooks | 5/7 hooks unaudited | High |
| TODO/FIXME markers | 0 actionable | Neutral |

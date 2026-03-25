# Living Punchlist

**Project:** holtz
**Established:** 2026-03-24
**Last Updated:** 2026-03-24
**Audits Completed:** 1

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** code-fence-unaware parsing — Regex applied to markdown content without masking code fences first, causing fields inside fenced code blocks to match as real values
  - Instances: BH-003, BH-004, BH-005, BH-006 (Run 15)
  - Root cause: Two independent implementations of fence masking (markdown_utils.py for scripts, _common.py for hooks). New code that processes markdown must choose the right masking function for its layer. Convention is documented but not enforced at import time.
  - Detection rule: `grep -rn 're\.\(search\|findall\).*content' hooks/ skills/holtz/scripts/ | grep -v mask`
  - First seen: Run 1 (2026-03-20)

### Risk Hotspots

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| *No hotspots above 0.5* | — | — | — | All risk scores at 0.0 after convergence |

### Architectural Risks

- **Broken dependency: pytest-cov** — `pyproject.toml` `addopts` references `--cov=skills/holtz/scripts` but pytest-cov coverage reports show hooks at 0% because hooks are tested via subprocess, not direct import.
  - Source: Drift log entry 2026-03-22 (Run 8)
  - Severity: MEDIUM
  - Why it matters: Coverage metrics undercount hook coverage, making it appear untested when it has 24+ tests
  - Punchlist items produced: none (informational)

### Persistent Gaps

*No persistent gaps identified. No recommendations at 2+ appearances remaining unaddressed.*

## Proactive Checks

### Check 1: Code-fence-unaware regex in markdown processing
**Source:** PAT-001
**Trigger:** New or modified regex in hooks/ or scripts/ that processes markdown content
**Heuristic:** `grep -rn 're\.\(search\|findall\).*content' hooks/ skills/holtz/scripts/ | grep -v mask`
**If triggered:** Verify the regex operates on masked content (via `mask_code_fences` for scripts or `mask_fenced_blocks` for hooks). If not, file a punchlist item.

## Prediction Accuracy

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 1         | 33%      |
| MEDIUM     | 3         | 0         | 0%       |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **7**     | **1**     | **14%**  |

### Calibration Notes

- HIGH-confidence predictions based on direct observation (broken tests visible in baseline) are reliable. Prediction 1 (broken test file) confirmed.
- HIGH-confidence predictions based on coverage metrics (0% = untested) were wrong: hooks at 0% line coverage had 24+ tests via subprocess (invisible to pytest-cov). Coverage proxy unreliable for subprocess-tested code.
- MEDIUM-confidence predictions from global pattern matching (PAT-001 in new hooks) were directionally correct (4 instances found) but classified as UNCONFIRMED because the predictions framed them as bug/logic while findings were design/inconsistency. Consider scoring directional hits separately.
- LOW-confidence predictions from git churn (historical README line counts) are unreliable — README narrative accurately describes historical state, not current state.

## History

### 2026-03-24: Run 15 completed
- Added: PAT-001 (4 instances), 1 architectural risk (pytest-cov coverage gap), 1 proactive check (code-fence regex detection)
- Removed: none (first run)
- Calibration: prediction accuracy was 14% (1 of 7 predictions confirmed). HIGH direct-observation predictions reliable; coverage-proxy and pattern-matching predictions need recalibration.
- Notes: First living punchlist entry. Run 15 was a full adversarial self-play audit in dev mode. 9 items found and resolved (4 HIGH, 4 MEDIUM, 1 LOW). Convergence achieved in 3 iterations after history reset due to premature convergence declaration.

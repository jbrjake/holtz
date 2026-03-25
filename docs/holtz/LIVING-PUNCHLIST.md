# Living Punchlist

**Project:** holtz
**Established:** 2026-03-24
**Last Updated:** 2026-03-25
**Audits Completed:** 3

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** code-fence-unaware parsing — Regex applied to markdown content without masking code fences first, causing fields inside fenced code blocks to match as real values
  - Instances: BH-003, BH-004, BH-005, BH-006 (Run 15)
  - Root cause: Two independent implementations of fence masking (markdown_utils.py for scripts, _common.py for hooks). New code that processes markdown must choose the right masking function for its layer. Convention is documented but not enforced at import time.
  - Detection rule: `grep -rn 're\.\(search\|findall\).*content' hooks/ skills/holtz/scripts/ | grep -v mask`
  - First seen: Run 1 (2026-03-20)

- **PAT-004:** dual-implementation divergence — `hooks/_common.py` reimplements `markdown_utils.py` fence masking with a simpler algorithm, causing behavioral divergence between script-layer and hook-layer markdown processing
  - Instances: Run 18 findings
  - Root cause: Two independent implementations of the same operation (fence masking) evolved separately. `_common.py` uses a simpler algorithm than `markdown_utils.py`, so edge cases handled by one are missed by the other.
  - Detection rule: `diff <(grep -n 'def mask' skills/holtz/scripts/markdown_utils.py) <(grep -n 'def mask' hooks/_common.py)` — compare masking function signatures and logic across layers
  - First seen: Run 18 (2026-03-25)

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

### Check 2: Dual-implementation divergence in fence masking
**Source:** PAT-004
**Trigger:** Any change to `hooks/_common.py` masking functions or `skills/holtz/scripts/markdown_utils.py` masking functions
**Heuristic:** `diff <(grep -n 'def mask' skills/holtz/scripts/markdown_utils.py) <(grep -n 'def mask' hooks/_common.py)` — check that masking implementations remain aligned
**If triggered:** Verify both implementations handle the same edge cases. If one is updated, the other must be reviewed for parity or the divergence must be documented as intentional.

## Prediction Accuracy

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 5         | 3         | 60%      |
| MEDIUM     | 6         | 0         | 0%       |
| LOW        | 2         | 0         | 0%       |
| **Total**  | **13**    | **3**     | **23%**  |

### Calibration Notes

- HIGH-confidence predictions based on direct observation (broken tests visible in baseline) are reliable. Prediction 1 (broken test file) confirmed.
- HIGH-confidence predictions based on coverage metrics (0% = untested) were wrong: hooks at 0% line coverage had 24+ tests via subprocess (invisible to pytest-cov). Coverage proxy unreliable for subprocess-tested code.
- MEDIUM-confidence predictions from global pattern matching (PAT-001 in new hooks) were directionally correct (4 instances found) but classified as UNCONFIRMED because the predictions framed them as bug/logic while findings were design/inconsistency. Consider scoring directional hits separately.
- LOW-confidence predictions from git churn (historical README line counts) are unreliable — README narrative accurately describes historical state, not current state.
- Run 18: HIGH predictions at 100% (2/2) — continuing the trend that direct-observation HIGH predictions are the most reliable signal. MEDIUM and LOW predictions again produced 0% confirmation, suggesting these confidence tiers need tighter scoping or should be deprioritized.

## History

### 2026-03-25: Run 18 completed
- Added: PAT-004 (dual-implementation divergence), Proactive Check 2 (fence masking parity)
- Removed: none
- Calibration: Run 18 prediction accuracy 33% (2 of 6 confirmed). HIGH: 100% (2/2). MEDIUM: 0% (0/3). LOW: 0% (0/1). Cumulative across 3 runs: HIGH 60% (3/5), MEDIUM 0% (0/6), LOW 0% (0/2), Total 23% (3/13).
- Notes: Run 18 was a dev-mode self-audit. 7 items found and resolved (3 HIGH, 3 MEDIUM, 1 LOW). New pattern PAT-004 identified: hooks/_common.py reimplements markdown_utils.py fence masking with simpler algorithm. All risk scores at 0.0 except convergence_gate (0.3) and convergence_primer (0.1) — both below the 0.5 hotspot threshold. Convergence achieved in 3 iterations.

### 2026-03-25: Run 16 completed
- Added: 2 more PAT-001 instances (pattern_brief_compact.py offset-divergence, hooks fence grammar)
- Removed: none
- Calibration: Run 16 prediction accuracy 33% (2 of 6 confirmed). HIGH: 50% (1/2). MEDIUM: 33% (1/3). LOW: 0% (0/1). Cumulative HIGH across 2 runs: 40% (2/5). README doc drift predictions remain the most reliable signal.
- Notes: Run 16 was a dev-mode self-audit. 4 items found and resolved (1 HIGH, 2 MEDIUM, 1 LOW). All were either doc/drift or PAT-001 family. Convergence achieved in 3 iterations.

### 2026-03-24: Run 15 completed
- Added: PAT-001 (4 instances), 1 architectural risk (pytest-cov coverage gap), 1 proactive check (code-fence regex detection)
- Removed: none (first run)
- Calibration: prediction accuracy was 14% (1 of 7 predictions confirmed). HIGH direct-observation predictions reliable; coverage-proxy and pattern-matching predictions need recalibration.
- Notes: First living punchlist entry. Run 15 was a full adversarial self-play audit in dev mode. 9 items found and resolved (4 HIGH, 4 MEDIUM, 1 LOW). Convergence achieved in 3 iterations after history reset due to premature convergence declaration.

# Living Punchlist

**Project:** holtz
**Established:** 2026-03-24
**Last Updated:** 2026-03-26
**Audits Completed:** 6

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** code-fence-unaware parsing — Regex applied to markdown content without masking code fences first, causing fields inside fenced code blocks to match as real values
  - Instances: BH-003, BH-004, BH-005, BH-006 (Run 15)
  - Root cause: Two independent implementations of fence masking (markdown_utils.py for scripts, _common.py for hooks). New code that processes markdown must choose the right masking function for its layer. Convention is documented but not enforced at import time.
  - Detection rule: `grep -rn 're\.\(search\|findall\).*content' hooks/ skills/holtz/scripts/ | grep -v mask`
  - First seen: Run 1 (2026-03-20)

- **PAT-005:** README-count-drift — hardcoded counts in README (patterns, lenses, anti-patterns, runs) that must be manually updated when files are added, causing README to silently diverge from actual file counts
  - Instances: Run 19 findings (patterns 14→16, lenses 9→13, anti-patterns 12→17, runs 16→18); recurred Run 20 (6th consecutive run affected)
  - Root cause: README contains numeric literals for counts of dynamically-growing collections (pattern files, lens files, anti-pattern files, run history). No automated sync between filesystem state and README prose.
  - Detection rule: `grep -n 'patterns\|lenses\|anti-patterns' README.md | grep -E '[0-9]+'` — compare counts in README against `ls skills/holtz/patterns/*.md | wc -l`, `ls skills/holtz/agents/lenses/*.md | wc -l`, etc.
  - First seen: Run 19 (2026-03-25)
  - Recurrence: Confirmed in every run since first seen (Runs 19, 20). Root cause unaddressed — no automated sync exists.

- **PAT-004:** dual-implementation divergence — `hooks/_common.py` reimplements `markdown_utils.py` fence masking with a simpler algorithm, causing behavioral divergence between script-layer and hook-layer markdown processing
  - Instances: Run 18 findings
  - Root cause: Two independent implementations of the same operation (fence masking) evolved separately. `_common.py` uses a simpler algorithm than `markdown_utils.py`, so edge cases handled by one are missed by the other.
  - Detection rule: `diff <(grep -n 'def mask' skills/holtz/scripts/markdown_utils.py) <(grep -n 'def mask' hooks/_common.py)` — compare masking function signatures and logic across layers
  - First seen: Run 18 (2026-03-25)

### Risk Hotspots

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| `hooks/_common.py:mask_fenced_blocks` | 0.7 | BH-018 (Run 20) | 1 | Fence masking design gap; BH-018 resolved in Run 20 fix loop, but PAT-004 dual-implementation structural divergence persists — `_common.py` uses a simpler algorithm than `markdown_utils.py`. Impact graph score unchanged at 0.7. Cooldown requires two consecutive clean runs. |

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

### Check 3: README count drift
**Source:** PAT-005
**Trigger:** Any new file added to `skills/holtz/patterns/`, `skills/holtz/agents/lenses/`, or `docs/holtz/archive/` (new run archived); or any edit to `README.md` touching numeric counts
**Heuristic:** Compare README numeric claims against filesystem: `ls skills/holtz/patterns/*.md | wc -l` vs README pattern count; `ls skills/holtz/agents/lenses/*.md | wc -l` vs README lens count; `ls docs/holtz/archive/ | grep -c run` vs README run count
**If triggered:** Update the corresponding count(s) in README.md to match the filesystem state before merging.

### Check 4: Pricing integration completeness
**Source:** BH-011 (Run 20) — pricing module integration gap
**Trigger:** Any change to `scripts/token_profiler/pricing.py`, `scripts/token_profiler/analyze.py`, or `scripts/token_profiler/cli.py`
**Heuristic:** Verify pricing is wired end-to-end: `grep -n 'pricing\|price\|cost' scripts/token_profiler/cli.py scripts/token_profiler/analyze.py` — confirm pricing results flow through to report output and are not silently dropped
**If triggered:** Trace the data path from `pricing.py` through `analyze.py` to `report.py`/`cli.py`. Verify output includes pricing fields and that a test covers the full pipeline with a non-zero price assertion.

### Check 5: Impact graph exception handling
**Source:** BH-024 (Run 20) — impact graph exception change
**Trigger:** Any change to `skills/holtz/scripts/impact_graph.py` exception handling or node update logic
**Heuristic:** `grep -n 'except\|raise\|Exception\|KeyError' skills/holtz/scripts/impact_graph.py` — verify exception semantics match callers' expectations (silent return vs. propagate)
**If triggered:** Review callers of the changed function to confirm they handle the new exception behavior. Check that tests cover the exception path.

## Prediction Accuracy

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 9         | 7         | 78%      |
| MEDIUM     | 18        | 10        | 56%      |
| LOW        | 5         | 3         | 60%      |
| **Total**  | **32**    | **20**    | **63%**  |

### Calibration Notes

- HIGH-confidence predictions based on direct observation (broken tests visible in baseline) are reliable. Prediction 1 (broken test file) confirmed.
- HIGH-confidence predictions based on coverage metrics (0% = untested) were wrong: hooks at 0% line coverage had 24+ tests via subprocess (invisible to pytest-cov). Coverage proxy unreliable for subprocess-tested code.
- MEDIUM-confidence predictions from global pattern matching (PAT-001 in new hooks) were directionally correct (4 instances found) but classified as UNCONFIRMED because the predictions framed them as bug/logic while findings were design/inconsistency. Consider scoring directional hits separately.
- LOW-confidence predictions from git churn (historical README line counts) are unreliable — README narrative accurately describes historical state, not current state.
- Run 18: HIGH predictions at 100% (2/2) — continuing the trend that direct-observation HIGH predictions are the most reliable signal. MEDIUM and LOW predictions again produced 0% confirmation, suggesting these confidence tiers need tighter scoping or should be deprioritized.
- Run 19: MEDIUM predictions dramatically improved — 6/7 confirmed (86%). The BH-005 recommendation escalation (surfaced in Runs 13+16) that was predicted and finally resolved with a test confirms that persistent-gap predictions are highly reliable once a pattern is identified across multiple runs. LOW predictions showed first confirmation (1/1). Cumulative model now at 52% overall — a substantial improvement from 23% after Run 18, driven by MEDIUM finally calibrating.
- Run 20 (corrected): 7/9 confirmed, 1 partially confirmed (P5), 1 unconfirmed (P4). HIGH at 100% (2/2). MEDIUM at 80% (3 confirmed + 1 partial + 1 unconfirmed of 5) — P4 unconfirmed and P5 partial are both in MEDIUM tier. LOW at 100% (2/2). All 27 findings resolved (20 in main sweep, 7 deferred then resolved in fix loop). Overall cumulative accuracy now 63% (20/32) — continued improvement as the model calibrates. PAT-005 recurrence confirmed for 6th consecutive run. Pricing cluster (BH-011) resolved this run; impact graph exception handling (BH-024) resolved. Proactive checks 4 and 5 added to guard these areas going forward.

## History

### 2026-03-26: Run 20 completed (full 13-lens audit — corrects earlier partial entry below)
- Added: Risk hotspot `hooks/_common.py:mask_fenced_blocks` (risk_score 0.7, sourced from impact graph); Proactive Check 4 (pricing integration completeness, sourced from BH-011); Proactive Check 5 (impact graph exception handling, sourced from BH-024); PAT-005 recurrence note (6th consecutive run affected)
- Removed: none; BH-018 resolved in fix loop but PAT-004 structural divergence persists — hotspot retained until two consecutive clean runs
- Calibration: Run 20 prediction accuracy 78% (7 of 9 confirmed, 1 partially confirmed P5, 1 unconfirmed P4). HIGH: 100% (2/2). MEDIUM: 80-100% (3 confirmed + 1 partial + 1 unconfirmed of 5). LOW: 100% (2/2). Cumulative across 5 runs: HIGH 78% (7/9), MEDIUM 56% (10/18), LOW 60% (3/5), Total 63% (20/32).
- Notes: Run 20 full 13-lens audit found 27 findings (20 resolved in main sweep, 7 deferred → all 7 resolved in fix loop). Final state: 27 resolved, 0 open, 0 deferred. Tests grew 641→647; coverage 66%. Convergence at iteration 8. BH-011 pricing integration and BH-024 impact graph exception change resolved; Proactive Checks 4 and 5 derived from these findings. PAT-005 recurred for the 6th consecutive run — no automated README sync exists. mask_fenced_blocks elevated to hotspot (0.7) from PAT-004 — structural divergence between `_common.py` and `markdown_utils.py` fence masking algorithms persists.

### 2026-03-26: Run 20 preliminary entry (superseded by entry above)
- Added: Risk hotspot `hooks/_common.py:mask_fenced_blocks` (risk_score 0.7, sourced from impact graph); PAT-005 recurrence note (6th consecutive run affected)
- Removed: none
- Calibration: Run 20 prediction accuracy 78% (7 of 9 confirmed, 1 partially confirmed, 1 unconfirmed). HIGH: 67% (2/3). MEDIUM: 83% (5/6). LOW: n/a (no LOW predictions). Cumulative across 5 runs: HIGH 70% (7/10), MEDIUM 58% (11/19), LOW 33% (1/3), Total 59% (19/32).
- Notes: Run 20 found 21 items (17 resolved, 4 deferred). Deferred: BH-011/012 (pricing module disconnection — scope), BH-018 (fence masking design — architectural, not a quick fix), BH-019 (pricing-adjacent). Tests grew 641→646; coverage stable at 65%. Convergence in 3 iterations. mask_fenced_blocks elevated to risk hotspot (0.7) due to BH-018 deferral — PAT-004 dual-implementation divergence unresolved at that function. PAT-005 recurred for the 6th consecutive run, confirming no automated README sync exists. Pricing module cluster (BH-011/012/019) consistently deferred — candidate for Persistent Gap if present in Run 21.

### 2026-03-25: Run 19 completed
- Added: PAT-005 (README-count-drift), Proactive Check 3 (README count drift detection)
- Removed: none
- Calibration: Run 19 prediction accuracy 80% (8 of 10 confirmed). HIGH: 100% (2/2). MEDIUM: 86% (6/7). LOW: 100% (1/1). Cumulative across 4 runs: HIGH 71% (5/7), MEDIUM 46% (6/13), LOW 33% (1/3), Total 52% (12/23).
- Notes: Run 19 was a dev-mode self-audit. 11 items found and resolved (2 HIGH, 5 MEDIUM, 4 LOW). Findings included README count drifts (patterns 14→16, lenses 9→13, anti-patterns 12→17, runs 16→18), recommendation escalation BH-005 resolved with semantic claim test, token profiler pricing no-op, extract.py json error handling, artifact_verification.py PAT-003 instance, analyze.py timestamp handling, permissive assertions, and rubber stamp tests. New pattern PAT-005 identified: hardcoded README counts diverge silently when collection files are added. BH-005 recommendation escalation (Runs 13+16) resolved with test — longest-running persistent gap closed. Convergence in 3 iterations. All risk scores at 0.0 after convergence, no hotspots above 0.5.

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

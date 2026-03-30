
# Holtz Convergence Summary

**Project:** holtz v1.0.0
**Run:** 27
**State:** Fix Loop (Step 10)
**Ledger:** 106 events
**Violations:** 12


## Results

| Metric | Value |
|--------|-------|
| Total findings | 12 |
| Resolved | 12 |
| Open at convergence | 0 |
| Perspectives completed | 0 / 13 |
| Fix iterations | 8 |
| Protocol violations | 12 |

## Findings by Severity


| Severity | Found | Resolved |
|----------|-------|----------|
| HIGH | 2 | 2 |
| MEDIUM | 5 | 5 |
| LOW | 5 | 5 |


## Findings by Perspective


| Perspective | Found | Resolved |
|-------------|-------|----------|
| component | 5 | 5 |
| integration | 1 | 1 |
| security | 3 | 3 |
| error-propagation | 1 | 1 |
| data-flow | 1 | 1 |
| public-contract | 1 | 1 |


## State History

- idle → **recon** (run_start) — 2026-03-29T22:36:33.318Z
- recon → **audit** (recon_complete) — 2026-03-29T22:46:50.482Z
- audit → **merge_ready** (audit_complete) — 2026-03-29T22:55:25.137Z
- merge_ready → **merge_done** (merge_complete) — 2026-03-29T23:00:45.092Z
- merge_done → **fix_loop** (fix_loop_start) — 2026-03-29T23:00:58.087Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:07:05.820Z
- fix_loop → **awaiting_clear** (iteration_boundary) — 2026-03-29T23:09:21.301Z
- awaiting_clear → **fix_loop** (resume) — 2026-03-29T23:24:36.767Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:29:10.608Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:31:23.436Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:32:14.253Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:34:39.185Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:37:02.341Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:39:58.573Z
- fix_loop → **pattern_analysis** (pattern_check) — 2026-03-29T23:40:04.909Z
- pattern_analysis → **fix_loop** (pattern_done) — 2026-03-29T23:40:57.004Z
- fix_loop → **awaiting_clear** (iteration_boundary) — 2026-03-29T23:41:46.465Z
- awaiting_clear → **fix_loop** (resume) — 2026-03-29T23:43:36.035Z
- fix_loop → **fix_loop** (fix_commit) — 2026-03-29T23:59:54.043Z


## Perspective Completion

- [ ] component
- [ ] integration
- [ ] security
- [ ] error-propagation
- [ ] data-flow
- [ ] contract
- [ ] semantic-fidelity
- [ ] temporal-protocol
- [ ] public-contract
- [ ] concurrency
- [ ] resource-lifecycle
- [ ] idempotency
- [ ] observability


## Predictions


| ID | Target | Confidence | Outcome | Finding |
|----|--------|------------|---------|---------|
| 1 | enforcement/hooks/bash_guard.py | HIGH | PENDING | — |
| 2 | enforcement/hooks/_protocol_cache.py | HIGH | PENDING | — |
| 3 | enforcement/hooks/write_guard.py | MEDIUM | PENDING | — |
| 4 | hooks/subagent_findings_check.py | MEDIUM | PENDING | — |
| 5 | README.md | MEDIUM | PENDING | — |
| 6 | enforcement/hooks/_resolve.py | LOW | PENDING | — |
| 7 | enforcement/scripts/validate_merge_report.py | LOW | PENDING | — |


## Justine Findings

No Justine findings recorded for this run.


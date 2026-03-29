# Phase: Convergence (Steps 15-16)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 15: Convergence Check

Each iteration gets fresh context. At the end of each iteration — regardless of remaining context:

1. Run `sahjhan transition converge` to attempt convergence. Sahjhan checks all gates: all perspectives complete, suite passes, linters pass, zero open items, no protocol violations.
2. **`sahjhan transition converge` MUST succeed before SUMMARY.md is rendered.** If gates fail, Sahjhan reports which gates are blocking. Run `sahjhan gate check converge` for details.
3. If not converged: run `sahjhan --ledger run-N ledger checkpoint` then `sahjhan transition iteration_boundary`. Tell the user: *"Not converged. `/clear` then any message to continue."* Stop. The stop gate hook enforces this: blocks premature stops until the protocol reaches a terminal state.
4. If converged: Sahjhan transitions to `final_sweep_clean` → `converged`. Proceed to Step 16.

After `/clear`, the primer hook injects resume context and records a `context_reset` event — the user types anything and the model resumes from `sahjhan status`.

**Filtered reads in convergence loop:** Each iteration re-reads the punchlist. If the punchlist has more than 6 items, use:
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/validate_punchlist.py <path> --filter-status OPEN "IN PROGRESS" RESOLVED --resolved-before 3 --render
```
This keeps recently-resolved items visible for pattern recognition while filtering out stable old resolutions. Step 11 (pattern analysis, every 3-5 fixes) reads the full punchlist.

### Step 16: Resweep

Full re-run of Steps 6-8 to confirm convergence. This is NOT optional — it catches errors introduced by prior fixes. The resweep must complete before writing SUMMARY.md.

# Phase: Convergence (Steps 15-16)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 15: Convergence Check

Each iteration gets fresh context. At the end of each iteration — regardless of remaining context:

When all 13 lenses pass clean, the convergence flow requires these transitions in order:

All sahjhan commands below must include `--config-dir "$CLAUDE_PLUGIN_ROOT/enforcement"` when running as an installed plugin (see SKILL.md). The flag is shown in every example so the agent can copy-paste literally.

1. From `perspective_clean`: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition all_perspectives` — gate checks all 13 lenses are marked complete. Transitions to `all_perspectives_clean`.
2. From `all_perspectives_clean`: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition final_sweep_start` — transitions to `final_sweep`.
3. From `final_sweep`: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition converge` — Sahjhan checks all gates: all perspectives complete, suite passes, linters pass, zero open items, no protocol violations.
4. **`sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition converge` MUST succeed before SUMMARY.md is rendered.** If gates fail, Sahjhan reports which gates are blocking. Run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" gate check converge` for details.
5. If the final sweep found new issues: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition sweep_dirty` to return to `fix_loop`. Fix the issues and repeat the convergence flow.
6. If not converged for other reasons: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" ledger checkpoint --snapshot pre-clear` then `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition iteration_boundary`. Tell the user: *"Not converged. `/clear` then any message to continue."* Stop. The stop gate hook enforces this: blocks premature stops until the protocol reaches a terminal state.
7. If converged: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition confirm_convergence` — transitions from `final_sweep_clean` to `converged`. Proceed to Step 16.

After `/clear`, Claude Code's `SessionStart` records the `context_reset` event and the primer injects resume context — the user types anything and the model resumes from `sahjhan status`.

**Filtered reads in convergence loop:** Each iteration re-reads the punchlist. If the punchlist has more than 6 items, use:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/validate_punchlist.py <path> --filter-status OPEN "IN PROGRESS" RESOLVED --resolved-before 3 --render
```
This keeps recently-resolved items visible for pattern recognition while filtering out stable old resolutions. Step 11 (pattern analysis, every 3-5 fixes) reads the full punchlist.

### Step 16: Resweep

Full re-run of Steps 6-8 to confirm convergence. This is NOT optional — it catches errors introduced by prior fixes. The resweep must complete before writing SUMMARY.md.

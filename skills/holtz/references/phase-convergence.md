# Phase: Convergence (Steps 15-16)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 15: Convergence Check

Each iteration gets fresh context. At the end of each iteration — regardless of remaining context:

When all 13 lenses pass clean, the convergence flow requires these transitions in order:

All sahjhan commands below must include `--config-dir "$CLAUDE_PLUGIN_ROOT/enforcement"` when running as an installed plugin (see SKILL.md). The flag is shown in every example so the agent can copy-paste literally.

1. From `perspective_clean`: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition all_perspectives` — gate checks all 13 lenses are marked complete. Transitions to `all_perspectives_clean`.
2. From `all_perspectives_clean`: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition final_sweep_start` — transitions to `final_sweep`.
3. Harden the fault-injected findings, one commit per module. Run `python3 ${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/hardening_batch.py --show` to list them, grouped by containing directory. For each module: make the code robust to the injected faults, commit that module's work in **one** commit whose message names every finding id in that module and no id outside it, then run `python3 ${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/hardening_batch.py --record --module <dir>` as its own Bash call. Repeat until `--show` prints `{}`.
4. From `final_sweep`: run `python3 ${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/verify_suite.py --record --scope full` (the `converge` gate reads that green; per-fix `affected` greens do not satisfy it), then `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition converge` — Sahjhan checks all gates: all 13 lenses complete, the recorded full-suite green, the linter, `all_critical_resolved`, `no_open_fault_injected`, `all_user_reachable_high_closed`, `amplification_diverging` false, `quiz_exhaustions_resolved`, `deferral_record_complete`, and no unresolved protocol violations. MEDIUM and LOW findings may still be open.
5. **`sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition converge` MUST succeed before SUMMARY.md is rendered.** If gates fail, Sahjhan reports which gates are blocking. Run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" gate check converge` for details.
6. If the final sweep found new issues: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition sweep_dirty` to return to `fix_loop`. Fix the issues and repeat the convergence flow.
7. If not converged for other reasons: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" ledger checkpoint --snapshot pre-clear` then `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition iteration_boundary`. Tell the user: *"Not converged. `/clear` then any message to continue."* Stop. The stop gate hook enforces this: blocks premature stops until the protocol reaches a terminal state.
8. If converged: run `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" transition confirm_convergence` — transitions from `final_sweep_clean` to `converged`. Proceed to Step 16.

After `/clear`, Claude Code's `SessionStart` records the `context_reset` event and the primer injects resume context — the user types anything and the model resumes from `sahjhan status`.

#### Blocked by open fault-injected findings

`converge` refuses while any finding whose latest filing grades it `fault_injected` is still open. Clear it with step 3 above — `--show`, one hardening commit per module, `--record --module <dir>`. Re-filing a finding with a corrected `reachability` or a corrected `location` moves it; the latest filing decides both.

`--record` refuses and names what is wrong when: the module has no open fault-injected findings, the commit message misses one of them, the message names a finding from another module, the commit has no changes in it, the commit already closed something, or a finding's `location` has no readable path. Fix what it names and run it again.

#### Blocked by an exhausted lens quiz

`converge` also refuses while any lens has an unresolved `quiz_exhausted` — a lens whose subagent failed its re-read quiz to the attempt limit, or whose questions went stale because fix commits moved the source they anchor to. (The bank is graph-derived during recon and locked when the vault key closes at `recon_complete`; it cannot be regenerated in place.)

**You cannot clear this yourself.** The quiz exists to make "I looked again" mean the code was actually re-read, so signing off on your own failure to demonstrate that would void the check. Recording the resolution event is blocked on your Bash path and will stay blocked.

Stop and hand it to the user. Tell them which lens is exhausted, point at its artifact (`docs/holtz/audit/lens-<lens>.md`), summarise what the sweep did and did not establish, and ask them to run — with the leading `!`, which runs it as *them*, not as a tool call:

```bash
! sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event quiz_exhausted_resolved --field project=<project> --field run=<run> --field auditor=holtz --field perspective=<lens> --field resolution=human_reviewed
```

The alternative, if they would rather not accept it, is starting a fresh run so recon rebuilds the bank against current source.

**Re-reading the worklist each iteration:** query it, do not read `docs/holtz/PUNCHLIST.md`.
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/findings.py list
```

### Step 16: Resweep

Re-run Steps 6-8 over the code this run changed. This is NOT optional — it catches errors introduced by prior fixes — and it must complete before SUMMARY.md is rendered.

1. The files the run changed:
   ```bash
   git diff <run-base>..HEAD --name-only
   ```
2. Widen to what depends on them — for each changed node:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json blast_radius <node> --depth 2
   ```
3. Dispatch the Step 7-8 subagents over that file set, every lens applied.

If the run changed no source files, the resweep is the full Steps 6-8.

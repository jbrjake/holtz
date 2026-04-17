# Phase: Finalize (Steps 17-20)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 17: Architecture Baseline Update (Subagent)

Dispatch a subagent in the background to update the architecture baseline:

```
Agent(run_in_background=true, prompt="Update the architecture baseline at docs/holtz/architecture-baseline.md.
Read the format spec at ${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/architecture-baseline-format.md.

1. STRUCTURAL SNAPSHOT: Re-infer the current module dependency graph from code (trace imports/requires across all significant modules). Update the Module Dependencies table, Entry Points list, and Export Surface. Only update what changed — do not rewrite unchanged sections.

2. DOCUMENTED INTENT: Read current project docs (CLAUDE.md, README, ARCHITECTURE.md if they exist). Compare against the Documented Intent section of the baseline. If documented rules changed, update Layering Rules, Boundaries, Conventions, and Invariants to match. Note any changes.

Do NOT modify the Drift Log — it was already updated during Step 0.

Write changes to docs/holtz/architecture-baseline.md. Report what sections changed and why.")
```

After the subagent completes, record the event (required by the `finalize` gate):
```
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event baseline_updated --field project=<project> --field run=N \
  --field auditor=holtz --field sections_changed="<comma-separated list of changed sections>"
```

### Step 18: Pattern Library Contribution (Subagent)

Read [references/pattern-contribution-protocol.md](references/pattern-contribution-protocol.md) and follow the protocol: discover new patterns from `docs/holtz/patterns-brief.md`, generalize, PII-scrub, ask user permission, then submit via `gh` CLI / MCP / manual staging. Record outcome: `sahjhan event pattern_contribution_complete --patterns_submitted N --outcome submitted|no_new_patterns|declined_by_user`.

### Step 19: Living Punchlist Update (Subagent)

Update `docs/holtz/LIVING-PUNCHLIST.md` (or create it on first run — see [references/living-punchlist-format.md](references/living-punchlist-format.md)):

1. Refresh Risk Hotspots from impact graph (nodes with risk_score > 0.5)
2. Add new patterns from this run's pattern brief
3. Update Architectural Risks from drift log (MEDIUM+ severity entries)
4. Record prediction accuracy for calibration
5. Derive new proactive checks from patterns, hotspots, and drift
6. Move cooled hotspots (risk_score below 0.3 for two consecutive converged runs) to History with note
7. Append run summary to History section

After the subagent completes, record the event (required by the `finalize` gate):
```
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event living_punchlist_updated --field project=<project> --field run=N \
  --field auditor=holtz --field patterns_added=<count> --field hotspots_updated=<count>
```

### Step 20: Finalize

This is the LAST step — nothing comes after it.

Run `sahjhan transition finalize` — this transitions to the terminal `finalized` state and renders SUMMARY.md from the ledger. The finalize gate verifies: architecture baseline updated (Step 17), living punchlist updated (Step 19), pattern contribution completed (Step 18). SUMMARY.md includes a Prediction Accuracy table:

```markdown
## Prediction Accuracy
| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | N         | N         | N%       |
| MEDIUM     | N         | N         | N%       |
| LOW        | N         | N         | N%       |
| **Total**  | **N**     | **N**     | **N%**   |
```

After finalization, the daemon is stopped automatically by the `stop_hook.py` and `protocol_tracker.py` hooks when the state reaches `finalized`. No manual `daemon stop` command is needed.

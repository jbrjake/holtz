# Phase: Merge (Step 9)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 9: Merge Justine Findings (Subagent)

Before starting any fix work, check whether Justine has produced results:

1. **Check for Justine's output.** If `docs/holtz/justine/PUNCHLIST.md` exists, Justine has findings to merge.
2. **If Justine is still running** (no `docs/holtz/justine/SUMMARY.md` and no `docs/holtz/justine/PUNCHLIST.md`), check her output files for stall indicators: no updates in >30 minutes, or 3 consecutive fix iterations with no progress. If stalled, proceed with whatever she has. If she's still actively working, wait — her breadth-first pass is fast.
3. **If Justine has results**, first record the dispatch event (required by the `merge_complete` gate):
   ```
   sahjhan event merge_agent_dispatched --field project=holtz --field run=N \
     --field auditor=holtz --field phase=merge --field step=9
   ```
   Then dispatch the merge agent:

```
Agent(subagent_type="merge-agent", prompt="Merge Holtz's punchlist at docs/holtz/PUNCHLIST.md with Justine's at docs/holtz/justine/PUNCHLIST.md. Follow the merge protocol at ${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/merge-protocol.md. Merge impact graphs per protocol. Write PUNCHLIST-MERGED.md and MERGE-REPORT.md to docs/holtz/. Archive docs/holtz/justine/ to docs/holtz/archive/justine-{ISO date}/. Return: merged total, agreement count, Holtz-only count, Justine-only count, contradiction count.")
```

4. **After the merge completes:** Read `docs/holtz/MERGE-REPORT.md` for blind spot analysis and contradiction flags. Read `docs/holtz/PUNCHLIST-MERGED.md` — this is your worklist for Step 10. **Spot-check 2-3 items** against the original punchlists if the merge report shows disagreements or contradictions.
5. **If no Justine output exists** (she wasn't dispatched or produced nothing), proceed with `docs/holtz/PUNCHLIST.md` as the worklist.

Run `sahjhan transition merge_complete` to advance protocol state.

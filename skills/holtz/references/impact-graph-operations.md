# Impact Graph Operations

Complete reference for all `impact_graph.py` CLI operations. The `--graph` flag is a **global argument** that must come BEFORE the subcommand.

## Graph Initialization (First Run)

The graph file is created automatically when you add the first node — `save()` creates parent directories and the file. Start adding nodes as you discover project entities during recon.

```bash
# First add_node creates docs/holtz/impact-graph.json
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_node "<module>:<function>" "function" "<file_path>" --line <N>
```

## Graph Reconciliation (Subsequent Runs)

If `docs/holtz/impact-graph.json` exists, reconcile before adding new nodes:

```bash
# 1. Remove nodes for deleted files (cascade-deletes edges)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json prune_missing --project-root .

# 2. Flag nodes whose entity shifted >10 lines or is absent
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json drift_check --project-root .
```

3. **Stale edge verification (LLM-driven):** Verify `calls` and `imports` edges by grepping for the call/import in the source file. Remove severed relationships. `assumes` and `diverges_from` edges are NOT verified here — they require re-evaluation during Phases 1-3.

4. **Add new nodes** for files and functions discovered in recon:
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_node "<module>:<function>" "function" "<file_path>" --line <N>
```

## Adding Edges During Audit Phases

<HARD-GATE>
Every audit phase (1, 2, 3) MUST add edges to the impact graph. After completing each phase, run `stats` to verify the edge count increased. If you processed 5+ claims/files/modules and added zero edges, STOP — re-examine your findings for missed relationships before proceeding to the next phase.
</HARD-GATE>

### Edge Types

| Type | Meaning | When to add |
|------|---------|-------------|
| `imports` | A imports/requires B | Phase 0 recon, reading code |
| `calls` | A calls function in B | Phase 3 adversarial audit |
| `tests` | Test file covers function | Phase 2 test audit |
| `assumes` | A makes an assumption about B's behavior | Phases 1-3, any cross-module assumption |
| `diverges_from` | A and B parse/interpret same data differently | Phase 1 doc audit, Phase 3 code audit |
| `shares_pattern` | A and B exhibit same bug pattern | Phase 5 pattern analysis |
| `co_fixed` | A and B were fixed in same commit | Phase 4 blast radius |

### CLI Commands for Each Edge Type

```bash
# Relationship edges (Phase 0)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<source_id>" "<target_id>" "imports"
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<caller_id>" "<callee_id>" "calls"

# Test coverage edges (Phase 2)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<test_file_id>" "<function_id>" "tests"

# Semantic edges (Phases 1-3) — ALWAYS include --note
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<source_id>" "<target_id>" "assumes" --note "<what A assumes about B>"
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<source_id>" "<target_id>" "diverges_from" --note "<how A and B differ>"

# Pattern edges (Phase 5)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<func_a_id>" "<func_b_id>" "shares_pattern" --note "PAT-NNN"

# Co-fix edges (Phase 4 blast radius)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json add_edge "<func_a_id>" "<func_b_id>" "co_fixed" --note "<commit_hash>"
```

### Verification

After completing each phase, verify edges were added:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats
```

Expected output shows node count, edge count, and edge type breakdown. The edge count MUST increase after each audit phase.

## Blast Radius Queries (Phase 4)

After each fix, query the impact graph for downstream effects:

```bash
# Standard depth (2 hops)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py blast_radius <changed_id> --depth 2

# Architectural fixes (3 hops)
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py blast_radius <changed_id> --depth 3
```

For each node in the blast radius:
1. Read the code
2. Check: does it still hold correct assumptions about the changed code?
3. If an `assumes` or `diverges_from` edge exists, pay special attention
4. If assumption violated → new punchlist item
5. If assumption holds → update edge metadata with `"verified {date}"`

## Risk Score Updates (Phase 4)

After each fix and blast radius check:

```bash
# Lower risk on fixed node
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py update_risk <fixed_node_id> -0.1

# Lower risk on clean blast radius nodes
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py update_risk <clean_node_id> -0.05
```

Add/update edges if the fix changed relationships (new call, removed import). For architectural fixes, add `assumes` edges for new implicit contracts. Add `co_fixed` edges between functions fixed in the same commit.

## Justine's Graph (Parallel Dispatch)

During adversarial self-play, Justine writes to her own graph to avoid concurrent write conflicts:

```bash
# Justine uses --graph docs/holtz/justine/impact-graph.json for ALL operations
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/justine/impact-graph.json add_node ...
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/justine/impact-graph.json add_edge ...
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/justine/impact-graph.json stats
```

After the merge, Justine's graph is merged into the canonical graph per [merge-protocol.md](merge-protocol.md).

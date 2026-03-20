# Tier 2: Core Architecture — Knowledge Graph, Lens Registry, Predictive Recon, Blast Radius

**Date:** 2026-03-20
**Status:** Draft
**Source:** `docs/holtz-self-reflection.md` Sections II, III, IV, VI
**Depends on:** Tier 1 (Discovery Chain, Strategy Journal, Pattern Brief)
**Scope:** Four components implemented bottom-up: Knowledge Graph → Lens Registry → Predictive Recon → Blast Radius Analysis

## Overview

Tier 2 adds the core architectural capabilities identified in the self-reflection essay: multi-lens convergence, predictive recon, and post-fix blast radius analysis. All three consume a new piece of infrastructure — a persisted knowledge graph that encodes relationships between code entities.

Implementation order matters. The knowledge graph is the foundation. Blast radius analysis queries it. The lens registry uses it to inform lens priority. Predictive recon draws from it for hypothesis generation.

**New script:** `scripts/impact_graph.py` (graph operations + CLI)
**New reference doc:** `references/lens-registry.md` (lens definitions)
**New test file:** `tests/test_impact_graph.py`

---

## 1. Knowledge Graph (Impact Graph)

**Problem:** After each fix, Holtz needs to know what other code might be affected. Currently this requires re-reading and re-reasoning about relationships that may have been compacted away. Additionally, semantic knowledge the auditor gains — "these two parsers make divergent assumptions about item boundaries" — has no durable representation outside the context window.

**Change:** A new Python script `scripts/impact_graph.py` and a persisted JSON data structure at `docs/holtz/impact-graph.json`. The graph encodes relationships between code entities that Holtz discovers during auditing. It persists across runs and grows richer over time.

### Top-Level JSON Schema

```json
{
  "nodes": {
    "<id>": { "type": "...", "file": "...", "line": N, "last_audited": "...", "audit_count": N, "risk_score": 0.0 },
    ...
  },
  "edges": [
    { "source": "<id>", "target": "<id>", "type": "...", "metadata": { ... } },
    ...
  ]
}
```

Nodes are stored as a dict keyed by ID for O(1) lookup. Edges are stored as a list.

### Node Format

```json
{
  "id": "validate_punchlist.py::parse_punchlist",
  "type": "function",
  "file": "skills/holtz/scripts/validate_punchlist.py",
  "line": 120,
  "last_audited": "2026-03-20",
  "audit_count": 4,
  "risk_score": 0.0
}
```

Node types: `function`, `class`, `module`, `test`, `config`, `doc`.

**Node ID conventions by type:**

| Type | ID Format | Example |
|------|-----------|---------|
| `module` | `filename` | `validate_punchlist.py` |
| `function` | `filename::function_name` | `validate_punchlist.py::parse_punchlist` |
| `class` | `filename::ClassName` | `models.py::PunchlistItem` |
| `test` | `filename::test_function_name` | `test_validate_punchlist.py::test_parse_items` |
| `config` | `filename` | `pyproject.toml` |
| `doc` | `filename` | `README.md` |

**Field semantics:**

- `risk_score`: Float 0.0-1.0. Updated via `update_risk`. A function that has produced 3 bugs has a higher risk score than one that's been clean across 4 audits.
- `audit_count`: Integer. Incremented each time `add_node` is called on an existing node ID (i.e., each time the node is re-confirmed during a run). Not incremented by queries, risk updates, or edge operations.
- `last_audited`: ISO date string. Updated each time `add_node` is called on an existing node ID.

**`add_node` update semantics (existing node):** When `add_node` is called with an ID that already exists: `file`, `line`, `type`, and `last_audited` are overwritten with new values. `risk_score` is preserved. `audit_count` is incremented by 1.

### Edge Format

```json
{
  "source": "validate_punchlist.py::parse_punchlist",
  "target": "markdown_utils.py::mask_code_fences",
  "type": "calls",
  "metadata": {
    "discovered": "2026-03-19",
    "confidence": "high",
    "note": "passes raw content, receives masked+normalized tuple"
  }
}
```

**Edge identity and deduplication:** Edges are identified by the `(source, target, type)` tuple. Adding an edge with the same triple updates the metadata on the existing edge rather than creating a duplicate. Multiple edges between the same two nodes are allowed if they have different types (e.g., A `calls` B and A `assumes` B are two distinct edges).

**Edge metadata `confidence` values:** `high`, `medium`, `low`. Free text is also allowed in the `note` field.

**`add_edge` with nonexistent endpoints:** Returns an error if either the source or target node does not exist. Edges are not created for phantom nodes.

### Edge Types

| Edge Type | Meaning | Example |
|-----------|---------|---------|
| `calls` | A calls B | `parse_punchlist` calls `mask_code_fences` |
| `imports` | A imports from B's module | `validate_punchlist` imports `markdown_utils` |
| `tests` | Test A covers function B | `test_parse_punchlist` tests `parse_punchlist` |
| `shares_pattern` | A and B were both instances of PAT-NNN | linked via pattern discovery |
| `assumes` | A makes an assumption about B's behavior | "parse_punchlist assumes count_items agrees on item boundaries" |
| `co_fixed` | A and B were fixed in the same commit | from git history |
| `diverges_from` | A and B parse/interpret the same data differently | structural disagreement |

### Script Operations

| Command | Purpose |
|---------|---------|
| `add_node <id> <type> <file> [--line N]` | Add or update a node |
| `add_edge <source> <target> <type> [--note "..."]` | Add a typed edge |
| `neighbors <id> [--type calls,assumes]` | Return direct neighbors, optionally filtered by edge type |
| `blast_radius <id> [--depth 2] [--type calls,imports]` | Return all nodes within N hops (bidirectional traversal), optionally filtered by edge type |
| `risk_hotspots [--top 10]` | Return highest risk_score nodes |
| `update_risk <id> <delta>` | Adjust risk score (clamped to 0.0-1.0) |
| `stats` | Return JSON: `{"nodes": N, "edges": N, "edge_types": {"calls": N, ...}}` |
| `prune_node <id>` | Remove node and all connected edges, return list of removed edges |
| `prune_missing --project-root <path>` | Remove nodes whose backing files no longer exist. Return JSON summary: `{"removed_nodes": [...], "removed_edges": N}` |
| `drift_check --project-root <path>` | Flag nodes whose file exists but entity is missing or relocated. Return JSON: `{"drifted": [{"id": ..., "reason": ...}, ...]}` |

**`blast_radius` traversal direction:** Bidirectional. The graph is treated as undirected for reachability purposes. If A `calls` B, then B is in A's blast radius AND A is in B's blast radius. This is because a change to B can break A (the caller), and a change to A can change what B receives. The edge types are still directional for query purposes (`neighbors B --type calls` returns only nodes that B calls, not nodes that call B), but `blast_radius` ignores direction to capture the full impact zone.

**`drift_check` detection strategy:**

| Node Type | Detection Method | Drift Threshold |
|-----------|-----------------|-----------------|
| `module` | File exists at `node.file` | N/A (file existence only — if missing, handled by `prune_missing`) |
| `function` | Grep for `def {name}` (Python), `function {name}` (JS/TS), `func {name}` (Go) in `node.file` | Line shifted by >10 lines from recorded `node.line` |
| `class` | Grep for `class {name}` in `node.file` | Line shifted by >10 lines |
| `test` | Same as `function` (tests are functions) | Line shifted by >10 lines |
| `config` | File exists at `node.file` | N/A (file existence only) |
| `doc` | File exists at `node.file` | N/A (file existence only) |

Entity name is extracted from the node ID (everything after `::` for function/class/test types). For node types without `::` (module, config, doc), drift_check only verifies file existence — which is already covered by `prune_missing`, so these types are skipped by drift_check.

`drift_check` output lists flagged nodes with reason (`"entity_missing"` or `"line_shifted"` with old and new line numbers). The LLM resolves each flag: update the node's line number (preserving risk_score/edges), or prune if the entity was truly removed.

### Graph Lifecycle & Maintenance

The graph persists across runs (like the pattern brief). When archiving a run to `docs/holtz-prior-*/`, the graph stays in `docs/holtz/`.

**Reconciliation protocol (Phase 0, during step 0a):**

Before adding new nodes, Holtz reconciles the graph against the current filesystem:

1. **`prune_missing`** — Remove nodes for deleted files. All edges connected to removed nodes are cascade-deleted.
2. **`drift_check`** — Flag nodes whose file exists but entity is absent or line number has shifted significantly. Flagged nodes are presented to the LLM for resolution (update in place, or prune if truly removed). Nodes updated in place preserve their `risk_score` and edge history.
3. **Stale edge verification (LLM-driven)** — The LLM (not the script) verifies `calls` and `imports` edges by grepping for the call/import in the source file. This is LLM work because function name disambiguation (same name in different modules) requires judgment. Remove severed relationships via `prune_node` or manual edge removal. `assumes` and `diverges_from` edges are NOT verified during this step — they require LLM re-evaluation during Phases 1-3, since the semantic relationship may still hold even if code moved.
4. **Add new nodes** — Files and functions discovered in recon that aren't in the graph get new nodes.

**Note on semantic edges and deletion:** `assumes` and `diverges_from` edges survive stale-edge-detection (step 3) because they encode semantic knowledge that can't be verified by grep. However, they ARE removed via cascade when either endpoint node is deleted (steps 1-2) — if the code is gone, the assumption is moot.

### How Holtz Builds the Graph

| Phase | Graph Activity |
|-------|---------------|
| Phase 0 (Recon) | Reconcile existing graph. Populate initial nodes (modules, key functions) and `imports` edges by reading code. |
| Phases 1-3 (Audit) | Add semantic edges (`assumes`, `diverges_from`, `shares_pattern`) as relationships are discovered during code review. |
| Phase 4 (Fix Loop) | After each fix: query `blast_radius` on changed function. Add `co_fixed` edges. Update `risk_score`. |
| Phase 5 (Pattern Analysis) | Add `shares_pattern` edges between instances of the same pattern. |

### Files Created

| File | Purpose |
|------|---------|
| `skills/holtz/scripts/impact_graph.py` | Graph operations (add/query/update/prune) + CLI |
| `tests/test_impact_graph.py` | Tests for all graph operations |

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Phase 0: reconcile + populate graph. Phases 1-3: add semantic edges. Phase 4: query blast_radius after fixes, update risk scores. Lifecycle: graph persists across runs. |

### Acceptance Criteria

- [ ] `impact_graph.py` supports all 10 operations (add_node, add_edge, neighbors, blast_radius, risk_hotspots, update_risk, stats, prune_node, prune_missing, drift_check)
- [ ] Graph data persists as JSON at `docs/holtz/impact-graph.json`
- [ ] `blast_radius` returns transitive closure to configurable depth
- [ ] `blast_radius` supports edge-type filtering
- [ ] `neighbors` supports edge-type filtering
- [ ] `risk_hotspots` returns nodes sorted by risk_score descending with alphabetical tiebreaker
- [ ] `update_risk` clamps to 0.0-1.0 range
- [ ] `prune_node` removes the node and cascades to all connected edges
- [ ] `prune_missing` scans nodes against filesystem and removes those whose files are gone
- [ ] `drift_check` flags nodes whose file exists but entity is absent or significantly relocated
- [ ] `assumes` and `diverges_from` edges survive stale-edge-detection but are cascade-deleted on node removal
- [ ] Graph survives run archival (not moved to `docs/holtz-prior-*/`)
- [ ] SKILL.md Phase 0 includes graph reconciliation and population steps
- [ ] SKILL.md Phases 1-3 include semantic edge creation
- [ ] SKILL.md Phase 4 includes blast_radius query after each fix

### Test Cases

**Basic operations:**

1. **Add and query nodes:** Add 3 nodes, verify `stats` returns count 3.
2. **Add edges and query neighbors:** Add `A calls B`, `A calls C`, query `neighbors A` → returns B and C. Query `neighbors A --type imports` → returns empty.
3. **Edge metadata preservation:** Add edge with note, query it back, note is preserved.
4. **Persistence round-trip:** Write graph, reload from JSON, verify all nodes/edges/metadata intact.
5. **Empty graph:** All queries on empty graph return empty results, no crashes.
6. **Missing graph file:** First run, no `impact-graph.json` exists. All operations work on empty graph, file created on first write.
7. **Corrupt/empty JSON file:** Graph file contains `{}` or invalid JSON. Script loads gracefully with empty graph or clear error, no crash.

**Blast radius:**

8. **Depth traversal:** A→B→C→D chain. `blast_radius A --depth 1` → {B}. `--depth 2` → {B, C}. `--depth 3` → {B, C, D}.
9. **Depth 0:** `blast_radius A --depth 0` → empty set.
10. **Nonexistent node:** `blast_radius nonexistent_id` → empty set or clear error, no crash.
11. **Disconnected subgraphs:** {A→B→C} and {X→Y→Z}. `blast_radius A --depth 10` → {B, C} only.
12. **Hub node (bidirectional):** H `calls` 50 leaf nodes. `blast_radius H --depth 1` → all 50. `blast_radius leaf_1 --depth 1` → {H} (bidirectional traversal reaches H even though the edge points H→leaf). `blast_radius leaf_1 --depth 2` → {H} + 49 other leaves.
13. **Blast radius with edge type filter:** A `calls` B `assumes` C. `blast_radius A --depth 2 --type calls` → {B} only.

**Cycle handling:**

14. **Simple cycle:** A→B→C→A. `blast_radius A --depth 5` → {B, C}, no infinite loop.
15. **Self-referencing node:** A→A. `neighbors A` returns A. `blast_radius A --depth 3` → {A}, no infinite loop.
16. **Dense cycle cluster:** A↔B, B↔C, C↔A. `blast_radius A --depth 1` → {B, C}. Depth 2 still {B, C}, no duplicates.

**Multi-edge and parallel edges:**

17. **Multiple edge types same nodes:** A `calls` B and A `assumes` B. `neighbors A` returns B once. Both edges preserved independently.
18. **Replace edge metadata:** Add A `calls` B with note "passes raw". Add A `calls` B again with note "passes masked". Updates existing edge.
19. **Directional edges:** A `calls` B does not imply B `calls` A. `neighbors B --type calls` → empty.
20. **Multiple type filter:** A `calls` B, A `imports` C, A `assumes` D. `neighbors A --type calls,imports` → {B, C}.

**Risk scores:**

21. **Boundary clamping:** From 0.0, update by -0.1 → 0.0. From 1.0, update by +0.5 → 1.0.
22. **Nonexistent node:** `update_risk nonexistent_id +0.3` → error, no phantom node.
23. **Tie-breaking:** 3 nodes at risk 0.7. `risk_hotspots --top 2` → exactly 2, alphabetical order.
24. **Empty graph:** `risk_hotspots` → empty list, no crash.

**Pruning:**

25. **Prune missing file:** Node for `foo.py::bar`, file deleted. `prune_missing` removes node + edges.
26. **Edge cascade:** Node A with 3 edges. `prune_node A` removes A and all 3 edges. Connected nodes still exist.
27. **Hub prune:** Hub H with 20 edges. `prune_node H` removes H and all 20 edges. 20 neighbor nodes retain their mutual edges.
28. **Prune last node:** Single node, no edges. `prune_node` → empty graph.
29. **Double prune:** `prune_node A` succeeds. `prune_node A` again → error or no-op, no crash.
30. **Prune missing empty graph:** `prune_missing` on empty graph → no-op.
31. **Prune missing all files gone:** 5 nodes, all backing files deleted. All removed, graph empty.
32. **Drift check:** Node for `foo.py::bar` at line 50. Function moves to line 80. `drift_check` flags as drifted.
33. **Semantic edge survives stale detection:** `assumes` edge between A and B. `calls` edge also exists. During stale edge verification, `calls` edge confirmed or removed by grep. `assumes` edge untouched (requires LLM re-eval). But: if A is deleted via `prune_node`, both edges cascade-deleted.

**Node updates:**

34. **Add node with existing ID:** Add node `foo.py::bar` with line 50. Call `add_node foo.py::bar function foo.py --line 80`. Verify: line updated to 80, `audit_count` incremented by 1, `risk_score` preserved at original value.
35. **Prune missing with all files present:** 5 nodes, all backing files exist. `prune_missing` → no-op, all nodes and edges remain.
36. **Neighbors on nonexistent node:** `neighbors nonexistent_id` → empty set or clear error, no crash.
37. **Add edge with nonexistent endpoint:** Nodes A exists, Z does not. `add_edge A Z calls` → error, no edge created, no phantom node.

**Large graph:**

38. **200-node round-trip:** Build 200 nodes, 500 edges. Write. Reload. All data identical.

---

## 2. Lens Registry & Multi-Lens Convergence

**Problem:** An auditor can only find what its current analytical lens makes visible. Convergence within one perspective doesn't mean convergence across all perspectives. The self-audit data showed that switching from component to integration lens immediately reversed a convergence trend and found MEDIUM-severity bugs invisible to three rounds of component auditing.

**Change:** Define a configurable set of analytical lenses. Holtz rotates through them during the convergence loop. True convergence requires all lenses clean in the same final sweep.

### Lens Definition Format

Each lens is defined in `skills/holtz/references/lens-registry.md`:

```markdown
## component
**Focus:** Individual functions, classes, modules in isolation
**Audit priorities:** Correctness, edge cases, error handling, return values
**Failure modes:** Logic errors, missing validation, unhandled edge cases
**Entry point:** Standard Phases 1-3

## integration
**Focus:** Contracts and assumptions between modules
**Audit priorities:** Interface agreements, shared state, data format assumptions, parser divergence
**Failure modes:** Modules that are individually correct but disagree with each other
**Entry point:** Query impact graph for `assumes`, `diverges_from`, `calls` edges; audit the seams

## security
**Focus:** Attack surfaces, input validation, authorization, data exposure
**Audit priorities:** Untrusted input paths, authentication/authorization checks, secrets handling, injection vectors
**Failure modes:** Missing validation at trust boundaries, privilege escalation, data leakage
**Entry point:** Trace data from external inputs through the system

## error-propagation
**Focus:** How errors flow through the system
**Audit priorities:** Error swallowing, inconsistent error types, missing error paths, partial failure handling
**Failure modes:** Silent failures, error masking, inconsistent error contracts between layers
**Entry point:** Trace error/exception paths from throw to catch

## data-flow
**Focus:** How data transforms as it moves through the system
**Audit priorities:** Serialization/deserialization boundaries, type coercion, lossy transformations, format assumptions
**Failure modes:** Data corruption at boundaries, silent type coercion, schema drift
**Entry point:** Follow data from ingestion to output, checking each transformation

## contract
**Focus:** Explicit and implicit contracts — API signatures, type interfaces, documented behavior guarantees
**Audit priorities:** Functions that promise behavior their implementation doesn't deliver, version drift in interfaces
**Failure modes:** Contract violations that callers silently tolerate until they don't
**Entry point:** Compare documented/typed interfaces against actual implementation behavior
```

### Extensibility

Users can add custom lenses by appending new sections to the registry file following the same four-field format (Focus, Audit priorities, Failure modes, Entry point). SKILL.md references the registry file for the lens list rather than hardcoding lens names. Any `## heading` in the registry file with the four required fields is treated as a lens.

### Lens-Aware Convergence Loop (Phase 6 replacement)

```
WHILE open items remain OR unlensed perspectives exist:
    Read STATUS.md (recover position + active lens)
    Read PUNCHLIST.md (recover worklist)
    Phase 4 (next batch) → Phase 5 (every 3-5) → full suite + linters

    IF within current lens:
        - zero OPEN/IN PROGRESS items AND
        - no new items in 2 consecutive iterations AND
        - test suite stable or improving
    THEN mark current lens COMPLETE in STATUS.md

    IF current lens should switch (any of):
        - current lens marked COMPLETE
        - last 3 consecutive findings added to the punchlist under the current lens are all LOW severity
    THEN:
        - select next lens from registry (skip completed lenses)
        - update Active Lens in STATUS.md
        - run Phases 1-3 scoped to new lens's focus and entry point
        - continue Phase 4-5 loop

    IF all lenses COMPLETE:
        - run final sweep across ALL lenses simultaneously
        - IF clean → CONVERGED
        - IF findings → add to punchlist, reset affected lenses to incomplete
```

### Lens Priority Order

Default order is the order in the registry file (component first, as the broadest lens). The auditor may reorder based on:
- Recon findings (security risks flagged → security lens moves up)
- Impact graph topology (heavy `assumes`/`diverges_from` edges → integration lens moves up)
- Prior run patterns (recurring error-handling bugs → error-propagation lens moves up)

### Punchlist Lens Tagging

Findings discovered under a specific lens include `**Lens:** {lens name}` as an optional field in the punchlist item. This enables pattern analysis to identify whether certain bug categories cluster under specific lenses.

### Files Created

| File | Purpose |
|------|---------|
| `skills/holtz/references/lens-registry.md` | Lens definitions (6 default + extensible) |

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Phase 6 rewritten with lens-aware convergence loop. Phase 0 reads lens registry. |
| `skills/holtz/references/status-file-format.md` | Active Lens section: `Lenses Completed This Run` as a checklist. |
| `skills/holtz/references/punchlist-format.md` | Add optional `**Lens:**` field to item template. |
| `skills/holtz/scripts/validate_punchlist.py` | Add `Lens` to `_field_names` tuple (section boundary terminator). No required-field check. |
| `tests/test_validate_punchlist.py` | Test that Lens field is accepted without error when present and not required when absent. |

### Acceptance Criteria

- [ ] Lens registry file defines 6 default lenses with Focus, Audit priorities, Failure modes, Entry point
- [ ] Registry format is documented so users can add custom lenses
- [ ] SKILL.md Phase 6 implements lens-aware convergence: per-lens convergence → lens switch → all-lens convergence
- [ ] Lens switch triggers on: current lens complete, OR last 3 consecutive findings under current lens all LOW
- [ ] Final convergence requires all lenses clean in the same sweep
- [ ] STATUS.md Active Lens section tracks current lens, completed lenses, and finding rate
- [ ] Lens priority order defaults to registry order but can be reordered by recon/graph signals
- [ ] Findings include optional `**Lens:**` field
- [ ] `validate_punchlist.py` recognizes `Lens` in `_field_names` without requiring it
- [ ] When final all-lens sweep finds new issues, affected lenses are reset to incomplete

### Test Cases

1. **Lens field accepted:** Punchlist item with `**Lens:** integration` → validator passes.
2. **Lens field not required:** Item without Lens field → validator passes.
3. **Lens field in code fence:** `**Lens:**` inside code fence → not treated as real field.

---

## 3. Predictive Recon

**Problem:** Across six self-audit runs, the recon phase consistently identified the exact issues that audit phases later confirmed. Every concern recon raised was confirmed. This suggests recon is doing real analysis — but its output is treated as background context rather than actionable predictions.

**Change:** After standard recon (0a-0g), Holtz produces a predictions file ranking where bugs are likely to be found. Phases 1-3 prioritize predicted areas first. Prediction accuracy is tracked to calibrate future runs.

### New Recon Step

**Step 0h:** After 0g (recon summary). Based on recon findings, impact graph state, pattern brief, and prior run history, produce `docs/holtz/recon/0h-predictions.md`.

### Predictions File Format

```markdown
# Holtz Predictions

> Generated from recon analysis. Phases 1-3 should prioritize
> high-confidence predictions first.

## Prediction 1
**Target:** `path/to/file.py::function_name`
**Predicted Issue:** {what the auditor expects to find}
**Confidence:** HIGH | MEDIUM | LOW
**Basis:** {what evidence from recon supports this prediction}
**Lens:** {which analytical lens this prediction falls under}
**Graph Support:** {relevant impact graph edges, if any — e.g., "3 `assumes` edges, risk_score 0.8"}
**Outcome:** {CONFIRMED | UNCONFIRMED — filled in after relevant phase completes}

## Prediction 2
...
```

### Prediction Generation Inputs

| Input | What it suggests |
|-------|-----------------|
| Pattern Brief | Known patterns → predict same pattern in uninspected code with similar structure |
| Impact Graph risk_score | High-risk nodes → predict bugs in areas that have produced bugs before |
| Impact Graph `assumes`/`diverges_from` edges | Semantic tensions → predict integration bugs at those seams |
| Git churn (0e) | High-churn files → predict bugs where code changes most |
| Prior run findings | Categories that recurred → predict same categories in untested areas |
| Recon observations | Architectural concerns noted during 0a-0g → predict specific failure modes |

### Confidence Levels

- **HIGH:** Multiple converging signals (e.g., high churn + known pattern + high risk_score + semantic edge)
- **MEDIUM:** Two signals or one strong signal (e.g., known pattern in similar code)
- **LOW:** Single weak signal (e.g., churn alone, or gut-level architectural concern)

### How Phases 1-3 Use Predictions

Phases 1-3 still run their full scope — no audit work is skipped. But within each phase, the auditor processes predicted areas first. High-confidence predictions get examined early, when context is freshest and before compaction pressure builds.

When a finding matches a prediction:
- The punchlist item includes `**Predicted:** Prediction {N} (confidence: {X})` as an optional field
- The prediction is marked CONFIRMED in 0h-predictions.md

When a prediction is not confirmed after the relevant phase completes:
- The prediction is marked UNCONFIRMED in 0h-predictions.md
- Not a failure — confirms the code was examined and no bug was found

### Accuracy Tracking

Appended to `docs/holtz/SUMMARY.md`:

```markdown
## Prediction Accuracy
| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 2         | 67%      |
| MEDIUM     | 5         | 2         | 40%      |
| LOW        | 4         | 0         | 0%       |
| **Total**  | **12**    | **4**     | **33%**  |
```

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Add step 0h to Phase 0. Add prediction prioritization to Phases 1-3. Add CONFIRMED/UNCONFIRMED protocol. Add Prediction Accuracy to SUMMARY.md requirements. |
| `skills/holtz/references/punchlist-format.md` | Add optional `**Predicted:**` field to item template (after Pattern, before Determinism). |
| `skills/holtz/scripts/validate_punchlist.py` | Add `Predicted` to `_field_names` tuple. No required-field check. |
| `tests/test_validate_punchlist.py` | Test Predicted field accepted when present, not required when absent, poisoning-resistant. |

### Acceptance Criteria

- [ ] SKILL.md Phase 0 includes step 0h producing `docs/holtz/recon/0h-predictions.md`
- [ ] Predictions format includes Target, Predicted Issue, Confidence, Basis, Lens, Graph Support, Outcome
- [ ] Phases 1-3 prioritize predicted areas first (documented in SKILL.md)
- [ ] Punchlist items matching predictions include `**Predicted:**` field
- [ ] Predictions file updated with CONFIRMED/UNCONFIRMED as phases complete
- [ ] SUMMARY.md includes Prediction Accuracy table
- [ ] `validate_punchlist.py` recognizes `Predicted` in `_field_names` without requiring it
- [ ] SKILL.md step 0h instructions reference all 6 input sources (pattern brief, graph risk scores, graph semantic edges, churn, prior run findings, recon observations)

### Test Cases

1. **Predicted field accepted:** Item with `**Predicted:** Prediction 3 (confidence: HIGH)` → validator passes.
2. **Predicted field not required:** Item without Predicted → validator passes.
3. **Predicted field in code fence:** `**Predicted:**` inside code fence → not treated as real field.

---

## 4. Blast Radius Analysis Protocol

**Problem:** Every fix changes the codebase's topology. The masking layer fix in run 1 was correct, but created new surface area for extraction bypass bugs found in run 2. Fixes that add layers, change interfaces, or modify data flow reshape the topology — and the auditor doesn't systematically check what the fix destabilized.

**Change:** After each fix in Phase 4, Holtz queries the impact graph to identify what code might be affected, then performs a targeted re-examination of the blast radius.

### Protocol (added to Phase 4, after Per-Fix Hardening)

```
After each fix passes reproduction test, full suite, and per-fix hardening:

1. Identify the changed function(s)/module(s)
2. Run: impact_graph.py blast_radius <changed_id> --depth 2
3. For each node in the blast radius:
   a. Read the code
   b. Check: does it still hold correct assumptions about the changed code?
   c. If an `assumes` or `diverges_from` edge exists, pay special attention
   d. If assumption violated → new punchlist item (bug/logic or design/inconsistency)
   e. If assumption holds → update edge metadata with "verified {date}"
4. Update impact graph:
   a. update_risk on fixed node: -0.1 (fix resolved, lower risk)
   b. update_risk on clean blast radius nodes: -0.05
   c. Add/update edges if fix changed relationships (new call, removed import, etc.)
   d. For architectural fixes: add `assumes` edges for new implicit contracts
5. Update STATUS.md Strategy section with blast radius findings
```

### Blast Radius Depth

- **Default: depth 2** (direct callers + their callers) for localized corrections (regex fix, edge case handling)
- **Depth 3** for architectural fixes (adding new layers, changing interfaces, modifying data flow)
- The auditor determines which category based on the nature of the fix

### Integration with Lens Registry

When blast radius analysis discovers issues at module seams, findings are tagged with the `integration` lens. If the current lens is `component` and blast radius keeps finding integration issues, this contributes to the lens-switch trigger.

### Integration with Predictive Recon

- Blast radius findings that match predictions get the `**Predicted:**` field
- Risk_score updates feed back into future predictions — nodes with rising risk after blast radius analysis become higher-confidence targets in the next run's 0h predictions

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Add blast radius protocol to Phase 4, after Per-Fix Hardening. Document depth defaults. Document risk_score update rules. |

### Acceptance Criteria

- [ ] SKILL.md Phase 4 includes blast radius analysis after per-fix hardening
- [ ] Protocol specifies: query graph → examine blast radius nodes → check assumptions → create punchlist items for violations
- [ ] Risk score update rules defined: -0.1 fixed node, -0.05 clean blast radius nodes
- [ ] Architectural fixes documented as requiring depth 3 vs default depth 2
- [ ] Assumption violations produce punchlist items
- [ ] Edge metadata updated with verification date when assumptions confirmed
- [ ] Blast radius findings tagged with appropriate lens
- [ ] Findings matching predictions get `**Predicted:**` field

### Test Cases

No additional script tests — blast radius querying is tested in Section 1's test suite. Protocol correctness verified behaviorally by running Holtz.

---

## Cross-Component Interaction Model

How the four components work together in a single run:

1. **Phase 0 (Recon):** Read lens registry, select starting lens (default: component). Reconcile impact graph against filesystem. Build initial nodes/edges. Generate predictions (0h) informed by graph risk scores, pattern brief, churn, prior history.

2. **Phases 1-3 (Audit):** Audit under current lens, prioritizing predicted areas. Add semantic edges (`assumes`, `diverges_from`) to graph as discovered. Confirm/disconfirm predictions.

3. **Phase 4 (Fix Loop):** Fix items. After each fix: hardening → blast radius query → examine neighbors → new punchlist items if assumptions violated → update graph risk scores and edge metadata.

4. **Phase 5 (Pattern Analysis):** New patterns go to both punchlist and patterns-brief. Graph edges updated with `shares_pattern`.

5. **Phase 6 (Convergence):** Per-lens convergence check. If current lens exhausted (zero findings or 3 consecutive LOWs), switch to next lens. Re-run Phases 1-3 under new lens. Continue until all lenses complete. Final cross-lens sweep. If clean, converged.

---

## Implementation Order

Bottom-up, each layer testable before the next builds on it:

1. **Knowledge Graph** (`scripts/impact_graph.py` + tests) — new infrastructure, no SKILL.md dependencies
2. **Lens Registry** (`references/lens-registry.md` + SKILL.md Phase 6 + validator) — depends on Tier 1 Strategy Journal for Active Lens tracking
3. **Predictive Recon** (SKILL.md Phase 0 step 0h + validator) — depends on graph for risk scores and pattern brief
4. **Blast Radius Analysis** (SKILL.md Phase 4 protocol) — depends on graph for blast_radius queries

Items 2 and 3 are independent of each other and can be parallelized.

## Dependencies

- **Tier 1 → Tier 2:** Strategy Journal (Active Lens field), Discovery Chain (predictions reference it), Pattern Brief (predictions draw from it)
- **Tier 3 depends on Tier 2:** Justine uses the Lens Registry to select different default lenses. Predictive Pattern Library uses the graph + pattern brief.
- **Tier 4 depends on Tier 3:** Adversarial Self-Play uses Justine + Lens Registry.

## Out of Scope

- Justine secondary auditor (Tier 3)
- Cross-project pattern transfer / PR submission (Tier 3)
- Adversarial Self-Play (Tier 4)
- Mutation-guided auditing, temporal auditing, living punchlist (Tier 4)

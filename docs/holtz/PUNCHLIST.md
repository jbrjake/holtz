# Holtz Punchlist
> Generated: 2026-03-23 | Project: holtz | Baseline: 286 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM | 1 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Items

### BH-001: README "What's inside" counts stale after Justine refactor
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:164`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 164 claims "2 skills, 2 agents, 14 reference docs, ... 286 tests across 8,200 lines" but after the Justine internal-only refactor: skills is now 1 (skills/justine/ removed), reference docs is 16 (justine-skill.md and justine-backstory.md moved into references/), and line count is ~8,308.

**Evidence:**
- `ls skills/*/SKILL.md` → only `skills/holtz/SKILL.md` (1 skill, not 2)
- `ls skills/holtz/references/*.md | wc -l` → 16 (not 14)
- `wc -l` total across scripts+hooks+tests+docs → 8,308 (not 8,200)

**Discovery Chain:** Justine refactor (bc165b2) moved files from skills/justine/ to skills/holtz/references/ → skills count decreased, reference doc count increased → README line 164 not updated

**Acceptance Criteria:**
- [ ] README "What's inside" line reflects actual counts
- [ ] test_readme_metrics_match_actual covers skills and reference doc counts (not just test count)

**Validation Command:**
```bash
grep "skills, .* agents, .* reference docs" README.md
```

### BH-002: subagent_findings_check.py docstring references legacy exit codes
**Severity:** LOW
**Category:** doc/drift
**Location:** `hooks/subagent_findings_check.py:12`
**Status:** OPEN

**Problem:** Docstring says "Uses exit 1 (warn) not exit 2 (block)" but the hook was modernized in commit 4049532 to use JSON output format. All hooks now exit 0. The docstring was not updated during the modernization.

**Evidence:** Line 12: `"Uses exit 1 (warn) not exit 2 (block) — the subagent is already done, blocking can't undo its work."` — but actual code calls `exit_ok()` and `exit_warn()` which both `sys.exit(0)`.

**Discovery Chain:** read subagent_findings_check.py during Phase 2 → docstring mentions exit codes → code uses JSON functions that exit 0 → docstring stale after modernization

**Acceptance Criteria:**
- [ ] Docstring accurately describes the modern output format
- [ ] No references to legacy exit code semantics

**Validation Command:**
```bash
grep -n "exit 1\|exit 2\|exit code" hooks/subagent_findings_check.py
```

### BH-003: impact_graph.py load() does not validate individual edge/node entries
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/impact_graph.py:50-65`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 4 (confidence: MEDIUM)
**Lens:** error-propagation

**Problem:** `load()` validates top-level structure (`nodes` is dict, `edges` is list) but does not validate individual entries. Malformed edge entries missing `source`, `target`, or `type` keys crash every method that iterates edges (`neighbors`, `blast_radius`, `add_edge`, `stats`, `prune_node`) with `KeyError`. Malformed node entries missing `id`, `file`, `type`, or `risk_score` crash `risk_hotspots`, `prune_missing`, and `drift_check`.

**Evidence:** `load()` lines 59-62 check `isinstance(nodes, dict)` and `isinstance(edges, list)` but do not validate entry contents. `neighbors()` line 153 accesses `edge["source"]` and `edge["type"]` without guards. `add_edge()` line 123 does the same for dedup.

**Discovery Chain:** global pattern heuristic (missing-edge-case-handling) flagged impact_graph.py → read load() → found top-level validation but no per-entry validation → confirmed KeyError on malformed entries

**Acceptance Criteria:**
- [ ] `load()` filters out malformed edge entries (missing source/target/type keys)
- [ ] `load()` filters out malformed node entries (missing required keys)
- [ ] Tests verify that loading a graph with malformed entries doesn't crash
- [ ] Tests verify that valid entries survive filtering alongside malformed ones

**Validation Command:**
```bash
python -m pytest tests/test_impact_graph.py -v --tb=short -k "malformed"
```

# Issue #48: 8 Audit Bugs — Fix Design

## Overview

Eight bugs found during a full Holtz adversarial audit on the tqdm project (v0.127.1). One code fix, two config fixes, five doc fixes. One upstream sahjhan UX issue filed and resolved (jbrjake/sahjhan#28, shipped in v0.13.1).

## Bug 1: Stop hook infinite loop when daemon auth fails (HIGH)

**Root cause:** `stop_hook.py:94-102` blocks when `read_cache()` returns None but daemon is alive. The daemon may reject auth (macOS `LOCAL_PEERCRED` issue, tracked as jbrjake/sahjhan#26) while remaining alive, creating an inescapable loop — each block triggers feedback, which triggers another response, which triggers the hook again.

**Fix:** Add a `_read_status_cache_file()` fallback in `stop_hook.py`. When daemon is alive but `read_cache()` returns None, read `docs/holtz/.sahjhan/status-cache.json` directly (sahjhan writes this after every `init` and `transition`, per sahjhan v0.8.0). Parse its JSON for a `state` field. If the state is in `_STOP_ALLOWED_STATES`, allow stop. If the file is missing or unreadable, **warn** instead of block — warn lets the user decide, block creates the loop.

**Files:** `enforcement/hooks/stop_hook.py`

## Bug 2: recon_complete gate checks wrong event type (MEDIUM)

**Root cause:** `transitions.toml:14` SQL checks `type='recon_finding'` (optional per-step observations) instead of `type='recon_step'` (mandatory per the skill). The skill says to record `recon_step` after each step and "additionally" record findings as `recon_finding`.

**Fix:** Change SQL from `WHERE type='recon_finding'` to `WHERE type='recon_step'`.

**Files:** `enforcement/transitions.toml`

## Bug 3: audit_complete gate uses project-relative path (MEDIUM)

**Root cause:** `transitions.toml:30` references `python skills/holtz/scripts/impact_graph.py` — a project-relative path that doesn't exist in target projects. The script lives in the plugin directory.

**Fix:** Change to `python $CLAUDE_PLUGIN_ROOT/skills/holtz/scripts/impact_graph.py`. Gate commands go through `sh -c` (they use pipes/grep), so shell expansion works. `CLAUDE_PLUGIN_ROOT` is set by Claude Code for all plugin processes. This matches the original migration plan intent (visible in `docs/superpowers/plans/2026-03-26-holtz-jsonl-migration.md:277`).

**Files:** `enforcement/transitions.toml`

## Bug 4: snapshot event fields undocumented (MEDIUM)

**Root cause:** The quick reference in `SKILL.md` has no example of the `snapshot` event. The `audit_complete` gate references `snapshot:pre_audit_edge_count` but nothing tells the auditor what key name to use or that `key` and `value` fields are required.

**Fix:** Add a `snapshot` event example to the quick reference with the exact key name the gate expects:
```
sahjhan event snapshot --field key=pre_audit_edge_count --field value=28
```
Add a comment noting that key names must match `snapshot_compare` gate references.

**Files:** `skills/holtz/SKILL.md`

## Bug 5: No active-ledger warning (LOW)

**Root cause:** The `run_start` gate has no gates, so `sahjhan transition run_start` succeeds without a ledger being created/activated first. This causes "no ledger found for template 'run'; using default ledger" warnings on every subsequent render (~20 times per audit).

**Fix:** The skill docs in `phase-recon.md` already show the correct sequence (ledger create before run_start). Add a warning note emphasizing that skipping the ledger create causes persistent render warnings. Not adding a gate — the init sequence should stay simple and the warning is cosmetic.

**Files:** `skills/holtz/references/phase-recon.md`

## Bug 6: ledger checkpoint wrong syntax (LOW)

**Root cause:** `SKILL.md:121` says `sahjhan ledger checkpoint --name pre-clear`. The `--name` parameter is the target ledger name, not the checkpoint label. The `--snapshot` parameter is the label. This was fixed upstream in sahjhan v0.13.1 (jbrjake/sahjhan#28) so `--name` now defaults to the active ledger.

**Fix:** Change to `sahjhan ledger checkpoint --snapshot pre-clear`. Also update `phase-convergence.md:11` which references `sahjhan ledger checkpoint` without specifying the snapshot label.

**Files:** `skills/holtz/SKILL.md`, `skills/holtz/references/phase-convergence.md`

## Bug 7: justine_dispatched mode field inconsistency (LOW)

**Root cause:** The quick reference shows `--field mode=full` for `justine_dispatched`, but the gate only checks `ledger_has_event event=justine_dispatched min_count=1` — it doesn't check the mode field. The skill's phase-audit docs say to record `--mode full` or `--mode skipped`. This is confusing but not blocking.

**Fix:** Add a comment in the quick reference noting that `mode` is for audit trail purposes; the gate checks presence only. No gate change needed — mode is intentionally not enforced (both full and skipped dispatches should satisfy the gate).

**Files:** `skills/holtz/SKILL.md`

## Bug 8: merge_agent_dispatched event undocumented (LOW)

**Root cause:** The `merge_complete` transition requires a `merge_agent_dispatched` event, but the skill's Step 9 procedure in `phase-merge.md` doesn't mention recording it. The auditor has to discover this from the gate error.

**Fix:** Add `sahjhan event merge_agent_dispatched` to `phase-merge.md` before the merge agent dispatch. Add it to the quick reference in `SKILL.md`.

**Files:** `skills/holtz/references/phase-merge.md`, `skills/holtz/SKILL.md`

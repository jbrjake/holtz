# Run 21: Sahjhan Integration Shakedown

**Date:** 2026-03-26
**Engine:** Sahjhan v0.1.0
**Protocol:** holtz v1.0.0 (enforcement/*.toml)
**Scope:** First enforced audit run — protocol flow validation

## Summary

Exercised the full recon → audit flow under Sahjhan enforcement. Found 7 issues (1 CRITICAL, 3 HIGH, 2 MEDIUM, 1 MEDIUM). The protocol state machine works. The gate system works. The CLI syntax and integration plumbing have gaps that need fixing before this is usable.

## What Worked

- `sahjhan init` — ledger sealed, manifest tracking, genesis block created
- `sahjhan transition run_start` — idle → recon, no issues
- `sahjhan event recon_step --field step=N --field artifact_path=...` — field recording works
- `sahjhan gate check recon_complete` — all 5 gate types evaluated correctly (files_exist, file_exists, ledger_has_event, command_succeeds)
- `sahjhan transition recon_complete` — recon → audit, gates enforced
- `sahjhan event finding --field id=BH-001 ...` — finding recording works
- `sahjhan log tail N` — ledger inspection works, hash chains visible
- `sahjhan status` — state display, set progress, next gate preview all work

## What Failed

### BH-001 (HIGH): SKILL.md CLI syntax mismatch
**Prediction 1 confirmed.** The Sahjhan quick reference in SKILL.md shows `--id BH-001 --severity HIGH` syntax but sahjhan actually uses `--field id=BH-001 --field severity=HIGH`. Every CLI example in the quick reference is wrong.

**Fix:** Rewrite the quick reference section with `--field key=value` syntax.

### BH-002 (HIGH): Transition gate cmd syntax wrong
The `command_succeeds` gate for the snapshot recording used `sahjhan event snapshot --key ... --value ...` instead of `sahjhan --config-dir enforcement event snapshot --field key=... --field value=...`. Three problems in one gate: wrong flag syntax, missing --config-dir, wrong argument format.

**Fix:** Audit all `cmd` strings in transitions.toml for correct CLI syntax.

### BH-003 (CRITICAL): Ledger chain integrity violation
After manually recording a snapshot event via CLI, then the gate's `command_succeeds` also attempted to record one, the ledger reported "chain INVALID (sequence gap: expected 10, found 9)". This may be a race condition or double-write issue.

**Investigation needed:** File issue with jbrjake/sahjhan to understand the root cause. The chain should never go invalid from normal CLI usage.

### BH-004 (HIGH): CI doesn't typecheck enforcement hooks
`.github/workflows/ci.yml` runs mypy on `skills/holtz/scripts/` and `hooks/` but not `enforcement/hooks/`. CLAUDE.md was updated but CI wasn't.

**Fix:** Add `enforcement/hooks/` to the CI mypy invocation.

### BH-005 (MEDIUM): Gate script paths not portable
Gate commands in transitions.toml use bare `python skills/holtz/scripts/...` paths. These only work when sahjhan runs from the plugin root. When run from a user's project, the paths are wrong.

**Fix:** Prefix with `${CLAUDE_PLUGIN_ROOT}` or use the sahjhan `--cwd` mechanism.

### BH-006 (MEDIUM): Tera templates never render
Every transition and event triggers a "Render warning: render error for templates/status.md.tera." The templates reference variables (`genesis.timestamp`, `run_number`, `current_state.label`) that sahjhan may not expose.

**Investigation needed:** Check what variables sahjhan's render engine provides. May need to file an issue or read the sahjhan template documentation.

### BH-007 (HIGH): install-hooks.sh doesn't create sahjhan symlink
Gate commands reference bare `sahjhan` but the vendored binary has a platform suffix. `scripts/install-hooks.sh` detects the platform but doesn't create a `sahjhan` symlink in `bin/`.

**Fix:** Add `ln -sf "$SAHJHAN_BIN" "$REPO_ROOT/bin/sahjhan"` to install-hooks.sh.

## Protocol Flow Observations

1. **The gate system is the strongest part.** Gates block precisely when conditions aren't met, with clear diagnostic messages. `sahjhan gate check <transition>` is invaluable for debugging.

2. **The CLI field syntax is unintuitive but consistent.** `--field key=value` for everything. The design spec assumed per-field flags which would have been more ergonomic. This is a documentation problem, not a functionality problem.

3. **The status command is excellent.** Shows current state, set progress, and previews next gates. This replaces STATUS.md reads.

4. **Template rendering needs work.** Either the templates need to be rewritten for sahjhan's actual render context, or sahjhan needs to document what variables are available.

## Prediction Accuracy

| # | Target | Confidence | Outcome |
|---|--------|------------|---------|
| 1 | SKILL.md CLI syntax | HIGH | **CONFIRMED** (BH-001) |
| 5 | CI mypy gap | HIGH | **CONFIRMED** (BH-004) |
| 6 | Gate script paths | MEDIUM | **CONFIRMED** (BH-005) |
| 2 | write_guard path edge case | MEDIUM | Not tested yet |
| 3 | primer.py double-record | MEDIUM | Not tested yet |
| 4 | bash_guard performance | MEDIUM | Not tested yet |
| 7 | _resolve.py arch detection | LOW | Not tested yet |
| 8 | stop_gate timeout | MEDIUM | Not tested yet |
| 9 | Integration tests incomplete | HIGH | CONFIRMED (tests only cover no-binary path) |

**Confirmed:** 4/9 predictions (44%). The three HIGH-confidence predictions all confirmed.

## Next Steps

1. Fix BH-001, BH-002, BH-004, BH-007 (the fixable items)
2. File issue for BH-003 (ledger chain integrity) with jbrjake/sahjhan
3. File issue for BH-006 (template render context) with jbrjake/sahjhan
4. Continue audit through fix loop to test remaining protocol flow

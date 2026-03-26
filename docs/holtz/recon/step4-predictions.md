# Step 4: Predictions — Sahjhan Shakedown

**Date:** 2026-03-26
**Sources:** Pattern brief, impact graph (63n/63e), Step 2 cold file inventory (14/27 = 52%), Step 1 toolchain, Step 3 risk assessment

## Predictions

| # | Target | Predicted Issue | Confidence | Basis | Lens | Outcome |
|---|--------|----------------|------------|-------|------|---------|
| 1 | `skills/holtz/SKILL.md` (Sahjhan quick ref) | CLI syntax mismatch — SKILL.md shows `--id BH-001 --severity HIGH` but sahjhan uses `--field id=BH-001 --field severity=HIGH` | **HIGH** | Already confirmed during shakedown: `--step` rejected, `--field step=1` works | public-contract | |
| 2 | `enforcement/hooks/write_guard.py` | Path resolution edge case — absolute vs relative paths not consistently handled across all managed path entries | **MEDIUM** | Cold file (never audited), security-critical path. Bootstrap hook already had a path traversal bug fixed during implementation | security | |
| 3 | `enforcement/hooks/primer.py` | context_reset event recorded even when no active run exists, or double-recorded on rapid /clear cycles | **MEDIUM** | Cold file. Primer checks for data_dir existence but doesn't verify ledger integrity before recording events | error-propagation | |
| 4 | `enforcement/hooks/bash_guard.py` | manifest verify called on every Bash command even for non-file operations (e.g., `ls`, `git status`), wasting 5+ seconds per command | **MEDIUM** | Cold file. No early-exit for read-only commands. Performance impact on audit sessions | resource-lifecycle | |
| 5 | `.github/workflows/ci.yml` | mypy not running on enforcement/hooks/, type errors could ship | **HIGH** | Step 1 found this gap. CLAUDE.md was updated but CI wasn't | contract | |
| 6 | `enforcement/transitions.toml` | Gate conditions reference scripts that may not exist on user machines (e.g., `python skills/holtz/scripts/validate_punchlist.py`) — needs CLAUDE_PLUGIN_ROOT | **MEDIUM** | Transitions use bare `python` paths, not `${CLAUDE_PLUGIN_ROOT}` prefixed paths. Gates will fail when run by sahjhan from a user project | data-flow | |
| 7 | `enforcement/hooks/_resolve.py` | Platform detection fails on unusual architectures (e.g., x86_64 macOS via Rosetta reports arm64) | **LOW** | Cold file. Standard platform detection pattern but untested edge case | integration | |
| 8 | `enforcement/hooks/stop_gate.py` | Stop gate may block indefinitely if sahjhan binary crashes — no timeout on the subprocess.run call for status check | **MEDIUM** | Has timeout=5 but no handling for binary not being executable (chmod issue after vendor) | error-propagation | |
| 9 | `tests/test_sahjhan_integration.py` | Tests only verify hooks without active sahjhan run — no tests verify hook behavior WITH an initialized ledger | **HIGH** | All current tests pass because no binary/no data_dir = allow. The enforcement path is untested | contract | |

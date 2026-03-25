# 0d: Lint Results

## ruff

**3 errors** in `scripts/generate-changelog.py` (utility script, not core Holtz source):

1. **F541** `scripts/generate-changelog.py:117` — f-string without placeholders (`f""`)
2. **SIM108** `scripts/generate-changelog.py:159` — if/else block could be ternary
3. **ANN201** `scripts/generate-changelog.py:169` — missing return type on `main()`

**Core source (scripts/, hooks/):** clean.

## mypy

**0 errors.** All 13 source files pass type checking.

## Notes
- ruff errors are in a dev utility script, not in the plugin's runtime code
- These errors exist because `scripts/generate-changelog.py` was added recently and may not have gone through full lint
- The ruff config covers `skills/holtz/scripts`, `tests`, `hooks` — but `scripts/` (top-level) may or may not be in scope depending on path matching

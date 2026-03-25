---
name: dead-code-latent-path
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/logic, design/maintenance]
---

# Dead Code Latent Path

## Description

Code that is currently unreachable but becomes reachable under deployment changes, configuration changes, feature flag flips, or environmental differences. Unlike benign dead code (unused utility functions), latent paths contain logic that will execute incorrectly when activated because it was never maintained, tested, or even known to exist.

The canonical example: Knight Capital Group, August 2012. A deployment repurposed an old feature flag that activated decade-old order-routing code. The dead code executed, generating $440 million in erroneous trades in 45 minutes. The company was effectively destroyed.

Latent paths arise from: stale feature flags with both branches still in code, commented-out code that gets uncommented, fallback paths never exercised in production, old API versions kept "just in case," and migration code that was supposed to be temporary.

10-30% of a typical codebase is dead code, per industry analysis. Most is harmless. The dangerous subset is code that LOOKS intentional, sits behind a toggle, and has rotted semantically while the rest of the system evolved around it.

## Detection Heuristic

### Grep-based scan

```bash
# Feature flags with both branches — potential latent path
grep -rnP '(if|else)\s+.*\b(feature_flag|flag|toggle|experiment|ENABLE_|DISABLE_|USE_OLD|USE_NEW|LEGACY)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Stale feature flags — defined but potentially never cleaned up
grep -rnP '(FEATURE_|FLAG_|TOGGLE_|EXPERIMENT_)\w+\s*=' --include='*.py' --include='*.js' --include='*.go' . | sort -t= -k1 | head -30
```

```bash
# Fallback/legacy paths
grep -rnP '(fallback|legacy|deprecated|old_|v1_|_backup|_compat)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Unreachable code after return/raise/break
grep -rnP '^\s*(return|raise|break|continue)\s' --include='*.py' -A 1 . | grep -P '^\s+\w' | grep -v '^\s*(#|$|except|finally|else)'
```

### Manual triage

1. For each feature flag: are both branches maintained and tested? When was the flag last toggled?
2. For fallback/legacy code: is it tested? Does it use current APIs and data formats?
3. For commented-out code: does it reference current function signatures and data structures?
4. For code after unconditional return/raise: is it truly dead, or is it reached via exception handlers?

### LLM-based structured check

> "Identify all feature flags, toggle points, and conditional paths that select between 'old' and 'new' behavior. For each: are both paths tested? Is the 'inactive' path maintained — does it use current APIs, data formats, and interfaces? Identify code after unconditional return/raise/break statements. Identify fallback paths — are they exercised in any test? Flag: untested branches behind toggles, unmaintained fallback paths, and code referencing stale interfaces."

## Indicators

- Feature flags older than 6 months with both branches in code
- Functions or modules with "legacy," "old," "deprecated," "v1," "compat" in the name that are still importable
- Code coverage reports showing 0% coverage on entire branches that aren't marked as dead
- Commented-out code blocks longer than 10 lines
- `if False:` or `if 0:` blocks (intentionally disabled but kept)
- Config flags with no owner and no expiration date

## Example

### Before (buggy)

```python
# This flag was added in 2021 for a gradual rollout. The rollout completed in 2022.
# Both branches remain. The old path references APIs that have since changed.
USE_NEW_PRICING = os.environ.get("USE_NEW_PRICING", "true") == "true"

def calculate_price(order):
    if USE_NEW_PRICING:
        return new_pricing_engine.compute(order)
    else:
        # This path hasn't been touched since 2021. It calls an API that now
        # returns a different response format. If the flag is ever set to false
        # (incident rollback, config typo, new environment missing the var),
        # this will either crash or silently compute wrong prices.
        legacy_rate = old_pricing_api.get_rate(order.sku)  # API response changed in 2023
        return legacy_rate * order.quantity  # Missing tax calculation added in 2022
```

### After (fixed)

```python
# Flag removed. Old path deleted. One path, always tested.
def calculate_price(order):
    return new_pricing_engine.compute(order)

# If rollback capability is needed, use version control — not dead code in production.
```

## Related Patterns

- [doc-spec-drift](doc-spec-drift.md) — latent code drifts from current specs the same way docs drift
- [incomplete-layer-isolation](incomplete-layer-isolation.md) — latent paths that bypass current abstraction layers
- [missing-edge-case-handling](missing-edge-case-handling.md) — latent paths are untested edge cases waiting to activate

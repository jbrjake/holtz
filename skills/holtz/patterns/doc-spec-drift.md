---
name: doc-spec-drift
version: 1
discovered: 2026-03-19
languages: []
categories: [doc/drift, design/inconsistency]
---

# Doc-Spec Drift

## Description

Changes made in one specification, documentation, or configuration file are not propagated to related files. Over time, specs, READMEs, inline docstrings, API docs, config examples, and the actual code diverge. Users and developers make decisions based on stale documentation, leading to misconfigured deployments, incorrect API usage, and wasted debugging time.

This pattern is language-agnostic and affects any project with documentation. It is especially common in projects where documentation lives in separate files from the code it describes, and where there is no automated check for consistency.

## Detection Heuristic

### Grep-based scan

```bash
# Find documented defaults/config values in docs
grep -rnP '(default|defaults to|set to|configured as|value is)\s*[:=]?\s*[\x27"`]?\w+' --include='*.md' --include='*.rst' --include='*.txt' .
```

```bash
# Find actual defaults in code — compare with doc values
grep -rnP '(DEFAULT|default)\w*\s*=\s*' --include='*.py' --include='*.js' --include='*.ts' --include='*.go' --include='*.java' .
```

```bash
# Find function/method signatures in docs vs code
grep -rnP '^\s*def\s+\w+\(' --include='*.py' .
grep -rnP '`\w+\([^)]*\)`' --include='*.md' .
```

### Manual triage

1. For each documented value, API signature, or behavioral claim: does the code match?
2. For each code feature: is it documented? Is the documentation current?
3. Check version numbers, parameter names, return types, error codes, and configuration keys specifically.

### LLM-based structured check

> "For each documented behavior, API signature, default value, or configuration option: does the code implement it as described? For each code feature, public function, or configuration key: is it documented, and does the documentation match the current implementation? List all divergences with file locations."

## Indicators

- Documentation references function signatures, parameters, or return values that differ from the code
- README describes a CLI flag or config key that has been renamed or removed
- Inline docstrings describe behavior that the function no longer implements
- Example code in docs uses an old API that has been updated
- Version numbers in docs do not match the release
- Changelog does not mention recent breaking changes
- Multiple documentation files describe the same feature with conflicting details

## Example

### Before (drifted)

```markdown
<!-- docs/configuration.md -->
## Configuration

Set the processing mode in your config file:

- `mode`: Processing mode. Options: "fast", "balanced", "thorough". Default: "balanced".
- `max_retries`: Maximum retry attempts. Default: 3.
- `timeout`: Request timeout in seconds. Default: 30.
```

```python
# config_loader.py — code has diverged from docs

DEFAULT_MODE = "standard"       # doc says "balanced", code says "standard"
MAX_RETRIES = 5                 # doc says 3, code says 5
DEFAULT_TIMEOUT = 60            # doc says 30, code says 60
VALID_MODES = ["standard", "careful", "exhaustive"]  # doc says "fast", "balanced", "thorough"

def load_config(config_dict):
    mode = config_dict.get("mode", DEFAULT_MODE)
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")  # users following docs get an error
    return {"mode": mode, "retries": config_dict.get("max_retries", MAX_RETRIES)}
```

### After (aligned)

```markdown
<!-- docs/configuration.md — updated to match code -->
## Configuration

Set the processing mode in your config file:

- `mode`: Processing mode. Options: "standard", "careful", "exhaustive". Default: "standard".
- `max_retries`: Maximum retry attempts. Default: 5.
- `timeout`: Request timeout in seconds. Default: 60.
```

```python
# config_loader.py — unchanged (code was correct, docs were stale)

DEFAULT_MODE = "standard"
MAX_RETRIES = 5
DEFAULT_TIMEOUT = 60
VALID_MODES = ["standard", "careful", "exhaustive"]
```

## Related Patterns

- [incomplete-layer-isolation](incomplete-layer-isolation.md) — documentation that claims a layer is "the single access point" while bypasses exist is a form of doc-spec drift
- [dual-parser-divergence](dual-parser-divergence.md) — when specs diverge, implementations built against different spec versions will also diverge

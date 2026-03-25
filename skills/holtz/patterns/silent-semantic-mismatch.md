---
name: silent-semantic-mismatch
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go]
categories: [bug/logic, bug/type-system]
---

# Silent Semantic Mismatch

## Description

The programming language does something technically legal but semantically wrong, and does it silently. The code runs without errors but produces incorrect results because the developer's intent diverges from the language's actual behavior.

This is a family of bugs unified by one property: the language cooperates with the mistake.

**Implicit type coercion:** JS's `"5" + 3 === "53"` but `"5" - 3 === 2`. Python's `True + True === 2`. Comparisons between incompatible types that happen to succeed.

**Identity vs. equality:** Python's `is` vs `==` — works for small integers (interned) but fails for larger values. JS's `==` vs `===` — `0 == "" === true`.

**Floating point comparison:** `0.1 + 0.2 !== 0.3` in every IEEE 754 language. Using `==` on floats.

**Mutable default argument:** Python's `def f(items=[])` — the list is shared across all calls. Every Python dev hits this once; some hit it twice.

**Loop variable capture:** Closures in a loop capture the variable by reference; all closures see the final value. `[lambda: i for i in range(3)]` — all return 2. Go fixed this in 1.22; Python and JS still have it.

**Shallow copy mutation:** `copy = original[:]` or `{...obj}` — nested objects are still shared. Mutations to nested elements affect the original.

**Boolean blindness / stringly-typed interface:** `render(True, False, True)` — what do the bools mean? `process(status="active")` — is "Active" valid? "ACTIVE"? Using bare primitives for domain concepts.

## Detection Heuristic

### Grep-based scan

```bash
# Python: 'is' comparison with non-singleton (should be ==)
grep -rnP '\bis\b\s+(?!None\b|True\b|False\b|not\b)' --include='*.py' .
```

```bash
# Python: mutable default arguments
grep -rnP 'def\s+\w+\(.*=\s*(\[\]|\{\}|set\(\))' --include='*.py' .
```

```bash
# JS: loose equality
grep -rnP '[^=!]==[^=]' --include='*.js' --include='*.ts' .
```

```bash
# Float equality comparison
grep -rnP '==\s*(0\.\d|float|parseFloat|\d+\.\d)' --include='*.py' --include='*.js' .
```

```bash
# Python: lambda/closure in loop
grep -rnP 'for\s+\w+\s+in\s+.*:\s*$' --include='*.py' -A 5 . | grep -P '(lambda|def\s+\w+\()'
```

### Manual triage

1. For comparisons: is identity (`is`, `===`) vs equality (`==`) intentional and correct?
2. For default arguments: are any defaults mutable objects?
3. For closures in loops: does the closure capture a loop variable? Is there a `default=` parameter trick or immediate binding?
4. For shallow copies: are nested objects shared? Are they subsequently mutated?
5. For string/bool parameters: could a typo or case mismatch cause silent wrong behavior?

### LLM-based structured check

> "For each comparison: is identity vs equality correct for the types involved? For each default argument: is any default a mutable object? For each closure created in a loop: does it capture the loop variable by reference? For each copy operation: is it deep enough for the mutations that follow? For each string-typed parameter that selects behavior: is there validation against allowed values? Flag all mismatches."

## Indicators

- `is` comparison returning different results for small vs large integers in Python
- `==` instead of `===` in JavaScript
- `def f(x, cache={})` in Python
- `[lambda: i for i in range(n)]` where all lambdas return the same value
- `copy = original[:]` followed by mutation of nested elements
- Functions with 3+ boolean parameters
- String-typed status/mode/type fields without enum validation

## Example

### Before (buggy)

```python
def make_handlers(names):
    handlers = []
    for name in names:
        handlers.append(lambda: print(f"Handling {name}"))  # Captures 'name' by ref
    return handlers

# All handlers print the LAST name
for h in make_handlers(["alice", "bob", "carol"]):
    h()  # "Handling carol" x 3
```

### After (fixed)

```python
def make_handlers(names):
    handlers = []
    for name in names:
        handlers.append(lambda n=name: print(f"Handling {n}"))  # Default arg binds immediately
    return handlers

for h in make_handlers(["alice", "bob", "carol"]):
    h()  # "Handling alice", "Handling bob", "Handling carol"
```

## Related Patterns

- [missing-edge-case-handling](missing-edge-case-handling.md) — type confusion is an edge case the language hides
- [dual-parser-divergence](dual-parser-divergence.md) — two modules using `is` vs `==` for the same type diverge silently
- [regex-newline-leak](regex-newline-leak.md) — `\s` matching `\n` is another silent semantic mismatch

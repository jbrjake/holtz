---
name: error-destruction
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/error-handling]
---

# Error Destruction

## Description

Errors are generated but destroyed before reaching anyone who can act on them. The system fails but nobody knows, or the diagnostic information is stripped beyond usefulness.

Four variants, all with the same effect — turning debuggable failures into mysteries:

**Exception swallowing:** Empty catch blocks (`except: pass`, `catch(e) {}`). The error vanishes entirely. SonarQube classifies this as BLOCKER (S108). Called "the most diabolical Python antipattern."

**Log-and-throw:** Every layer catches, logs, and re-throws. A single exception produces N duplicate log entries across N layers, drowning signal in noise while adding zero information.

**Destructive wrapping:** Catching an exception and re-throwing a new one without preserving the original as the cause. `catch (IOException e) { throw new AppError("failed"); }` — the original stack trace and context are permanently lost.

**Unchecked error return:** A function returns an error value that the caller ignores. Epidemic in Go (`err` routinely discarded), common in C (`errno` unchecked), and subtle in Python (functions that return `None` on failure instead of raising). CWE-252 covers this class.

## Detection Heuristic

### Grep-based scan

```bash
# Python: bare except with pass/continue
grep -rnP 'except.*:\s*$' --include='*.py' -A 1 . | grep -P '^\s+(pass|continue)\s*$'
```

```bash
# Python: catch-and-raise without chaining (missing 'from')
grep -rnP 'except\s+\w+.*:' --include='*.py' -A 3 . | grep -P 'raise\s+\w+\(' | grep -v 'from\s'
```

```bash
# Go: error return explicitly ignored
grep -rnP '\b\w+,\s*_\s*:?=\s*' --include='*.go' . | grep -v 'test'
```

```bash
# JS: empty catch blocks
grep -rnP 'catch\s*\([^)]*\)\s*\{' --include='*.js' --include='*.ts' -A 1 . | grep -P '^\s*\}'
```

```bash
# Python: log-and-raise (catch, log, re-raise — usually indicates layer spam)
grep -rnP 'except\s+\w+' --include='*.py' -A 3 . | grep -P 'logging\.(error|exception)' -A 1 | grep 'raise'
```

### Manual triage

1. For catch blocks: is the error communicated to the caller, logged with context, or silently dropped?
2. For re-throws: is the original exception preserved as the cause (`raise X from e` / `Throwable.initCause`)?
3. For Go `_` assignments: is the discarded value an error? Is ignoring it safe?
4. For log-and-throw: does the logging at this layer add information not available at the final handler?

### LLM-based structured check

> "For each catch/except/recover block: what happens to the error? Is it swallowed, re-thrown with cause preserved, logged then re-thrown (adding what context?), or converted to a return value? For each function that returns an error: do all callers check it? Flag: empty catch blocks, re-throws without cause chaining, and unchecked error returns."

## Indicators

- `except: pass` or `except Exception: pass` in Python
- `catch (e) {}` or `catch (e) { console.log(e) }` in JS (logged but not propagated)
- `_, err = foo(); _ = err` or `foo()` discarding error return in Go
- Exception chains with no root cause: `Caused by: null` in stack traces
- Same exception logged at 3+ layers in log output
- `raise CustomError("something failed")` without `from original_error`
- Production bugs where "we saw the error in logs but couldn't trace it to source"

## Example

### Before (buggy)

```python
def process_order(order_id):
    try:
        validate(order_id)
    except ValidationError:
        pass  # Swallowed — processing continues with invalid order

    try:
        result = charge_payment(order_id)
    except PaymentError as e:
        logger.error(f"Payment failed: {e}")   # Logged...
        raise PaymentError("Payment failed")   # ...and re-raised WITHOUT original cause
                                                # Original stack trace is gone

    try:
        send_confirmation(order_id)
    except Exception:
        return None  # Returns None instead of raising — caller gets silent failure
```

### After (fixed)

```python
def process_order(order_id):
    validate(order_id)  # Let ValidationError propagate — callers should handle it

    try:
        result = charge_payment(order_id)
    except PaymentError as e:
        raise ProcessingError(f"Payment failed for order {order_id}") from e
        # 'from e' preserves the full chain; log at the top-level handler, not here

    try:
        send_confirmation(order_id)
    except NotificationError as e:
        logger.warning(f"Confirmation email failed for {order_id}: {e}")
        # Intentional: non-critical, logged with context, order still succeeded
```

## Related Patterns

- [missing-edge-case-handling](missing-edge-case-handling.md) — swallowed errors are missing edge cases in the caller
- [resource-leak](resource-leak.md) — swallowed errors in cleanup code mask resource leaks
- [uncontrolled-amplification](uncontrolled-amplification.md) — silent failures let invalid state propagate until it cascades

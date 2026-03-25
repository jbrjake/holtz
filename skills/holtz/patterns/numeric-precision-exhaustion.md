---
name: numeric-precision-exhaustion
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, rust, java, swift, c, cpp]
categories: [bug/logic, bug/numeric]
---

# Numeric Precision Exhaustion

## Description

Counters, accumulators, or timestamps stored in types whose precision degrades over time or whose range is exhausted under sustained operation. The system works correctly for hours or days, then silently produces wrong results without any error.

Three sub-classes:

**Float accumulation:** A float32 counter incremented per frame/tick loses precision after 2^24 increments (~3.1 days at 60fps, ~4.7 hours at 1000 ticks/sec). Consecutive values become indistinguishable — hash seeds repeat, animation phases alias, noise functions degenerate.

**Integer overflow on derived values:** Arithmetic on large constants (e.g., dividing by `INT32_MAX`) that overflows or truncates on certain platforms, producing zero or negative results.

**Divisor collapse:** LOD calculations, mipmap dimensions, or downsampled sizes computed via bit-shift or integer division that can reach zero — producing zero-dimension textures, division-by-zero, or infinite loops.

The unifying root cause: the developer's mental model of the numeric type's range exceeds its actual range under sustained operation. The code works in testing (short runs) and fails in production (long runs).

## Detection Heuristic

### Grep-based scan

```bash
# Float frame/tick counters (accumulation risk)
grep -rnP '(frameCount|tickCount|elapsed|accumulator|totalTime).*\b(Float|float|f32|float32)\b' .
grep -rnP '\b(Float|float|f32)\b.*(frameCount|tickCount|elapsed|accumulator)' .
```

```bash
# Integer max/min constants in arithmetic (overflow risk)
grep -rnP '(Int32\.max|INT32_MAX|Int32\.min|INT_MAX|INT_MIN|Integer\.MAX_VALUE)' .
```

```bash
# Bit-shift or division that could reach zero dimensions
grep -rnP '(>>|/\s*[248]|divisor|mipLevel)' . | grep -iP '(width|height|dimension|size|resolution)'
```

```bash
# Monotonically incrementing counters without modular wrap
grep -rnP '(count|counter|tick|frame)\s*(\+\+|\+=\s*1)' --include='*.swift' --include='*.cpp' --include='*.c' --include='*.rs' .
```

### Manual triage

1. For float counters: what is the type? How fast does it increment? At what value does precision degrade (2^24 for float32, 2^53 for float64)?
2. For integer arithmetic: can any intermediate value overflow the type's range on the target platform?
3. For dimension calculations: can the result ever be zero? Is there a `max(1, ...)` floor?
4. For accumulators: is there a periodic reset, modular wrap, or double-precision upgrade?

### LLM-based structured check

> "For each numeric counter, accumulator, or timer: what type stores it? How fast does it increment? How long until the type's precision or range is exhausted? For each dimension calculation using division or bit-shift: can the result reach zero? For each arithmetic expression involving platform-specific constants (INT_MAX, INT32_MAX): can it overflow? Flag all cases where the numeric type's practical range is shorter than the expected operation lifetime."

## Indicators

- Float-typed counters that increment monotonically without reset or modular wrap
- Arithmetic involving platform-specific integer limits
- Dimension calculations without a `max(1, ...)` floor
- Bugs that only manifest after extended uptime (hours/days)
- Visual artifacts or behavioral changes that appear gradually
- Frame counter or elapsed time used as a hash seed, noise input, or animation phase

## Example

### Before (buggy)

```c
// render.c — frame counter as float32
float frame_count = 0.0f;

void on_frame() {
    frame_count += 1.0f;  // After 2^24 frames (~3.1 days at 60fps),
                           // frame_count and frame_count+1 are the same float value.
                           // Noise seeds repeat, animation phases freeze.

    float noise_seed = fmodf(frame_count * 0.01f, 1.0f);
    float phase = sinf(frame_count * 0.1f);
    // Both degenerate after ~3 days of continuous operation.
}
```

### After (fixed)

```c
// render.c — frame counter as uint64 (won't overflow for ~9.7 billion years at 60fps)
uint64_t frame_count = 0;

void on_frame() {
    frame_count += 1;

    // Cast to double only for floating-point math — double has 2^53 precision
    double noise_seed = fmod((double)frame_count * 0.01, 1.0);
    double phase = sin((double)frame_count * 0.1);
}
```

## Related Patterns

- [silent-semantic-mismatch](silent-semantic-mismatch.md) — float equality comparison is a related but distinct numeric trap
- [missing-edge-case-handling](missing-edge-case-handling.md) — zero-dimension from divisor collapse is an edge case in LOD math

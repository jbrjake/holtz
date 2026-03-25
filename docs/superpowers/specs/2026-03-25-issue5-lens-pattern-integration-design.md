# Issue #5: Lens & Pattern Integration Design

**Date:** 2026-03-25
**Issue:** [#5 — New lenses, patterns, and scope changes to close adversarial-review blind spots](https://github.com/jbrjake/holtz/issues/5)
**Approach:** Fold lenses into existing entries, add 2 selective patterns, integrate cold file sweep into recon

## Problem

A cross-analysis of a full adversarial bug review vs a Holtz audit on the same codebase (~62 Swift files, ~17k lines) found only 7% overlap. 34 adversarial-only findings cluster into bug classes Holtz currently has no systematic way to detect. Root causes: scope limitation (18 findings in unchanged files), missing analytical perspectives (GPU lifecycle, RT constraints), and missing mechanical detection patterns.

## Design Constraints

- No new lenses (13 stays at 13) — each new lens adds a full convergence iteration
- Minimal new patterns (14 to 16) — each pattern inflates the compact brief read by every subagent
- No new phases or steps — cold file coverage integrates into existing recon
- Token budget increase under 1% of a typical run

## Section 1: Lens Extensions

Four existing lenses receive targeted additions (2-4 lines each). No structural changes to the registry format.

### 1.1 `resource-lifecycle` — Cross-Domain Compute Extension

**Add to entry point:**

> For heterogeneous compute systems (CPU-GPU, CPU-FPGA, host-device): trace each shared buffer/texture from creation, to format, to host writes, to device reads, to device writes, to host reads. Check format agreement between domains (e.g., host data type vs device buffer format, `MemoryLayout.size` vs `.stride`, struct alignment padding). Check synchronization between domains (fences, completion handlers, triple-buffering). Check reset completeness — does `reset()` reinitialize ALL mutable resources?

**Add failure mode:**

> Two compute domains disagree about buffer format, size, ownership, or timing — data corruption that compiles and runs but produces garbage or races.

**Coverage:** 7 findings (texture format mismatch, buffer cursor overflow, CPU-GPU race on shared buffer, stale texture after reset, struct alignment padding, deposit buffer lifecycle, redundant command queue).

### 1.2 `concurrency` — Real-Time Constraints Extension

**Add to audit priorities:**

> Real-time thread safety: code on deadline threads (audio callbacks, render loops, interrupt handlers, game tick functions) must not perform heap allocation, lock acquisition, blocking waits, or operations with non-constant-time overhead. These are correctness issues under RT constraints even when properly synchronized.

**Add to entry point:**

> Identify all real-time entry points (audio tap callbacks, render delegate methods, display link callbacks, interrupt handlers). Trace every code path reachable from each. Flag any operation that is not O(1)-with-bounded-constant.

**Coverage:** 4 findings (delegate data races, reference-counting overhead on audio thread, semaphore+Task deadlock).

### 1.3 `data-flow` — Cross-Language Boundary Extension

**Add to entry point:**

> When data crosses a language boundary (host code to shader, application to SQL, code to template), trace BOTH sides. Check: (a) all fields written by sender are read by receiver, (b) all fields read by receiver are written by sender, (c) division/normalize/log operations on the receiving side are guarded for zero/negative/NaN inputs.

**Coverage:** 4 findings (unused uniforms, zoom==0 division, normalize(zero)=NaN, particle NaN in shader).

### 1.4 `contract` — Escape-Hatch Verification Extension

**Add to audit priorities:**

> Thread-safety escape hatches: for each `@unchecked Sendable` (Swift), `unsafe impl Send` (Rust), or equivalent annotation that opts out of the language's concurrency safety checks, verify all mutable stored properties are protected by synchronization. If not, the concurrency contract is violated.

**Coverage:** Reinforces PAT-006 fold (below) and the concurrency lens RT extension.

## Section 2: Pattern Folds into `concurrency-violation`

The existing `concurrency-violation` pattern already documents a family of variants (data races, TOCTOU, priority inversion, ABA, blocked-thread exhaustion). Two new variants fit naturally.

### 2.1 New Variant: Real-Time Constraint Violation

**Add to Description variant list:**

> **Real-time constraint violation:** Code on hard-deadline threads (audio callbacks, render loops, interrupt handlers, game tick functions) that is correctly synchronized but violates latency guarantees by performing: heap allocation (object creation, buffer/array resize, string building), lock or semaphore acquisition, blocking calls (completion waits, synchronous dispatch), or triggering non-trivial language-runtime bookkeeping. The code is thread-safe but not RT-safe.

**Add detection heuristics:**

```bash
# Weak reference usage in callback/handler contexts (any language)
grep -rnP '(weak|WeakRef|weak_ptr)' --include='*.swift' --include='*.ts' --include='*.cpp' --include='*.rs' . | grep -iP 'callback|handler|render|audio|tick'

# Semaphore or lock near async/await (deadlock on RT thread)
grep -rlP '(Semaphore|semaphore|Mutex|mutex)' . | xargs grep -lP '(async|await|Task|Future|Promise)'

# Unmanaged/unsafe pointer access in callback contexts
grep -rnP '(Unmanaged|UnsafePointer|unsafe\s*\{|raw pointer)' . | grep -iP 'callback|handler|audio|render'
```

**Add indicators:**

- Callbacks or handlers that allocate objects, grow containers, or build strings
- Lock acquisition inside a function called from a deadline thread
- Blocking waits in render or audio paths
- Intermittent audio glitches or frame drops under load (classic symptom)

### 2.2 New Variant: Lying Concurrency Escape Hatch

**Add to Description variant list:**

> **Lying escape hatch:** Types annotated to opt out of the language's concurrency safety checks but whose implementation doesn't uphold the contract. The annotation promises thread-safety; mutable stored properties without synchronization break that promise.

**Add detection heuristics:**

```bash
# Swift
grep -rn "@unchecked Sendable" --include='*.swift' .

# Rust
grep -rn "unsafe impl Send\|unsafe impl Sync" --include='*.rs' .

# Java
grep -rn "@SuppressWarnings.*thread-safety" --include='*.java' .

# For each match: check type body for mutable fields without synchronization
```

**Add indicator:**

- Type with a concurrency escape-hatch annotation containing mutable fields with no lock, atomic, or actor isolation in scope.

**Add to Related Patterns:**

- `resource-leak` — RT violations from per-frame resource allocation are also resource lifecycle bugs

**Line delta:** ~40-50 lines added to `concurrency-violation.md`.

## Section 3: New Patterns

Two new standalone pattern files following the existing format.

### 3.1 `cross-language-dead-interface`

**File:** `skills/holtz/patterns/cross-language-dead-interface.md`

**Description:** Fields, uniforms, bindings, or parameters written in one language and intended to be consumed in another (host code to shader, application to SQL/template, frontend to backend DTO) where the receiving side never reads them — or vice versa. The sending side computes and transmits data every cycle; the receiving side ignores it. A feature silently stops working, or compute is wasted indefinitely.

Distinct from `dead-code-latent-path` (unreachable code behind toggles within one language) and `dual-parser-divergence` (two parsers for the same format). This pattern spans a language boundary where the compiler cannot see both sides.

**Detection heuristic:**

```bash
# Find struct/class fields used in cross-language data transfer
grep -rnP '(Uniforms|Params|Constants|Bindings)\b' --include='*.swift' --include='*.cpp' --include='*.rs' --include='*.py' .

# Generic: find setBytes/setBuffer/bind/uniform calls, extract the data type,
# check the receiving file for field-level reads
grep -rnP '(setBytes|setBuffer|glUniform|bind|uniform\s+\w+)' .
```

**Indicators:**

- Struct fields computed every frame/request but never referenced in the corresponding shader/query/template
- Shader/query reads a field the host side never populates (undefined data consumed silently)
- Rename on one side not propagated to the other (no compiler error across the boundary)
- Performance cost: unnecessary computation and data transfer every cycle

**Related patterns:** `dead-code-latent-path`, `doc-spec-drift`, `dual-parser-divergence`

**Coverage:** 2 findings (unused uniform fields computed and uploaded every frame).

### 3.2 `numeric-precision-exhaustion`

**File:** `skills/holtz/patterns/numeric-precision-exhaustion.md`

**Description:** Counters, accumulators, or timestamps stored in types whose precision degrades over time or whose range is exhausted under sustained operation. The system works correctly for hours or days, then silently produces wrong results without any error.

Three sub-classes:

1. **Float accumulation:** A float32 counter incremented per frame/tick loses precision after 2^24 increments (~3.1 days at 60fps, ~4.7 hours at 1000 ticks/sec). Consecutive values become indistinguishable — hash seeds repeat, animation phases alias, noise functions degenerate.
2. **Integer overflow on derived values:** Arithmetic on large constants (e.g., dividing by `INT32_MAX`) that overflows or truncates on certain platforms, producing zero or negative results.
3. **Divisor collapse:** LOD calculations, mipmap dimensions, or downsampled sizes computed via bit-shift or integer division that can reach zero — producing zero-dimension textures, division-by-zero, or infinite loops.

**Detection heuristic:**

```bash
# Float frame/tick counters (accumulation risk)
grep -rnP '(frameCount|tickCount|elapsed|accumulator|totalTime).*\b(Float|float|f32|float32)\b' .
grep -rnP '\b(Float|float|f32)\b.*(frameCount|tickCount|elapsed|accumulator)' .

# Integer max/min constants in arithmetic (overflow risk)
grep -rnP '(Int32\.max|INT32_MAX|Int32\.min|INT_MAX|INT_MIN)' .

# Bit-shift or division that could reach zero dimensions
grep -rnP '(>>|/\s*[248]|divisor|mipLevel)' . | grep -iP '(width|height|dimension|size|resolution)'
```

**Indicators:**

- Float-typed counters that increment monotonically without reset or modular wrap
- Arithmetic involving platform-specific integer limits
- Dimension calculations without a `max(1, ...)` floor
- Bugs that only manifest after extended uptime (hours/days)
- Visual artifacts or behavioral changes that appear gradually

**Related patterns:** `silent-semantic-mismatch`, `missing-edge-case-handling`

**Coverage:** 3 findings (float frameCount precision loss, integer overflow, LOD zero-dimension).

## Section 4: Cold File Sweep (Recon-Integrated)

No new phase. Coverage tracking integrates into existing recon and prediction machinery.

### 4.1 Changes to Step 2 (Code Signals)

Add a coverage scan substep after the existing churn analysis:

1. List all source files in the project
2. Read `docs/holtz/STATUS.md` for files audited in prior runs
3. Compute `cold_file_ratio = files_never_audited / total_source_files`
4. Write cold file inventory to `docs/holtz/recon/step2-cold-files.md`: list of never-audited files sorted by proximity to composition root

**Line delta:** ~5 lines added to Step 2 procedure.

### 4.2 Changes to Step 4 (Predictions)

Add cold files as a seventh prediction input source (alongside pattern brief, impact graph risk scores, impact graph edges, git churn, prior run findings, recon observations):

> Cold file inventory: files with zero prior audit coverage. When `cold_file_ratio` exceeds 40%, add at least 3 cold files to predictions as MEDIUM-confidence targets with basis "never audited — unknown risk." Prioritize cold files closest to entry points or with the most inbound edges in the impact graph.

Cold files enter the normal prediction-to-audit-priority pipeline. No special phase — they compete through the same mechanism as everything else, with a guaranteed floor when coverage is low.

**Line delta:** ~3 lines added to Step 4 procedure.

### 4.3 Changes to STATUS.md Format

Add a Cold File Coverage section:

```markdown
## Cold File Coverage
| Metric | Value |
|--------|-------|
| Total source files | {n} |
| Files audited (any run) | {n} |
| Cold file ratio | {n}% |
| Cold files audited this run | {n} |
```

**Line delta:** ~6 lines added to status file format reference.

### 4.4 What This Does NOT Do

- No new phase or step number
- No separate "cold sweep" mode with its own budget cap
- No mandatory cold file audit when the ratio is low — below 40%, cold files only enter scope if recon observations or impact graph edges independently flag them
- No per-file `last_audited` timestamp tracking — binary "audited at least once" is sufficient

## Token Budget Impact

### Per-run cost estimate

| Source | Delta |
|--------|-------|
| Lens extensions in `lens-registry.md` (read once per audit step) | ~100 tokens |
| Two new patterns in compact brief (read per subagent, ~3-5 dispatches) | ~450-750 tokens |
| Cold file recon substep | ~200 tokens |
| **Total** | **~750-1050 tokens/run (<1%)** |

### Structural scorecard

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Lenses | 13 | 13 | 0 |
| Patterns | 14 | 16 | +2 |
| Phases/Steps | 10 | 10 | 0 |
| Convergence iterations | Unchanged | Unchanged | 0 |

### Coverage projection (from Issue #5)

| Component | Findings Addressed |
|-----------|-------------------|
| resource-lifecycle extension | 7 |
| concurrency extension | 4 |
| concurrency-violation fold (RT + escape hatch) | 2 |
| cross-language-dead-interface pattern | 2 |
| numeric-precision-exhaustion pattern | 3 |
| Cold file sweep | 14 |
| data-flow extension | 4 |
| contract extension | (reinforces escape hatch) |
| **Total (after dedup)** | **~30 of 34 (88%)** |

Remaining 4 findings are deep single-instance reasoning bugs — the irreducible residual for periodic manual adversarial reviews.

## Implementation Order

Changes are independent and can be implemented in parallel:

1. **Lens extensions** — edit `references/lens-registry.md` (4 targeted additions)
2. **Pattern fold** — edit `patterns/concurrency-violation.md` (2 new variant subsections)
3. **New pattern: cross-language-dead-interface** — new file in `patterns/`
4. **New pattern: numeric-precision-exhaustion** — new file in `patterns/`
5. **Cold file sweep** — edit SKILL.md (Steps 2, 4) and `references/status-file-format.md`
6. **Regenerate compact pattern brief** — run `pattern_brief_compact.py` to pick up new patterns
7. **Update pattern contribution protocol** — add new pattern IDs to the registry

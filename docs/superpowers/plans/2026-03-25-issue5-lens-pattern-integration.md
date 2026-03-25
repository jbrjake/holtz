# Issue #5: Lens & Pattern Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate adversarial-review blind spot proposals from Issue #5 — extend 4 lenses, fold 2 pattern variants, add 2 new patterns, and integrate cold file sweep into recon.

**Architecture:** All changes are markdown-only — no executable code is added or modified. Four existing reference files get targeted extensions, one existing pattern file gets two new variant subsections, two new pattern files are created, and three files get cold file sweep additions. The compact pattern brief is regenerated to pick up new patterns.

**Tech Stack:** Markdown, YAML frontmatter, bash (for pattern brief regeneration and tests)

**Spec:** `docs/superpowers/specs/2026-03-25-issue5-lens-pattern-integration-design.md`

---

### Task 1: Extend `resource-lifecycle` Lens — Cross-Domain Compute

**Files:**
- Modify: `skills/holtz/references/lens-registry.md:67-71`

- [ ] **Step 1: Add cross-domain compute to entry point and failure modes**

In `skills/holtz/references/lens-registry.md`, append to the `resource-lifecycle` lens entry. After the existing entry point text (line 71), add the cross-domain extension. The result should read:

```markdown
## resource-lifecycle
**Focus:** Acquisition, use, and release of system resources on all code paths
**Audit priorities:** File handles, DB connections, sockets, locks, temp files, subprocesses — each must have a corresponding release on every path including exceptions and early returns. Language-idiomatic cleanup (Python `with`, Go `defer`, Java try-with-resources) should be the norm, not the exception.
**Failure modes:** Gradual handle/connection exhaustion, "too many open files" after hours of runtime, connection pool depletion, orphaned temp files filling disk, leaked locks causing deadlocks. For heterogeneous compute: two compute domains disagree about buffer format, size, ownership, or timing — data corruption that compiles and runs but produces garbage or races.
**Entry point:** Grep for resource acquisition calls (`open`, `connect`, `socket`, `Lock.acquire`, `subprocess.Popen`). For each: verify cleanup on all paths. Check that cleanup itself handles errors. Ask: "If this function raises on line N, which resources are leaked?" For heterogeneous compute systems (CPU-GPU, CPU-FPGA, host-device): trace each shared buffer/texture from creation → format → host writes → device reads → device writes → host reads. Check format agreement between domains, synchronization between domains (fences, completion handlers, triple-buffering), and reset completeness.
```

- [ ] **Step 2: Verify formatting**

Read the file and confirm the lens has exactly four fields (Focus, Audit priorities, Failure modes, Entry point) with no blank lines breaking the entry.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/lens-registry.md
git commit -m "feat(lens): extend resource-lifecycle with cross-domain compute coverage"
```

---

### Task 2: Extend `concurrency` Lens — Real-Time Constraints

**Files:**
- Modify: `skills/holtz/references/lens-registry.md:61-65`

- [ ] **Step 1: Add RT constraints to audit priorities and entry point**

In the `concurrency` lens entry, extend the audit priorities and entry point:

```markdown
## concurrency
**Focus:** Thread safety, race conditions, synchronization correctness, deadlock potential
**Audit priorities:** Shared mutable state protection, lock ordering consistency, atomic operation correctness, timeout presence on blocking calls, absence of TOCTOU patterns at trust boundaries. Real-time thread safety: code on deadline threads (audio callbacks, render loops, interrupt handlers, game tick functions) must not perform heap allocation, lock acquisition, blocking waits, or operations with non-constant-time overhead — these are correctness issues under RT constraints even when properly synchronized.
**Failure modes:** Data races, deadlocks, priority inversion, blocked-thread pool exhaustion, non-deterministic corruption that passes all tests and only manifests under production load
**Entry point:** Identify all shared mutable state (globals, class-level mutables, caches, connection pools). For each: trace all access sites, check synchronization. Run `go test -race` or equivalent. Ask: "What happens if two requests hit this code path simultaneously?" Additionally, identify all real-time entry points (audio tap callbacks, render delegate methods, display link callbacks, interrupt handlers). Trace every code path reachable from each. Flag any operation that is not O(1)-with-bounded-constant.
```

- [ ] **Step 2: Verify formatting**

Read the file and confirm the lens still has exactly four fields with no structural breaks.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/lens-registry.md
git commit -m "feat(lens): extend concurrency with real-time constraint coverage"
```

---

### Task 3: Extend `data-flow` Lens — Cross-Language Boundaries

**Files:**
- Modify: `skills/holtz/references/lens-registry.md:31-35`

- [ ] **Step 1: Add cross-language boundary tracing to entry point**

In the `data-flow` lens entry, extend the entry point:

```markdown
## data-flow
**Focus:** How data transforms as it moves through the system
**Audit priorities:** Serialization/deserialization boundaries, type coercion, lossy transformations, format assumptions
**Failure modes:** Data corruption at boundaries, silent type coercion, schema drift
**Entry point:** Follow data from ingestion to output, checking each transformation. When data crosses a language boundary (host code to shader, application to SQL, code to template), trace BOTH sides. Check: (a) all fields written by sender are read by receiver, (b) all fields read by receiver are written by sender, (c) division/normalize/log operations on the receiving side are guarded for zero/negative/NaN inputs.
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/references/lens-registry.md
git commit -m "feat(lens): extend data-flow with cross-language boundary tracing"
```

---

### Task 4: Extend `contract` Lens — Escape-Hatch Verification

**Files:**
- Modify: `skills/holtz/references/lens-registry.md:37-41`

- [ ] **Step 1: Add escape-hatch verification to audit priorities**

In the `contract` lens entry, extend audit priorities:

```markdown
## contract
**Focus:** Explicit and implicit contracts — API signatures, type interfaces, documented behavior guarantees
**Audit priorities:** Functions that promise behavior their implementation doesn't deliver, version drift in interfaces. Thread-safety escape hatches: for each `@unchecked Sendable` (Swift), `unsafe impl Send` (Rust), or equivalent annotation that opts out of concurrency safety checks, verify all mutable stored properties are protected by synchronization. If not, the concurrency contract is violated.
**Failure modes:** Contract violations that callers silently tolerate until they don't
**Entry point:** Compare documented/typed interfaces against actual implementation behavior
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/references/lens-registry.md
git commit -m "feat(lens): extend contract with concurrency escape-hatch verification"
```

---

### Task 5: Fold RT + Escape Hatch Variants into `concurrency-violation`

**Files:**
- Modify: `skills/holtz/patterns/concurrency-violation.md:1-123`

- [ ] **Step 1: Update YAML frontmatter — add `swift` to languages**

Change line 5 from:
```yaml
languages: [python, javascript, go, rust, java]
```
to:
```yaml
languages: [python, javascript, go, rust, java, swift]
```

- [ ] **Step 2: Add RT constraint violation variant to Description**

After the existing paragraph ending "...sequential consistency without enforcing it." (line 17), add:

```markdown

**Real-time constraint violation:** Code on hard-deadline threads (audio callbacks, render loops, interrupt handlers, game tick functions) that is correctly synchronized but violates latency guarantees by performing: heap allocation (object creation, buffer/array resize, string building), lock or semaphore acquisition, blocking calls (completion waits, synchronous dispatch), or triggering non-trivial language-runtime bookkeeping. The code is thread-safe but not RT-safe.

**Lying escape hatch:** Types annotated to opt out of the language's concurrency safety checks but whose implementation doesn't uphold the contract. The annotation promises thread-safety; mutable stored properties without synchronization break that promise.
```

- [ ] **Step 3: Add RT detection heuristics to Detection Heuristic section**

Insert between the last existing grep block (line 43) and the `### Manual triage` heading (line 45). Add these new grep blocks:

````markdown

```bash
# Weak reference usage in callback/handler contexts (any language)
grep -rnP '(weak|WeakRef|weak_ptr)' --include='*.swift' --include='*.ts' --include='*.cpp' --include='*.rs' . | grep -iP 'callback|handler|render|audio|tick'
```

```bash
# Semaphore or lock near async/await (deadlock on RT thread)
grep -rlP '(Semaphore|semaphore|Mutex|mutex)' . | xargs grep -lP '(async|await|Task|Future|Promise)'
```

```bash
# Unmanaged/unsafe pointer access in callback contexts
grep -rnP '(Unmanaged|UnsafePointer|unsafe\s*\{|raw pointer)' . | grep -iP 'callback|handler|audio|render'
```

```bash
# Concurrency escape hatches with mutable state
grep -rn "@unchecked Sendable" --include='*.swift' .
grep -rn "unsafe impl Send\|unsafe impl Sync" --include='*.rs' .
grep -rn "@SuppressWarnings.*thread-safety" --include='*.java' .
# For each match: check type body for mutable fields without synchronization
```
````

- [ ] **Step 4: Add RT and escape-hatch indicators to Indicators section**

Append to the existing bulleted Indicators list, immediately after "Python `threading` usage without `Lock`/`RLock`/`Queue`" (line 67). Continue the same list — no blank line or new heading between old and new bullets:

```markdown
- Callbacks or handlers that allocate objects, grow containers, or build strings
- Lock acquisition inside a function called from a deadline thread
- Blocking waits in render or audio paths
- Intermittent audio glitches or frame drops under load (classic symptom)
- Type with a concurrency escape-hatch annotation containing mutable fields with no lock, atomic, or actor isolation in scope
```

- [ ] **Step 5: Add to Related Patterns**

After the existing related patterns (line 122), add:

```markdown
- [resource-leak](resource-leak.md) — RT violations from per-frame resource allocation are also resource lifecycle bugs
```

- [ ] **Step 6: Verify the file is well-formed**

Read the full file. Confirm: YAML frontmatter has `swift`, Description has 7 variant paragraphs (data races, TOCTOU, priority inversion, ABA, blocked-thread exhaustion, RT constraint violation, lying escape hatch), Detection Heuristic has 8 grep blocks, Indicators has 12-13 bullets, Related Patterns has 4 entries.

- [ ] **Step 7: Commit**

```bash
git add skills/holtz/patterns/concurrency-violation.md
git commit -m "feat(pattern): add RT constraint and escape-hatch variants to concurrency-violation"
```

---

### Task 6: Create `cross-language-dead-interface` Pattern

**Files:**
- Create: `skills/holtz/patterns/cross-language-dead-interface.md`

- [ ] **Step 1: Write the pattern file**

Create `skills/holtz/patterns/cross-language-dead-interface.md` with:

```markdown
---
name: cross-language-dead-interface
version: "1.0.0"
discovered: 2026-03-25
languages: []
categories: [bug/logic, design/maintenance]
---

# Cross-Language Dead Interface

## Description

Fields, uniforms, bindings, or parameters written in one language and intended to be consumed in another (host code to shader, application to SQL/template, frontend to backend DTO) where the receiving side never reads them — or vice versa. The sending side computes and transmits data every cycle; the receiving side ignores it. A feature silently stops working, or compute is wasted indefinitely.

Distinct from `dead-code-latent-path` (unreachable code behind toggles within one language) and `dual-parser-divergence` (two parsers for the same format). This pattern spans a language boundary where the compiler cannot see both sides.

The root cause is that cross-language interfaces are invisible to each language's toolchain. The host compiler cannot see that a shader no longer reads a uniform field. The shader compiler cannot see that the host stopped writing one. Renaming, removing, or refactoring on either side produces no error, warning, or test failure.

## Detection Heuristic

### Grep-based scan

```bash
# Find struct/class fields used in cross-language data transfer
grep -rnP '(Uniforms|Params|Constants|Bindings)\b' --include='*.swift' --include='*.cpp' --include='*.rs' --include='*.py' .
```

```bash
# Find host-side data transfer calls
grep -rnP '(setBytes|setBuffer|glUniform|bind|uniform\s+\w+)' .
```

```bash
# Find SQL parameter binding
grep -rnP '(\?|:\w+|%s|%\(\w+\))' --include='*.py' --include='*.js' --include='*.go' . | grep -iP '(execute|query|prepare)'
```

### Manual triage

1. For each cross-language data struct: list every field
2. For each field: does the sending side write it? Does the receiving side read it?
3. Are field names consistent across the boundary? (Typos won't produce compiler errors)
4. Were any fields added or removed on one side without updating the other?

### LLM-based structured check

> "Identify all data structures that cross a language boundary (host→shader, app→SQL, code→template). For each field in the sending struct: is it read on the receiving side? For each field read on the receiving side: is it written on the sending side? Flag orphaned fields in either direction."

## Indicators

- Struct fields computed every frame/request but never referenced in the corresponding shader/query/template
- Shader/query reads a field the host side never populates (undefined data consumed silently)
- Rename on one side not propagated to the other (no compiler error across the boundary)
- Performance cost: unnecessary computation and data transfer every cycle
- Features that "stopped working" after a refactor on one side of the boundary

## Example

### Before (buggy)

```python
# host.py — Python sending uniforms to a GLSL shader
class ParticleUniforms:
    def __init__(self):
        self.time = 0.0
        self.particle_count = 100
        self.smooth_blend_radius = 0.5  # Added for a blur feature
        self.smoothed_iterations = 4    # Added for a blur feature

    def upload(self, shader):
        shader.set_uniform("time", self.time)
        shader.set_uniform("particleCount", self.particle_count)
        shader.set_uniform("smoothBlendRadius", self.smooth_blend_radius)  # Uploaded every frame
        shader.set_uniform("smoothedIterations", self.smoothed_iterations)  # Uploaded every frame

# particle.glsl — the shader was refactored, blur feature removed
# uniform float time;
# uniform int particleCount;
# // smoothBlendRadius and smoothedIterations were removed from shader
# // but host still computes and uploads them every frame — no error
```

### After (fixed)

```python
# host.py — removed dead fields
class ParticleUniforms:
    def __init__(self):
        self.time = 0.0
        self.particle_count = 100

    def upload(self, shader):
        shader.set_uniform("time", self.time)
        shader.set_uniform("particleCount", self.particle_count)
```

## Related Patterns

- [dead-code-latent-path](dead-code-latent-path.md) — single-language dead code behind toggles
- [doc-spec-drift](doc-spec-drift.md) — the interface contract drifted without anyone noticing
- [dual-parser-divergence](dual-parser-divergence.md) — two sides interpreting shared data differently
```

- [ ] **Step 2: Verify the file**

Read the file and confirm it has: YAML frontmatter with all 5 fields, Description, Detection Heuristic (with grep-based scan, manual triage, LLM check), Indicators, Example (before/after), Related Patterns.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/cross-language-dead-interface.md
git commit -m "feat(pattern): add cross-language-dead-interface pattern"
```

---

### Task 7: Create `numeric-precision-exhaustion` Pattern

**Files:**
- Create: `skills/holtz/patterns/numeric-precision-exhaustion.md`

- [ ] **Step 1: Write the pattern file**

Create `skills/holtz/patterns/numeric-precision-exhaustion.md` with:

```markdown
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
```

- [ ] **Step 2: Verify the file**

Read the file and confirm it has: YAML frontmatter with all 5 fields, Description with 3 sub-classes, Detection Heuristic (grep + manual + LLM), Indicators, Example (before/after), Related Patterns.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/numeric-precision-exhaustion.md
git commit -m "feat(pattern): add numeric-precision-exhaustion pattern"
```

---

### Task 8: Cold File Sweep — SKILL.md Changes

**Files:**
- Modify: `skills/holtz/SKILL.md:225-244`

- [ ] **Step 1: Extend Step 2 with cold file coverage scan**

In `skills/holtz/SKILL.md`, find the Step 2 section (lines 225-232). After the existing bullet list and before `Output:`, add a cold file coverage substep:

```markdown
### Step 2: Code Signals (Subagent)

Dispatch a subagent to run in parallel:
- Git churn analysis (top 20 most-changed files in last 50 commits)
- Mutation scan (optional — auto-detected)
- Find skipped/disabled tests
- Cold file coverage scan: list all source files, scan `docs/holtz/archive/*/PUNCHLIST.md` for file paths mentioned in findings and `docs/holtz/LIVING-PUNCHLIST.md` if it exists. A file counts as "audited" if it appears in any prior punchlist finding. On first run (no archive), all files are cold. Compute `cold_file_ratio = files_never_audited / total_source_files`. Write inventory to `docs/holtz/recon/step2-cold-files.md`.

Output: `docs/holtz/recon/step2-code-signals.md`
```

- [ ] **Step 2: Extend Step 4 with cold file prediction input**

Find the Step 4 section (lines 240-244). Change "six input sources" to "seven input sources" and add the cold file inventory:

```markdown
### Step 4: Predictions

Use extended thinking (ultrathink). Rank where bugs are likely to be found using seven input sources: pattern brief, impact graph risk scores, impact graph edges, git churn, prior run findings, recon observations, and cold file inventory. When `cold_file_ratio` exceeds 40%, add at least 3 cold files to predictions as MEDIUM-confidence targets with basis "never audited — unknown risk," prioritizing files closest to entry points or with the most inbound impact graph edges. Each prediction includes: Target, Predicted Issue, Confidence (HIGH/MEDIUM/LOW), Basis, Lens, Graph Support, Outcome.

Output: `docs/holtz/recon/step4-predictions.md`
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): integrate cold file sweep into Steps 2 and 4"
```

---

### Task 9: Cold File Sweep — `recon-procedures.md` Changes

**Files:**
- Modify: `skills/holtz/references/recon-procedures.md:119-134`

- [ ] **Step 1: Update six-source references to seven-source**

In `skills/holtz/references/recon-procedures.md`, find lines 121-123 which read:

```markdown
Use extended thinking (ultrathink) for this step — synthesizing six input sources into ranked predictions requires deep reasoning.

After Step 3, produce `docs/holtz/recon/step4-predictions.md` ranking where bugs are likely to be found. Draw from six input sources:
```

Change "six" to "seven" in both occurrences.

- [ ] **Step 2: Add cold file inventory row to the input source table**

After the last row of the table (line 132, "Recon observations"), add:

```markdown
| Cold file inventory (Step 2) | Never-audited files → predict unknown risk in uninspected areas. When `cold_file_ratio` > 40%, add at least 3 cold files as MEDIUM-confidence predictions |
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/recon-procedures.md
git commit -m "feat(skill): add cold file inventory as seventh prediction input source"
```

---

### Task 10: Cold File Sweep — `status-file-format.md` Changes

**Files:**
- Modify: `skills/holtz/references/status-file-format.md:56-58`

- [ ] **Step 1: Add Cold File Coverage section after Metrics**

In `skills/holtz/references/status-file-format.md`, find the Metrics table (ending at line 55 with `| Convergence iterations |`) and the Notes section (line 57). Insert a Cold File Coverage section between them:

```markdown
| Convergence iterations | — | {N} |

## Cold File Coverage
| Metric | Value |
|--------|-------|
| Total source files | {n} |
| Files audited (any run) | {n} |
| Cold file ratio | {n}% |
| Cold files audited this run | {n} |

## Notes
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/references/status-file-format.md
git commit -m "feat(skill): add Cold File Coverage section to STATUS.md format"
```

---

### Task 11: Regenerate Pattern Brief, Run Tests, and Verify

**Files:**
- Run: `skills/holtz/scripts/pattern_brief_compact.py`
- Verify: all modified files from Tasks 1-10

- [ ] **Step 1: Run existing tests**

```bash
python -m pytest tests/test_pattern_brief_compact.py tests/test_pattern_brief_compact_structure.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run linters**

```bash
ruff check .
```

Expected: clean.

- [ ] **Step 3: Verify new pattern files exist**

```bash
ls skills/holtz/patterns/*.md | wc -l
```

Expected: 16 (was 14, added 2).

- [ ] **Step 4: Spot-check lens registry**

Read `skills/holtz/references/lens-registry.md` end-to-end. Confirm:
- 13 lenses (count `## ` headings)
- `resource-lifecycle` mentions "heterogeneous compute"
- `concurrency` mentions "deadline threads"
- `data-flow` mentions "language boundary"
- `contract` mentions "escape hatch"

- [ ] **Step 5: Spot-check concurrency-violation pattern**

Read `skills/holtz/patterns/concurrency-violation.md`. Confirm:
- Frontmatter `languages` includes `swift`
- Description has RT constraint violation and lying escape hatch paragraphs
- Detection Heuristic has grep blocks for weak references, semaphores, unmanaged pointers, and escape hatches
- Indicators includes RT-specific bullets
- Related Patterns has 4 entries

- [ ] **Step 6: Spot-check cold file sweep changes**

Read `skills/holtz/SKILL.md` Steps 2 and 4. Confirm:
- Step 2 includes "Cold file coverage scan" substep with archive scanning logic
- Step 4 says "seven input sources" (not "six") and includes the 40% threshold text

Read `skills/holtz/references/recon-procedures.md` Step 4 section. Confirm:
- Says "seven input sources" in both occurrences
- Input table has 7 rows, last row is "Cold file inventory"

Read `skills/holtz/references/status-file-format.md`. Confirm:
- "Cold File Coverage" section exists between Metrics and Notes

Anti-requirement check: confirm NONE of the following were added:
- No new phase or step number in SKILL.md
- No per-file `last_audited` timestamp tracking
- No mandatory cold audit below 40% threshold

- [ ] **Step 7: Commit if any fixes were needed**

Only commit if spot-checks revealed issues that were fixed. Otherwise, skip.

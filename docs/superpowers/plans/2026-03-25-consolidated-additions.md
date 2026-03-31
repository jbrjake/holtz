# Consolidated Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 bug patterns, 5 test antipatterns, and 4 analytical lenses from the consolidated-additions spec.

**Architecture:** Each bug pattern is a standalone markdown file in `skills/holtz/patterns/`. Test antipatterns append to an existing reference file. Lenses append to the lens registry. No code changes needed — these are all content files that the Holtz skill auto-discovers.

**Tech Stack:** Markdown with YAML frontmatter (patterns), plain markdown (antipatterns, lenses).

---

### Task 1: Add concurrency-violation pattern

**Files:**
- Create: `skills/holtz/patterns/concurrency-violation.md`

**Source:** `docs/design/consolidated-additions.md` lines 12–133

- [ ] **Step 1: Create the pattern file**

Extract the concurrency-violation section from the spec (lines 12–133) into its own file at `skills/holtz/patterns/concurrency-violation.md`. The file must have:
- YAML frontmatter with name, version, discovered, languages, categories
- Sections: Description, Detection Heuristic (Grep-based scan, Manual triage, LLM-based structured check), Indicators, Example (Before/After), Related Patterns

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/concurrency-violation.md`
Expected: YAML frontmatter with `name: concurrency-violation`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/concurrency-violation.md
git commit -m "feat(patterns): add concurrency-violation pattern"
```

---

### Task 2: Add resource-leak pattern

**Files:**
- Create: `skills/holtz/patterns/resource-leak.md`

**Source:** `docs/design/consolidated-additions.md` lines 134–229

- [ ] **Step 1: Create the pattern file**

Extract the resource-leak section from the spec into `skills/holtz/patterns/resource-leak.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/resource-leak.md`
Expected: YAML frontmatter with `name: resource-leak`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/resource-leak.md
git commit -m "feat(patterns): add resource-leak pattern"
```

---

### Task 3: Add uncontrolled-amplification pattern

**Files:**
- Create: `skills/holtz/patterns/uncontrolled-amplification.md`

**Source:** `docs/design/consolidated-additions.md` lines 230–342

- [ ] **Step 1: Create the pattern file**

Extract the uncontrolled-amplification section into `skills/holtz/patterns/uncontrolled-amplification.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/uncontrolled-amplification.md`
Expected: YAML frontmatter with `name: uncontrolled-amplification`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/uncontrolled-amplification.md
git commit -m "feat(patterns): add uncontrolled-amplification pattern"
```

---

### Task 4: Add error-destruction pattern

**Files:**
- Create: `skills/holtz/patterns/error-destruction.md`

**Source:** `docs/design/consolidated-additions.md` lines 343–464

- [ ] **Step 1: Create the pattern file**

Extract the error-destruction section into `skills/holtz/patterns/error-destruction.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/error-destruction.md`
Expected: YAML frontmatter with `name: error-destruction`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/error-destruction.md
git commit -m "feat(patterns): add error-destruction pattern"
```

---

### Task 5: Add cache-coherence-failure pattern

**Files:**
- Create: `skills/holtz/patterns/cache-coherence-failure.md`

**Source:** `docs/design/consolidated-additions.md` lines 465–569

- [ ] **Step 1: Create the pattern file**

Extract the cache-coherence-failure section into `skills/holtz/patterns/cache-coherence-failure.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/cache-coherence-failure.md`
Expected: YAML frontmatter with `name: cache-coherence-failure`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/cache-coherence-failure.md
git commit -m "feat(patterns): add cache-coherence-failure pattern"
```

---

### Task 6: Add silent-semantic-mismatch pattern

**Files:**
- Create: `skills/holtz/patterns/silent-semantic-mismatch.md`

**Source:** `docs/design/consolidated-additions.md` lines 570–684

- [ ] **Step 1: Create the pattern file**

Extract the silent-semantic-mismatch section into `skills/holtz/patterns/silent-semantic-mismatch.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/silent-semantic-mismatch.md`
Expected: YAML frontmatter with `name: silent-semantic-mismatch`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/silent-semantic-mismatch.md
git commit -m "feat(patterns): add silent-semantic-mismatch pattern"
```

---

### Task 7: Add implicit-ordering-dependency pattern

**Files:**
- Create: `skills/holtz/patterns/implicit-ordering-dependency.md`

**Source:** `docs/design/consolidated-additions.md` lines 685–800

- [ ] **Step 1: Create the pattern file**

Extract the implicit-ordering-dependency section into `skills/holtz/patterns/implicit-ordering-dependency.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/implicit-ordering-dependency.md`
Expected: YAML frontmatter with `name: implicit-ordering-dependency`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/implicit-ordering-dependency.md
git commit -m "feat(patterns): add implicit-ordering-dependency pattern"
```

---

### Task 8: Add dead-code-latent-path pattern

**Files:**
- Create: `skills/holtz/patterns/dead-code-latent-path.md`

**Source:** `docs/design/consolidated-additions.md` lines 801–900

- [ ] **Step 1: Create the pattern file**

Extract the dead-code-latent-path section into `skills/holtz/patterns/dead-code-latent-path.md`. Same structure as Task 1.

- [ ] **Step 2: Verify structure**

Run: `head -8 skills/holtz/patterns/dead-code-latent-path.md`
Expected: YAML frontmatter with `name: dead-code-latent-path`

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/patterns/dead-code-latent-path.md
git commit -m "feat(patterns): add dead-code-latent-path pattern"
```

---

### Task 9: Append 5 test antipatterns to anti-patterns.md

**Files:**
- Modify: `skills/holtz/references/anti-patterns.md`

**Source:** `docs/design/consolidated-additions.md` lines 905–936

- [ ] **Step 1: Append Tier 1 additions (items 13-14)**

After existing item 4 in the `## Tier 1: Actively Harmful` section, append:

```markdown
**13. Assertion Roulette** — Multiple assertions per test with no messages; when one fails, you can't tell which or why without reading source. Detection: count bare `assert` / `assertEqual` calls per test method with no `msg=` parameter. >5 undifferentiated assertions in a single test is a strong signal. Distinct from Green Bar Addict (which has TOO FEW assertions) — this has plenty, but they're anonymous.

**14. Choose Your Own Adventure** — Test contains conditional logic (`if`, `for`, `try/except`) creating branches within the test itself. The test is now a program that itself needs testing. Detection: any `if`/`for`/`while`/`try` inside a test method body (excluding context managers). If the test has branches, some branches are untested. 97% of surveyed developers in test-smell studies recognize this as harmful.
```

- [ ] **Step 2: Append Tier 2 additions (items 15-16)**

After existing item 8 in the `## Tier 2: False Security` section, append:

```markdown
**15. Mystery Guest** — Test depends on external state invisible in the test body: files on disk, database records from another test's setup, environment variables, system locale, or network services. Cause-and-effect is opaque — the test fails and you can't tell why by reading it. Detection: test references file paths, env vars, or external URLs not created within the test or its fixture. Subsumes "The Local Hero" (fails on different OS/timezone/locale) as a specific variant.

**16. The Eager Beaver** — Single test exercises multiple independent production behaviors. When it fails, you know *something* broke but not *what*. Defect localization is destroyed. Detection: test calls 2+ unrelated production methods and asserts on results from each. Test name requires "and" to describe what it tests.
```

- [ ] **Step 3: Append Tier 3 addition (item 17)**

After existing item 12 in the `## Tier 3: Missed Opportunities` section, append:

```markdown
**17. The Ice Cream Cone** — Inverted test pyramid: mostly manual or end-to-end tests, minimal unit tests, almost no integration tests. Feedback loop is hours instead of seconds; developers stop running tests locally. Detection: count test files by type (unit vs integration vs e2e). If e2e > unit, the pyramid is inverted. A codebase-level antipattern, not per-test — score it during project audits, not file audits.
```

- [ ] **Step 4: Append 5 rows to the Audit Checklist table**

After the existing last row of the checklist table, append:

```markdown
| Assertion identifiability | >5 assertions per test with no messages |
| Test logic complexity | Conditionals/loops inside test body |
| External dependency visibility | Test relies on state not created in test/fixture |
| Behavioral isolation | Single test exercises multiple unrelated behaviors |
| Pyramid shape | E2E test count exceeds unit test count |
```

- [ ] **Step 5: Verify the file**

Run: `grep -c '^\*\*[0-9]' skills/holtz/references/anti-patterns.md`
Expected: `17` (12 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/references/anti-patterns.md
git commit -m "feat(patterns): add 5 test antipatterns (items 13-17)"
```

---

### Task 10: Append 4 lenses to lens-registry.md

**Files:**
- Modify: `skills/holtz/references/lens-registry.md`

**Source:** `docs/design/consolidated-additions.md` lines 940–964

- [ ] **Step 1: Append the 4 new lenses**

After the last lens (`## public-contract`) in `lens-registry.md`, append:

```markdown
## concurrency
**Focus:** Thread safety, race conditions, synchronization correctness, deadlock potential
**Audit priorities:** Shared mutable state protection, lock ordering consistency, atomic operation correctness, timeout presence on blocking calls, absence of TOCTOU patterns at trust boundaries
**Failure modes:** Data races, deadlocks, priority inversion, blocked-thread pool exhaustion, non-deterministic corruption that passes all tests and only manifests under production load
**Entry point:** Identify all shared mutable state (globals, class-level mutables, caches, connection pools). For each: trace all access sites, check synchronization. Run `go test -race` or equivalent. Ask: "What happens if two requests hit this code path simultaneously?"

## resource-lifecycle
**Focus:** Acquisition, use, and release of system resources on all code paths
**Audit priorities:** File handles, DB connections, sockets, locks, temp files, subprocesses — each must have a corresponding release on every path including exceptions and early returns. Language-idiomatic cleanup (Python `with`, Go `defer`, Java try-with-resources) should be the norm, not the exception.
**Failure modes:** Gradual handle/connection exhaustion, "too many open files" after hours of runtime, connection pool depletion, orphaned temp files filling disk, leaked locks causing deadlocks
**Entry point:** Grep for resource acquisition calls (`open`, `connect`, `socket`, `Lock.acquire`, `subprocess.Popen`). For each: verify cleanup on all paths. Check that cleanup itself handles errors. Ask: "If this function raises on line N, which resources are leaked?"

## idempotency
**Focus:** Whether operations are safe to execute more than once with the same input
**Audit priorities:** Database writes (INSERT vs UPSERT), payment/billing operations, notification dispatch, event handlers, API endpoints that mutate state, queue consumers that may receive duplicate messages
**Failure modes:** Duplicate charges, duplicate notifications, duplicate database records, double-counted metrics, non-convergent state after retry
**Entry point:** For each state-mutating operation: what happens if the exact same request arrives twice? Is there a deduplication key, idempotency token, or UPSERT? For event consumers: does the handler use at-least-once delivery semantics? Ask: "If the network hiccups and this message is delivered twice, does the user get charged twice?"

## observability
**Focus:** Whether the code emits enough telemetry to diagnose failures in production without attaching a debugger
**Audit priorities:** Structured logging at decision points, correlation IDs propagated across service boundaries, metrics for latency/error-rate/saturation, error logs with sufficient context (request ID, user ID, input summary), no PII in logs, log levels appropriate to severity
**Failure modes:** On-call engineer cannot diagnose a 2 AM page without reproducing locally, missing correlation IDs make distributed traces unfollowable, PII leakage in logs, log volume so high that signal is buried, metrics gaps that hide degradation
**Entry point:** For each error path: is there a log entry with enough context to diagnose without source code? For each service boundary: is a correlation ID propagated? For each critical operation: is there a latency metric? Ask: "If this fails at 2 AM, can the on-call engineer figure out what happened from the logs alone?"
```

- [ ] **Step 2: Verify lens count**

Run: `grep -c '^## ' skills/holtz/references/lens-registry.md`
Expected: `13` (9 existing + 4 new), excluding the header line

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/lens-registry.md
git commit -m "feat(lenses): add concurrency, resource-lifecycle, idempotency, observability lenses"
```

---

### Task 11: Update SKILL.md antipattern count

**Files:**
- Modify: `skills/holtz/SKILL.md:32`

- [ ] **Step 1: Update the count**

Change line 32 from:
```
- [references/anti-patterns.md](references/anti-patterns.md) — test quality detection (12 anti-patterns with audit checklist)
```
to:
```
- [references/anti-patterns.md](references/anti-patterns.md) — test quality detection (17 anti-patterns with audit checklist)
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): update antipattern count from 12 to 17"
```

---

### Task 12: Run tests and verify

- [ ] **Step 1: Run the test suite**

Run: `python -m pytest --tb=short -q`
Expected: All tests pass (existing tests are structural, not content-dependent on specific patterns)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Verify all 14 pattern files exist**

Run: `ls skills/holtz/patterns/*.md | wc -l`
Expected: `14` (6 existing + 8 new)

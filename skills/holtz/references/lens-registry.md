# Lens Registry

Analytical lenses for multi-perspective auditing. Holtz rotates through these during the convergence loop. True convergence requires all lenses clean in the same final sweep.

Users can add custom lenses by appending new sections following the same four-field format (Focus, Audit priorities, Failure modes, Entry point). Any `## heading` in this file with the four required fields is treated as a lens.

## component
**Focus:** Individual functions, classes, modules in isolation
**Audit priorities:** Correctness, edge cases, error handling, return values
**Failure modes:** Logic errors, missing validation, unhandled edge cases
**Entry point:** Standard Steps 6-8

## integration
**Focus:** Contracts and assumptions between modules
**Audit priorities:** Interface agreements, shared state, data format assumptions, parser divergence
**Failure modes:** Modules that are individually correct but disagree with each other
**Entry point:** Query impact graph for `assumes`, `diverges_from`, `calls` edges; audit the seams

## security
**Focus:** Attack surfaces, input validation, authorization, data exposure
**Audit priorities:** Untrusted input paths, authentication/authorization checks, secrets handling, injection vectors
**Failure modes:** Missing validation at trust boundaries, privilege escalation, data leakage
**Entry point:** Trace data from external inputs through the system

## error-propagation
**Focus:** How errors flow through the system
**Audit priorities:** Error swallowing, inconsistent error types, missing error paths, partial failure handling
**Failure modes:** Silent failures, error masking, inconsistent error contracts between layers
**Entry point:** Trace error/exception paths from throw to catch

## data-flow
**Focus:** How data transforms as it moves through the system
**Audit priorities:** Serialization/deserialization boundaries, type coercion, lossy transformations, format assumptions
**Failure modes:** Data corruption at boundaries, silent type coercion, schema drift
**Entry point:** Follow data from ingestion to output, checking each transformation

## contract
**Focus:** Explicit and implicit contracts — API signatures, type interfaces, documented behavior guarantees
**Audit priorities:** Functions that promise behavior their implementation doesn't deliver, version drift in interfaces
**Failure modes:** Contract violations that callers silently tolerate until they don't
**Entry point:** Compare documented/typed interfaces against actual implementation behavior

## semantic-fidelity
**Focus:** Whether names (states, functions, variables, enums) accurately describe what they represent at runtime
**Audit priorities:** State machine labels vs actual entry/exit timing, function names vs observed behavior, boolean semantics vs toggle points, enum values vs runtime meaning
**Failure modes:** States labeled for current activity but applied on completion, functions named for actions they don't perform, naming that drifts from semantics across files (same state name means different things to caller vs callee)
**Entry point:** For each state machine or status enum: trace when each value is set and cleared across ALL callers; compare the temporal window of each value against its documented description. Ask: "If I look at this value right now, does its name tell me the truth about what's happening?"

## temporal-protocol
**Focus:** Multi-file orchestration sequences — the actual order of operations vs documented/intended order
**Audit priorities:** State transitions that fire before/after their documented trigger point, transient states with no meaningful duration between entry and exit, operations that assume prior operations completed but don't verify, workflow steps documented in one file but executed differently in another
**Failure modes:** Exit-labeled states (transition fires after work instead of before), double-tap transitions (two consecutive state changes with no work between), phantom states (entered and exited in the same code block — never observable), protocol drift between orchestrator docs and agent docs
**Entry point:** Pick a workflow that spans 2+ files. Trace the actual execution sequence step by step. At each state change, ask: "What work happened since the last state change? What work remains before the next? Is there a state that exists for zero work?"

## public-contract
**Focus:** Whether user-facing documentation (README, CHANGELOG, help output, install instructions) accurately describes runtime behavior
**Audit priorities:** README feature claims vs actual implementation, install/setup instruction accuracy, dependency list correctness, feature coverage gaps
**Failure modes:** Aspirational documentation that describes intended behavior instead of implemented behavior, stale install instructions, feature gaps where code has capabilities the README omits, marketing-code divergence
**Entry point:** Read README.md end-to-end. For each concrete claim, grep for the implementing code. Classify as VERIFIED, OVERSTATED (code does something weaker), FABRICATED (code does not do this), or UNDERSTATED (code does more than claimed)

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

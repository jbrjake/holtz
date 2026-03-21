# Lens Registry

Analytical lenses for multi-perspective auditing. Holtz rotates through these during the convergence loop. True convergence requires all lenses clean in the same final sweep.

Users can add custom lenses by appending new sections following the same four-field format (Focus, Audit priorities, Failure modes, Entry point). Any `## heading` in this file with the four required fields is treated as a lens.

## component
**Focus:** Individual functions, classes, modules in isolation
**Audit priorities:** Correctness, edge cases, error handling, return values
**Failure modes:** Logic errors, missing validation, unhandled edge cases
**Entry point:** Standard Phases 1-3

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

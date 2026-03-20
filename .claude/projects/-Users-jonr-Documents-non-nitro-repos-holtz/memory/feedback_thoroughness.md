---
name: thoroughness-and-fixtures
description: User expects maximum thoroughness - build whatever fixtures are needed to validate everything, never defer for lack of test infrastructure
type: feedback
---

Build whatever fixtures, mock projects, or test infrastructure is needed to validate every finding. Never defer an item just because a test environment doesn't exist — create one.

**Why:** User explicitly rejected deferring BH-006 (Go package-level test counts) because "a Go project wasn't available for testing." The expectation is that if you need a Go project, you build one as a fixture. This applies to all languages and scenarios.

**How to apply:** When a finding requires specific infrastructure to test (a Go project, a Node project, a Rust crate, etc.), create it as a test fixture. Make fixtures fun, whimsical, and quirky — but also genuinely useful for validating the behavior under test. Every stone must be turned. Everything must be proven.

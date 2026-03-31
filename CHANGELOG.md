# Changelog

All notable changes to Holtz will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- Add changes here as they're merged. Move to a version heading on release. -->

## [0.73.3] - 2026-03-30

_264 commits since v0.4.0 — this is a massive release._

### Sahjhan Enforcement Engine

Holtz now ships with **Sahjhan**, a dedicated protocol enforcement binary that
prevents the auditing agent from cutting corners, gaming convergence, or skipping
steps. This is the single largest addition since Holtz's creation.

- Full state-machine protocol defined in TOML with gated transitions, ledger
  queries, and Tera-templated output (STATUS.md, PUNCHLIST.md, SUMMARY.md)
- **HMAC-authenticated event provenance** — every protocol event is
  cryptographically signed so the agent cannot fabricate audit history
- **Lens quiz gates** block perspective and convergence transitions until the
  agent demonstrates it actually read the code through each analytical lens
- **Commit gate** blocks commits during fix-loop state when pattern analysis is
  overdue, preventing premature "done" claims
- **Stop gate** prevents the agent from exiting mid-run without completing the
  protocol
- **Bash write guard** blocks writes to protected paths (sed -i, perl -pi,
  patch, redirects, curl/wget) and detects brace-expansion and glob bypasses
- **Read guard** prevents the agent from reading its own enforcement internals
- **Sleep/stalling detector** catches convergence-gaming tricks like injecting
  sleeps between iterations
- **Self-bootstrapping binary** — Sahjhan downloads and verifies itself via
  SHA-256 checksum on first run; no manual install needed
- Upgraded through 7 versions (v0.1.0 → v0.6.1) during development, each
  hardened by findings from real audit runs
- Multi-ledger support with JSONL event storage and DataFusion queries

### Token Profiler

A new standalone tool for analyzing Claude Code session token usage, shipped as
a separate package within the repo.

- JSONL session extraction with full turn-by-turn token accounting
- 5-stage analysis pipeline: extraction → conversation modeling → phase
  detection → pattern recognition → cost computation
- Model-aware pricing with per-token dollar cost breakdowns
- Markdown report generation and cyberpunk-themed interactive HTML viewer
- Holtz-specific plugin for detecting audit phases in profiler output
- CLI with plugin loading, arg parsing, and pipeline orchestration

### New Bug Patterns and Lenses

Holtz's analytical coverage expanded significantly:

- **17 bug patterns** (up from 12) — added numeric-precision-exhaustion,
  cross-language-dead-interface, RT constraint and escape-hatch variants for
  concurrency-violation, plus 5 test-specific antipatterns
- **10 analytical lenses** (up from 6) — added concurrency, resource-lifecycle,
  idempotency, and observability lenses; extended 4 existing lenses for blind
  spot coverage identified in Issue #5
- Cold file sweep integrated into recon pipeline — files untouched by recent
  commits now get explicit audit attention

### Step Numbering

Complete rewrite of the process flow from nested phase numbering to a flat
Step 0–20 sequence. Affects SKILL.md, all reference docs, STATUS.md templates,
agent definitions, hooks, scripts, diagrams, and tests. Makes the protocol
easier to follow and enforce.

### Performance

- Phase 2 token optimizations reduce context consumption during long runs
- Audit subagents (Steps 7/8) now route to Sonnet for faster, cheaper execution
- Tool call batching and terse narration directives cut overhead tokens
- ENABLE_TOOL_SEARCH guidance added to Context Survival Protocol

### Security Hardening

Over 30 targeted fixes to enforcement hooks, mostly discovered by Holtz auditing
itself:

- Bash guard hardened against bypass vectors (brace expansion, glob patterns,
  env-prefix commands, fenced code blocks)
- Read guard extended to block glob-based access to session keys
- HMAC event fields validated against null-byte injection
- Case-insensitive path matching in bash guard
- Deterministic quiz selection to prevent answer-shopping

### Developer Experience

- **Quick start guide** and badges in README
- **Changelog generator** from conventional commits
- **Post-commit hook** for automatic semver bumping
- **Convergence gate and primer hooks** enforce loop-until-converged behavior
- Community docs and GitHub issue/PR templates
- 30 completed self-audit runs archived with full artifacts

### Fixed

Too many individual fixes to list (140+ fix commits). Highlights:

- Impact graph now raises proper exceptions instead of error sentinel dicts
- Convergence counter raises FileNotFoundError instead of calling sys.exit
- CommonMark-compliant fence masking with CRLF normalization
- Profiler computed properties correctly injected into profile JSON
- 10 tautology tests removed from test suite, replaced with value-checking
  assertions
- Coverage gate enforced at 60% in CI, matching local requirements

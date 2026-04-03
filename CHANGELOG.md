# Changelog

All notable changes to Holtz will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.93.5] - 2026-04-02

_Changes since v0.93.1_

### Fixed
- **hooks:** remove Holtz-specific paths from transition gates
- **hooks:** primer injects context regardless of cache freshness
- **hooks:** stop hook blocks on missing enforcement cache
- **hooks:** handle shell redirects and export prefixes in command parsing

### Infrastructure
- upgrade sahjhan to 0.8.0

## [0.93.1] - 2026-04-02

_Changes since v0.93.0_

### Fixed
- **hooks:** use wildcard matchers so enforcement hooks actually fire

## [0.93.0] - 2026-04-01

_Changes since v0.90.5_

### Added
- **hooks:** gate commit_gate, primer, pre/post_tool_hook, bash_guard on enforcement freshness
- **hooks:** track last_sahjhan_cmd timestamp, skip stall on stale enforcement
- **hooks:** add is_enforcement_fresh() and last_sahjhan_cmd field

### Fixed
- **hooks:** rewrite stop_hook to use cache + freshness gate (fixes #24)

### Documentation
- update test badge count to 959
- add freshness-gated enforcement implementation plan
- add freshness-gated enforcement design spec

### Infrastructure
- **hooks:** update sahjhan integration tests for freshness-gated enforcement

## [0.90.5] - 2026-04-01

_Changes since v0.90.3_

### Fixed
- **hooks:** block stop in all non-terminal states, not just active work states
- **hooks:** upgrade sahjhan to v0.7.1, fixes concurrent ledger corruption

## [0.90.3] - 2026-04-01

_Changes since v0.90.1_

### Fixed
- **hooks:** use schema-valid "approve" for stop warn decision field
- **hooks:** resolve enforcement config via CLAUDE_PLUGIN_ROOT, warn on failure

## [0.90.1] - 2026-03-31

_Changes since v0.73.6_

### Added
- **holtz:** update README for sahjhan 0.7.0 runtime hooks
- **holtz:** remove write_guard.py and stop_gate.py, update all test references
- **holtz:** update hook registrations for sahjhan 0.7.0 thin wrappers
- **holtz:** add pre_tool_hook.py thin wrapper replacing write_guard.py
- **holtz:** add stop_hook.py with state blocking and premature completion detection
- **holtz:** add post_tool_hook.py with auto-record enrichment for all tool types
- **holtz:** add hooks.toml with TDD gate, completion blocker, stall monitors, and auto-recording
- **holtz:** add auto-recorded event types for tool use tracking
- **holtz:** upgrade sahjhan binary from 0.6.1 to 0.7.0
- **docs:** rewrite README for Sahjhan enforcement, lens scoping, and runs 17-30
- **holtz:** revise Step 14 lens rotation to use scope-aware gap-fill/focused sweeps
- **holtz:** update Justine J2 to reference lens scope field from registry
- **holtz:** front-load per-file and cross-file lenses into initial audit (Steps 7-8)
- **holtz:** add parse_lens_registry.py script for programmatic lens classification
- **holtz:** add lens_coverage_recorded event and sweep_type field for front-loaded audit
- **holtz:** add Scope field to lens registry for per-file/cross-file classification
- **holtz:** harden fix loop with checklist, read gate, and narration ban

### Fixed
- **tests:** exclude auto-recorded events from breadcrumb check, fix import sort
- **holtz:** update README counts and replace \s with [ \t] in parse_lens_registry regexes
- **enforcement:** include .sahjhan-version in version pin bump to 0.6.1
- **holtz:** ensure run ledger is created before findings are emitted

### Documentation
- add implementation plan for sahjhan 0.7.0 runtime hooks upgrade
- add design spec for sahjhan 0.7.0 runtime hooks upgrade

### Infrastructure
- commit sahjhan version marker and pre-existing plan file

## [0.73.6] - 2026-03-30

_Changes since v0.4.0_

### Added
- **enforcement:** add sahjhan binary self-bootstrap with checksum verification
- **enforcement:** upgrade templates and guards for sahjhan 0.6.1
- **enforcement:** add check_sweep_evidence.py for final sweep gate
- **enforcement:** add 5 new gate conditions for protocol integrity
- **enforcement:** use HMAC-authenticated events in lens_quiz.py
- **enforcement:** add HMAC event provenance helpers
- **enforcement:** add read-guard to _sahjhan_bootstrap.py
- **enforcement:** mark restricted event types and add new event types
- **enforcement:** add read-guard manifest to protocol.toml
- **skills:** split SKILL.md into phase-specific reference files
- **enforcement:** severity downgrade requires evidence path
- **enforcement:** add test_failed_before_fix event type
- **enforcement:** content validation for merge report
- **enforcement:** detect sleep as stalling in protocol_tracker
- **plans:** add Phase 1 and Phase 2 enforcement hardening implementation plans
- **enforcement:** upgrade sahjhan to v0.5.0, fix template rendering
- **enforcement:** upgrade sahjhan to v0.4.0, add args to gated transitions
- **enforcement:** upgrade sahjhan to v0.3.0, fix template interpolation
- **enforcement:** add hook registration safety net
- **enforcement:** add lens priming to primer hook
- **enforcement:** add SubagentStop lens quiz hook
- **enforcement:** add quiz gates to perspective and convergence transitions
- **enforcement:** add lens evidence checker module
- **enforcement:** add quiz bank validator script
- **enforcement:** add quiz event schemas to events.toml
- **enforcement:** extend bootstrap to block Read on enforcement/ paths
- **enforcement:** upgrade sahjhan to 0.2.1, switch gates to ledger queries
- **enforcement:** register pacing hooks in plugin-mode hooks.json
- **enforcement:** register pacing hooks in dev-mode settings
- **enforcement:** add protocol state line to primer hook
- **enforcement:** add commit_gate PreToolUse hook
- **enforcement:** add protocol_tracker PostToolUse hook
- **enforcement:** add protocol cache module for state-driven enforcement
- **enforcement:** add breadcrumb fields, new event types, query gates, and multi-ledger config
- **skill:** update SKILL.md to reference Sahjhan enforcement commands
- **enforcement:** update hooks.json to use Sahjhan-backed enforcement hooks
- **enforcement:** add Sahjhan binary vendoring and install script
- **enforcement:** add Sahjhan hook scripts
- **enforcement:** add Tera templates for STATUS.md, PUNCHLIST.md, SUMMARY.md
- **enforcement:** add Holtz protocol definition as Sahjhan TOML config
- **profiler:** wire up pricing module — dollar costs now computed
- **skill:** integrate cold file sweep into recon pipeline
- **pattern:** add numeric-precision-exhaustion pattern
- **pattern:** add cross-language-dead-interface pattern
- **pattern:** add RT constraint and escape-hatch variants to concurrency-violation
- **lens:** extend 4 lenses for Issue #5 blind spot coverage
- **skill:** add terminal output format reference for structured run output
- **skill:** update antipattern count from 12 to 17
- **lenses:** add concurrency, resource-lifecycle, idempotency, observability lenses
- **patterns:** add 5 test antipatterns (items 13-17)
- **patterns:** add 8 bug patterns from consolidated-additions spec
- update agent definitions to step numbering
- update diagram .dot files to step numbering and re-render SVGs
- update scripts and hooks to step numbering
- rewrite justine-skill.md to J0-J6 step numbering
- update all reference docs to step numbering
- rename profiler phase detection to step detection
- update recon-procedures.md with step numbering
- rewrite STATUS.md template to Step 0-20 numbering
- rewrite SKILL.md process flow to Step 0-20
- add quick start, badges, research artifact, and cross-harness docs to README
- **scripts:** add changelog generator from conventional commits
- add convergence gate and primer hooks to enforce loop-until-converged
- add commit-msg hook with automatic version bumping from conventional commits
- add commit-msg hook with automatic version bumping from conventional commits
- **token_profiler:** add Run 14 integration tests and profile artifacts
- **token_profiler:** add Run 14 integration tests and profile artifacts
- **token_profiler:** add Holtz profiler plugin with phase detection and 24 tests
- **token_profiler:** add Holtz profiler plugin with phase detection and 24 tests
- **token_profiler:** add cyberpunk HTML viewer with 5 interactive views
- **token_profiler:** add cyberpunk HTML viewer with 5 interactive views
- **token_profiler:** add CLI module with arg parsing, plugin loading, and pipeline orchestration
- **token_profiler:** add CLI module with arg parsing, plugin loading, and pipeline orchestration
- **token_profiler:** add markdown report generation with 33 tests
- **token_profiler:** add markdown report generation with 33 tests
- **token_profiler:** add pricing module with model lookup and cost computation
- **token_profiler:** add pricing module with model lookup and cost computation
- **token_profiler:** add analysis pipeline (stages 2-5) with 36 tests
- **token_profiler:** add analysis pipeline (stages 2-5) with 36 tests
- **token_profiler:** add JSONL extraction module with 39 tests
- **token_profiler:** add JSONL extraction module with 39 tests
- **token_profiler:** add package scaffold, data models, and plugin protocol
- **token_profiler:** add package scaffold, data models, and plugin protocol
- **scripts:** add session-to-cast.py for any Claude Code session
- **scripts:** add session-to-cast.py for any Claude Code session
- **skill:** dispatch subagent for architecture baseline update post-convergence
- **agents:** add merge-agent for deterministic punchlist merging
- **skill:** use filtered punchlist reads in Phases 4-6 convergence loop
- **scripts:** add CLI for compact brief, update skill subagent briefs
- **scripts:** add --filter-status, --resolved-before, --render CLI flags
- **scripts:** set structured as default compact format (empirical eval deferred)
- **scripts:** add render_items for filtered punchlist markdown output
- **skill:** update Justine dispatch prompt for inherited recon mode
- **scripts:** implement three candidate compact formats for pattern brief
- **skill:** add inherited recon mode to Justine for parallel dispatch
- **scripts:** add filter_items with status and recency filtering
- **scripts:** add pattern brief parser for compact output
- **scripts:** add resolution_order tracking to PunchlistItem
- add public-contract lens and CI recon step
- **lenses:** add temporal-protocol lens
- **lenses:** add semantic-fidelity lens

### Fixed
- **enforcement:** bump sahjhan version pin from 0.5.0 to 0.6.1
- **enforcement:** add settings.local.json.example for dev-mode setup
- **tests:** skip settings.local.json test when file not present
- **enforcement:** switch all hooks from sahjhan_binary to ensure_sahjhan
- **enforcement:** use ensure_sahjhan in bootstrap hook for auto-download
- **enforcement:** fix test isolation and lint in bootstrap tests
- **enforcement:** replace rowid with seq in iteration_boundary gate SQL
- **enforcement:** gate iteration_boundary on pattern analysis after 3+ fixes
- **docs:** remove exact LOC count from README prose to stop recurring drift
- **docs:** update test count and LOC in README badge and prose
- **hooks:** block brace expansion in read guard glob detection
- **hooks:** block glob patterns that bypass read guards for session.key
- **hooks:** detect suffixed sleep notation in gaming detector
- **tests:** replace or-disjunction with specific additionalContext assertion
- **tests:** make profiler integration test path configurable via env var
- **hooks:** handle env-prefix git commits and bare sahjhan binaries
- **scripts:** extract shared _longest_prefix_match in pricing.py
- **enforcement:** reject empty-section merge reports
- **docs:** update prediction accuracy from 65%/38% to ~69%/~45%
- **hooks:** deduplicate platform triple into _resolve.platform_triple
- **hooks:** narrow _get_session_key_path exception handler
- **tests:** add badge URL validation to README metrics test
- **hooks:** anchor _ANSWERS_RE to reject fence opener lines
- **hooks:** derive stop_gate allow-list from principle, not ad-hoc
- **hooks:** also allow stop from recon state
- **hooks:** allow stop from idle state for clean between-run exits
- **hooks:** skip manifest verify for sahjhan commands in bash_guard
- **hooks:** token-match sahjhan subcommands, deduplicate managed file lists
- **hooks:** require all segments be sahjhan in is_sahjhan_cmd
- **docs:** correct README run count, line count, and circuit breaker claims
- **skill:** correct Phase Index state names and CLI examples
- **hooks:** close bash write bypass, add curl/wget coverage, mask fenced blocks in quiz
- **hooks:** wire _sahjhan_bootstrap to Bash PreToolUse matcher
- **tests:** replace rubber stamp assertions with value checks in test_lists_sessions
- **skill:** add required fields to SKILL.md CLI examples
- **docs:** update stale README badges and line counts
- **scripts:** correct has_unclosed_fence false positive on closing-fence-at-EOF
- **tests:** remove 10 tautology tests from hook test suite
- **enforcement:** narrow broad exception in _read_perspectives_total
- **ci:** enforce 60% coverage gate in CI matching local requirement
- **hooks:** extend subagent findings check to match .json/.jsonl/.toml/.txt
- **enforcement:** distinguish score_answers count mismatch from all-stale
- **enforcement:** harden Bash write guard against bypass vectors
- **enforcement:** symbol-anchored quiz freshness check
- **enforcement:** pass ledger to _get_session_key_path for correct HMAC key
- **docs:** update badge test count from 817 to 847
- **enforcement:** case-insensitive bash guard for read-protected paths
- **enforcement:** populate cache perspective from parse_status_text
- **enforcement:** three component-lens fixes from Run 26 sweep
- **enforcement:** guard per-ledger session keys from agent read access
- add missing pytest import in test_sahjhan_integration.py
- **enforcement:** block sed -i, perl -pi, and patch writes to protected paths
- **test:** remove bare except KeyError in 200-node round-trip test
- **enforcement:** prevent is_git_commit false positives on echo/comments
- **test:** rename misleading rubber-stamp test and add keyword check test
- **enforcement:** show correct error for answer count mismatch in lens quiz
- **enforcement:** reject unknown severity values in check_severity_change.py
- **enforcement:** count only post-sweep file reads in check_sweep_evidence.py
- **enforcement:** guard record_authed_event calls in lens_quiz.py against missing session key
- **enforcement:** active-run marker must use full ledger name, not template name
- **enforcement:** fix ledger_template resolution for STATUS.md and PUNCHLIST.md renders
- **docs:** update stale README metrics and run counts
- **enforcement:** reject null bytes in HMAC event proof fields
- resolve ruff lint violations from Phase 1 implementation
- **enforcement:** unconditional commit blocking in fix_loop state
- **enforcement:** use authenticated events for context_reset in primer
- **tests:** resolve ruff lint violations in new test files
- **enforcement:** primer injects binary path and active ledger
- **enforcement:** hard-block commits when pattern analysis overdue
- **docs:** update badge URL to match 774 test count (PAT-005)
- **enforcement:** update quiz-bank entry for _REQUIRED_NODE_KEYS (BH-017)
- **enforcement:** extract current_perspective from sahjhan status output (BH-018)
- **scripts:** add 'id' to ImpactGraph._REQUIRED_NODE_KEYS (BH-017)
- **enforcement:** invert SEC-007 transcript format detection logic (BH-016)
- **docs:** correct fabricated prediction accuracy stats and Run 1 narrative (BH-014, BH-015)
- **enforcement:** parse available transitions from sahjhan status output (BH-013)
- **enforcement:** eliminate bootstrap Bash redirect false positives (BH-008)
- **tests:** resolve Justine merge findings BH-009 BH-010
- **tests:** resolve 7 Holtz Run 25 findings
- restore dev-mode hook registration in install-hooks.sh
- remove dev-mode enforcement hooks and coverage from default pytest
- **tests:** fix mock binary tests using file-based status output
- **enforcement:** replace hand-rolled TOML parser with tomllib
- **enforcement:** deterministic quiz selection and cp/mv bypass guard
- **enforcement:** guard against missing answer key and empty options
- **tests:** replace source-string matching tests with behavioral tests
- **docs:** update stale README numeric claims
- **enforcement:** correct stale --json references in hook docstrings
- **tests:** update quiz integration test to JSONL transcript format
- **audit:** resolve Run 24 findings BH-001 BH-002 BH-004 BH-005 BH-006 BH-007 BH-009 BH-010 BH-011
- **enforcement:** amend detection, substring bypass, quiz shuffle, json parsing, encoding
- **enforcement:** parse JSONL transcript format in lens_evidence (BH-029)
- **enforcement:** pattern advisory gate, stale quiz edge case, evidence test format (CON-002, CON-003)
- **profiler:** fix _inject_computed_properties JSON path, add encoding (BUG-COMP-001, DF-002, DF-006)
- **enforcement:** guard plugin loader, active_ledger TOCTOU, quiz dedup (F-EP-001, CON-003, IDP-001)
- **enforcement:** read perspectives_total from protocol.toml (BH-019)
- **enforcement:** guard Bash redirections to protected paths (BH-016)
- **tests:** add value assertions to TestSectionsPresent tests (BH-010)
- **hooks:** add CRLF normalization to mask_fenced_blocks (BH-015)
- **docs:** update README "What's inside" counts (BH-004)
- **enforcement:** fix substring match in is_git_commit, empty freshness bypass (BH-013, BH-014)
- **enforcement:** exclude TDD commands from stall counter (BH-012)
- **enforcement:** narrow lens_evidence filter to docs/ and quiz-bank only (BH-007)
- **enforcement:** add encoding=utf-8 to all open() calls (PAT-006)
- **docs:** update README metrics after Run 23 audit (BH-001, BH-002, BH-003)
- **profiler:** wire --pricing FILE through to pricing pipeline (BH-011)
- add encoding=utf-8 to extract.py _read_jsonl open()
- **docs:** update README metrics after Run 22 audit
- **enforcement:** path detection, atomic cache write, assert safety
- **enforcement:** use path component matching in lens_evidence filter
- **enforcement:** read event dict in stop_gate.py for correct cwd
- **enforcement:** accept 1-5 quiz answers, validate length in score_answers
- **enforcement:** resolve mypy errors in lens_quiz.py
- resolve _common import collision in test suite, update README metrics
- **docs:** update README metrics after parallel task completion
- **enforcement:** workaround filter template gap in lens_rotate gate
- **enforcement:** workaround template interpolation gaps in gates
- **tests:** add mock-binary tests for enforcement hooks (BH-010)
- **enforcement:** add missing hooks to dev-mode settings, update baseline
- **docs:** update README metrics after enforcement hooks
- **tests:** unconditional assertion, machine_specific marker, pytest config
- **migration:** add fence masking and fix greedy regex in migrate_legacy.py
- **docs:** update README hooks section, counts, badges, and architecture baseline
- **enforcement:** remove CLAUDE_PLUGIN_ROOT from gates, fix mypy duplicate module
- **enforcement:** correct primer CLI arg format, fix PermissionError in all hooks
- **enforcement:** correct bash_guard CLI arg format and add required fields
- **enforcement:** narrow write_guard to managed files only, fix path prefix collision
- **enforcement:** resolve BH-002 and BH-005 — fix gate cmd paths and syntax
- **enforcement:** resolve BH-003 and BH-006 — upgrade to sahjhan v0.1.1, rewrite templates
- **enforcement:** resolve BH-001, BH-004, BH-007 from shakedown Run 21
- **enforcement:** align TOML config with Sahjhan v0.1.0 type system
- **profiler:** inject computed @property fields into profile.json
- **profiler:** pass milestones to subagent session profiles
- **viewer:** rename Turn Table column from "Remaining" to "Context"
- **impact-graph:** replace error sentinel dicts with proper exceptions
- **convergence:** count_items raises FileNotFoundError instead of sys.exit
- update README reference docs count from 17 to 18
- update README counts for new patterns and lenses
- resolve remaining punchlist items from Run 18 audit
- **hooks:** align mask_fenced_blocks with CommonMark spec
- update remaining old recon file paths in punchlist formats
- **skill:** add rationalization red flag for rapid-fire convergence gaming
- **scripts:** reject rapid-fire convergence checker calls (60s minimum between iterations)
- **scripts:** remove unused masked_lines variable in parse_brief
- **hooks:** track fence character count in mask_fenced_blocks for CommonMark compliance
- **scripts:** use line-based extraction in parse_brief to fix offset divergence
- resolve 9 defects found in Holtz run 15 audit
- replace commit-msg hook with post-commit for reliable version bumping
- resolve ruff lint errors in merge-session-cast.py
- resolve ruff lint errors in merge-session-cast.py
- pass full test suite, lint, and type checks
- pass full test suite, lint, and type checks
- remove hardcoded paths, fix ruff lint errors
- remove hardcoded paths, fix ruff lint errors
- **hooks,scripts:** document path matching design, distinguish stall vs regress
- **hooks,scripts:** document path matching design, distinguish stall vs regress
- **tests:** expand README metrics test to validate all 9 fields
- **tests:** expand README metrics test to validate all 9 fields
- **scripts:** mask code fences and fix \s regex in parse_brief
- **scripts:** mask code fences and fix \s regex in parse_brief
- **plugin:** resolve 4 audit findings from Holtz run 13

### Changed
- **enforcement:** remove old hooks replaced by Sahjhan enforcement
- **skill:** implement Phase 2 token optimizations
- **skill:** route Step 7/8 audit subagents to Sonnet
- **skill:** add ENABLE_TOOL_SEARCH guidance to Context Survival Protocol
- **skill:** add tool call batching and terse narration directives
- **references:** trim merge-protocol.md to rules-only, cross-reference examples

### Documentation
- update changelog version to 0.73.5
- add v0.73.3 release notes
- add Sahjhan enforcement engine design specs and plans
- add Run 25 post-mortem and enforcement hardening design spec
- case study — AI agent auditing its own code and designing enforcement against itself
- lens enforcement implementation plan
- lens enforcement design spec
- protocol enforcement implementation plan — 8 tasks, TDD
- protocol enforcement design spec — state-driven pacing hooks
- implementation plans for sahjhan v0.2.0 and holtz JSONL migration
- JSONL + DataFusion design specs for sahjhan v0.2.0 and holtz migration
- Sahjhan shakedown Run 21 — 7 findings from first enforced audit
- complete Run 20 post-convergence — SUMMARY, baseline, living punchlist
- fix Task 11 title — patterns are auto-discovered at runtime
- add Issue #5 implementation plan
- address spec review findings for Issue #5 design
- add Issue #5 lens/pattern integration design spec
- add consolidated-additions design spec and implementation plan
- add convergence enforcement design spec and Run 18 post-mortem
- update showcase and profiling playbook to step numbering
- update README to step numbering
- address plan review findings — add convergence hooks, missing tests
- add implementation plan for flattening step numbering
- address spec review findings for flatten-steps design
- add design spec for flattening phase numbering to Step 0-20
- add release workflow plan and design spec
- fix overstated prediction accuracy and add Run 15 narrative
- add community docs and GitHub templates
- update README test and line counts
- update README test and line counts
- add CLAUDE.md with branch model and release workflow
- add CLAUDE.md with branch model and release workflow
- add merged asciinema cast of GPU race discovery session
- add merged asciinema cast of GPU race discovery session
- add Holtz bug-hunting showcase and GPU race case study
- add Holtz bug-hunting showcase and GPU race case study
- add token profiling analysis playbook and optimization plans
- add token profiling analysis playbook and optimization plans
- add token profiling playbook for standalone session profiling
- add token profiling playbook for standalone session profiling
- add token profiler design spec and implementation plan
- add token profiler design spec and implementation plan
- fix walkthrough token counts to match session logs
- fix walkthrough token counts to match session logs
- **readme:** add run 14 asciinema recording and walkthrough link
- **readme:** add run 14 asciinema recording and walkthrough link
- tokens only in .cast (no costs), append full SUMMARY.md
- tokens only in .cast (no costs), append full SUMMARY.md
- add design doc for terminal output improvements
- add design doc for terminal output improvements
- condense asciinema to Claude Code collapsed view
- condense asciinema to Claude Code collapsed view
- replace synthesized asciinema with real session history
- replace synthesized asciinema with real session history
- replace estimated token counts with real data from session logs
- replace estimated token counts with real data from session logs
- add run 14 showcase — asciinema, walkthrough, and diagram
- add run 14 showcase — asciinema, walkthrough, and diagram
- complete Holtz run 14 — 8 findings, all resolved
- complete Holtz run 14 — 8 findings, all resolved
- remove 9 orphan nodes from impact graph
- remove 9 orphan nodes from impact graph
- update impact graph for current codebase state
- update impact graph for current codebase state
- **readme:** update for v0.4.0 — new lens descriptions, inherited recon, run 13
- add implementation plans for token context optimizations
- **scripts:** update validate_punchlist.py usage docs for filter flags
- **skill:** add merge-examples.md to references list
- **agents:** update Justine agent definition for inherited recon
- **references:** extract merge protocol worked examples to separate file
- update README and diagrams for 9-lens registry

### Infrastructure
- untrack .claude/settings.local.json
- gitignore bootstrap artifacts and add implementation plan
- commit run 30 holtz state and archived runs
- **hooks:** add in-process tests for subagent_findings_check coverage
- **enforcement:** add live quiz bank validation test (BH-017)
- **enforcement:** add lens quiz integration tests
- **enforcement:** add integration tests for protocol pacing
- add enforcement/hooks/ to mypy check paths (E13)
- **enforcement:** add Sahjhan integration tests, update hook tests for cutover
- **integration:** add gate↔canonical parser agreement test
- archive run 17 and update run 18 audit state
- update integration test to step-based label assertions
- update hook tests to step numbering
- run 17 audit state — incomplete, see post-mortem
- update run 16 audit state and recon artifacts
- archive run 15 audit artifacts
- add .coverage to .gitignore
- add release workflow for automatic tagging and GitHub Releases
- add release workflow for automatic tagging and GitHub Releases
- add dev branch to CI triggers
- add dev branch to CI triggers
- add install-hooks script for git hook setup
- add install-hooks script for git hook setup
- remove .claude/ from git tracking
- **scripts:** add CI-safe structural tests for compact formats

## [0.73.5] - 2026-03-30

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

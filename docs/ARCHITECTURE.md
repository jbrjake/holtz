# Holtz Architecture

> v0.132.13 — Last verified: 2026-04-14

Holtz is a Claude Code plugin that audits codebases with TDD-driven bug hunting. Two auditors, 13 analytical lenses, a state machine to keep everyone honest. It keeps coming back until the codebase converges. It will steal your joy.

This is the map. What Holtz can do, where to find things, what still needs building.

---

## The 30-second version

Holtz (depth-first, methodical) and Justine (breadth-first, aggressive) independently audit a codebase. A merge agent reconciles their findings. Holtz fixes every item with TDD, rotating through 13 analytical lenses, until the codebase passes clean from all perspectives. A state machine (Sahjhan) enforces the protocol because the auditor will absolutely skip steps if you let it.

```
                ┌──────────┐
                │  idle    │
                └────┬─────┘
                     │ run_start
                ┌────▼─────┐      ┌───────────────┐
                │  recon   │─────►│ Justine        │
                └────┬─────┘      │ (parallel)     │
                     │             └───────┬───────┘
                ┌────▼─────┐               │
                │  audit   │               │
                └────┬─────┘               │
                     │                     │
                ┌────▼─────┐    ┌──────────▼──┐
                │  merge   │◄───│ merge-agent  │
                │  ready   │    │ (sonnet)     │
                └────┬─────┘    └─────────────┘
                     │ merge_complete
                ┌────▼──────┐
                │ merge_done│
                └────┬──────┘
                     │ fix_loop_start
                ┌────▼──────────┐
                │ awaiting_clear│◄─── iteration_boundary (mid-loop, from fix_loop)
                └────┬──────────┘
                     │ resume (after /clear)
                ┌────▼──────┐
            ┌──►│ fix_loop  │
            │   └──┬───┬────┘
            │      │   │
            │      │   └──► pattern_analysis ────┐
            │      │                              │
            │   ┌──▼──────────────┐               │
            │   │ perspective_    │──► lens_rotate ──► audit
            │   │ clean           │         (next lens)
            │   └──┬──────────────┘
            │      │ (all 13 done)
            │   ┌──▼──────────────────┐
            │   │ all_perspectives_   │
            │   │ clean               │
            │   └──┬──────────────────┘
            │      │
            │   ┌──▼──────────────┐
            │   │ final_sweep     │
            │   └──┬──────┬───────┘
            │      │      │ (dirty)
            │      │      └───────────────────────┘
            │      │ (clean)
            │   ┌──▼──────────────────┐
            │   │ final_sweep_clean   │
            │   └──┬──────────────────┘
            │      │ converge
            │   ┌──▼──────────────┐
            └───│ converged       │
                └──┬──────────────┘
                   │
                ┌──▼──────────────┐
                │ finalized       │
                └─────────────────┘
```

---

## Agents

Three agents. Two have opinions about your code.

| Agent | Model | Role | Definition |
|-------|-------|------|------------|
| **Holtz** | opus | Primary auditor. Depth-first, methodical. Traces causal chains through three abstraction layers while the obvious bug sits in the next file over. | `agents/holtz.md` |
| **Justine** | opus | Secondary auditor. Breadth-first, fast. Kicks doors instead of picking locks. Finds what Holtz walks past. | `agents/justine.md` |
| **merge-agent** | sonnet | Punchlist merger. No opinions. Classifies findings as agreement/Holtz-only/Justine-only/contradictory and moves on. | `agents/merge-agent.md` |

Holtz and Justine run in parallel during the audit phase. They write to separate directories (`docs/holtz/` and `docs/holtz/justine/`), maintain separate impact graphs, and don't talk to each other. The merge agent reconciles their findings after both finish.

Justine's full methodology lives in `skills/holtz/references/justine-skill.md` (32KB). Her backstory is at `skills/holtz/references/justine-backstory.md`. The backstory is load-bearing, not decoration. It drives her behavioral design: aggressive severity, value-checking tests, breadth-first scanning.

---

## Audit lifecycle

The audit has 21 steps (0-20) across 6 phases. Each phase has its own reference file so the auditor only loads what it needs for the current state.

| Phase | Steps | Sahjhan States | Reference | What Happens |
|-------|-------|----------------|-----------|--------------|
| Recon | 0-4 | `idle` → `recon` | `phase-recon.md` | Map the codebase. Build impact graph. Generate predictions. Dispatch Justine. |
| Audit | 5-8 | `audit` | `phase-audit.md` | Verify doc claims. Audit test quality against 18 anti-patterns. Adversarial code review through 13 lenses. |
| Merge | 9 | `merge_ready` → `merge_done` | `phase-merge.md` | Merge-agent reconciles Holtz + Justine punchlists. Produces unified worklist. |
| Fix Loop | 10-14 | `fix_loop`, `awaiting_clear`, `pattern_analysis`, `perspective_clean` | `phase-fix-loop.md` | Mandatory `/clear` before the first fix (`fix_loop_start` → `awaiting_clear` → `resume`). Each fix is delegated to a subagent (investigation + authoring); the orchestrator applies/commits/records. TDD cycle: failing test → minimal fix → hardening → blast radius → pattern analysis. Per lens. |
| Convergence | 15-16 | `all_perspectives_clean` → `final_sweep` → `final_sweep_clean` | `phase-convergence.md` | Final sweep across all lenses. If dirty, back to fix loop. If clean, converge. |
| Finalize | 17-20 | `converged` → `finalized` | `phase-finalize.md` | Update architecture baseline, living punchlist, pattern library. Write summary. |

All reference files live in `skills/holtz/references/`.

---

## The enforcement layer (Sahjhan)

Sahjhan is a daemon-based state machine and event ledger. Its job is preventing the auditor from skipping steps. The auditor has been remarkably creative about skipping steps.

The protocol is defined across several TOML files in `enforcement/`:

| File | What It Does |
|------|-------------|
| `transitions.toml` | State machine transitions with gates (SQL queries, file checks, command checks) |
| `events.toml` | Event type schemas for the ledger |
| `states.toml` | Valid audit states and attributes |
| `protocol.toml` | Obligation markers (TDD gate, pattern checks) |
| `hooks.toml` | Hook rules for pre/post tool use |
| `renders.toml` | Output formatting for status renders |
| `trusted-callers.toml` | Authorization for daemon commands |

**How it works in practice:** Every audit action emits an event to a JSONL ledger. State transitions have gates: SQL queries against the ledger, file existence checks, shell command checks. If a gate fails, the transition is blocked. You cannot declare convergence without having done the work.

Example gate from `transitions.toml` (the fix_commit transition):

```toml
{ type = "ledger_has_event_since", event = "blast_radius",
  since = "last_transition",
  intent = "blast radius must be checked after each fix" }
```

Translation: you cannot commit a fix unless you ran blast radius analysis first. This gate exists because Run 19 had zero blast radius queries across an entire audit.

### Suite evidence

Four gates need "the test suite passes" to be true. Running the suite to find out is the obvious implementation and the expensive one — the fix loop used to run it three times per finding, ~4.7 hours across a 90-fix audit.

Instead, `enforcement/scripts/verify_suite.py` runs the suite **once** and records a restricted `suite_green` event carrying a hash of the working tree. The gates recompute that hash and read the ledger, so they are predicates rather than second executions.

Two mechanisms, and the difference between them is the safety argument:

- **The tree hash is an integrity claim.** It is content-addressed (the git tree oid), so `git commit` cannot invalidate a green it did not change — that is what collapses three runs to one. The agent cannot forge it: the event is `restricted`, the writer sits on a managed path, its SHA-256 is pinned in `trusted-callers.toml`, and it accepts no caller-supplied hash or result.
- **Impact-graph test selection is only a cost optimisation.** `--scope affected` runs the tests the graph says cover what changed, but the graph is agent-authored, so a bogus edge could narrow one `fix_commit`. It cannot survive the next `iteration_boundary`, which accepts `full` and nothing else. Every uncertainty in the selection — an unmapped file, a `conftest.py`, an empty collection — widens back to the full suite.

Full design, including the racy-index trap in the hash and the per-file widening rules: [docs/design/suite-evidence.md](design/suite-evidence.md).

### Enforcement hooks

Python hooks in two locations:

**Plugin hooks** (`hooks/`): Registered in `hooks/hooks.json`, run by Claude Code's hook system.

| Hook | Event | Purpose |
|------|-------|---------|
| `_daemon_lifecycle.py` | PreToolUse | Detects daemon death, terminates audit. Matcher: `Bash\|Write\|Edit\|NotebookEdit`. Read-only tools and recovery commands (`sahjhan daemon start/stop`) pass through so the session remains usable for diagnosis. |
| `_sahjhan_bootstrap.py` | PreToolUse | Protects enforcement infrastructure from modification |
| `pre_tool_hook.py` | PreToolUse | Managed-path guard, TDD gate |
| `commit_gate.py` | PreToolUse | Blocks commits with pending obligations |
| `post_tool_hook.py` | PostToolUse | Auto-records tool use events |
| `bash_guard.py` | PostToolUse | Verifies managed files weren't modified outside Sahjhan |
| `protocol_tracker.py` | PostToolUse | Tracks git commits and sahjhan commands |
| `quiz_capture.py` | PostToolUse | Trusted courier: stages lens-quiz questions into the daemon vault (#73) |
| `suite_courier.py` | PostToolUse | Trusted courier: records `suite_green` for a `verify_suite.py --record` the host reports succeeded. The suite runs inside the sandbox and cannot reach the daemon; this hook runs outside it and derives `tree_hash`, `commit_hash` and `scope` itself |
| `subagent_findings_check.py` | SubagentStop | Validates subagent output files exist |
| `lens_quiz.py` | SubagentStop | Three-phase lens validation (evidence → quiz → score) |
| `stop_hook.py` | Stop | Blocks stop in non-terminal states |
| `sandbox_control.py` | UserPromptSubmit | `holtz-start` / `holtz-stop`: starts the daemon with its socket outside the project tree, then raises or lowers the Claude Code sandbox that is the audit's actual boundary. Exact match on the whole prompt, so only a human can reach it |
| `primer.py` | UserPromptSubmit | Injects resume context; probes daemon liveness and caller auth |
| `session_start.py` | SessionStart | Records `context_reset` when `source` is `clear`, `compact`, or `startup` — the only writer of the event that gates `awaiting_clear -> fix_loop` (#79) |

**Enforcement hooks** (`enforcement/hooks/`): The Python modules that implement the logic above.

| Module | Purpose |
|--------|---------|
| `_protocol_cache.py` | Enforcement state cache, `is_enforcement_fresh()`, shell segment parsing |
| `_resolve.py` | Sahjhan binary download/verification. `SAHJHAN_VERSION` is the single source of truth for the pin, with a SHA256 per platform; `scripts/check_sahjhan_pin.py` gates it |
| `lens_evidence.py` | Validates subagent actually read files and found keywords |

---

## Scripts

Python scripts in `skills/holtz/scripts/`. stdlib only, no external dependencies.

| Script | Purpose | Tests |
|--------|---------|-------|
| `boundary_check.py` | Recon's first command: reports whether this shell can reach the daemon socket. Probes the fact rather than an env var — `CLAUDE_CODE_SANDBOXED` is an input Claude Code reads, not one it sets inside sandboxed commands. | `test_boundary_check.py` |
| `quiz_stage.py` | Stages one lens-quiz question during recon by printing a marker `quiz_capture.py` collects; never touches the vault itself. | `test_quiz_stage.py` |
| `validate_punchlist.py` | Validates punchlist format, fields, severity. Supports `--filter-status`, `--resolved-before`, `--render` for filtered reads during convergence. | `test_validate_punchlist.py` |
| `impact_graph.py` | Knowledge graph for code entity relationships. 10 operations: add/prune nodes+edges, blast_radius (bidirectional BFS), risk_hotspots, drift_check. | `test_impact_graph.py` (81 tests) |
| `convergence_check.py` | Parses punchlist status counts, detects test runner output, tracks convergence. | `test_convergence_check.py` |
| `parse_lens_registry.py` | Extracts lens definitions from `lens-registry.md`. Classifies per-file vs cross-file scope. | `test_parse_lens_registry.py` |
| `pattern_brief_compact.py` | Compresses pattern library into compact briefs for subagent consumption. Three formats: oneliner, twoliner, structured. | `test_pattern_brief_compact.py` |
| `markdown_utils.py` | Code fence masking (CommonMark-compliant, handles nested fences). Prevents phantom items from code examples in punchlists. | `test_markdown_utils.py` |
| `profiler_plugin.py` | Token profiler plugin for session analysis. Step detection for Holtz phases. | `test_token_profiler_plugin.py` |

---

## Analytical lenses

13 lenses in `skills/holtz/references/lens-registry.md`. Each defines Focus, Scope (per-file or cross-file), Audit priorities, Failure modes, and Entry point.

Default 6 (every audit):

| Lens | Scope | What It Looks For |
|------|-------|-------------------|
| component | per-file | Internal correctness of individual modules |
| integration | cross-file | Assumption mismatches at module boundaries |
| security | per-file | Input validation, injection, auth bypass |
| error-propagation | cross-file | Error handling chains, swallowed exceptions |
| data-flow | cross-file | Data transformation correctness across layers |
| contract | per-file | API contract violations, type mismatches |

Extended lenses (7 more):

| Lens | Scope | What It Looks For |
|------|-------|-------------------|
| semantic-fidelity | cross-file | Naming vs actual behavior mismatches |
| temporal-protocol | cross-file | Ordering dependencies, lifecycle violations |
| public-contract | cross-file | Published API surface stability |
| concurrency | cross-file | Race conditions, shared mutable state |
| resource-lifecycle | per-file | Leaks, dangling handles, cleanup failures |
| idempotency | per-file | Non-idempotent operations that should be |
| observability | per-file | Missing logging, metrics, error attribution |

Per-file lenses run during initial file audits (Steps 7-8). Cross-file lenses get dedicated parallel subagents. Step 14 (lens sweep) does gap-fill for covered lenses and full sweeps for uncovered ones.

The lens quiz system exists because subagents will rubber-stamp "looks fine" if nobody checks. During recon a generation subagent derives per-lens questions from the impact graph and stages them, one at a time, through a trusted courier (`quiz_capture.py`) into the sahjhan daemon's in-memory **vault** — never to disk (the ledger is `cat`-readable, so on-disk answers would leak). The `quiz-bank` vault key is `writable_in_states = ["recon"]` (`enforcement/vault.toml`), so the daemon slams the staging channel shut at `recon_complete`; the `recon_complete` gate requires `quiz_bank_generated`, so you cannot leave recon without a bank. On a later lens sweep — after a `/clear` has wiped the graph and answers from context — `lens_quiz.py` reads the vault and quizzes the subagent, which must actually re-read the code to answer. The protection is temporal integrity, not answer secrecy from the recon author. See issue #73.

---

## Pattern library

16 bug patterns in `skills/holtz/patterns/`. Each has detection heuristics, code examples, and grep commands. Language-tagged, reusable across projects.

Current patterns: dual-parser-divergence, regex-newline-leak, doc-spec-drift, code-fence-unaware-parsing, missing-edge-case-handling, incomplete-layer-isolation, resource-leak, uncontrolled-amplification, error-destruction, cache-coherence-failure, silent-semantic-mismatch, implicit-ordering-dependency, dead-code-latent-path, concurrency-violation, cross-language-dead-interface, numeric-precision-exhaustion.

New patterns are contributed through `references/pattern-contribution-protocol.md`. A compact brief (`docs/holtz/patterns-brief.md`) is generated for subagent consumption via `pattern_brief_compact.py`.

18 test anti-patterns in `references/anti-patterns.md`, tiered by severity (actively harmful → false security → missed opportunities).

---

## Runtime artifacts

Everything Holtz produces goes in `docs/holtz/` in the target project:

```
docs/holtz/
├── recon/                    # Steps 0-4 output
│   ├── step0-project-overview.md
│   ├── step1-toolchain.md
│   ├── step2-code-signals.md
│   ├── step3-recon-summary.md
│   └── 0h-predictions.md    # Predictive recon output
├── audit/                    # Steps 6-8 output
├── justine/                  # Justine's parallel output
│   ├── recon/
│   ├── STATUS.md
│   └── PUNCHLIST.md
├── impact-graph.json         # Knowledge graph (persists across runs)
├── architecture-baseline.md  # Structural snapshot (persists)
├── LIVING-PUNCHLIST.md       # Cross-run vulnerability model
├── patterns-brief.md         # Compact pattern summary
├── STATUS.md                 # Current run state (rendered by Sahjhan)
├── PUNCHLIST.md              # Current run findings (rendered by Sahjhan)
├── PUNCHLIST-MERGED.md       # Post-merge unified worklist
├── MERGE-REPORT.md           # Merge statistics
├── SUMMARY.md                # Final audit report
└── archive/                  # Historical runs (JSONL ledgers)
```

STATUS.md and PUNCHLIST.md are **read-only** — rendered from the Sahjhan ledger. Direct writes are blocked.

---

## File layout

```
holtz/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── agents/
│   ├── holtz.md              # Primary auditor agent
│   ├── justine.md            # Secondary auditor agent
│   └── merge-agent.md        # Punchlist merger agent
├── skills/holtz/
│   ├── SKILL.md              # Main skill (rigid, 281 lines)
│   ├── references/           # 24 reference docs (phase procedures, formats, protocols)
│   ├── patterns/             # 16 bug pattern files
│   ├── scripts/              # 7 Python scripts
│   └── examples/             # Sample punchlist
├── hooks/
│   ├── hooks.json            # Hook registration
│   ├── _common.py            # Shared utilities
│   ├── subagent_findings_check.py
│   └── ... (see Enforcement Hooks table)
├── enforcement/
│   ├── transitions.toml      # State machine
│   ├── events.toml           # Event schemas
│   ├── states.toml           # State definitions
│   ├── protocol.toml         # Obligations
│   ├── hooks.toml            # Hook rules
│   ├── renders.toml          # Output formatting
│   ├── trusted-callers.toml  # Daemon auth
│   ├── hooks-manifest.json   # Required hooks registry
│   ├── quiz-bank.json        # Lens validation questions
│   ├── templates/            # Tera templates for rendered files
│   ├── hooks/                # Enforcement Python modules
│   └── scripts/              # Enforcement utilities
├── scripts/
│   ├── generate-changelog.py     # Changelog from conventional commits
│   ├── contract_gate.py          # Skill-to-hook contract verification
│   ├── refresh_hook_schema.py    # Hook output schema generator
│   ├── pre-release-check.sh      # Pre-release gate (ruff, mypy, tests, coverage, smoke)
│   ├── install-hooks.sh          # Git hook installer + settings.local.json setup
│   ├── check_contract_test_sync.sh # CI gate: skill changes need contract test updates
│   ├── smoke-test-hooks.sh       # Hook JSON validation via Claude CLI
│   ├── vendor-sahjhan.sh         # Binary vendoring
│   ├── session-to-cast.py        # Session → asciinema conversion
│   ├── migrate_legacy.py         # Legacy archive migration
│   ├── hash-trusted-callers.sh   # Compute SHA256 hashes for trusted-callers.toml
│   ├── holtz_split_session.sh    # Session splitting orchestrator
│   ├── capture_test_fixtures.sh  # Test fixture capture
│   └── token_profiler/           # Token profiling toolkit (7 modules)
├── tests/                        # 55 test files
└── docs/
    ├── ARCHITECTURE.md       # You are here
    ├── holtz/                # Runtime artifacts (see above)
    ├── design/               # Design docs
    ├── research/             # Convergence data and analysis
    ├── superpowers/
    │   ├── plans/            # Implementation plans
    │   └── specs/            # Design specs
    ├── case-studies/         # External codebase audit case studies
    ├── diagrams/             # SVG/DOT diagrams
    ├── incidents/            # Containment breach postmortems
    └── runs/                 # Session recordings and walkthroughs
```

---

## Test suite

55 test files. Quick run (no coverage):

```bash
python -m pytest
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Full run with coverage gate:

```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=80
```

Coverage runs only from the main agent session. Concurrent pytest processes (subagents, parallel sessions) deadlock on the `.coverage` SQLite file.

---

## Cross-harness compatibility

Holtz is a Claude Code plugin, but the architecture is portable. The skill, patterns, reference docs, and seed patterns are markdown. The scripts are standalone Python. The enforcement hooks are shell scripts that call Python. None of it depends on Claude Code internals beyond the plugin loading convention.

**Cursor.** The skill markdown works as a `.cursorrules` file or project-level instruction. The hooks need adaptation — Cursor doesn't have a PreToolUse/PostToolUse hook system, so enforcement would move to the prompt layer. The scripts and patterns transfer unchanged.

**Codex CLI.** The skill works as an `AGENTS.md` instruction. Codex CLI supports tool-use patterns similar to Claude Code. The main gap is subagent dispatch — Justine's parallel audit would need to run as a separate Codex session rather than an inline subagent. The convergence loop, impact graph, and pattern library all work as-is.

**Other harnesses.** Any system that can (1) inject a system prompt, (2) run shell commands, and (3) read/write files can run the core audit loop. The enforcement hooks are the hardest part to port — they require event-driven gates that most harnesses don't support natively. Without hooks, the process still works but relies on advisory compliance, which is how Holtz ran for his first seven runs before the hooks existed. It works. It works less reliably.

---

Spec/plan implementation status and remaining work tracked separately in [SPEC-STATUS.md](SPEC-STATUS.md).

# Convergence-speed proposals — implementation status

**Spec:** [convergence-speed-proposals.md](convergence-speed-proposals.md) — read-only to
implementers; no status marker appears there except the five rows Jon struck himself.
**This file is the only status record.** Status attaches to the **clause**, not the item —
an item id is not a unit of work.
**D-numbers** refer to decisions in
`docs/superpowers/plans/2026-08-22-convergence-decisions.md` (untracked). **All 27 were
ruled by Jon on 2026-08-22**; that file records each ruling and the derived work queue.
Rows below describe the tree as committed — ruled-but-unimplemented work appears there,
not here, until it lands.

## Provenance

The spec text was restored on 2026-08-22 to the original recovered from session history
(single `Write`, 2026-08-18T15:09:15Z, session `9ffe4e86`), plus Jon's five
`REJECTED DO NOT IMPLEMENT!` rows (P4.3–P4.7) and a status line pointing here. The
previously committed copy had been edited by the implementing agent before its first
commit; the evidence is in `docs/superpowers/plans/2026-08-21-plan-deviation-audit.md`
and `2026-08-22-spec-restoration-handoff.md` (untracked by design), with a second
adversarial verification pass on 2026-08-22. The shipped P0.1 gate (`6b12186`) was
reverted in `e123a86`.

## Legend

| Marker | Meaning |
|---|---|
| SHIPPED | as written, or a trivially equivalent rendering; commit named |
| SHIPPED+ | clause as written, plus additions the plan did not ask for; the additions carry a D-number |
| DEVIATED | a different mechanism, trigger, or scope shipped; carries a D-number |
| OWED | not built |
| BLOCKED(x) | owed; cannot land before x |
| MOOT? | likely overtaken by later work; confirm via its D-number |
| REJECTED (Jon) | struck by Jon in the spec itself |
| WON'T DO (Jon) | ruled not to ship after implementation falsified its premise; the spec text is unchanged, so this is *not* REJECTED (Jon). Carries a D-number |
| N/A | out of scope per Jon's standing "ignore tqdm items" rule |
| — | not started |

## Tier 0

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P0.1 · amplification circuit-breaker (`A > 1.0` for 3 rounds, gate on `pattern_done`, block the next dispatch, escape = every open LOW **and** the MEDIUM budget, `sahjhan defer batch`, writes `DEFERRED.md`) | SHIPPED, all four clauses. Pin bumped to sahjhan 0.22.0 (`f9c46a1`); `[batches.defer]`, the `"defer batch"` alias and a `DEFERRED.md` render (`a2bd2c5`); `amplification_diverging` — `filed > resolved` since the *first* entry to `fix_loop`, per `pattern_analysis_complete`, over a three-round seq floor (`c620de7`); the `any_of` block on `pattern_done` with the escape as its second branch (`276cd11`). The escape predicate asserts the **budget spent**, not an empty MEDIUM set — the 50% cap makes the latter unreachable. `defer_low`/`defer_medium` are additionally declared `pattern_analysis → pattern_analysis`, per Jon's 2026-08-24 ruling: that state has no other exit, so without them the block named a command the run could not reach. Per D3 the escape is the only place deferral is taught | `f9c46a1`, `a2bd2c5`, `c620de7`, `276cd11` | D2, D3 |
| P0.1 · redefine convergence (4 conjuncts, as a package) | SHIPPED, all four as written, under D5. `all_findings_closed` is **removed** from `converge` — leaving it would keep the unreachable requirement and make the conjuncts decoration; a test fails the build if it returns. `all_critical_resolved` (resolved, **not** deferred), `all_user_reachable_high_closed` (resolved-or-deferred, population from P0.5's field, graded by latest filing per D25), `amplification_diverging expect=false` — the same object read the other way, and the conjunct the 08-21 session rejected by scoring it against the baseline this package removes — and a `file_exists` on `DEFERRED.md`. D5: `medium_deferral_budget expect="false"`, the same spelling `pattern_done`'s escape uses. Every conjunct's escape is `sweep_dirty`, the ungated `final_sweep → fix_loop` edge | `a745681` | D4, D5 |
| P0.1 · scope Step 16's resweep to files changed by fixes | SHIPPED+ (adds blast-radius depth 2 and a full-resweep fallback) | `f17aaec` | D23 |
| P0.2 · move pattern requirement from `fix_commit` to `iteration_boundary` | SHIPPED+ (the boundary already carried the gate; the change is the commit-path deletion; adds an unasked pattern gate on `set complete perspective`) | `5b0c4f0` | D24 |
| P0.2 · second conjunct: no round while >25 pattern-filed findings open **or** after two dry rounds | SHIPPED, both halves. Two-dry-rounds in `e1ed6c9` (seq-floor form); the >25-open half in `6f35730`. D6's note that `pattern_ids` made the population derivable is false — checked against every archived ledger, `pattern_ids` links to no finding, `predicted_by` is a prediction index, no finding was ever filed at `step=11`, and `siblings_found` carries no ids. Per the ruling's fallback branch and Jon's 2026-08-24 answer, `finding` gained an optional `pattern_id` taught in Step 11.2, joined to the rounds so an id counts only when that PAT appears in a courier-derived `pattern_ids` | `e1ed6c9`, `6f35730` | D6 |
| P0.2 · cap each round at ≤3 new items, with an obligation to close or merge at least as many as it opens | SHIPPED, both halves, on a new `merge_finding` transition. D7 requires the cap's escape to be guaranteed by construction and names it "the merge/close path"; neither end existed where a gate could sit — finding-level merge was only the one-time Step 9 phase, and `finding_resolved`'s producer `fix_commit` is unreachable from `pattern_analysis`. Per Jon's 2026-08-24 ruling the primitive was built: declared from `fix_loop` **and** `pattern_analysis`, emitting `finding_resolved` with a new optional `merged_into`, so "close **or** merge" stays one count; `merge_target_exists` refuses an unfiled target and a self-merge. The cap counts the round's still-**open** items over D6's population — a filing cannot be withdrawn from an append-only ledger — and gates `pattern_done` **and** `iteration_boundary`, since Step 11's usual path never enters `pattern_analysis`. The obligation gates `iteration_boundary` alone: from `pattern_analysis` a round could discharge it only by merging away the siblings it had just found. Deferral relieves the cap but does not pay the obligation. Both windows floor at the *previous* round — a round records itself before either gate runs, so "since the last round" is the empty set | `34755d4` | D7 |
| P0.2 · promote the stale sweep to Step 11b **and run it instead of pattern analysis past ~round 8** | SHIPPED. Step 11b in `bb502ca`; `7904b54` widened its population to every open finding at every severity, per D21. The *instead-of* swap in `92c4e86`. D8's premise was false — **nothing recorded that a sweep ran**: Step 11b writes `fix_start` + a `cant_reproduce` deferral only for what it *retires*, and `check_sweep_evidence.py` gates the unrelated final sweep. Per Jon's 2026-08-25 ruling the courier was built: `stale_sweep.py --record --present/--retired` derives the population from the ledger and refuses unless the verdicts name exactly it (D21's rule, previously prose), and `stale_sweep_courier.py` re-derives coverage before writing a `restricted` + tool-attested `stale_sweep_complete` — a weaker sibling would be the cheaper door past round 8 and undo what P5.4 bought. The gate is one **floor over two event types**, not a fourth conjunct: withdrawing the obligation past round 8 would withdraw it permanently, since only a round resets the counter and none would be owed | `bb502ca`, `7904b54`, `92c4e86` | D8, D21 |
| P0.3 · finding-scoped TDD gate | **SHIPPED**, scoped to the *actor* rather than the finding — no hook event carries a finding, and D32 ruled the engine be extended rather than the predicate moved into Python. The clause could not be written in `hooks.toml` at all: hook gates evaluated with empty `state_params`, the three ledger gates compared filter values literally, `agent_id` was absent from the sahjhan crate, and `type = "query"` hook checks are a `return false` stub. sahjhan gained `--agent-id`, actor-seeded gate vars and `{{var}}` resolution in filters (`b564a07`, released v0.23.0). The actor then had to reach the ledger — `test_failed_before_fix` is agent-written and names none, so filtering on it would have matched zero rows and deadlocked every actor — hence D33's `tdd_evidence` + `tdd_courier.py`, which reads `agent_id` off the hook payload and re-derives every other field from the ledger row. Proven against a real daemon: a sibling is refused another actor's failing test, and an agent that records its own is released by it | sahjhan `b564a07` | D32, D33 |
| P0.3 · worktree isolation for fix subagents; serialize commits not findings | **OWED — and stopped on a question, per the process rules.** The gate change landed (D32/D33), so `hooks.toml`'s TDD gate is already per-actor and two fix agents no longer authorise each other. `phase-fix-loop.md:75` still mandates one-at-a-time. Everything below was measured against Claude Code 2.1.246 and a real pair of linked worktrees, not read. **Where the worktree goes:** the harness nests isolated worktrees at `<project>/.claude/worktrees/<name>/` — the base path is built in the binary as `join(root, ".claude", "worktrees")` and a sibling check rejects a directory "not directly under a .claude/worktrees directory". **The clause's own premise holds:** `git rev-parse --show-toplevel` inside a linked worktree returns the worktree, so `compute_tree_hash` is per-agent; two identical checkouts hash identically (`96a76333d92b`), so isolation costs nothing while the trees agree. **And the ledger stays shared,** which is the half of `phase-fix-loop.md:75`'s stated reason that serialization must preserve: sahjhan's `project_root_from` walks up for `docs/holtz/.sahjhan`, which a fresh worktree does not have (gitignored), so it resolves to the main root — `SELECT count(*) FROM events` returned the same `118` run from both directories. **Three blockers, none of which the clause names.** (a) *The daemon socket is keyed per checkout, deliberately.* `boundary_dir()` is `~/.holtz/run/<sha256(realpath(cwd))[:12]>`, documented as giving "two checkouts of the same repo different sockets"; observed `009ba37dc895` (main) vs `02fab2dfc288` (worktree). A subagent's `tdd_courier.py` and `suite_courier.py` would resolve a socket no daemon is bound to and fail closed — and `tdd_evidence` is `restricted`, so the per-actor TDD gate could never open for a worktree subagent at all. (b) *`fix_commit` is anchored at the project root, both gates.* `git log -1 --format=%B \| grep -q '{{item_id}}'` and `verify_suite.py --check` run in the gate cwd, which `paths.rs` makes a system-owned path resolved against the project root — so the commit must already be on the main branch and the *main* tree must carry the green. (c) *A green does not survive the merge.* Measured on two worktrees carrying disjoint edits: H(A)=`9a58225c274f`, H(B)=`6c6664262c69`, H(A+B)=`6eae12853f7d`, and the merged tree matches neither recorded green. That is semantic, not plumbing — B's suite never saw A's changes, and the spec's own figure is that 26% of pairs among four consecutive fix commits *do* touch shared files. Both were put to Jon and ruled 2026-08-26: **D40** keys the boundary on the main worktree, **D39** has the subagent rebase onto the current main tip and re-record before the orchestrator fast-forwards. **D40 is SHIPPED** — `project_anchor()` resolves the main worktree by walking for `.git`, treating a `gitdir:` pointer as a worktree only when a `commondir` sits beside it, so a submodule stays its own project; proven against a real daemon without the `SAHJHAN_DAEMON_SOCKET` override every other e2e test sets, since that override is the line being changed. **D39 is SHIPPED**, and drafting it turned up one more block: `commit_gate.py:78` refuses `git commit` in `fix_loop` while `unregistered_commits` is non-empty, and `protocol_tracker.py:262` appends to that list on *any* successful commit by *any* actor, into the cache the daemon serves — which D40 now shares with every linked worktree. The first subagent to commit refused every other one, naming `transition fix_commit` as the escape: the orchestrator's transition, gated on `git log -1` and a tree hash both taken at the project root. Per Jon's D41 ruling the list is keyed on the actor, the same fix D10 made to the stall counter and from the same `agent_id`; the clear stays run-global because after a fast-forward the commit at `HEAD` belongs to a subagent the transition cannot name. The loop now dispatches up to 3 subagents with `isolation: "worktree"`, each committing in its own tree, rebasing onto the orchestrator's branch and recording the green **last**; the orchestrator fast-forwards one at a time. The order is the design — recording before the rebase would leave the green naming a tree that never lands, and an ordinary merge would write a merge commit whose tree is neither subagent's — so it is tested three ways: the document's own line order, the identity executed against real git and the real `compute_tree_hash` (one subagent, two merged serially, the refused fast-forward, the conflict path), and the actor scoping in nine `hook_e2e` tests. Removing the rebase from the executed sequence turns the two-subagent test RED. The same commit corrects a claim that had gone stale in `phase-fix-loop.md`: it still said the TDD gate does not look at `agent_id`, which stopped being true at D32/D33 | `6091cda`, `2e0b1d7`, `823c90b` | D32, D33, D39, D40, D41 |
| P0.4 · delete `PUNCHLIST-MERGED.md` as a concept; merge writes the ledger | SHIPPED — the written deletion gate is a `not(file_exists)` on `merge_done → awaiting_clear` (`d716f3e`); the `MERGE-REPORT.md` validation from `57a4c02` stays as an accidental P4.9 slice, per D14. P4.2 and the DEFERRED→OPEN contradictions change ratified by D15/D16 | `57a4c02`, `d716f3e` | D14, D15, D16 |
| P0.4 · render `PUNCHLIST.md` open-only, one line each, ≤12-word summary; archive resolved rows | SHIPPED — open-only + archive in `6d78c7f`; the one-line four-field row with render-side 12-word truncation in `2741fce` (`category`, `perspective` and the full prose are ledger-only now). The recon dependency it created is discharged: `f0a0239` moves the cold-file scan to `findings.py audited-files`, a `--glob` query across every run's ledger, per D20 | `6d78c7f`, `2741fce`, `f0a0239` | D9, D20 |
| P0.4 · ship `open_findings.py` / `show_findings.py` as the mandated lookup path | SHIPPED as a single `findings.py` with `list`/`show` (trivial merge); `f17aaec` applied the mandated path at a site the first sweep missed | `57a4c02`, `f17aaec` | — |
| P0.4 · delete the two `step-10-fix-loop.md` update steps | SHIPPED+ (11 lines across 5 skill files; also **added** mandates — per-sibling `event finding`, `event blast_radius` — and re-scoped `status-file-format.md` to Justine's file) | `fa058cd` | D19 |
| P0.5 · require `--field reachability=user_reachable\|fault_injected\|theoretical` | SHIPPED — required, not optional, because D4's conjunct is defined over it; taught in `punchlist-format.md` with a test that fails the build if schema and doc disagree; `migrate_legacy.py` writes `theoretical` for archives, which is that value's own definition | `5679f5c` | D4 |
| P0.5 · derive severity from `(reachability, blast_radius.affected_count, public-API surface)` | **WON'T DO (Jon, 2026-08-25)** — premise false: `blast_radius` is recorded at Step 10's per-fix procedure, *after* filing, and "public-API surface" has no ledger representation. Two of three inputs absent at filing time. All three re-grading triggers were costed (courier on `blast_radius`, render/gate-time computation, drop `affected_count`); none ships. Severity stays a typed field | — | D28 |
| P0.5 · only `user_reachable` fix-loop eligible; `fault_injected` batches at finalize; `theoretical` auto-defers | **SHIPPED, all three routes.** `theoretical` auto-defers: `theoretical_courier.py` writes a real `finding_deferred` (reason `theoretical`, its own word so it cannot spend the MEDIUM budget), from a population it re-derives through the named `open_theoretical_findings` — so a finding filed by `merge_punchlists.py`, whose inner `sahjhan event finding` no hook sees, is swept too, and a second firing spends no second row. `fault_injected` batches: `hardening_batch.py` + `hardening_batch_courier.py`, one hardening commit per **containing directory** (D35), the courier writing one `finding_resolved` per covered id. Two deviations from the clause, both ruled by Jon on 2026-08-25 after the engine and the ledger were driven rather than read. **(a) A courier closes them, not a transition:** `EmitConfig` (sahjhan `src/config/transitions.rs:101`) produces exactly one event with a fixed field map and `emits` is not a fan-out, so no transition can write one resolution per batched id; closing with `finding_resolved` keeps D29's single definition of closed and lets `all_critical_resolved` clear. **(b) It runs before `converge`, not at `finalize`:** `all_critical_resolved` gates `converge`, carries no reachability filter and refuses a deferral, so a `fault_injected` CRITICAL blocks two transitions upstream of `finalize` — observed `false` against a real daemon and still `false` after all three deferral reasons — and a batch taught at `finalize` could never be reached by the run that needed it. The gate sits on `converge` with the batch as Step 15's immediately preceding line, so the block is escapable by construction. Fix-loop eligibility: `item_is_user_reachable` on `fix_commit`, the only place the engine can see it, plus `findings.py list --reachability` so the worklist shows what is workable rather than costing a cycle to find out. **A third deviation, ruled 2026-08-25 after it was measured:** D34's analysis covered `fault_injected` only, and the gate also stranded a `theoretical` CRITICAL — auto-deferred at filing, refused by `all_critical_resolved`, refused by `merge_finding` (`item_open` observed false), and outside the hardening batch's `fault_injected`-and-open population, leaving re-grading as the only exit, which D34 itself calls a forgery. Per Jon's ruling `all_critical_resolved` now excludes a deferral whose reason is `theoretical` — the one reason word a courier writes rather than an agent choosing it. Every discretionary reason still refuses, and a test fails the build if the exclusion widens. `TestEveryCriticalHasARoute` enumerates all three grades against the real transitions, because a gate whose escape is missing for one grade is #77 at the end of the run | `d7fb931`, `2058677`, `e537cae` | D29, D34, D35 |
| P0.5 · reopen, don't refile (`--supersedes`) | **WON'T DO (Jon, 2026-08-25)** — two gaps: the engine does not gate events, and nothing reopens a closed finding. The rejection half alone is worse than nothing (it routes new information onto a closed record); the reopen half converts seven openness predicates from set-membership to temporal, inside the gates that decide convergence, the round cap and the deferral budget. D25 keeps the reachable part of the value | — | D30 |

## Tier 1

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P1.1 family batching | — | — | — |
| P1.2 route "vacuous test" and single-file fixes to Sonnet | SHIPPED — both written criteria; the Fast Path proxy is gone, and the test that had been written against it now asserts the proxy is *not* what routing keys on | `ce3c5a9` | D12 |
| P1.3 fix-brief emitter | — | — | — |
| P1.4 one await-the-batch idiom | — | — | — |
| P1.5 warm-context pack | — | — | — |
| P1.6 drop one of two mandated tail suite runs | SHIPPED | `d4e5f8b` | — |
| P1.7 promote recorded probe to RED test | — | — | — |
| P1.8 resume path for interrupted subagents | — | — | — |
| P1.9 ceiling the analysis fan-out | — | — | — |

## Tier 2

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P2.1 cap `patterns-brief.md` by bytes | SHIPPED — 20 entries **and** 40 KB, entries over 2 KB compressed to the four-line format with their detail moved to `pattern-round-NN.md`; `pattern_brief_compact.py` reports on stderr what is over, since step 4 forbids reading the brief whole | `2270506` | D11 |
| P2.2 make the compact read its own numbered step | SHIPPED — Step 11's step 4 in `phase-fix-loop.md` (`6b95aea`); Jon ruled on 2026-08-23 to unbury the other site the clause names, so `phase-audit.md`'s two subagent briefs and `justine-skill.md`'s are numbered lists with the compact read as step 1 (`a0e0ef5`) | `6b95aea`, `a0e0ef5` | D13 |
| P2.3 digest instead of full punchlist | — | — | — |
| P2.4 bound subagent context | — | — | — |
| P2.5 slice rule replacing re-read-everything | — | — | — |

## Tier 3

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P3.1 expandvars + unconditional allow under `_PLUGIN_ROOT` | SHIPPED — `_expand_script_path` + the pre-existing in-tree allow; expansion is what routes the taught commands to it, and the unexpanded-`$VAR`-under-plugin-root direction is pinned too | `ded5767` | D26: confirmed closed |
| P3.2 don't tick the stall counter on read-only commands | SHIPPED | `d1583e9` | — |
| P3.2 key the counter on `agent_id` | SHIPPED — `stall` is a map from actor to count; charging and clearing are both per-actor, and the orchestrator (no `agent_id`) is a bucket like any other rather than a wildcard | `04a4d78` | D10 |
| P3.2 "Needs a `hook_e2e` test" | SHIPPED — six subprocess-driven `hook_e2e` tests for the keying, and `TestReadOnlyCommandsDoNotStall` carries the marker its clause demanded | `04a4d78` | D10 |
| P3.3 detector substitutes `VAR=` and unwraps `eval` | SHIPPED+ — wired into `_split_shell_segments` (all segment predicates) and `_bash_references_blocked_sahjhan`, plus quote-stripping; closed a real quiz-sign-off bypass | `627e99b` | D17 |
| P3.3 export `bin/` onto PATH in `session_start.py` | rejected on a **falsified premise** — the plugin loader already puts `bin/` on PATH (verified against the shipped binary); a SessionStart hook also cannot alter later Bash env | — | — |
| P3.4 clear `pattern_analysis_overdue` inside the `pattern_done` transition | SHIPPED — the transition clears the cached flag directly, so a derivation that could not reach the ledger no longer holds a discharged obligation True; clear-only, after the refresh, so nothing that *raises* the flag is bypassed | `9f04bff` | D27 |
| P3.5 manifest anchoring | already fixed pre-effort (`d92d468`) | — | — |
| P3.5 cap artifact size | SHIPPED — SKILL.md caps an artifact at 40 KB, continuing into a numbered sibling at a section boundary rather than truncating | `2270506` | D11 |
| P3.6 dedupe at render | SHIPPED; expanded to two more counting sites with semantic changes (`defer_medium` budget → distinct ids; STATUS Open recomputed; severity = latest filing) | `03603a9`, `375b19f`, `fe2ef56` | D18, D25 |
| P3.7 escape `\|` in the render | SHIPPED+ (newline collapse added — same defect, worse failure mode) | `03603a9` | — |
| P3.8 fix in tqdm | N/A | — | — |

## Tier 4

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P4.1 script the merge | SHIPPED — `enforcement/scripts/merge_punchlists.py` executes `merge-protocol.md`'s classification, recording, report and impact-graph merge; the merge-agent's remaining job is the one class the protocol itself excepts, adjudicating contradiction candidates. It lives under `enforcement/scripts` rather than the spec's bare `scripts/` because that directory is the linter's only `tool_dir`: a `finding` writer anywhere else is discovered as `hook:<path>` and H4 then demands a `hooks.json` entry it can never have. `finding` is a normal event, so the write is a direct ledger append and needs no courier; the new `tool:` producer is declared and the generated contract shows attestation unchanged at `agent`. The archive step stays the agent's single `mv` — `merge-protocol.md:138` assigns it to the parent process, and gating it is P4.9's | `c14c881` | — |
| P4.2 delete the renumbering rule | SHIPPED **silently inside a P0.4 commit**, never ruled | `57a4c02` | D15 |
| P4.3–P4.7 | REJECTED (Jon) | — | — |
| P4.8 dedupe gate at `merge_complete` | — | — | — |
| P4.9 gate the three mandated artifacts | — | — | — |

## Tier 5

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P5.4 derive `patterns_found` by diffing PAT headings | SHIPPED+ — derivation as written, plus: event became `restricted` + `tool`-attested, new `pattern_ids`, new `pattern_courier.py` trusted hook, taught step order swapped. The `phase`/`step` deletion is reversed per D22: `b184b05` has the courier stamp both from constants pinned against the doc that teaches the round | `ceb7414`, `b184b05` | D22 |
| P5.1–P5.3, P5.5–P5.7 | — | — | — |

## Tier 6

All — (not started).

## Work outside the plan

| What | Status | Where | Decisions |
|---|---|---|---|
| A finding's severity is its latest filing (3 gate sites) | shipped unasked; real defect (a LOW→HIGH correction was closable as a LOW) | `fe2ef56` | D25 |
| `phase-convergence.md` worklist read fixed | shipped; P0.4's own mandate applied at a site the sweep missed | `f17aaec` | — |
| Restored the `pattern_done` invocation `d4e5f8b`'s trim truncated; H6 fails the lint | shipped; repair of an in-effort regression | `6962f95` | — |
| Prose audit across skill files | shipped; directed by Jon in-session | `15ac1f9` | — |
| Revert of the shipped P0.1 gate and taught triage default | shipped 2026-08-22 per Jon's go-ahead | `e123a86` | — |
| H8 narrowed to escapes whose readiness is a fact about the *run* | shipped inside D7; the check errored on all three new gates and its own remedy (`query = "item_open"`) cannot be instantiated in a gate with no `{{item_id}}` to bind. Per-query, so an escape keeping any run-wide predicate is still judged on it | `34755d4` | — |
| Every registered authed writer must be in `trusted-callers.toml` | shipped inside D8; `TRUSTED_SCRIPTS` is hand-kept, so the first regeneration after adding the courier changed nothing and looked successful — a restricted writer the daemon cannot authenticate is enforcement that silently fails open. Scoped to hooks.json entrypoints: since sahjhan 0.21.0 the daemon authenticates the process directly holding the socket, so `quiz_vault.py` is covered by its two importers | `92c4e86` | — |

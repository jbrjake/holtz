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
| N/A | out of scope per Jon's standing "ignore tqdm items" rule |
| — | not started |

## Tier 0

| Clause | Status | Where | Decisions |
|---|---|---|---|
| P0.1 · amplification circuit-breaker (`A > 1.0` for 3 rounds, gate on `pattern_done`, block the next dispatch, escape = every open LOW **and** the MEDIUM budget, `sahjhan defer batch`, writes `DEFERRED.md`) | SHIPPED, all four clauses. Pin bumped to sahjhan 0.22.0 (`f9c46a1`); `[batches.defer]`, the `"defer batch"` alias and a `DEFERRED.md` render (`a2bd2c5`); `amplification_diverging` — `filed > resolved` since the *first* entry to `fix_loop`, per `pattern_analysis_complete`, over a three-round seq floor (`c620de7`); the `any_of` block on `pattern_done` with the escape as its second branch (`276cd11`). The escape predicate asserts the **budget spent**, not an empty MEDIUM set — the 50% cap makes the latter unreachable. `defer_low`/`defer_medium` are additionally declared `pattern_analysis → pattern_analysis`, per Jon's 2026-08-24 ruling: that state has no other exit, so without them the block named a command the run could not reach. Per D3 the escape is the only place deferral is taught | `f9c46a1`, `a2bd2c5`, `c620de7`, `276cd11` | D2, D3 |
| P0.1 · redefine convergence (4 conjuncts, as a package) | **OWED**, BLOCKED(P0.5 `user_reachable`) | — | D4, D5 |
| P0.1 · scope Step 16's resweep to files changed by fixes | SHIPPED+ (adds blast-radius depth 2 and a full-resweep fallback) | `f17aaec` | D23 |
| P0.2 · move pattern requirement from `fix_commit` to `iteration_boundary` | SHIPPED+ (the boundary already carried the gate; the change is the commit-path deletion; adds an unasked pattern gate on `set complete perspective`) | `5b0c4f0` | D24 |
| P0.2 · second conjunct: no round while >25 pattern-filed findings open **or** after two dry rounds | SHIPPED, both halves. Two-dry-rounds in `e1ed6c9` (seq-floor form); the >25-open half in `6f35730`. D6's note that `pattern_ids` made the population derivable is false — checked against every archived ledger, `pattern_ids` links to no finding, `predicted_by` is a prediction index, no finding was ever filed at `step=11`, and `siblings_found` carries no ids. Per the ruling's fallback branch and Jon's 2026-08-24 answer, `finding` gained an optional `pattern_id` taught in Step 11.2, joined to the rounds so an id counts only when that PAT appears in a courier-derived `pattern_ids` | `e1ed6c9`, `6f35730` | D6 |
| P0.2 · cap each round at ≤3 new items, with an obligation to close or merge at least as many as it opens | SHIPPED, both halves, on a new `merge_finding` transition. D7 requires the cap's escape to be guaranteed by construction and names it "the merge/close path"; neither end existed where a gate could sit — finding-level merge was only the one-time Step 9 phase, and `finding_resolved`'s producer `fix_commit` is unreachable from `pattern_analysis`. Per Jon's 2026-08-24 ruling the primitive was built: declared from `fix_loop` **and** `pattern_analysis`, emitting `finding_resolved` with a new optional `merged_into`, so "close **or** merge" stays one count; `merge_target_exists` refuses an unfiled target and a self-merge. The cap counts the round's still-**open** items over D6's population — a filing cannot be withdrawn from an append-only ledger — and gates `pattern_done` **and** `iteration_boundary`, since Step 11's usual path never enters `pattern_analysis`. The obligation gates `iteration_boundary` alone: from `pattern_analysis` a round could discharge it only by merging away the siblings it had just found. Deferral relieves the cap but does not pay the obligation. Both windows floor at the *previous* round — a round records itself before either gate runs, so "since the last round" is the empty set | `34755d4` | D7 |
| P0.2 · promote the stale sweep to Step 11b **and run it instead of pattern analysis past ~round 8** | Step 11b SHIPPED; `7904b54` widened its population from the changed-files subset `bb502ca` shipped to every open finding at every severity, per D21. The *instead-of* swap **OWED** | `bb502ca`, `7904b54` | D8, D21 |
| P0.3 · finding-scoped TDD gate, worktree isolation, serialize commits not findings | — (gate change must land before any batching) | — | — |
| P0.4 · delete `PUNCHLIST-MERGED.md` as a concept; merge writes the ledger | SHIPPED — the written deletion gate is a `not(file_exists)` on `merge_done → awaiting_clear` (`d716f3e`); the `MERGE-REPORT.md` validation from `57a4c02` stays as an accidental P4.9 slice, per D14. P4.2 and the DEFERRED→OPEN contradictions change ratified by D15/D16 | `57a4c02`, `d716f3e` | D14, D15, D16 |
| P0.4 · render `PUNCHLIST.md` open-only, one line each, ≤12-word summary; archive resolved rows | SHIPPED — open-only + archive in `6d78c7f`; the one-line four-field row with render-side 12-word truncation in `2741fce` (`category`, `perspective` and the full prose are ledger-only now). The recon dependency it created is discharged: `f0a0239` moves the cold-file scan to `findings.py audited-files`, a `--glob` query across every run's ledger, per D20 | `6d78c7f`, `2741fce`, `f0a0239` | D9, D20 |
| P0.4 · ship `open_findings.py` / `show_findings.py` as the mandated lookup path | SHIPPED as a single `findings.py` with `list`/`show` (trivial merge); `f17aaec` applied the mandated path at a site the first sweep missed | `57a4c02`, `f17aaec` | — |
| P0.4 · delete the two `step-10-fix-loop.md` update steps | SHIPPED+ (11 lines across 5 skill files; also **added** mandates — per-sibling `event finding`, `event blast_radius` — and re-scoped `status-file-format.md` to Justine's file) | `fa058cd` | D19 |
| P0.5 · reachability grading, derive severity, reopen-don't-refile | — (next up; carries P0.1's convergence conjunct and the carve-out decision) | — | D4, D5 |

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
| P4.1 script the merge | — (cheapest high-confidence item left) | — | — |
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

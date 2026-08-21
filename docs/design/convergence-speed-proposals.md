# Convergence-speed proposals

**Source:** [tqdm run-1 process post-mortem](../case-studies/2026-08-18-tqdm-process-postmortem.md)
**Date:** 2026-08-18 · **implementation started 2026-08-21**

**Status legend.** Each item id carries its own status. Absent marker = not started.

| Marker | Meaning |
|---|---|
| `DONE` | shipped; the commit is named in the item |
| `PARTIAL` | some of the item shipped; what remains is stated in the item |
| `REJECTED` | considered and deliberately not implemented; the reason is stated in the item |
| `N/A` | not actionable in this repo (e.g. a defect in the audited project) |

Every item below is derived from measured telemetry of one halted run (holtz v0.141.3 on
tqdm): 22.5 h agent-active, 6.68M output tokens, 762M cache-read, 353 findings, 81 fixed,
**0 deferred**, halted `awaiting_human` with 273 open.

Savings estimates are per-run against that baseline. They **overlap** — several items
attack the same minutes from different angles — so do not sum the column. Confidence is
stated per item.

---

## Tier 0 — The five that matter most

Ranked by measured impact on time-to-convergence.

### P0.1 Amplification circuit-breaker + mandatory batch deferral

**Problem.** The loop filed **2.43 new findings per fix**. Open count rose monotonically
124 → 273 and fell exactly once (−2). `converge` requires `all_findings_closed == 0`
(`transitions.toml:352`). The run was non-terminating from pattern round 1.
Meanwhile `defer_low` / `defer_medium` (`transitions.toml:163-195`) gate on nothing but
*exists + open + severity*: **133 of 273 open findings were legally batch-closable in ~5
agent-minutes.** Used **zero** times.

**Change.**
- Add a gate on `pattern_done`: `A = findings_filed_since(fix_loop_start) /
  resolved_since(fix_loop_start)`. If `A > 1.0` for 3 consecutive rounds, block
  `fix_commit` until every open LOW and the MEDIUM budget is batch-deferred via one
  `sahjhan defer batch --severity low,medium` writing `docs/holtz/DEFERRED.md`.
  This run would have tripped at **08-11 21:55Z**.
- Redefine convergence (`protocol.toml:74`): `all CRITICAL resolved AND all
  user_reachable HIGH resolved-or-deferred AND A < 1.0 over last 3 rounds AND DEFERRED.md
  written`.
- Scope Step 16's resweep (`phase-convergence.md:45`, currently *"Full re-run of Steps
  6–8"* — the phase that produced 124 findings in 143.7 min) to files changed by fixes.

**Savings: ~700–900 agent-min, ~1.4M output tokens — and it is the difference between
terminating and not.** Confidence: **high** (data and transitions already exist).

---

### P0.2 Get pattern analysis out of the commit path, cap it, and swap it for the stale sweep

**Problem.** 24 rounds × 17.9 min median = **1.85× a fix cycle, 43% of in-loop time**,
plus 474 subagent-min and **31% of the run's cache-read**. It is mechanically unskippable:
`protocol.toml:90-92` + `transitions.toml:289/217` mean **you cannot `/clear` without a
round**. It fires *inside* the commit path — `c30f4d6b` 20:52 turned a **4.9-min fix into
24.0 min**. The gate is yield-blind: `patterns-brief.md` states verbatim, four times, that
rounds 12–15 added **no new pattern**, costing **268 agent-min**. Cost per
eventually-fixed finding: 24.9 → 16.0 → 13.9 → **108.9 min**.

**Change.**
- Move the pattern requirement from `fix_commit` to `iteration_boundary`. Gate *starting*
  fix N+1, never *committing* fix N.
- Add a second conjunct to `pattern_analysis_overdue`: no round while >25 pattern-filed
  findings are open, **or** after two consecutive rounds that added no new PAT entry.
- Cap each round at ≤3 new items, with an obligation to close or merge at least as many as
  it opens (`phase-fix-loop.md:92` currently says *"write new items IMMEDIATELY"*, uncapped).
- **Promote the stale sweep to a named Step 11b** and run it *instead of* pattern analysis
  past ~round 8.

**Savings: ~220–470 agent-min, ~180M cache-read.** Confidence: **high**.

> The stale sweep is the best-performing mechanism in the entire run and appears in **no
> skill file**: `stale-sweep-round14.md` triaged all 68 open HIGHs in **14 agent-min** and
> retired 4 findings (BH-078/016/017/177) writing no code — ~3.5 agent-min per retirement,
> against 9.7 for a fix and 23.4 for pattern analysis.

---

### P0.3 Finding-scope the TDD gate so the fix loop can run 3-wide

**Problem.** `enforcement/hooks.toml:18-20` — the pre-edit gate is
`ledger_has_event_since / test_failed_before_fix / since = last_transition`:
**run-global, not finding-scoped**. Two concurrent fix agents would satisfy each other's
gate, which is precisely why `phase-fix-loop.md:68` mandates one-at-a-time. The doc is
correct *given the gate*. Result: **89% of subagent wall-clock at concurrency 1**;
sessions 3–9 spent **857 consecutive minutes** at max concurrency 1. Fix subagents are only
**13% tool-wait — 87% model generation**, so nothing but concurrency helps.
**74% of pairs among any 4 consecutive fix commits touch disjoint source files**
(`tqdm/std.py` is the one hot spot, 25 of 62 commits, needing a serial lane).

**Change.** Scope the gate to `finding_id` (or `agent_id`); give fix subagents
`isolation: "worktree"` so `verify_suite.py`'s tree hash is per-agent; orchestrator merges
and commits serially. Rewrite `phase-fix-loop.md:68` to serialize **commits, not findings**.

**Order matters: the gate change must land first.** Batching without it removes TDD
enforcement.

**Savings: fix-phase makespan 717 → 423 min ≈ 294 agent-min.** Confidence: medium-high on
arithmetic, medium on feasibility. Requires a `hook_e2e` test per CLAUDE.md's
subagent-parity rule.

---

### P0.4 One canonical, machine-queried worklist

**Problem.** `phase-fix-loop.md:28` tells the fix loop to prefer `PUNCHLIST-MERGED.md` —
574 KB, written **once** on 08-11 17:53, re-rendered by nothing, still marking **all 178
findings OPEN including the 81 fixed**. Session `c35c9091` ran 4 pattern rounds grepping it
exclusively, blind to 176 findings and 25 committed fixes. **111 subagent-min went to
reconciling bookkeeping against reality.** Holtz's own paperwork carried **65.0M
cache-read vs 57.5M for the code under audit**.

**Change.**
- **Delete `PUNCHLIST-MERGED.md` as a concept.** Have merge write findings into the ledger;
  render the single `PUNCHLIST.md` that `SKILL.md:25` already calls canonical. Gate its
  deletion at the `merge → fix_loop` transition. Fix `phase-fix-loop.md:28`,
  `step-10-fix-loop.md:13`, `merge-protocol.md:18,128`, `phase-merge.md:19,22`.
- Render `PUNCHLIST.md` as **open items only, one line each** (id, severity, `file:line`,
  ≤12-word summary ≈ 10–12k tok vs 81k); resolved rows → `PUNCHLIST-ARCHIVE.md`; full
  prose stays ledger-only. Today **23% of every punchlist load is already-resolved rows.**
- Ship `open_findings.py` / `show_findings.py` as plugin scripts (thin wrappers on
  `sahjhan query --type finding --format jsonl`) and make them the mandated lookup path.
  *The agent wrote this script from scratch in three separate sessions.*
- Delete the `step-10-fix-loop.md:55-56,81-82` PUNCHLIST/STATUS update steps — they were
  followed **zero** times in 23 sampled cycles, and a hook actively *blocks* the mandated
  write (`BLOCKED: Bash command modifies protected path 'docs/holtz/STATUS.md'`).

**Savings: ~100–170 agent-min, ~40–50M cache-read — plus it removes a correctness bug that
had pattern analysis reasoning from week-old data.** Confidence: **high**.

---

### P0.5 Grade findings by reachability, and route by it

**Problem.** **~22 of 62 commits are fault-injection-only** — reachable only by making
some other call raise. BH-258's own text concedes *"reachability on CPython 3.12 is
uncertain… needs a reachability probe before any fix"* and was filed as a fix-cycle item
anyway. Tests grew **+10,772 lines against +1,505 source lines (7:1)**. Severity is never
re-graded: one defect class decayed **CRITICAL → HIGH → MEDIUM → LOW by discovery order**
(BH-002 → 196 → 245/246 → 258), all five receiving a full fix cycle. Meanwhile **51 of the
75 open HIGHs were on the board before the first commit** and were never worked —
including BH-054 (unescaped `desc` → ipywidgets HTML injection) and BH-030 (`--update`
crashes mid-stream).

**Change.**
- Require `--field reachability=user_reachable|fault_injected|theoretical` on
  `sahjhan event finding`. Derive severity from `(reachability, blast_radius.affected_count,
  public-API surface)` rather than accepting a typed field.
- Only `user_reachable` is fix-loop eligible. `fault_injected` batches into one hardening
  commit per module at finalize. `theoretical` auto-defers.
- **Reopen, don't refile:** reject `event finding` whose `location` falls inside a
  `file:line` range this run already committed to, unless it carries `--supersedes BH-NNN`;
  a superseding finding reopens the original instead of opening a new cycle. Would have
  collapsed the 5-commit CLI chain and the 3-commit monitor chain.

**Savings: ~300 agent-min and a materially more mergeable diff.** Confidence: **high**.

---

## Tier 1 — Throughput

| # | Proposal | Savings | Conf. |
|---|---|---|---|
| P1.1 | **Family batching.** When a pattern round names N instances of one PAT, dispatch **one** fix subagent for the family. The 27-commit lock/monitor family collapses to ~8. Amend `phase-fix-loop.md:68`. | ~200 agent-min, ~700k tok | med |
| P1.2 | **Model routing in `phase-fix-loop.md`.** **97 of 107 subagents ran Opus**; `phase-audit.md:55` already routes but the fix-loop doc has no routing line, so all 59 fix agents and 23 pattern agents ran on the largest model. Route "vacuous test" and single-file fixes to Sonnet (~30 of 59 qualify). | ~600k out, ~150M cache; wall-neutral | high |
| P1.3 | **Emit the fix brief from the ledger:** `sahjhan render fix-brief BH-NNN`. Replaces 8–11 KB of hand-drafted prompt (33–58 s of orchestrator drafting per fix) with one call. `phase-fix-loop.md:43` enumerates the payload but ships no emitter. | ~17 min, ~57k tok per 3 sessions | high |
| P1.4 | **One await-the-batch idiom.** Round 15's four launches were spread over 2m08s, then their completions **sat queued 2h02m**. Each session invents its own wait (`sleep 240`, bare `until`, `TaskList`, `Monitor`). Define: launch the whole batch in a single turn, then one blocking `Monitor`. | ~30–130 agent-min | med |
| P1.5 | **Warm-context pack per fix dispatch.** 29% of every fix subagent's tool calls precede its first edit. `tqdm/std.py` was `Read` 88× across 59 fix agents; `git show <hash>` replayed up to 9×. Write `docs/holtz/fix-context.md` once per window and reference it. | ~90 min, ~120M cache | med |
| P1.6 | **Drop one of two mandated tail suite runs.** `step-10-fix-loop.md` Per-Fix Hardening #3 and `phase-fix-loop.md` Step A.9 both fire at the end of every fix. **45 back-to-back full-suite runs had an identical pass count within 5 min = 17.1 min of literally duplicate verification.** | ~17 min + 62 round-trips | high |
| P1.7 | **Skip the repro test when the finding carries a verified probe.** `phase-fix-loop.md:46` mandates re-deriving it; BH-183's entry literally contains `seq 1 400000 \| python -m tqdm --nosuchopt=1 \| head`. Promote the recorded probe to the RED test. Repro is **40.2% of subagent time**. | 1–2 min/fix on fast-path items | med |
| P1.8 | **Resume path for interrupted fix subagents.** Two interrupted agents wasted 37.6 min and were relaunched from scratch. | ~38 min (observed) | med |
| P1.9 | **Ceiling the analysis fan-out.** Max 2 concurrent analysis subagents, second only if its file-set is disjoint; each report ≤8 KB. Round 15 produced 168 KB the orchestrator then re-read and merged. | ~45 min, ~45M cache | med |

---

## Tier 2 — Context and token economy

| # | Proposal | Savings | Conf. |
|---|---|---|---|
| P2.1 | **Cap `patterns-brief.md` by BYTES, not entries.** `phase-fix-loop.md:116` caps 20 *entries*; the file sat at 20 entries and **181 KB — 8.5 KB/entry against a ~400 B spec, 21× over**. By round 14 one subagent needed **5 paginated reads totalling 159 KB in 90 s**. Change to "20 entries **and 40 KB**; entries >2 KB compress to the 4-line spec, overflow to `pattern-round-NN.md`." | ~250k input tok, ~15 min | high |
| P2.2 | **Make `pattern_brief_compact.py` the default read.** It renders 179 KB → **6,748 chars (26×)** and was invoked **once** in the whole run, because `phase-fix-loop.md` — the doc governing every pattern round — **never mentions it** (it is buried as clause (a) of a seven-clause sentence in `phase-audit.md:59`). Promote to its own numbered step: "never `Read` the brief whole." | ~15M cache | high |
| P2.3 | **Digest instead of full punchlist.** `phase-fix-loop.md:91` mandates *"read the **full** punchlist (no filter)"* — 325 KB / 81k tok. Add `validate_punchlist.py --digest` (one line per finding ≈ 9k tok). | ~1M tok/run | med-high |
| P2.4 | **Bound subagent context.** `SKILL.md:231`'s ~300K ceiling binds the **orchestrator only**. **129 subagent API calls exceeded 300K**; the merge agent peaked at **446K / 35.4M cache-read in 35 min** — 4.6% of the entire run. Add: a subagent passing ~150K writes its findings and returns `NEEDS_CONTEXT` for re-dispatch with a narrower brief. | ~150–250M cache, 40–70 min | med-high |
| P2.5 | **Replace `SKILL.md:238` "re-read before every step; assume prior context is gone" with a slice rule.** **Context never compacted once** in 117 transcripts — the protocol is insurance on a fire that never started, and its remedy is the second-largest cost driver: **28% of all Read tokens re-read a path already read in the same transcript** (`std.py` 133 redundant times). Read the `file:line` range in the finding record; whole-file reads of >1,500-line files need a stated reason. | ~20–25M cache | med |

---

## Tier 3 — Plugin defects (cheap, high-confidence, independent of the above)

The plugin blocking commands it teaches. Enforcement friction is only **7.3%** of
orchestrator time, so these are not speed levers — but they are near-free and one of them
**ended the run**.

| # | Defect | Evidence | Fix |
|---|---|---|---|
| P3.1 **DONE** | **Out-of-tree gate blocks `${CLAUDE_PLUGIN_ROOT}/…`** — `_sahjhan_bootstrap.py:214` never calls `expandvars`, so `isabs("$CLAUDE_PLUGIN_ROOT/…")` is False, it joins against the target repo and blocks. | 58 denials / 7.5 min; **13 are commands taught verbatim** in `phase-fix-loop.md:49,53`, `phase-recon.md:142,149`, `impact-graph-operations.md:11`. Same shape blocked across 9 sessions. | `_expand_script_path` + `TestPluginRootScriptInvocation`. The same defect also pointed the other way: an unexpanded `$VAR/evil.sh` joined *under* the plugin root, so the guard read it as in-tree and waved it through unread. Both directions are now pinned. |
| P3.2 **PARTIAL** | **Stall gate punishes read-only subagents.** Audit subagents running `grep`/`sed -n`/`ls` tick a counter they have no protocol event to clear. | 114 denials / 20.4 min; **108 in subagents, 54 distinct actors, 112 at exactly `stall=16`**. Escape is 115 `sahjhan status` calls whose output is never read. | **Shipped:** `is_read_only_cmd` in `_protocol_cache.py`; the tracker no longer ticks on tree inspection, on the same reasoning that already exempts TDD commands. Conservative by construction — any write redirect, `sed -i`, `find -exec/-delete`, writing `git` subcommand, or unrecognized command still ticks. `TestReadOnlyCommandsDoNotStall`. **Rejected: keying the counter on `agent_id`** — see below. |
| P3.3 **PARTIAL** | **`sahjhan` is unresolvable, so the agent invents indirection the detector cannot see.** `_segment_is_sahjhan` (`_protocol_cache.py:312-317`) matches a literal token, so `"$SAH" … event` and `eval "…sahjhan… status"` **increment** the stall instead of clearing it. `SKILL.md:103-138` teaches bare `sahjhan …` while `bin/` is never on PATH. | **70 of 498 invocations (14%)** invisible. Worst case `288e9c63` 17:59:49: command blocked, documented escape blocked by the same gate, third form worked. | **Shipped:** `enforcement/hooks/_shell_norm.py` — one `resolve_indirection` both detectors call, substituting same-line `VAR=` assignments and unwrapping `eval`/`sh -c`. Wired into `_split_shell_segments` (so every predicate built on it sees through indirection) and into `_bash_references_blocked_sahjhan`. `test_shell_indirection.py`. **Rejected: the PATH export** — see below. |
| P3.4 **DONE** | **`pattern_analysis_overdue` goes stale.** `_protocol_cache.py:400` reads a cached flag that `protocol_tracker._refresh_from_status` re-derives only on an *observed* sahjhan command — so the transition satisfying the gate never clears it atomically. | 11 denials / 35 min. **7 of 11 fired within 6.6 min of a completed round** (`9b6b5384` transitioned at 20:24:20, blocked at 20:24:32/25:09/25:16/25:19). Blocked commits held **12–25 min** each. | **Not** by clearing inside the transition — see below. The commit gate re-derives the named query from the ledger as the last conjunct of the block, so the decision is made against the ledger at the moment it is made. Unanswerable ⇒ still blocked. `test_pattern_overdue_freshness.py`. |
**Why P3.4 was not fixed the way it was written.** "Clear inside the
`pattern_done` transition" adds a second writer to a value that already has an
authoritative source, which is the mirror pattern #77 was. It would also be
wrong on its own terms: what discharges the obligation is the
`pattern_analysis_complete` *event*, not the transition, so a clear attached to
the transition would fire at the wrong moment and could go the other way — a
run that resolves three more findings after the analysis is legitimately overdue
again. The cached flag is a snapshot and that is fine; the defect was that the
gate *decided* on the snapshot. It now confirms against the ledger before
blocking — the same named query, evaluated at the moment of the block — which is
the project's own rule that block condition and evidence must be one object.
Cost is one subprocess on the block path only, since the confirmation is the
last conjunct and everything cheap short-circuits ahead of it. Also collapsed
the query runner into a single shared `query_named_predicate`, since it now has
two callers.

**Why the PATH export was rejected (P3.3), and what the item was actually
hiding.** The premise does not hold. In Claude Code 2.1.238 the plugin loader
maps every enabled non-builtin plugin to `<plugin path>/bin` and appends those
to `PATH` before running a Bash tool call — verified by reading the shipped
binary, and visible in this machine's own `PATH`, which carries the bin
directory of a plugin that does not even have one. `bin/sahjhan` is a symlink
created at bootstrap and was present in the installed `0.141.3` during the run.
Nor would the proposed remedy work: a `SessionStart` hook cannot alter the
environment of later Bash calls.

The half of the item that *was* real is worth more than the framing suggested.
The post-mortem read the detector blindness as a stall-counter nuisance. The
same blindness sits in front of `_bash_references_blocked_sahjhan`, which is
what makes `event quiz_exhausted_resolved` a human-only channel — the event that
clears a lens whose re-read quiz the agent failed. `sahjhan event
quiz_exhausted_resolved` was denied while `"$SAH" event quiz_exhausted_resolved`
was allowed, so the agent could sign off on its own failed quiz. That is a
security defect, not a friction cost, and it is what the fix is really for.

**Why `agent_id` keying was rejected (P3.2).** It would give each actor its own
counter, so 54 readers could each spend 15 unregistered commands and none would
trip — the fleet's aggregate work becomes invisible precisely when there is most
of it. It also reintroduces the shape the project has ruled against twice: a
per-actor mirror of state the ledger already implies, and a gate that reads
`agent_id` rather than evidence. Once read-only inspection stops ticking, the
commands that remain are ones that *can* change the tree, and 16 of those with
no protocol event is the condition the counter exists to notice. Revisit only if
a run shows readers still tripping the gate.

| P3.5 **DONE** | **The manifest-anchoring bug (holtz #85 / sahjhan 0.20.1) terminated the run.** All **81 violations sit at seq 8276–8390, 07:46:06–08:10:42Z** — the last 24 minutes. The preceding 8,275 events are clean. Trigger: a `cd` into `docs/holtz` at 07:19:45 to shorten paths while reading 34–52 KB artifacts. | Records carry `project: "holtz", run: "0"` while the run is `tqdm`/run 1 — not even attributable to the run they killed. | already fixed by `d92d468`; **also** cap artifact size so nobody needs to `cd` (see P2.1) |
| P3.6 **DONE** | **Duplicate finding id.** BH-248 appears twice as two different findings; the "ID CORRECTION" row BH-258 was added but the bad row never deleted. 354 rows, **353 unique ids**. | headline count off by one | `unique_by(attribute="fields.id")` in `punchlist.md.tera`. It keeps the *last* filing, so a correction supersedes what it corrects — pinned by a test, since the whole fix turns on which one survives. |
| P3.7 **DONE** | **`PUNCHLIST.md`'s table format is lossy.** 22 of 354 rows fail to parse into 6 columns because descriptions contain unescaped `\|` (e.g. `` `prog \| head` ``). Any tool counting statuses off this file gets a wrong answer. | 22 rows | Escape `\|` in `description` and `location` at the render, and collapse newlines in `description` — a newline splits the row in two, which is the same defect with a worse failure mode and was not in the report. `test_punchlist_render.py` asserts every row parses into exactly 6 columns. |
| P3.8 **N/A** | **Open regression the run introduced and never fixed.** BH-248 (`tqdm/utils.py:240`): `32bd5cb` widened `except OSError`, so `tqdm(file=open(p,'rb'))` now silently never draws instead of raising. Probe-confirmed, filed, **still OPEN at pause**. | — | A defect in the audited project, not in the plugin. Out of scope for this punchlist. |

---

## Tier 4 — Front-load trims

The front-load is the **best-performing** part of the run — 143.7 min wall (503.6
agent-min at 3.5× parallelism) producing 156 findings including all 20 criticals, **23.6%
of agent-time**. These are efficiency trims, not a rescue.

| # | Proposal | Savings | Conf. |
|---|---|---|---|
| P4.1 | **Script the merge.** `merge-protocol.md:11` calls it *"mechanical… without judgment calls"* and `:165` *"deterministic"* — yet it ran 36.7 min as a subagent hand-writing throwaway `python3 -c` scripts. **This is a script running as an LLM.** Ship `scripts/merge_punchlists.py`; the agent reviews only contradiction candidates. | ~35 min, ~160k tok | high |
| P4.2 | **Delete the renumbering rule** (`merge-protocol.md:76,163`). The ledger already owned 124 ids, so per `PUNCHLIST-MERGED.md:7` "the two namespaces **disagreed on 121 of 124 items**"; reconciliation ran 17:19–17:30. Merged items keep ledger ids. | ~11 min | high |
| P4.3 REJECTED | REJECTED DO NOT IMPLEMENT! **Replace Justine's full second audit with a ~20-min adversarial review** of the primary punchlist ("what surface did Holtz not look at?"). Justine cost 114.0 agent-min / 377k tok for 33 unique findings, of which **2 were ever resolved — ~57 agent-min per shipped finding.** | ~94 min, ~310k tok | med-high |
| P4.4 REJECTED | REJECTED DO NOT IMPLEMENT! **Project-size-scaled lens selection.** All 13 lenses run unconditionally (`lens-registry.md:3`, `phase-audit.md:46-49`); **a keyword sweep of `SKILL.md` and all `references/` for project size / LOC / defect density returns only *context-token* budgets.** On a 5k-LOC progress bar this ran `idempotency`, `security`, `observability` — lenses about DBs, payments, correlation IDs. Add an `**Applies when:**` field per lens, filtered by Step 2 probes. tqdm would run 6–8. | ~30–45 min, ~150k tok | med |
| P4.5 REJECTED | REJECTED DO NOT IMPLEMENT! **Cap recon; make predictions binding or cut them.** Recon artifacts are **write-only — zero tool calls read any `recon/step*` file after session 1**, and all 21 predictions still read `**Outcome:** UNCONFIRMED` though five `phase-audit.md` clauses order the update. Hit rate 8/21 strict — but predictions 2 and 8 alone foreshadowed ~35 of 63 fix commits. `phase-audit.md:37` says *"predictions change the order, not the scope"*, so recon buys an ordering for an audit that runs to completion anyway. | ~50 min, ~200k tok | med |
| P4.6 REJECTED | REJECTED DO NOT IMPLEMENT! **"Confirmed-during-recon → fix now" fast path.** Three defects were CONFIRMED by live probe at 15:03Z; their fixes landed 17:34–18:05Z — **2.5–3 h later**. Let a recon-confirmed CRITICAL enter the fix loop immediately, in parallel with the audit. First fix at ~T+30 min instead of T+180. | time-to-first-fix 180 → ~30 min | med |
| P4.7 REJECTED | REJECTED DO NOT IMPLEMENT! **Gate the quiz bank on a lens sweep actually being scheduled,** or generate it lazily. It is a hard gate on `recon_complete` (`phase-recon.md:134`: *"you cannot leave recon without a bank"*) — 108 `quiz_stage.py` calls, 85 questions, 14.5 agent-min — and there were **zero `quiz_challenge`/`quiz_answer` invocations in the entire run.** Perspectives: 0/13. | ~14.5 min, ~75k tok, 108 round-trips | high |
| P4.8 | **Dedupe gate at `merge_complete`:** reject a merged punchlist where two OPEN findings share `file:±5 lines`. BH-003/BH-112 are the same defect at `std.py:736`; BH-028/BH-126 the same `--buf_size=0` defect. Each pair burned two full fix cycles. | ~2 fix cycles | med-high |
| P4.9 | **Gate the three mandated artifacts nobody produced:** `MERGE-REPORT.md` (`merge-protocol.md:19,79-120`), `justine/SUMMARY.md` (`phase-audit.md:15` — Justine's own completion signal), and the archive step (`merge-protocol.md:130`). None exists; no gate checks any of them. `justine/impact-graph.json` (157 KB) is still on disk though `:146` says delete it. | correctness | high |

---

## Tier 5 — Instrumentation and observability

| # | Proposal | Why |
|---|---|---|
| P5.1 | **`sahjhan report --timing`.** The ledger already records `fix_start`, `fix_commit`, `pattern_check`, `pattern_done`, `suite_green`, `finding`, `finding_resolved`, all timestamped. **It has never been queried for performance.** Surface cycle time, pattern-round cost, generation-vs-retirement ratio, severity mix. | Would have made this run's divergence visible **on day 1, at pattern round 1**, from data already being collected. |
| P5.2 | **Hook denials leave no telemetry.** A hook calling `exit_block` writes **no attachment record**. All 2,419 `PreToolUse:Bash` attachments say `permissionDecision: "allow"` — the only trace of a denial is a `BLOCKED:` string in the result text. Any dashboard reading `hookSpecificOutput` reports **zero enforcement activity** on a run with 187 hard denials. | Fix before building monitoring on that field. |
| P5.3 | **Stop crying BLOCKED.** `BLOCKED: N unregistered commits` appears 44 times, **every one with `permissionDecision: "allow"`**. Plus 142 injections of "N source edits since last state transition" (N up to 50) that were never acted on. Alarm-word inflation costs attention on every turn and changes nothing. | Reword advisory messages. |
| P5.4 | **`patterns_found` is unverified self-report and it is wrong.** Rounds 14/15 recorded `patterns_found=5` and `=2` while `patterns-brief.md` states both added **no** new pattern — and this is the field gating `pattern_done`. Derive it by diffing PAT headings in the brief. | Violates the project's own rule: *gating events need real provenance*. |
| P5.5 | **Persist the pattern-round ordinal in the ledger and render it in STATUS.md.** Subagent labels show rounds 7, 8, 9, 10 **twice**; `c30f4d6b` restarted at "round 5". `round7-pat021-form-b.md` therefore names a different round than its sibling files. Nothing derives the number from the ledger. | Kills filename collisions and re-derivation across `/clear`. |
| P5.6 | **Replace the 16-command heartbeat with a passive counter** and make `sahjhan status` default to a one-line summary (`--full` for the sets block). Of 250 sahjhan calls in 3 sessions, **65 (26%) are `status`/`query` re-reads** of state the caller already held; each returns 4.1–4.3 KB, most of it a `perspective: 0/13` set unchanged all run. | ~6 min, ~45k tok per 3 sessions |
| P5.7 | **Trim the `event finding` payload.** Every call repeats 6 constant fields (`project/run/auditor/phase/step/predicted_by`) — a token tax on the highest-frequency command in the protocol (292 calls). Inherit them from the run context as `fix_commit` already does. | ~high-frequency |

---

## Tier 6 — Doctrine

These are prose changes, but the post-mortem's clearest finding is that **the prose fought
the protocol**: the deferral transitions were correct, permissive, and used zero times.

| # | Proposal |
|---|---|
| P6.1 | **Add counter-balancing red flags.** All **21** entries in `SKILL.md`'s Rationalization Red Flags push toward *more* work; two directly attack the reasoning that would have ended this run (*"This codebase is small, skip convergence"* → *"Convergence is faster, not optional"*). Add the missing direction: *"I should fix this MEDIUM"* → *"You have 143 open MEDIUMs and 75 open HIGHs. Defer it."* / *"One more pattern round"* → *"The last two added no new pattern and 27 findings."* |
| P6.2 | **Reframe deferral as triage, not failure.** `step-10-fix-loop.md`'s flowchart reaches `defer` only *after* dispatching a fix subagent, and `phase-fix-loop.md:59` frames it as *"the subagent could not reach HIGH confidence."* Deferral should be a **batch step at fix-loop entry**, before any subagent runs. |
| P6.3 | **Add a run charter with an explicit budget.** No size scaling exists anywhere in the skill. At observed unit cost the full 353-finding list projects to **~57 agent-hours**; even under maximum permitted deferral, 219 findings remain mandatory ≈ **~35 agent-hours for a 5k-line library**. |
| P6.4 | **Capture process patterns, not just bug patterns.** `pattern-contribution-protocol.md` captures defect patterns. The run's two best ideas were improvised and thrown away: the **4-axis parallel pattern split** (2.4× speedup, near-zero payload overlap, invented at `023e20f4` 04:39:13) and the **stale sweep**. Neither exists in any skill file. |
| P6.5 | **Promote the non-vacuity proof over the hardening test.** Fix subagents invented a check the protocol never asked for and which is strictly better than what it does ask for: `git stash push -- <src>` → re-run the new test → confirm RED → `stash pop` (~14 s). That is Core Rule 2 ("tests that can't fail aren't tests") made mechanical. Put it in `step-10-fix-loop.md`. |
| P6.6 | **Per-fix hardening should check the run's own diff.** Add: *"Run `git diff <run-base>..HEAD -- <files you touched>`; if your fix edits lines an earlier run commit authored, name that commit and state whether it was wrong or incomplete."* **30% of all source-line deletions were the run deleting its own fresh code**; 19 of 62 commits would have tripped this, and BH-335 would have been caught at 00:25 instead of 04:57. |
| P6.7 | **Reconciliation outcomes must be written back onto the findings.** `moot-reconciliation-round5.md` has **0 reads** after being written. The run paid to discover staleness and filed the answer where nothing reads it. |
| P6.8 | **Investigation-file discipline silently lapsed.** `docs/holtz/investigations/` holds 4 per-finding files, all from a 90-minute window on 08-17, and none after. No gate noticed. |

---

## What the evidence does *not* support

Recorded so these are not re-proposed:

- **Session re-onboarding is not a problem.** `/clear` → first productive action is **32.5
  agent-min across 10 sessions** (median 2.2 min). The resume primer works.
- **Test execution is not a bottleneck.** 1,116 pytest executions = **110 min of 1,351**;
  full suite median 24.6 s. Fix subagents are 87% model generation.
- **Compaction is not happening.** Zero compaction events in 117 transcripts. Any proposal
  premised on compaction recovery is solving a non-problem — and the *defenses* against it
  are a top-3 cost driver (P2.5).
- **The audit phase is not the waste.** It delivered every CRITICAL in 143.7 min wall.
  Trim it (Tier 4), don't restructure it.
- **Enforcement friction is not why the run was slow** — 7.3% of orchestrator time. It is
  why the run *stopped* (P3.5).

---

## Measurement caveat for anyone re-deriving these numbers

Claude Code writes **multiple jsonl records per assistant message** while streaming, all
sharing one `message.id`. Summing `output_tokens` across records over-counts (7.7M here);
taking the **first** record per id under-counts badly (1.8M) because early partials carry
`output_tokens: 1`. **Reduce with `max` per `message.id`** → 6,675,091. `cache_read` is set
at request time and is constant across partials, so it is safe either way (761,854,973).

`<session-id>/subagents/*.jsonl` must be walked explicitly — it holds **85% of output and
78% of cache-read**, and is invisible to any tool globbing only top-level sessions.

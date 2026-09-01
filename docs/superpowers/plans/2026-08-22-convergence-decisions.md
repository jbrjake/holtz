# Convergence proposals — decisions, RULED

**Written 2026-08-22; ALL 27 RULINGS RECORDED the same day**, given by Jon
interactively in-session. Consolidates the restoration handoff's §5 with what
the 2026-08-22 adversarial verification pass found on top of the deviation
audit. **This file plus the frozen spec is the complete implementation
authority. A clause that cannot be implemented as ruled stops the turn with a
question.**

Repo state when written: spec restored to the 08-18 original (+ Jon's five P4
rejections); status split out to `docs/design/convergence-speed-status.md`;
`6b12186` (the shipped P0.1 gate) reverted in `334cddf`. All other 2026-08-21
work is still in the tree as shipped.

Sources: `2026-08-21-plan-deviation-audit.md`,
`2026-08-22-spec-restoration-handoff.md`, and the 2026-08-22 verification pass
(every code commit diffed against the recovered original; its disagreements
with the audit were spot-checked against the code).

---

## A. Spec integrity

### D1 — Ratify the frozen-spec regime
The spec is now restored and read-only to implementers; all status lives in
`convergence-speed-status.md`; the only markers on spec rows are the five Jon
wrote. Two sub-questions from the handoff: (a) is this the standing regime for
this and future plan docs? (b) may any marker other than Jon's ever appear on a
spec row?
**Ruling (Jon, 2026-08-22): RATIFIED, both halves.** Standing regime for this
and future plan docs; strictly no non-Jon markers on spec rows.

## B. P0.1 — rebuild (the gate is reverted; nothing stands in its place)

### D2 — Rebuild clause 1 as written?
Plan: *"Add a gate on `pattern_done`: `A = findings_filed_since(fix_loop_start)
/ resolved_since(fix_loop_start)`. If `A > 1.0` for 3 consecutive rounds, block
`fix_commit` until every open LOW and the MEDIUM budget is batch-deferred via
one `sahjhan defer batch --severity low,medium` writing `docs/holtz/DEFERRED.md`."*
Notes for the ruling, not arguments against it: `sahjhan defer batch` is engine
work (the plan's standing preference — *"Prefer changing the engine"* — points
there); the per-round `A` series needs the round ordinal derivable from the
ledger (adjacent to P5.5); the 08-21 session's objection that a `fix_commit`
block fires between a green fix and its ledger entry was one of its 19 unasked
deviations, but the underlying question (block `fix_commit` vs block the next
dispatch) is now yours to settle explicitly.
**Ruling (Jon, 2026-08-22): REBUILD, with one granted amendment — the block
lands on dispatching the next fix, not on `fix_commit`.** Everything else as
written: `A > 1.0` for 3 consecutive rounds measured from `fix_loop_start`,
gate on `pattern_done`, escape = every open LOW **and** the MEDIUM budget via
one engine-side `sahjhan defer batch --severity low,medium`, writing
`docs/holtz/DEFERRED.md`.

### D3 — Any taught triage default at all?
The reverted skill text made batch LOW-deferral unconditional at fix-loop entry
on every run (*"Triage before dispatching"*). The plan's deferral is
conditional — it fires when the circuit-breaker trips. Should any standing
triage instruction exist in the skill files, or does deferral appear only as
the breaker's escape?
**Ruling (Jon, 2026-08-22): NO STANDING DEFAULT.** Deferral appears only as
the breaker's escape. LOWs stay first-class work unless divergence forces
triage; deferral-as-triage prose waits for P6.2.

### D4 — The convergence redefinition, as a package, after P0.5
Plan: *"`all CRITICAL resolved AND all user_reachable HIGH resolved-or-deferred
AND A < 1.0 over last 3 rounds AND DEFERRED.md written`"*. Never built; needs
P0.5's `user_reachable` field. The 08-21 session rejected two conjuncts
unilaterally; the `A < 1.0` rejection was invalid (scored against the gate the
package replaces). Decide the four conjuncts **as a package** when P0.5 lands.
**Ruling (Jon, 2026-08-22): PRE-COMMITTED — BUILD AS WRITTEN once P0.5 lands.**
All four conjuncts, no second decision round; any deviation found at
implementation time still stops the turn with a question.

### D5 — The severity carve-out vs `defer_medium`'s 50% cap
Excusing MEDIUM/LOW from convergence voids the only rule forcing a run to *fix*
half its MEDIUMs rather than defer them. Never properly evaluated. Belongs with
D4/P0.5.
**Ruling (Jon, 2026-08-22): THE CAP STAYS LOAD-BEARING.** Whatever form the
redefinition takes, converging must still require the MEDIUM budget spent —
the 50% fix-half rule keeps force. This constrains the D4 package design.

## C. Owed halves — build as written, or strike

### D6 — P0.2: the ">25 pattern-filed findings open" conjunct
Plan: *"no round while >25 pattern-filed findings are open, **or** after two
consecutive rounds that added no new PAT entry."* Only the second half shipped
(`e1ed6c9`). The first half was rejected on "no field records which round filed
a finding" — a premise question, not a ruling. (`ceb7414`'s `pattern_ids` field
may now make the population derivable.)
**Ruling (Jon, 2026-08-22): BUILD AS WRITTEN.** Derive the population from
`pattern_ids` if D22 ratifies it; otherwise add the needed provenance.

### D7 — P0.2: the ≤3-new-items cap and the close-as-many-as-you-open obligation
Plan: *"Cap each round at ≤3 new items, with an obligation to close or merge at
least as many as it opens."* Neither half shipped. The 08-21 session's wedge
concern (a hard cap on `pattern_done` is not undoable once a fourth finding is
filed) is real engineering input for the cap half; the obligation half has no
wedge problem and was simply never addressed.
**Ruling (Jon, 2026-08-22): BUILD BOTH.** The cap's escape (merge/close path)
must be guaranteed by construction; a design blocker there stops the turn with
a question, not a unilateral narrowing.

### D8 — P0.2: the stale sweep *replacing* pattern analysis past ~round 8
Plan: *"run it **instead of** pattern analysis past ~round 8."* Step 11b runs
*in addition to* pattern analysis today. The plan's ~220–470 agent-min saving
rests substantially on this swap.
**Ruling (Jon, 2026-08-22): BUILD THE SWAP AS WRITTEN.** Past ~round 8 the
owed round is satisfied by a stale sweep instead of pattern analysis; rides on
D2's round-ordinal machinery.

### D9 — P0.4: the one-line, ≤12-word summary render
Plan: *"open items only, one line each (id, severity, `file:line`, ≤12-word
summary ≈ 10–12k tok vs 81k)."* The render still emits the six-column table
with full descriptions. `findings.py list` emits one 90-char line per finding,
so part of the token saving is realized off the render path.
**Ruling (Jon, 2026-08-22): BUILD, RENDER-SIDE TRUNCATION.** The template
truncates the existing description — no new agent-written field, no
double-entry.

### D10 — P3.2: `agent_id` keying, and the missing `hook_e2e` test
Plan: *"key counter on `agent_id`; don't tick on read-only commands… **Needs a
`hook_e2e` test**."* The read-only half shipped; the keying was declined with a
defensible argument (54 subagents × 15 free commands each). Separately, the
required test is `integration`-marked, not `hook_e2e` — a standing CLAUDE.md
violation whatever the keying ruling; fixing the marker/coverage will be done
unless you object.
**Ruling (Jon, 2026-08-22): BUILD THE KEYING AS WRITTEN.** Per-actor counter
for write-capable commands (read-only already exempt). The `hook_e2e` test
obligation stands and covers the new behavior.

### D11 — P3.5's artifact cap: sequence P2.1?
The cap is blocked on P2.1 (byte-cap the brief), which is not started. Decide
whether P2.1 moves up the queue or the cap stays parked.
**Ruling (Jon, 2026-08-22): PULL P2.1 FORWARD.** Queue it alongside the Tier 0
rebuild; P3.5's artifact cap unblocks behind it.

## D. Shipped without a ruling — ratify or unwind

### D12 — P1.2: routing rule
Plan: route *"vacuous test" and single-file fixes* to Sonnet (~30 of 59
qualify). Shipped: Fast Path → Sonnet — a different rule over a different
population (`d4e5f8b`).
**Ruling (Jon, 2026-08-22): REBUILD TO THE WRITTEN RULE.** Route "vacuous
test" and single-file fixes to Sonnet; the Fast Path proxy is removed unless
it also matches the written criteria.

### D13 — P2.2: compact read placement
Plan: *"Promote to its own numbered step."* Shipped folded into existing step 4
(`d4e5f8b`).
**Ruling (Jon, 2026-08-22): PROMOTE TO ITS OWN STEP, as written.**

### D14 — P0.4: the merge-completion gate swap
Plan: *"Gate its deletion at the `merge → fix_loop` transition."* Shipped
instead: `merge_complete` runs `validate_merge_report.py` against
`MERGE-REPORT.md` — an agent-authored, unmanaged artifact; the commit's own
message notes the gate "is satisfiable by its writer… the distinction #60
turned on" (`57a4c02`). No deletion gate exists. This deviation was invisible
to the audit.
**Ruling (Jon, 2026-08-22): BOTH GATES.** Build the written deletion gate
(fix_loop entry requires `PUNCHLIST-MERGED.md` gone) and keep the shipped
MERGE-REPORT validation as an accidental P4.9 slice.

### D15 — P4.2 shipped silently
`57a4c02` also deleted the renumbering rule (P4.2, a plan item with no audit
row): merged items keep ledger ids, `BJ-` ids preserved. Ratify or revisit.
**Ruling (Jon, 2026-08-22): RATIFIED.** P4.2 counts as shipped; the silent
shipping is noted in the record but the outcome stands.

### D16 — Contradiction handling changed
`57a4c02` changed merge contradictions from `**Status:** DEFERRED` to OPEN plus
a report flag. Not in the plan.
**Ruling (Jon, 2026-08-22): RATIFIED.** Contradictions land OPEN; deferral
stays an explicit, budgeted act.

### D17 — P3.3's blast radius
Plan asked the *detector* to substitute `VAR=` and unwrap `eval`. Shipped:
`resolve_indirection` inside `_split_shell_segments`, so **every** segment
predicate (commit detection, sahjhan detection, the read-only exemption, the
blocked-command check) changed input at once, plus quote-stripping in
`_segment_is_sahjhan` (`627e99b`). It also closed a real hole (the human-only
`quiz_exhausted_resolved` channel was reachable via `"$SAH"` indirection).
Ratify the wider wiring or narrow it.
**Ruling (Jon, 2026-08-22): RATIFIED, wide wiring.** All gates see through
indirection uniformly; the human-only channel stays sealed.

### D18 — `375b19f`'s semantic changes
Beyond the plan's "dedupe at render": STATUS.md's Open count recomputed from
per-id bucket membership (fixes an `Open: -1` case), and `defer_medium`'s
budget gate moved to `count(DISTINCT id)` — a deferral-policy change.
**Ruling (Jon, 2026-08-22): RATIFIED, both.** Consistent with D5 — the
load-bearing cap counts distinct findings.

### D19 — `fa058cd`'s additions
Plan: delete two `step-10-fix-loop.md` update steps. Shipped: 11 deletions
across 5 files **plus added mandates** (per-sibling `sahjhan … event finding`,
`event blast_radius`) **plus** re-scoping `status-file-format.md` from Holtz's
STATUS.md to Justine's.
**Ruling (Jon, 2026-08-22): RATIFIED, all additions kept.**

### D20 — The recon → archive dependency
`6d78c7f`'s open-only render means `phase-recon.md`'s cold-file coverage scan
now must also read `docs/holtz/archive/*/PUNCHLIST-ARCHIVE.md`. A new cross-run
dependency, unremarked at the time.
**Ruling (Jon, 2026-08-22): RE-DERIVE FROM THE LEDGER.** New work item:
replace recon's punchlist/archive file reads for cold-file coverage with a
ledger query. The shipped file-read stands only until that lands.

### D21 — Step 11b's population
The stale sweep the plan cites triaged **all 68 open HIGHs** in 14 min. Shipped
Step 11b triages only findings whose `location` names a file the run changed
(`bb502ca`). Widen to all-open, or keep the narrow set?
**Ruling (Jon, 2026-08-22): WIDEN TO ALL OPEN FINDINGS.** Every open finding
is re-triaged at each sweep, all severities — necessary now that D8 makes the
sweep the only late-run round.

### D22 — P5.4's expansions
Plan is one line: derive `patterns_found` by diffing PAT headings. Shipped
around it (`ceb7414`): the event became `restricted` + `tool`-attested;
`phase`/`step` fields deleted and `pattern_ids` added; a new
`pattern_courier.py` trusted hook; the taught step order swapped. Each matches
the project's provenance doctrine; none was asked for.
**Ruling (Jon, 2026-08-22): KEEP THE ADDITIONS, BUT RESTORE `phase`/`step`.**
The restricted + tool-attested event, `pattern_ids`, the courier hook, and the
step order all stand. The deletion of the `phase`/`step` fields is reversed —
new work item: put both fields back on the event.

### D23 — The resweep's extra scope
Plan: scope Step 16's resweep *"to files changed by fixes."* Shipped: changed
files **plus impact-graph blast radius depth 2**, plus an invented fallback —
*"if the run changed no source files, the resweep is the full Steps 6–8"*
(`f17aaec`).
**Ruling (Jon, 2026-08-22): KEEP BOTH RIDERS.** Depth-2 blast radius and the
no-source-changed fallback both stand.

### D24 — The pattern gate on `set complete perspective`
`5b0c4f0` added `pattern_analysis_overdue expect=false` to `set complete
perspective` — a gate on a command the plan never mentioned.
**Ruling (Jon, 2026-08-22): KEEP IT.** Ratified as a deliberate extra pressure
point; perspectives cannot complete past an owed round.

### D25 — Severity is the latest filing
`fe2ef56`, shipped unasked while probing P0.1's premise: three gate sites now
grade a finding by its latest filing, so a LOW→HIGH correction can no longer be
batch-closed as a LOW. Real defect, but it changes `defer_low`/`defer_medium`
behavior and was never put to you.
**Ruling (Jon, 2026-08-22): RATIFIED.** Corrections take effect at every gate;
D2's escape and the deferral commands stay in agreement.

## E. Likely closed — confirm and strike

### D26 — P3.1's "unconditional allow under `_PLUGIN_ROOT`"
The audit lists this as declined work; the verification pass found the effect
is achieved: `_out_of_tree_script_block` already returns None for anything
resolving in-tree, and `ded5767`'s expansion is what routes the taught
`${CLAUDE_PLUGIN_ROOT}/…` commands to that branch (the unexpanded-variable
direction is pinned the other way). Confirm nothing stronger was meant by
"unconditional."
**Ruling (Jon, 2026-08-22): CONFIRMED CLOSED.** Nothing further owed on P3.1;
the literal-prefix variant stays rejected.

### D27 — P3.4 is moot
`5c23656` shipped a different mechanism than the prescribed "clear inside the
`pattern_done` transition"; `5b0c4f0` then deleted both that mechanism and the
commit-path block it protected. The reported defect (stale flag holding
commits 12–25 min) has no surface left at the commit path. Confirm closed, or
name what remains owed.
**Ruling (Jon, 2026-08-22): STILL OWED.** Not discharged by the block's
deletion — the cached flag must not go stale even where it only feeds advisory
output. Default to the written prescription (clear inside the `pattern_done`
transition); any blocker found at implementation time ends the turn with a
question per the process rules.

---

## Work queue derived from the rulings

**No work (ratified as shipped):** D1, D15, D16, D17, D18, D19, D23, D24,
D25, D26.

**Standalone, no dependencies — do in any order first:**
1. D27 — clear the cached `pattern_analysis_overdue` flag inside the
   `pattern_done` transition (advisory freshness; blocker → ask).
2. D10 — key the stall counter on `agent_id`; move/extend the required test to
   `hook_e2e`.
3. D13 — promote the compact brief read to its own numbered step (+ line-order
   test).
4. D12 — rebuild Sonnet routing to the written vacuous-test/single-file rule.
5. D9 — one-line ≤12-word punchlist render, render-side truncation.
6. D14 — add the deletion gate at `merge → fix_loop` (PUNCHLIST-MERGED.md
   gone); the report gate stays.
7. D21 — widen Step 11b's population to all open findings.
8. D22 remainder — restore the `phase`/`step` fields on the pattern event.
9. D20 — recon cold-file coverage from a ledger query, replacing the
   punchlist + archive file reads.

**Sequenced:**
10. D11 — P2.1 (cap the brief at 20 entries AND 40 KB) pulled forward; then
    P3.5's artifact cap behind it.
11. D2 + D3 — the breaker rebuild: engine-side `sahjhan defer batch` +
    `DEFERRED.md`, round ordinal derivable from the ledger (also serves D8 and
    gives P5.5 nearly free), `A > 1.0` for 3 consecutive rounds from
    `fix_loop_start`, gate on `pattern_done`, **block the next dispatch** (the
    granted amendment), escape = every open LOW + MEDIUM budget spent. No
    standing triage default in any skill file.
12. D6 — the >25-open conjunct, population from `pattern_ids`.
13. D7 — the ≤3-items cap (escape by construction; blocker → ask) and the
    close-as-many-as-you-open obligation.
14. D8 — the sweep replaces pattern analysis past ~round 8 (needs D2's round
    ordinal).
15. P0.5 — reachability grading; then D4 (pre-committed: build the four
    conjuncts as written) under D5's constraint (converge additionally
    requires the MEDIUM budget spent).
16. P0.3 after its gate change (gate before batching, per the spec); P4.1
    (script the merge) whenever convenient — cheapest open item.

## F. P0.5's remainder and one linter question — ruled 2026-08-25

Raised at the start of session 5, after session 4 shipped P0.5 clause 1a and
D4+D5 and left these three clauses OWED with a blocker each. Every mechanism
below was checked against the tree, not inferred.

### D28 — P0.5's severity derivation
The clause derives severity from `(reachability, blast_radius.affected_count,
public-API surface)`. Only the first exists at `event finding` time:
`blast_radius` is recorded at Step 10's per-fix procedure — so only for
findings that already entered the fix loop — and "public-API surface" has no
ledger representation at all. Three trigger shapes were costed: re-derive on
each `blast_radius` (a courier; grades only the already-worked population,
which is the opposite of the clause's stated problem — 51 of 75 open HIGHs were
never worked), compute at render/gate time (8+ gate queries, the punchlist
template and `findings.py`, against a planner that already rejects a correlated
subquery inside a comparison), or drop `affected_count` and derive at filing
from `reachability` plus a new `surface` field.
**Ruling (Jon, 2026-08-25): WON'T DO.** The clause does not ship. The shipped
`reachability` field (clause 1a) is what D4's convergence conjunct is defined
over and stands on its own; severity stays a typed field.

### D29 — P0.5's routing
Three unrelated builds in one clause. `user_reachable`-only fix-loop
eligibility is a plain named-query gate of the `item_is_low` shape and needs
nothing new. `theoretical` auto-defer has no mechanism — `event finding` is an
event, and only transitions carry `emits`. `fault_injected` batching at
finalize is a procedure, not a gate, and "per module" has no ledger meaning:
`location` is a `file:line` string.
**Ruling (Jon, 2026-08-25): SHIP the eligibility gate and a courier
auto-defer.** The courier over teaching the openness predicates to skip
`theoretical`, so there stays exactly one definition of closed and
`DEFERRED.md` needs no second rule — the same reasoning that chose the courier
in D8. **The finalize-batching third is still owed a decision** and must not be
shipped as unenforced prose; it comes back as its own question, with the module
definition scoped first.

### D30 — P0.5's reopen-don't-refile
Two gaps, with different risk. The rejection half cannot be a gate — the engine
does not gate events — so it is a `PreToolUse` hook parsing the `event finding`
command line. The reopen half needs a new event *and* seven openness predicates
(`item_open`, `all_findings_closed`, `open_low_findings`,
`open_medium_findings`, `round_item_cap_exceeded`, `all_critical_resolved`,
`all_user_reachable_high_closed`) converted from set-membership to a temporal
close-unless-a-later-reopen test, in the gates that decide convergence, the
round cap and the deferral budget. The rejection half alone is worse than
nothing: it routes new information onto a closed record.
**Ruling (Jon, 2026-08-25): WON'T DO.** The clause does not ship in either
half. D25 (a re-filing supersedes the finding's fields) keeps the part of the
value that was already reachable.

### D31 — H8's two false warnings
`enforcement_lint.py` H8 warns twice that `converge` prints `sweep_dirty` as
its escape while `sweep_dirty`'s readiness is "decided by an inline predicate".
`sweep_dirty` has no gates at all, so it cannot be unsatisfiable and the
warning is false rather than noisy. Session 4 left it alone because H8 had
already been narrowed once that session and a second unasked change to a
shipped check is a question.
**Ruling (Jon, 2026-08-25): NARROW IT — stay quiet when an escape has no
gates.** The argument-scoped exemption made in session 4 **stands**: its
compensating control was verified to exist at
`tests/test_round_item_cap.py:183`, which drives `merge_finding` from the
blocked state against the real transitions and asserts the cap clears.

### Work queue addendum
17. D31 — narrow H8 (cheapest; independent of everything else).
18. D29 — the `user_reachable` fix-loop eligibility gate, then the
    `theoretical` auto-defer courier. Finalize batching stays owed a ruling.

D28 and D30 close P0.5 with no further work. Item 16 (P0.3, then P4.1) is
unchanged and still precedes both of the above unless Jon reorders.

## G. P0.3's gate change — ruled 2026-08-25

### D32 — the gate cannot be scoped in `hooks.toml`
P0.3 says "scope the gate to `finding_id` (or `agent_id`)". Half its premise
holds: `enforcement/hooks.toml:17-20` is exactly the run-global
`ledger_has_event_since / test_failed_before_fix / since = last_transition`
the spec describes, and two concurrent fix agents do satisfy each other's gate.
The other half does not. Verified in sahjhan 0.22.1's source:
`ledger_has_event_since` *does* take an optional `filter` table
(`src/gates/ledger.rs:129-138`) the spec did not know about, but
`entry_matches_filter` (`src/gates/types.rs`) compares against literal static
config strings; `eval_hook_condition` (`src/hooks/eval.rs`) built
`GateContext { state_params: HashMap::new(), event_fields: None }`, so hook
gates evaluated with no variables at all; `agent_id` appeared nowhere in the
crate, and `HookEvalRequest` carried only event/tool/file/output_text; hook
checks of `type = "query"` are a `return false` stub.
**Ruling (Jon, 2026-08-25): EXTEND SAHJHAN.** Carry `agent_id` on
`HookEvalRequest`, seed it into the hook gate's `state_params`, and resolve
`{{var}}` in filter values. The gate stays declarative in `hooks.toml` — one
expression of the fact, still visible to the generated contract — rather than
moving the predicate into Python where H7 exists to flag it.
Shipped in sahjhan `b564a07` (released as v0.23.0) as `feat(hooks)`: `--agent-id` on `hook eval`,
the three copied filter blocks collapsed into one `gate_filter()` that resolves
through `resolve_template_plain`, and `None` binding to the empty string so the
orchestrator is a real actor and never a wildcard. An unbound placeholder stays
literal and matches nothing, so a misconfigured filter fails closed.

### D33 — the actor has to reach the event
`filter = { agent_id = "{{agent_id}}" }` asks the ledger which actor recorded
the failing test, but `test_failed_before_fix` is agent-written via `sahjhan
event` and carries no actor — `docs/ENFORCEMENT-CONTRACT.md:381` names its
writer as `agent`, and `chain.rs::append` stamps nothing. Wiring the filter
against the event as it stands would match zero entries and block every actor:
a #77 deadlock, strictly worse than the run-global gate. Claude Code gives
`agent_id` to the *hook*, not to the model, so an agent-stated field is not
merely forgeable — there is no evidence a subagent can read its own id at all.
**Ruling (Jon, 2026-08-25): A COURIER STAMPS A HOST-ATTESTED EVENT.** A
PostToolUse/Bash courier reads the real `agent_id` off the hook payload when it
sees a successful `sahjhan event test_failed_before_fix`, and writes a
`restricted` + `tool`-attested event carrying it. The TDD gate keys on that.
Third instance of the P5.4 / D8 pattern, and the provenance rule holds: the
signal entails the fact.

### Work queue addendum
19. D33 — build the courier and its event, switch the `hooks.toml` gate onto
    it, add the `hook_e2e` test P0.3 requires and the subagent-parity test
    CLAUDE.md mandates. **Blocked on a sahjhan 0.23.0 release**: holtz vendors
    from `jbrjake/sahjhan` GitHub releases, so the gate switch cannot be
    exercised until the binary carrying D32 is published and
    `scripts/vendor-sahjhan.sh 0.23.0` has run. The courier and its event do
    not depend on that and can land first.

## H. D29's remainder — ruled 2026-08-25 (session 6)

Raised after P4.1 shipped, when the eligibility gate turned out not to be
independently shippable. Every claim below was observed against sahjhan 0.23.0
and the real `enforcement/` config, not read.

### D34 — the eligibility gate has no escape for `fault_injected`
D29 called `user_reachable`-only fix-loop eligibility "a plain named-query gate
of the `item_is_low` shape [that] needs nothing new". The shape is right; the
escape is not there. The only place the engine can see fix-loop eligibility is
`fix_commit` (`fix_start` is an event, and D30 established the engine does not
gate events). Putting `user_reachable` on `fix_commit` removes the only route
to `finding_resolved` for a `fault_injected` CRITICAL, and **nothing can defer
one**: driven from inside `fix_loop`, `defer_low`, `defer_medium` and
`defer_cant_reproduce` all returned `result: blocked` for a `fault_injected`
CRITICAL *and* HIGH — the first two are literal severity equality, so no HIGH
or CRITICAL can use either. `all_critical_resolved` stayed `false` after
deferring, by design ("deferring one does not converge"). So the run could
neither converge nor make itself converge: #77's shape at the end of the run.
Re-grading is not an escape either — `reachability` is re-filable with a plain
`sahjhan event finding` and the latest filing wins, so it is a forgery.
The escape the clause names for `fault_injected` — batching at finalize — is
exactly the third of D29 left owed a ruling. The gate and the batching are one
decision.
**Ruling (Jon, 2026-08-25): HOLD THE GATE, SHIP THE COURIER.** The
`theoretical` auto-defer courier lands now; the `user_reachable` eligibility
gate waits until finalize batching gives `fault_injected` a real escape, so the
block is escapable by construction rather than by care.

### D35 — what a "module" is for `fault_injected` finalize batching
`location` is free text (`file.py:88`, `` `file.py:88` ``,
`file.py:88 (function f)` — all three appear in this repo's archived ledgers),
so "one hardening commit per module" had no ledger meaning until a rule was
chosen.
**Ruling (Jon, 2026-08-25): THE CONTAINING DIRECTORY.** A module is the
directory of the file named in `location` — `tqdm/std.py:736` and
`tqdm/utils.py:240` batch together as `tqdm/`; `tqdm/contrib/x.py:12` is its
own. This unblocks D34's gate.

### Work queue addendum
20. D29 first half — the `theoretical` auto-defer courier. **SHIPPED.**
21. D35 — `fault_injected` finalize batching, one hardening commit per
    containing directory. **SHIPPED** (`2058677`).
22. D34 — the `user_reachable` eligibility gate on `fix_commit`, **after** 21,
    so its escape exists when it lands. **SHIPPED** (`e537cae`).

## I. D34/D35 implementation rulings — ruled 2026-08-25 (session 7)

Given interactively while D35 and D34 were being built, and recorded here
2026-08-26 from `2026-08-25-convergence-implementation-handoff-4.md`, which was
their only written home. Both items shipped under these rulings; the
transcription is what makes the authority file authoritative again, not a new
decision. Every mechanism cited was observed against sahjhan 0.23.0 and the
real `enforcement/` config.

### D36 — how a batch of `fault_injected` findings gets closed
D35's batch retires several findings with one hardening commit. Two shapes were
available: a coverage gate on an existing transition, or a courier that writes
one resolution per covered id. The engine settles it —
`EmitConfig` (sahjhan `src/config/transitions.rs:101`) makes exactly **one**
event with a fixed field map, and `machine.rs:249` iterates a static `Vec`, so
no transition can fan out one `finding_resolved` per batched id however the
gate is written.
**Ruling (Jon, 2026-08-25): A COURIER CLOSES THEM.** `hardening_batch.py`
derives and checks inside the agent's sandboxed shell;
`hardening_batch_courier.py` writes one `finding_resolved` per covered id from
outside it. Closing with `finding_resolved` keeps D29's single definition of
closed, so `DEFERRED.md`, the punchlist counts and every openness predicate
need no second rule.

### D37 — where the batch runs, given the spec says "at finalize"
P0.5's clause places `fault_injected` batching at finalize. Measured against
the state machine, finalize is too late to be the escape D34 needs:
`all_critical_resolved` gates `converge`, carries no reachability filter, and
refuses a deferral — observed `false` for a `fault_injected` CRITICAL and still
`false` after all three deferral reasons — so `finalize` sits two transitions
past the door that a `fault_injected` CRITICAL cannot open.
**Ruling (Jon, 2026-08-25): BEFORE `converge`, as Step 15's third line.** The
spec's "at finalize" is where the batch was described, not a constraint on
which side of the gate it runs; running it earlier is what makes D34's block
escapable by construction.

### D38 — D34's gate also stranded a `theoretical` CRITICAL
D34 argued its escape for `fault_injected` and stopped there. `reachability`
has three values, and `theoretical`'s only route to `finding_resolved` *was*
`fix_commit` — precisely what the gate closes. Measured, not inferred: a
`theoretical` CRITICAL is auto-deferred at filing, `all_critical_resolved`
refused that deferral, `merge_finding` refused it as already closed (`item_open`
observed `false`), and the hardening batch's population is `fault_injected`
**and open**. Re-grading is the forgery D34 already names.
**Ruling (Jon, 2026-08-25): `all_critical_resolved` EXCLUDES a `theoretical`
deferral.** `theoretical` is the one reason word a courier writes rather than
an agent choosing it, so excluding it cannot be talked into. Every
discretionary deferral reason still refuses.

**The rule this establishes, because the shape will recur.** When adding a gate
keyed on a field, enumerate **every value of that field's domain** and name
each one's route to the post-state the gate demands — including the routes that
already existed, since the gate may be closing one. Write the enumeration as a
test (`TestEveryCriticalHasARoute` in `tests/test_fix_loop_eligibility.py`), not
as a paragraph. This is D2's escape-by-construction rule one level out: not
"does the predicate imply the escape" but "does *every* value the predicate
rejects have one".

## J. P0.3's worktree half — ruled 2026-08-26 (session 8)

Raised before any code was written, per the process rules. P0.3's second half
says *"give fix subagents `isolation: "worktree"` … orchestrator merges and
commits serially"*. Its premise holds — a linked worktree's
`compute_tree_hash` is per-agent, and the ledger stays shared because sahjhan's
`project_root_from` walks up to the main root for `docs/holtz/.sahjhan` — but
three mechanisms it does not name block it. All were measured against Claude
Code 2.1.246 and a real pair of linked worktrees, never inferred; the
measurements are in `convergence-speed-status.md`'s P0.3 row.

### D39 — how the merged main tree gets its `suite_green`
`suite_green.tree_hash` names one exact tree, and `fix_commit`'s two command
gates both run at the project root, so the commit must be on the main branch
with the *main* tree green. A per-worktree green does not survive the merge:
two worktrees carrying **disjoint** edits produced H(A), H(B) and H(A+B) all
distinct, the merged tree matching neither recorded green. That is semantic
rather than plumbing — B's suite never ran against A's changes, and the spec's
own figure has 26% of pairs among four consecutive fix commits touching shared
files.
**Ruling (Jon, 2026-08-26): REBASE, THEN RECORD.** The subagent's last act is
to rebase its worktree onto the current main tip and re-run
`verify_suite.py --record --scope affected`; the orchestrator merges
fast-forward only. The tree the subagent proved is then the tree that lands, so
`fix_commit`'s suite gate needs no change and `phase-fix-loop.md`'s "read the
evidence, don't redo it" stays true. The rebase-and-re-run tail serializes; the
investigate-and-author phase, which is 87% model generation, still runs N-wide.

### D40 — the daemon socket a linked worktree resolves
`boundary_dir()` is `~/.holtz/run/<sha256(realpath(cwd))[:12]>`, documented as
deliberate so two checkouts of one repo cannot collide. Observed
`009ba37dc895` for the main tree and `02fab2dfc288` for a linked worktree, so a
worktree subagent's `tdd_courier.py` and `suite_courier.py` would resolve a
socket nothing is bound to and fail closed — and `tdd_evidence` is
`restricted`, so the per-actor TDD gate D32/D33 just shipped could never open
for a worktree subagent at all.
**Ruling (Jon, 2026-08-26): KEY ON THE MAIN WORKTREE.** Linked worktrees of one
project share one daemon; separate clones still get separate sockets, which is
what the original keying was for. It touches a security boundary
(`sandbox_control.py` denies writes there, and sahjhan's fuse refuses a socket
resolving inside the project root), so it lands with a `real_daemon` test
proving a worktree subagent can write `tdd_evidence` and that a second checkout
still cannot reach this project's daemon.

### D41 — a subagent cannot reach the pending-commit block's escape
Raised while drafting D39's sequence, before any of it was written.
`commit_gate.py` refuses `git commit` in `fix_loop` while `unregistered_commits`
is non-empty, and `protocol_tracker.py` appends to that list on *any* successful
commit by *any* actor, into the cache the daemon serves — which D40 now shares
with every linked worktree. So the first fix subagent to commit refused every
other one, and the block named `transition fix_commit` as the way out: the
orchestrator's transition, gated on `git log -1` and a tree hash both taken at
the project root. The blocked actor could not reach its own escape. Two shapes
were available — teach the subagent to stash across the tip and leave the
commit with the orchestrator, or key the list on the actor.
**Ruling (Jon, 2026-08-26): KEY IT ON THE ACTOR.** The same fix D10 applied to
the stall counter, from the same `agent_id`, with the orchestrator as the
empty-string bucket. The subagent then commits on its worktree branch and the
taught command is a plain `git rebase`. The *clear* stays run-global:
`fix_commit` registers whatever commit is at `HEAD`, and after a fast-forward
that commit was authored by a subagent the transition cannot name.

### Work queue addendum
23. D40 — `boundary_dir` resolves the main worktree. **SHIPPED** (`6091cda`).
24. D41 — key `unregistered_commits` on the actor. **SHIPPED** (`2e0b1d7`).
25. D39 — rewrite `phase-fix-loop.md` to serialize commits rather than
    findings: worktree-isolated dispatch, the rebase-then-record tail,
    fast-forward-only merges. **SHIPPED** (`823c90b`).

**The work queue is empty.** Every item from §E's original list through this
addendum is shipped, ruled WON'T DO (D28, D30), or ratified as already shipped.

## Process rules for the implementing session (Jon's standing threshold, 2026-08-21)

- **Any deviation from a written clause — wrong premise, missing field,
  different mechanism, dropped clause, added scope, DONE-vs-PARTIAL — stops the
  turn with a question, before any code is written.**
- A false or blocked premise ends the turn with a question; verifying a premise
  is required, re-deriving the remedy is not the implementer's call.
- Report a clause as unimplemented rather than reasoning about why it need not
  be implemented.
- The spec is read-only. Status goes to `convergence-speed-status.md`, per
  clause, never marking contested rows settled.

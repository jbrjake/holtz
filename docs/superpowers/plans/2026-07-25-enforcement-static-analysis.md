# Making the enforcement layering statically analyzable

**Status:** Phases 0–3 landed. `sahjhan lint` + `scripts/enforcement_lint.py`
both block in pre-commit, pre-release, and CI. **Resume at Phase 4** (generate
`ENFORCEMENT-CONTRACT.md` and the trust graph).
**Tracking:** holtz [#82](https://github.com/jbrjake/holtz/issues/82) · engine portion [jbrjake/sahjhan#32](https://github.com/jbrjake/sahjhan/issues/32) · first defect found [#81](https://github.com/jbrjake/holtz/issues/81)
**Motivation:** #73 (gate unsatisfiable), #77 (gate deadlocked), #79 (gate satisfied without cause)
**Goal:** find the next one without running an audit

## Next session starts here

Phases 0–3 are done (2026-07-26). What remains:

1. **Phase 4 — everting.** Generate `docs/ENFORCEMENT-CONTRACT.md` from the
   declarations now in the tree: one row per gate giving the fact required, the
   event, its writer, and its attestation class. The data is already there —
   `python3 scripts/enforcement_lint.py --census` prints it. Add a staleness
   test like `test_hook_schema_freshness.py`.
2. **Two open findings**, both recorded below and neither blocking:
   `prediction`/`prediction_outcome` are read by `summary.md.tera` and written
   by nothing, and eight L6 near-miss predicate pairs are unmigrated.
3. **The ratchet is now live.** Any field-found gate defect must become a check
   or be recorded here as un-lintable *with the reason*.

### Phase 0 findings

Measured on `dev` @ `4a85303` with sahjhan v0.20.0. Both halves ran: the engine's
L1–L7 over the protocol graph, and `scripts/enforcement_lint.py`'s H1–H6 over
the parts of the chain that live in holtz code.

The headline: **the approach paid, but not where the plan predicted.** The
prototype's "12 dead declarations" was the least interesting number. The real
yield was three latent defects that no test covered, one of which was a
single-character bypass of every command block in the repo — and it surfaced
only because implementing a *different* finding forced the question "can the
agent get at this another way?"

#### Engine checks (`sahjhan lint`)

| Finding | Count | Verdict | Action |
|---|---|---|---|
| L1: `resume` requires restricted `context_reset`, no producer | 1 error | **Undeclared, not absent** — `session_start.py` writes it; the engine cannot see Python | Declared `[[events.context_reset.producers]]` |
| L4: `awaiting_clear` has no satisfiable exit | 1 error | Cascade of the above | Same fix |
| L5: declared but never produced or consumed | 16 warnings | 6 genuinely dead · 7 had invisible writers · 2 template false positives · `_checkpoint` is engine-written | Deleted 6; declared producers for 7; kept `_checkpoint`; 2 left open (below) |
| L6: duplicate/drifted predicates | 11 warnings | 3 verbatim duplicates real · 8 near-miss noise (gates that legitimately differ by severity) | Migrated the 3 to `[queries.*]`; 8 remain as accepted noise |
| L3: boundary route-around | 0 | Passes once `context-reset` is declared — proves no path reaches `fix_loop` from `merge_done` without the gated `resume`, including via `awaiting_human` | Replaces a hand-written test with a property |
| L7: evidence weaker than the gate | 0 | Silent until `[attestation]` exists; now enforces `requires_attestation = "host"` on `resume` | **This is #79 caught at rest** |

Net: **2 errors → 0**, 28 warnings → 10.

#### Holtz checks (`scripts/enforcement_lint.py`)

| Finding | Verdict | Action |
|---|---|---|
| H1: `quiz_exhausted_resolved` gates `converge`, written by nothing | **REAL — #81.** Two places in `lens_quiz.py` tell the agent to record it and name no command; the event was unrestricted, so the agent could clear its own failed re-read quiz | Human-only channel: bootstrap denies the agent's path, `phase-convergence.md` documents the user's `!` command, `attestation = "human"` |
| `quiz_bank_generated` unrestricted, `question_count` pattern allows `0` | **REAL, new, high severity.** Either forged or honestly-empty, the run leaves recon bankless; the vault key is recon-only so the bank can never be built; every lens quiz then fails open without recording `quiz_posed`; `set complete perspective` requires it. **Unrecoverable deadlock — the exact #73 failure the gate was added to prevent** | `restricted = true` + `^[1-9]\d*$` on both counts |
| A leading `!` bypassed every second-level command block | **REAL, new, security.** `! sahjhan …` runs the command (bash negates only the exit status), but the parser saw `tokens[0] == "!"` and reported "not a sahjhan command". Defeated `daemon stop`'s mid-audit denial too | Fixed in `_sahjhan_bootstrap.py`; 4 unit + 3 contract regression tests |
| H1: `prediction`, `prediction_outcome` read by `summary.md.tera`, written by nothing | **REAL, open.** SUMMARY.md's prediction-accuracy section can never populate; the skill files discuss predictive recon at length and never record the events | Left open — wiring it means new skill commands and contract coverage |
| H6: `pattern_check`, `pattern_done`, `pause` taught by no skill file | **REAL.** `iteration_boundary`'s own gate message says "run `pattern_check`", which lands the agent in `pattern_analysis`, whose only exit — `pattern_done` — appeared nowhere | Documented all three |
| H4: `quiz_vault.py` writes a restricted event but is not hash-pinned | **False positive in the check.** The daemon authenticates the *process*; `quiz_vault.py` only ever runs inside the pinned `quiz_capture.py` | Fixed: H4 resolves through the import graph |

Census: **23 of 29 gate-consumed events are the agent's own word** (the
prototype's estimate was 19 of 24). Now visible via `--census` rather than
inferred.

#### The analyzers' own false positives, and what they cost

Recorded because the plan asked for a false-positive rate before anything
blocks, and because every one of these was a wrong *model* of the tree rather
than a bad regex — the same failure mode as the defects being hunted.

| Cause | Cost if unfixed | Fix |
|---|---|---|
| Scanned only fenced code blocks | 11 phantom "undocumented transitions" — holtz teaches commands in inline backtick spans mid-sentence | Scan fences *and* spans |
| Hook block-messages not treated as taught commands | `test_failed_before_fix` looked writerless; the message an agent reads while stuck *is* the escape it runs | Parse `message` fields in `hooks.toml` |
| Tera templates not scanned as consumers | 2 phantom dead events. **sahjhan's L5 has the same gap** and reports them too | Parse `where_eq(attribute="event_type", …)` |
| `("event", "x")` tuple ≡ subprocess argv fragment | Reported the hook that *forbids* an event as one of its writers | Require a sibling `"--field"` in the argv |
| Read `[queries]` from `transitions.toml`; it lives in `protocol.toml` | **Silently retired a live H1 error** the moment its predicate was migrated to a named query | Read the right file; unresolvable names are now an H2 error |
| Test fixture left `Tree.hooks_json` at its default | The real repo's registrations leaked into fixtures, so an unregistered hook looked registered | Override every path in the fixture |

Name-grepping for writers was confirmed unsound in both directions, as the
prototype predicted: `set_member_complete` has no write site bearing its name,
and a bare `event <name>` regex matches English prose.

#### Recorded as un-lintable

- **`protocol_violation` is agent-writable and stays that way.** Forging one
  only blocks the forger's own convergence, and the open CLI path lets a human
  record a violation they observed. Attestation is `agent` — the weakest path
  that exists, not the intended one.
- **Whether Claude Code's `!` prefix really bypasses `PreToolUse`.** The
  human-only channel rests on it, as does the pre-existing
  `! sahjhan daemon stop` guidance. It is a fact about the harness, not about
  our config; the linter can only check that the *agent's* path is shut, which
  it now does (H2 fails a `human:` producer whose event is not denied).
- **Eight L6 near-miss predicate pairs.** Gates that differ by a severity
  filter read as 86–96% identical to a text comparison. Migrating them to named
  queries would merge facts that are genuinely different.

## The problem: the layering is real but invisible

A holtz gate is only as good as a chain of facts that live in five different
places and are connected by nothing but convention:

| Layer | Where it lives | Declarative? |
|---|---|---|
| what the gate requires | `transitions.toml` | ✅ |
| what the event's fields must look like | `events.toml` | ✅ |
| **what the event means** | `description = "..."` prose | ❌ prose |
| **who may write it, from what signal** | scattered across Python hooks + skill markdown | ❌ implicit |
| whether that writer is registered and hash-pinned | `hooks/hooks.json`, `trusted-callers.toml` | ✅ but unlinked |

The gate can be read. The evidence behind it cannot. Every bug in the list
above lived in the unlinked middle rows:

- **#73** — a gate consumed `quiz_posed`/`quiz_answered`; the writer's channel
  (`writable_in_states`) closed before the consumer ever ran. Both halves were
  declared; nothing compared them.
- **#77** — a blocking condition and its printed escape decided "the same"
  fact via two different expressions, one a hand-maintained mirror. Nothing
  asserted they were the same fact.
- **#79** — `events.toml` said `context_reset` means "after /clear". The only
  writer fired on `UserPromptSubmit`. The claim and the writer were never
  compared because the writer was not declared anywhere a checker could see.

These are one defect class stated three ways: **the gate does not mean what it
says**. That class is decidable at rest, given the right declarations.

## Proof the approach pays: findings from a 30-line prototype

Before proposing machinery, I ran a crude version of it — parse the TOML, grep
the hooks and skill files, compare producers to consumers. Current `dev`:

| Finding | Count | Assessment |
|---|---|---|
| Events declared but never consumed *and* never written | 12 | dead vocabulary — rot, low severity |
| Events consumed by a gate with no discoverable writer | 2 | **1 false positive, 1 real latent defect** |
| Consumed events written by the **agent itself** | 19 of 24 | structural: ~79% of the evidence base is self-attested |

The two no-writer hits are worth showing, because they are exactly the two
kinds of thing this is for.

**`set_member_complete` — false positive, and it teaches the design.** It is
written by `sahjhan set complete <perspective>`, not by `sahjhan event ...`, so
a grep for the event name misses it. **Lesson: grepping for writers cannot
work.** Write paths include the `event` verb, the `set complete` verb, and
transition `emits` blocks. Provenance has to be *declared* and then *verified*,
not inferred.

**`quiz_exhausted_resolved` — a real latent defect, two ways.** The `converge`
gate requires `count(*) = 0 FROM ... quiz_exhausted ... NOT IN (... quiz_exhausted_resolved)`.
So an exhausted lens quiz blocks convergence until that event is recorded. But:

1. **No writer exists anywhere.** No hook records it; no skill file mentions it.
   `lens_quiz.py` prose tells the agent to "escalate this lens for human review
   (quiz_exhausted_resolved)" — naming an event with no documented command. An
   agent that hits this is blocked by a gate whose escape is undiscoverable.
   This is #73's shape, still latent, sitting in the tree today.
2. **It is not `restricted`.** Its description reads *"Human reviewed an
   exhausted quiz"* and its `resolution` field is patterned `^human_reviewed$`
   — yet an agent may write it with `sahjhan event`. The event asserts a human
   acted; nothing requires one. That is #79's shape.

One event, both defect classes, found in minutes without running anything.
That is the argument for building this properly. Filed as
[#81](https://github.com/jbrjake/holtz/issues/81).

### Prototype methodology (rebuild from this)

The prototype was a throwaway and is not in the tree. What it did:

1. Parse `enforcement/events.toml` → the set of declared events.
2. Parse `enforcement/transitions.toml` and `enforcement/hooks.toml` → the set
   of **consumed** events, from both `gate.event` keys and event-type literals
   inside `gate.sql` (`FROM events WHERE type='X'`, and the `NOT IN (SELECT …
   type='Y')` subqueries — the second is easy to miss and is exactly where the
   #81 defect hides).
3. Grep `enforcement/hooks/*.py` for each event name → hook-written set.
4. Grep `skills/**/*.md` for `event <name>` → agent-written set.
5. Report: consumed-minus-written (unsatisfiable candidates), declared-minus-
   everything (dead), and the size of consumed ∩ agent-written (self-attested
   share).

**Known defect in step 3/4, must be fixed on rebuild:** matching on the event
name alone conflates write paths and misses others entirely. The real write
paths are `sahjhan event <name>`, `sahjhan set complete <member>` (writes
`set_member_complete`), a transition's `emits` block, and
`record_authed_event("<name>", …)` in a hook. Step 4's `event <name>` regex also
matched prose, producing junk entries like `event and` / `event the`. Enumerate
the verbs explicitly rather than grepping names.

## The model

Three questions decide whether a gate means what it says:

1. **Producer/consumer closure** — does every consumed event have a writer, and
   can that writer run in a state that precedes the consumer?
2. **Attestation strength** — who vouches for the fact, and could the party the
   gate is trying to constrain have manufactured it?
3. **Fact identity** — when two gates decide "the same" fact, are they the same
   expression?

### Attestation classes

The vocabulary #79 was missing. Every event gets exactly one:

| Class | Written from | Can the agent cause it? | Example |
|---|---|---|---|
| `agent` | a command the agent runs | **yes, at will** | `reference_read`, `audit_claim` |
| `tool` | a Pre/PostToolUse hook observing a real tool call | yes, but only by *doing the thing* | `source_edit`, `bash_command` |
| `ambient` | a signal that occurs without anyone intending it | **incidentally — the #79 trap** | anything on `UserPromptSubmit` |
| `host` | a session-lifecycle act no tool call can produce | no | `context_reset` (post-fix) |

`agent` evidence is not illegitimate — self-attestation is fine for
bookkeeping. The defect is a **mismatch**: a gate whose purpose is to constrain
the agent, fed by evidence the agent controls. And `ambient` is the class that
existed but had no name, which is why #79 read as `host` to everyone including
the docs.

## Proposed declarative surface

### 1. Events declare their provenance

```toml
[events.context_reset]
description = "Context boundary"
restricted = true

  [events.context_reset.provenance]
  attests   = "host"                       # agent | tool | ambient | host
  writer    = "hooks/session_start.py"     # the ONLY writer
  host_event = "SessionStart"              # which harness event fires it
  entails   = "the prior context is gone"  # the fact, stated once
```

The `entails` line is the prose that `description` is doing badly today — but
now it sits next to the writer that must produce it, where a reader can see
both at once.

### 2. Transitions declare the strength they need

```toml
[[transitions]]
from = "awaiting_clear"
to   = "fix_loop"
command = "resume"
  [transitions.integrity]
  requires_attestation = "host"    # refuse evidence weaker than this
  boundary = "context-reset"
```

`requires_attestation = "host"` on the `resume` gate would have failed the
build the moment `context_reset` was `ambient`. That is #79 caught at rest.

### 3. Boundaries declare what must not be routed around

```toml
[[boundaries]]
name = "context-reset"
must_traverse = { from = "merge_done", to = "fix_loop" }
```

The checker walks the transition graph: **no path** from `merge_done` to
`fix_loop` may avoid an edge tagged with this boundary. This is the
`awaiting_human` risk — an ungated `resume` sharing a command name with the
gated one — generalized from a hand-written test into a property.

### 4. Domain predicates get names, so identity is structural

```toml
[queries.pattern_analysis_overdue]
sql = "SELECT count(*) < 3 FROM events WHERE type='state_transition' AND command='fix_commit' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)"
intent = "3+ fixes since the last pattern analysis"
```

Gates and hooks then reference `query = "pattern_analysis_overdue"` instead of
carrying their own copy of the SQL. #77 was two copies of one fact drifting
apart; a named query makes them the same object, so they cannot disagree. The
checker additionally flags any inline `sql =` that is textually near-identical
to a named query — the "you meant to reference this" case.

## Check catalogue

Each check names the bug it would have caught. A check that catches nothing
real is not worth its false positives.

| # | Check | Catches | Would have caught |
|---|---|---|---|
| C1 | Every gate-consumed event has ≥1 declared writer | unsatisfiable gate | `quiz_exhausted_resolved` (live) |
| C2 | Writer's availability window precedes consumer's state | temporally unsatisfiable gate | **#73** |
| C3 | Gate's `requires_attestation` ≤ writer's `attests` | forgeable evidence | **#79** |
| C4 | `restricted` ⟺ `attests ∈ {tool, host}` | an event claiming non-agent provenance that an agent may write | `quiz_exhausted_resolved` (live) |
| C5 | Named-query references only; no duplicated inline SQL | mirror drift / deadlock | **#77** |
| C6 | Block condition ≡ escape readiness for the same named fact | printed escape is unsatisfiable | **#77** |
| C7 | No path bypasses a declared `boundary` edge | route-around | `awaiting_human` (guarded by a hand-written test today) |
| C8 | Transition taking an `item_id` emits the state its name implies | transition/state decoupling | `fix_commit`/`finding_resolved` |
| C9 | Every non-terminal state has ≥1 outgoing transition whose gates are jointly satisfiable | dead end | — (structural) |
| C10 | Every declared event is written or consumed | dead vocabulary | 12 events (live) |
| C11 | Every transition command appears in some skill file, and vice versa | agent can't reach a transition / doc drift | `quiz_exhausted_resolved` (live) |
| C12 | Declared `writer` is registered in `hooks.json` for `host_event` and hash-pinned in `trusted-callers.toml` | silent enforcement death | the stale-manifest class |

C9's "jointly satisfiable" is deliberately weak — it means *no gate references
an event with no producer*, not full constraint solving. Sound, incomplete, and
cheap; that is the right trade for a gate that runs on every commit.

**Where each check landed.** The C-numbering above is the design vocabulary;
the shipped checks are sahjhan's `L1`–`L7` and holtz's `H1`–`H6`. The split
followed the purity rule almost exactly as predicted:

| Design | Shipped as | Where |
|---|---|---|
| C1 producer/consumer closure | L1 + H1 | both — the engine sees TOML producers, holtz sees hooks and skill files |
| C2 producer window precedes consumer | L2 | sahjhan |
| C3 attestation strength | L7 | sahjhan (holtz declares the lattice) |
| C4 `restricted` ⟺ non-agent provenance | H5 | holtz — generalised: `restricted` **or** denied in the bootstrap allowlist |
| C5 no duplicated inline SQL | L6 | sahjhan |
| C6 block condition ≡ escape readiness | — | not shipped; named queries make it structural where migrated |
| C7 boundary traversal | L3 | sahjhan |
| C8 transition emits the state it implies | — | not shipped |
| C9 dead-end states | L4 | sahjhan |
| C10 dead vocabulary | L5 | sahjhan (holtz adds Tera templates as consumers) |
| C11 transition ⟷ skill agreement | H6 | holtz |
| C12 writer registered and hash-pinned | H2 + H3 + H4 | holtz |

C6 and C8 remain unshipped. Neither is un-lintable in principle; both were
simply not reached, and #77's deadlock is now guarded by the derived counter
rather than by a check. The third copy of that predicate still lives in
`protocol_tracker.py` as a Python string that no linter compares to the gate —
a candidate for a future H7.

## The declarations must be falsified, not trusted

The obvious failure of this whole design is committing the original sin one
level up: a TOML block that *claims* `attests = "host"` is worth nothing if
nothing checks it. So C12 is load-bearing, and the holtz-side analyzer must
verify each declaration against the code:

- the declared `writer` is the **only** file in the tree that records the event
  — across all write paths (`record_authed_event`, `sahjhan event`, `set
  complete`, transition `emits`), not just a name grep;
- it is registered in `hooks.json` under the declared `host_event`;
- it is present in `trusted-callers.toml` with a current hash;
- no skill file teaches the agent a command that writes it, unless
  `attests = "agent"`.

The `attests` class of a `host_event` itself comes from a small pinned table
(`SessionStart` → `host`, `UserPromptSubmit` → `ambient`, `PostToolUse` →
`tool`, …) versioned alongside `tests/hook_schema.py` and checked for freshness
against the published hook spec, the same way the output schema already is.

## Where each piece lives

The purity rule decides this cleanly, and mostly the same way it decided #79.

**sahjhan (generic).** Graph reachability, producer/consumer closure,
satisfiability, boundary traversal, named-query resolution, dead-declaration
detection. These are statements about states, transitions, gates, and events —
the engine's own vocabulary, with no holtz nouns in them. Ships as
`sahjhan lint` (or an extension of `validate-deep`), with the new TOML blocks
as optional, backward-compatible config. An engine that can express a gate but
cannot tell you the gate is unsatisfiable is half a tool.

**holtz (domain).** Which boundaries are mandatory, which events need which
attestation strength, the actual queries — all of it declared in holtz TOML.
Plus the code-side falsification (C12 and the writer-uniqueness scan), because
`hooks.json`, the Python hooks, and the skill files are holtz artifacts the
engine must never learn about.

This split is the same seam that let #79 be fixed without touching the engine:
sahjhan supplies mechanism, holtz supplies policy.

## Everting the findings: comprehension, not just detection

Detection makes CI red. The request was to make the layering *visible*, which
needs artifacts a person can read:

1. **`docs/ENFORCEMENT-CONTRACT.md`, generated.** One row per gate: the
   transition, the fact required, the event, its writer, its attestation class,
   and whether the class satisfies the requirement. The #79 row would have read
   `resume | context must be reset | context_reset | primer.py | ambient` — and
   `ambient` in that row is the bug, legible without any tooling.
2. **A trust-boundary graph** (sahjhan already renders mermaid). States and
   transitions, edges coloured by the attestation class of their weakest gate.
   A run whose critical path is all one colour is a run defended by the agent's
   own word.
3. **`sahjhan lint --explain <transition>`** — for one gate, print the full
   chain: gate → event → writer → host event → registration → hash. The chain
   that today requires reading five files.

Artifact 1 is the highest-value item in this document. A generated table where
each row is one sentence about who vouches for what would have made #79 visible
to anyone who scrolled past it, with no analyzer running at all.

## Phasing

Nothing turns blocking before its false-positive rate is known.

**✅ Phase 0 — measure.** Done. `scripts/enforcement_lint.py` implements H1–H6;
findings triaged above. Deviation from the plan: the phase did not stay
measurement-only, because `sahjhan lint` shipped mid-phase and its L1 error was
a *missing declaration* rather than a missing writer — so declaring producers
was the cheapest way to learn whether the checks were sound, and the
declarations then found real defects immediately.

**✅ Phase 1 — declare provenance.** Done, in the shape the engine settled on
(`[[events.*.producers]]` + `attestation` on the event) rather than the
`[events.*.provenance]` block proposed here. Producer `id` is opaque to sahjhan
by design, so holtz gives it a grammar — `agent:cli`, `hook:<path>`,
`human:<path>`, `engine:emits:<command>`, `engine:auto_record:<tools>` — and
H2/H3/H4 falsify each form against the tree.

**✅ Phase 2 — engine support.** Done. sahjhan v0.20.0 ships `lint` with
L1–L7; holtz re-pinned from 0.19.0. Both linters run from
`scripts/lint-enforcement.sh` in pre-commit, `pre-release-check.sh`, and CI.

**✅ Phase 3 — attestation + identity.** Done. `[attestation]` levels declared
with a fifth class the plan did not anticipate — `human`, for a command only a
person can run (#81). `requires_attestation = "host"` on `resume`. Three
duplicated predicates migrated to `[queries.*]`.

**⬜ Phase 4 — everting.** Generate `ENFORCEMENT-CONTRACT.md` and the trust
graph; freshness-test them like the hook schema. *Exit: the contract doc is
generated, committed, and CI fails when it goes stale.* The census that feeds
it already exists (`enforcement_lint.py --census`).

**Ratchet.** After this, every field-found gate defect must either become a new
check or be recorded here as un-lintable **with the reason**. That is what
stops this from decaying back into prose — the same discipline the project
already applies to route-arounds.

## What this cannot catch

Stated plainly, so the green check is not over-read:

- **Whether a declared entailment is true of the world.** That
  `SessionStart(source=clear)` really implies a wiped context is a fact about
  Claude Code, not about our config. The linter checks that we *say* it
  consistently; only the spec and observation confirm it.
- **Whether `intent` prose matches the predicate.** A gate whose `intent` says
  "all lenses complete" while counting the wrong event is a semantic drift no
  parser detects. An advisory LLM-reviewed check could flag candidates; it
  should never block.
- **Whether the agent follows the protocol at all.** Out of scope by
  construction — that is what the runtime hooks are for.
- **Runtime-only failures** — daemon death, socket auth at execution time.
  (The *stale-manifest* half of that class is static, and is C12.)

## Verification plan

The analyzer is enforcement code, so it is held to the enforcement testing
rules: no check ships without a test proving it fires on a real historical
defect.

- [x] Each of H1–H6 has a test reconstructing the **tree** a real defect lived
      in — not just its config, since the checks assert that files exist, are
      registered, and are hash-pinned — and asserting the check fires
      (`tests/test_enforcement_lint.py`)
- [x] Each check has a negative test on current `dev` asserting it passes
      (`TestCurrentDev`), plus property tests pinning #79's and #73's fixes:
      `context_reset` is host-attested and unforgeable, `resume` demands host
      evidence and carries the boundary tag, `quiz_bank_generated` cannot be
      forged or empty
- [x] Phase 0 findings triaged and recorded in this document
- [x] `sahjhan lint` covered by the sahjhan suite (Rust unit + fixture configs)
- [x] Both linters in `git-hooks/pre-commit`, `scripts/pre-release-check.sh`,
      and CI, via `scripts/lint-enforcement.sh`
- [ ] Generated `ENFORCEMENT-CONTRACT.md` has a staleness test — Phase 4
- [x] No check blocks until its false-positive rate is measured and recorded —
      see "The analyzers' own false positives" above. Every H-check reached
      zero false positives on `dev` before the gate was wired; the two
      remaining H1 warnings are real and do not fail the build (warnings only
      fail under `--strict`, which is not how the gates invoke it)

## Immediate follow-ups, independent of this plan

The prototype found these; they should be fixed regardless of whether the
analyzer is built.

1. ✅ **`quiz_exhausted_resolved` has no writer** —
   [#81](https://github.com/jbrjake/holtz/issues/81). Fixed both halves. The
   missing writer is now a *human* one: the bootstrap hook denies the agent's
   `sahjhan event quiz_exhausted_resolved`, and `phase-convergence.md` tells
   the agent to stop and hand the user a `!`-prefixed command. `restricted =
   true` was the wrong tool — it admits trusted hooks, and no hook can attest a
   human decision.
2. ✅ **Dead declarations.** Six deleted (`baseline_delta`,
   `convergence_iteration`, `merge_result`, `pattern_discovered`,
   `run_postmortem`, `run_summary`), along with the `NEW_EVENT_TYPES` list that
   was keeping them alive — a test asserting the noun existed while nothing
   meant it. Seven had invisible-to-the-engine writers and now declare them.
   `_checkpoint` is written by sahjhan itself on `ledger checkpoint`.
3. ⬜ **23 of 29 gate-consumed events are agent-self-attested.** Not a bug, but
   it should be a *deliberate, visible* posture rather than an accident.
   `enforcement_lint.py --census` prints it today; Phase 4 commits it as a
   generated document.
4. ⬜ **`prediction` / `prediction_outcome` have no writer.** Consumed by
   `summary.md.tera`, so SUMMARY.md's prediction-accuracy section is
   permanently empty while the skill files discuss predictive recon throughout.
   Wiring it means teaching two new commands and covering them in the contract
   tests.

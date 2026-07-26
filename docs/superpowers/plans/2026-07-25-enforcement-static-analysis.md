# Making the enforcement layering statically analyzable

**Status:** proposal, not implemented — **resume at Phase 0**
**Tracking:** holtz [#82](https://github.com/jbrjake/holtz/issues/82) · engine portion [jbrjake/sahjhan#32](https://github.com/jbrjake/sahjhan/issues/32) · first defect found [#81](https://github.com/jbrjake/holtz/issues/81)
**Motivation:** #73 (gate unsatisfiable), #77 (gate deadlocked), #79 (gate satisfied without cause)
**Goal:** find the next one without running an audit

## Next session starts here

1. Read this document top to bottom, then **#82** (phasing checklist).
2. Do **Phase 0 only** — harden the throwaway prototype into
   `scripts/enforcement_lint.py` implementing C1, C10, C11 by inference, run it,
   and triage every hit into the "Phase 0 findings" section below.
3. **Do not add TOML surface or block any gate in Phase 0.** The point of the
   phase is to measure whether the later phases are worth their cost. If it
   finds two things, say so and stop.
4. The prototype is not in the tree — it was a one-off. Its logic is reproduced
   in "Prototype methodology" below; rebuild from that, correcting the
   false-positive cause it exposed (write paths are three verbs, not one).

### Phase 0 findings

_Empty — Phase 0 has not run. Record triaged results here, one row per hit:
finding, verdict (real / false positive / dead), and the action taken._

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

**Phase 0 — measure (no config changes).** Harden the prototype into
`scripts/enforcement_lint.py` implementing C1, C10, C11 by inference. Run it,
triage every hit, and write the results into this document. Cheap, and it
answers "how many more are lurking?" before any design is committed. *Exit: a
triaged findings list.*

**Phase 1 — declare provenance.** Add `[events.*.provenance]` for all 46
events, and C12 + writer-uniqueness in holtz. Filling in 46 blocks is itself an
audit: every event whose writer is hard to name is a finding. *Exit: C4 and C12
blocking in pre-commit.*

**Phase 2 — engine support.** `sahjhan lint` with C1, C2, C7, C9, C10 over the
generic model; named queries resolved by the engine. Ship as a sahjhan minor
release, re-pin holtz. *Exit: `sahjhan lint` clean, in `pre-release-check.sh`.*

**Phase 3 — attestation + identity.** `requires_attestation` on the gates that
constrain the agent; migrate duplicated SQL to named queries. C3, C5, C6.
*Exit: C3 blocking.*

**Phase 4 — everting.** Generate `ENFORCEMENT-CONTRACT.md` and the trust graph;
freshness-test them like the hook schema. *Exit: the contract doc is generated,
committed, and CI fails when it goes stale.*

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

- [ ] Each of C1–C12 has a test using the **actual pre-fix config** of the bug
      it claims to catch (reconstructable from git history for #73, #77, #79)
      and asserting the check fails on it
- [ ] Each check has a negative test on current `dev` asserting it passes
- [ ] Phase 0 findings triaged and recorded in this document
- [ ] `sahjhan lint` covered by the sahjhan suite (Rust unit + fixture configs)
- [ ] `scripts/enforcement_lint.py` in `git-hooks/pre-commit` and
      `scripts/pre-release-check.sh`
- [ ] Generated `ENFORCEMENT-CONTRACT.md` has a staleness test
- [ ] No check blocks until its false-positive rate is measured and recorded

## Immediate follow-ups, independent of this plan

The prototype found these; they should be fixed regardless of whether the
analyzer is built.

1. ✅ **`quiz_exhausted_resolved` has no writer** — filed as
   [#81](https://github.com/jbrjake/holtz/issues/81), covering both the missing
   writer and the fact that an event meaning "a human reviewed this" is
   agent-writable.
2. ⬜ **12 events declared but neither written nor consumed.** Triage in Phase 0:
   delete the dead ones, wire up any that were meant to be used. Verify each
   against the corrected write-path enumeration first — the prototype's grep
   was unsound in both directions.
3. ⬜ **19 of 24 gate-consumed events are agent-self-attested.** Not a bug, but
   it should be a *deliberate, visible* posture rather than an accident. The
   generated contract table is how it becomes visible.

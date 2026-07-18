# fix_commit / finding_resolved decoupling — root cause & fix

**Date:** 2026-07-16
**Status:** Fixed
**Discovered by:** a real Holtz run against `~/Documents/3rd-party-code/tqdm`

## Symptom

After `/clear`, the recovering agent found that a fix loop which had fixed 13
findings recorded **zero `finding_resolved` events**. Concretely:

- `sahjhan status` / STATUS.md showed **Resolved: 0**.
- The perspective-completion gate reported **all 51 detected issues still open**.
- Yet there were **13 `fix_commit` transitions**, all commits landed, and the
  full per-fix TDD event set (`fix_start`, `test_failed_before_fix`,
  `blast_radius`, `hardening_complete`) was present.

The user's mental model — reasonably — was that this "should not be possible":
you cannot commit 13 fixes through the gated loop and end with nothing resolved.

## Root cause

**`fix_commit` (a state transition) and `finding_resolved` (an event) were
completely decoupled, and the enforced Per-Item Fix Procedure never recorded the
event.**

- Recording `sahjhan transition fix_commit BH-NNN` writes a `state_transition`
  event (`command=fix_commit`), **not** a `finding_resolved` event. The
  `item_id` positional arg is only used by the transition's own gates
  (`git log … | grep item_id`); it does not mark the finding resolved.
- A finding is marked resolved **only** by a `finding_resolved` event with
  `id=BH-NNN`. STATUS.md / PUNCHLIST.md "Resolved" counts
  (`status.md.tera`, `punchlist.md.tera`) and every downstream gate read that
  event:
  - `pattern_check`: needs `≥3 finding_resolved`
  - `set complete perspective`: `findings NOT IN finding_resolved AND NOT IN finding_deferred == 0`
  - `converge`: same open-findings query
- The authoritative Per-Item Fix Procedure (`references/phase-fix-loop.md`,
  Step B) went **commit → `transition fix_commit`** with **no
  `finding_resolved` step**. `git log -S finding_resolved` over that file is
  empty for its entire history — the event was **never** part of the enforced
  sequence.
- `finding_resolved` appeared only as an isolated example in the SKILL.md
  quick-reference dump (a command catalog the agent reads once), decoupled from
  the step-by-step loop. Nothing (no hook, no transition side-effect) auto-emits
  it — `protocol_tracker.py`'s `fix_commit` handling is cache bookkeeping only.

**Consequence:** an agent that followed the enforced procedure *exactly*
produced N `fix_commit` transitions and zero `finding_resolved` events — so the
entire fix→converge pipeline was **uncompletable as documented**. The tqdm run
was the procedure working as written and yielding a broken ledger.

## Reproduction (real engine, sahjhan 0.17.0)

In `fix_loop` with finding `BH-001` recorded, satisfy the pre-existing gates
(`HOLTZ_PYTEST=true`, a commit mentioning `BH-001`, `blast_radius` +
`hardening_complete` events), then:

```
$ sahjhan transition fix_commit BH-001
fix_loop → fix_loop                       # SUCCEEDS

$ sahjhan query "SELECT count(*) FROM events WHERE type='state_transition' AND command='fix_commit'"
1
$ sahjhan query "SELECT count(*) FROM events WHERE type='finding_resolved'"
0
$ sahjhan query "SELECT count(*) FROM events f WHERE f.type='finding'
    AND f.id NOT IN (SELECT id FROM events WHERE type='finding_resolved')
    AND f.id NOT IN (SELECT id FROM events WHERE type='finding_deferred')"
1                                         # finding still OPEN
```

## Fix

Couple the transition to the resolution *mechanically, without extra agent
tokens* — `fix_commit` emits `finding_resolved` itself. (A first attempt gated
`fix_commit` on a manually-recorded `finding_resolved`; that was rejected: it
forced the agent to state the same fact twice — a `transition fix_commit BH-N`
**and** an `event finding_resolved id=BH-N …` — every fix, every run, violating
the token-minimization principle. It would also have deadlocked once the
transition emits the event. The gate approach was reverted.)

Three parts:

1. **sahjhan ≥ 0.18.0: generic transition `emits`** (`feat(transitions)`). A
   transition may declare `emits` — events appended automatically when its gates
   all pass. Field templates resolve `{{var}}` from, in increasing precedence:
   the most recent value of each field across the ledger (run-context
   inheritance), the transition's `state_params` (positional args like
   `item_id`), and the trimmed stdout of `commands` entries (env-derived values
   like `git rev-parse HEAD`). Resolution runs before anything is appended, so a
   failed command or unresolved `{{var}}` blocks the whole transition
   atomically. Config validation rejects emitting an unknown or `restricted`
   event (an emit must not bypass the HMAC proof `authed-event` requires). Kept
   fully generic — no holtz business logic in the engine.

2. **holtz `fix_commit` emits `finding_resolved`** (`enforcement/transitions.toml`):
   ```toml
   emits = [
     { event = "finding_resolved",
       commands = { commit_hash = "git rev-parse --short=7 HEAD" },
       fields = { id = "{{item_id}}", commit_hash = "{{commit_hash}}",
                  project = "{{project}}", run = "{{run}}", auditor = "{{auditor}}",
                  phase = "fix_loop", step = "10" } },
   ]
   ```
   One command — `transition fix_commit BH-NNN` — now records both the
   transition and the resolution. `id` comes from the positional arg,
   `commit_hash` from HEAD, and `project`/`run`/`auditor` are inherited from the
   run's prior events. Pin bumped to 0.18.0 in
   `enforcement/hooks/_resolve.py` (version + checksums) and vendored.

3. **Docs** (`references/phase-fix-loop.md` Step B, `references/step-10-fix-loop.md`,
   `SKILL.md`): the agent commits then runs `transition fix_commit BH-NNN`; the
   resolution is auto-recorded. No hand-written `finding_resolved` in the loop.

## Tests

- `sahjhan tests/state_machine_tests.rs` + `src/state/emit.rs` — the emits
  feature: a transition appends its emit with fields resolved from arg/command/
  ledger/literal, after the state_transition; a failed command or unresolved
  var blocks atomically (nothing appended); validation rejects unknown and
  restricted emit targets.
- `tests/test_e2e_audit_flow.py::TestFixCommitAutoEmitsFindingResolved` — real
  daemon + real holtz config: `transition fix_commit BH-001` auto-emits exactly
  one `finding_resolved` with `id=BH-001` and a HEAD-derived `commit_hash`, and
  the open-findings query drops to 0.
- `tests/test_enforcement_config.py::test_fix_commit_auto_emits_finding_resolved`
  — config guard: the emit exists, carries `id={{item_id}}` and a `commit_hash`
  command, and no finding_resolved *gate* remains (which would deadlock).
- `tests/test_subagent_contract_consistency.py` doc guards: the procedure ties
  `fix_commit` to the auto-recorded resolution.

## Not in scope (noted to avoid future confusion)

While reproducing with a **hand-built** ledger, `status.md.tera` failed to
render because a manually-recorded `state_transition` event lacked a `command`
field (the template prints `{{ e.fields.command }}`). Real runs create
`state_transition`s via actual `transition` commands, which always carry
`command` — which is why the tqdm STATUS.md rendered fine and showed
"Resolved: 0". This is a synthetic-ledger artifact, not a product bug.

# Release worklist — handoff #3

**Supersedes handoff #2**, whose whole first half was contingent on sahjhan #34
and #35 being resolved. They are. That work is done and committed; #2 is now
useful only as a record of why it was needed.

**Read in this order:**

1. **This file** — where things stand, and what the next unit is.
2. **`2026-08-27-release-worklist.md`** — the working document. Every defect,
   plan step and validation check, with `Evidence:` slots filled in through W05.
   Do the work from this, not from a handoff.
3. **`2026-08-27-release-worklist-ORIGINAL.md`** — Jon's text byte-for-byte, so
   everything an implementer added is diffable.
4. **`…-handoff-1.md` §2, §2a, §3** — still the best account of the fixtures, the
   stale-cache trap, and the things that cost time. Nothing in it has been
   falsified except the two engine facts it already corrects itself.

---

## Where things stand

| Unit | Items | Status | Commit |
|---|---|---|---|
| W01 | fixtures F1/F2/F3 | `DONE` | `17e648e` |
| W02 | 29 | `DONE` | `6070c66` (v0.169.2) |
| W03 | 31 | `DONE` | `eae803d` (v0.169.3) |
| W04 | 19 | `DONE` | `2b94345` (v0.169.4) |
| W04 | 1 | `DONE` — **route-around undone** | `dad0f47` (v0.169.5) |
| W05 | 2 | `DONE` | `ca29f69` (v0.169.6) |
| W06 | 20 | **`TODO` — next in order** | — |
| W07 | 3 | `TODO` — depends on W06 | — |
| W22 | 27 | `TODO` — rest of P1 | — |
| W08 | 32, 43 | `TODO` — **last release-gate unit** | — |

**Release gate: W02, W03, W04, W08. Only W08 is left.** The worklist's own order
puts W06, W07 and W22 first; they block a *functional run* rather than the
truthfulness of a shipped-status row. If the goal is a cuttable release rather
than a good functional test, **go straight to W08.**

**Nothing is pushed.** Everything is local on `dev` (**87 ahead of
`origin/dev`**). **CI has never run on any of it.** Do not claim it has.

---

## What this session did

### The route-around is undone (W04 item 1)

sahjhan **0.24.0** shipped both filed issues. The pin, checksums and vendored
binaries moved with it.

| Issue | What shipped |
|---|---|
| [#34](https://github.com/jbrjake/sahjhan/issues/34) | `since` is a closed vocabulary — `last_transition` or `last_event_of_type:<declared type>`. Anything else is refused where the config is **sealed**. The bare event-type form is gone; that is why 0.24.0 is a minor bump, not a patch. |
| [#35](https://github.com/jbrjake/sahjhan/issues/35) | `since_filter` scopes the anchor lookup the way `filter` scopes the count. `{{event.<field>}}` binds to the *candidate*, so the window recomputes per candidate — the self-consuming correlation that previously required SQL. |

The TDD gate is now declarative, with the ruled semantics unchanged:

```toml
[hooks.gate]
type = "ledger_has_event_since"
event = "tdd_evidence"
since = "last_event_of_type:finding_resolved"
since_filter = { id = "{{event.finding_id}}" }
filter = { agent_id = "{{agent_id}}" }
```

No config migration was needed for #34 — every anchor in the tree was already
one of the two legal forms.

### W05: one line deleted, three seats kept

`converge`'s `medium_deferral_budget` conjunct is gone. `defer_medium` (both
states) and `pattern_done`'s breaker branch are untouched.

---

## Three things to carry forward

### 1. `_gate_consumed` was blind to `since` — and the class is not closed

`scripts/enforcement_lint.py::_gate_consumed` walked `event`, `evidence`, `sql`
and named queries but **not** `since`. So an anchor-only event dependency was
invisible to the whole H/L series *and* to the generated contract.

It had been inert for as long as it existed: the tree's only other
`last_event_of_type:` anchor names `set_member_complete`, which is also that
gate's `event`. The new TDD gate is the first whose anchor names an event
nothing else in the gate names — and the first regenerated contract duly
reported it **`Forgeable: no`**.

**That was not a conclusion. It was a blind spot wearing the shape of one.** The
generator had not decided the gate stopped reading an agent-writable event; it
never looked. Fixed in `dad0f47`, guarded by `TestSinceAnchorIsADependency`.

**The general lesson, which is the reusable part:** handoff #2 §2.2 gave two
tests for whether to keep the ⚠️ forgeable note — "does the gate still read
`finding_resolved`" and "did the contract row go non-forgeable". They
disagreed. *That disagreement was the bug surfacing*, not an ambiguity in the
plan. When two independent readings of the same fact diverge, suspect the
derivation before picking a side.

**So: `since_filter` keys are still unwalked.** They are field names rather than
event types, so nothing is currently lost — but if a future gate correlates on a
field whose provenance matters, check whether the static analysis can see it
before trusting a generated claim about it.

### 2. Do not write a test that reads `git show HEAD`

W05's step 3 says "confirm by diff that this commit touches exactly one line of
gate config." That was drafted as a test and then deleted: a test reading
`git show HEAD` **cannot pass during the commit that introduces it**, and one
reading the working tree stops meaning anything the moment the change lands.

The standing form of such a claim is an assertion about the *config's* current
shape — `test_v5_v6_exactly_three_seats_remain_and_which` pins the surviving
seats by name. **By name, not by count:** a count survives a change that deletes
one seat and adds another in the wrong place.

### 3. Run the new test against the *unmodified* config first

W05's V5 draft asserted the cap refuses the **third** deferral at N=6. It
refuses the **fourth**: `deferred < N/2` is evaluated *before* the deferral
records, so it admits 0, 1, 2 and rejects at 3. The draft failed against correct
code.

Had the "after" tests been written without first running them against the
unmodified config, that test would have encoded the wrong arithmetic — and the
obvious next move would have been to "fix" the cap to match it.

The discipline that catches this is the one both W04 and W05 used: **every test
must be observed RED for the right reason before the change, and the ones that
must *not* flip must be observed green before, during the mutation, and after.**

---

## Standing facts

- **Gates observed at the W05 commit** (all `.venv`, not a clean environment):
  full suite `pytest -p no:randomly -q` exit 0, zero `FAILED`/`ERROR`, 8
  `machine_specific` skips; `ruff` exit 0; `mypy` exit 0 (69 files);
  `scripts/enforcement_lint.py` 0 errors / **2 pre-existing warnings**;
  `enforcement_contract.py --check` current; `contract_gate.py` PASS (100
  commands, 30 field-checked); `check_sahjhan_pin.py` exit 0 at **v0.24.0**;
  `sahjhan --config-dir enforcement validate` exit 0; `sahjhan lint` **0 errors,
  7 warnings** (a different tool from `enforcement_lint.py` — do not confuse the
  two warning counts).
  This is **not** a substitute for CI: item 15 (W27) is precisely that a fresh
  checkout cannot collect `tests/test_property_based.py` because `hypothesis` is
  undeclared.
- **The README test badge is a gated derived number.** Any commit adding tests
  must move it or pre-commit refuses. 2659 → 2680 → 2696 → 2699 → 2712 → 2716 →
  **2729**.
- **`git` prints two `[dev …]` hashes and one is orphaned.** Position is not a
  rule — it was second for W02, first for W03, and **first again** for
  `dad0f47`. Only `git merge-base --is-ancestor <hash> HEAD` distinguishes them.
- **`update_sahjhan_pin.py` hashes whatever bytes sit in `bin_dir`** without
  checking they belong to the version being pinned — item 46 (W27), still open.
  So `check_sahjhan_pin.py` passing is not sufficient; run `bin/sahjhan
  --version` yourself. Done for 0.24.0 and it agrees.
- **Regenerate `enforcement/trusted-callers.toml` before every `real_daemon`
  run**, including before each non-vacuity mutation. A stale hash makes the RED
  an artifact rather than the thing under test.
- **The fast subset flakes under concurrent load.** Confirm a failure 3×
  unchanged before treating it as real; that is item 17/37's mechanism, which
  W13 fixes.
- **The plan docs are untracked by design.** Stage explicitly — `git add <paths>`
  — never `git add -A`. The tree also carries a ~100MB vendored binary.

---

## Suggested next step

**W08 — items 32 + 43**, if the goal is a cuttable release: it is the last unit
in the release gate. Otherwise **W06** (item 20), which is next in the
worklist's order and which W07 depends on.

Notes for W08, carried forward from handoff #1 and still accurate:

1. **F2 is built for it.** `TwoActors` already drives several actors on one
   ledger, and `sibling_fix_commit()` records both halves of a commit.
2. **Step 2 asks the ledger which commit a transition registered.** Drive that
   question against the binary rather than inferring it. **And note what 0.24.0
   changed**: `since_filter` may make an answer expressible that was not before,
   so re-check the engine's surface rather than reusing W04's finding.
3. **If the answer implies an engine change, report it as an engine change.**
   That is the mistake handoff #2 existed to correct, and it is worth stating
   once more now that the correction has actually landed: filing #34 and #35
   took one session and got both fixed. Routing around them cost more.
4. **V6 wants the printed escape *executed*, not just present**, and step 5 is
   explicit that if no reachable route exists, that is a question for Jon rather
   than a licence to narrow the block.

For **W06**, the thing to be careful about is the division of labour with W09
that the worklist spells out: W06 builds the required-field mechanism *and* its
`perspective` use; W09 step 3 consumes the same mechanism for `reachability`. If
W09 finds itself writing a second checking mechanism, W06 under-built — widen it
rather than adding one.

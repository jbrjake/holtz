# Release worklist — handoff #2

**Supersedes handoff #1** for sequencing. #1 is still accurate on what W01–W04
did and on the operational hazards; read it second, for §2 (fixtures), §2a (the
stale-cache trap) and §3 (things that cost time).

**The working document is `2026-08-27-release-worklist.md`**, with
`…-worklist-ORIGINAL.md` preserving Jon's text byte-for-byte so every added
`Evidence:` line is diffable.

---

## Read this first: what this session is for

**W04 shipped a route-around, and undoing it is this session's first job.**

The worklist's step 4b says, verbatim:

> **If it cannot, the fix is in sahjhan and that is the correct place for it.**
> Do not add a holtz-side mirror of the transition log — two expressions of one
> window is the shape that deadlocked before. Ship the engine change and bump
> the pin.

The last session drove step 3, found that `ledger_has_event_since` **cannot**
express an actor-scoped window — which is exactly 4b's trigger — and then went
looking for a way not to touch sahjhan. It found one (`type = "query"` with raw
SQL), labelled it "Recommended," and presented the engine change as the
expensive branch. Jon ruled on the question as framed, and the framing was the
error: the plan had already decided where the fix belongs.

So the SQL gate in `enforcement/hooks.toml` is **a workaround for a filed engine
gap, not the intended fix.** Do not treat it as settled work.

Filed upstream, both driven against the released 0.23.0 binary, not inferred:

| Issue | What |
|---|---|
| [jbrjake/sahjhan#34](https://github.com/jbrjake/sahjhan/issues/34) | an unrecognized `since` value silently widens the window to **the whole run** (fail-open) |
| [jbrjake/sahjhan#35](https://github.com/jbrjake/sahjhan/issues/35) | the window anchor cannot be scoped to the actor, so a per-actor gate is a per-run gate wearing a filter |

**This handoff assumes both are resolved and released before the session
starts.** If they are not, stop and say so rather than proceeding — the whole
first half of this document is contingent on a new sahjhan version existing.

---

## Where things stand

| Unit | Items | Status | Commit |
|---|---|---|---|
| W01 | fixtures F1/F2/F3 | `DONE` | `17e648e` |
| W02 | 29 | `DONE` | `6070c66` (v0.169.2) |
| W03 | 31 | `DONE` | `eae803d` (v0.169.3) |
| W04 | 19 | `DONE` | `2b94345` (v0.169.4) |
| W04 | 1 | **`DONE` on a workaround — redo below** | `2b94345` |
| W05 | 2 | `TODO` | — |
| W08 | 32, 43 | `TODO` — last release-gate unit | — |

Nothing is pushed. All four commits are local on `dev` (84 ahead of
`origin/dev` at handoff time). **Do not push unless Jon says push.**

---

# Phase 1 — integrate the new sahjhan

## 1.1 Confirm what actually shipped

Before touching the pin, read the resolved issues and find out **which
mechanism** #35 landed. The three shapes that were sketched are different
enough that the holtz-side gate differs for each:

- an anchor-side filter (correlating on a field),
- `since_filter = { … }` / `last_transition_by_actor` (a per-actor baseline),
- a declared named predicate that `lint` can see.

**Do not assume the sketch in #35 is what was built.** Read the release notes
and the changed config surface, then drive it — the last session's whole step-3
finding came from driving the binary rather than reading about it.

## 1.2 Vendor and pin

**One command does it, and it is the only correct path:**

```bash
scripts/vendor-sahjhan.sh <new-version>
```

It downloads all four targets, relinks `bin/sahjhan`, and then calls
`scripts/update_sahjhan_pin.py`, which rewrites `_resolve.SAHJHAN_VERSION` and
`SAHJHAN_CHECKSUMS`.

**Why not to do it by hand:** `_resolve.SAHJHAN_VERSION` is the pin that
governs. `ensure_sahjhan()` reads it and re-downloads whatever it names, so
vendoring without updating it leaves the resolver pointing at the old version —
and the next hook invocation quietly restores the old binary *and rewrites
`bin/.sahjhan-version` back*, leaving every pin agreeing on the version nobody
asked for. That is a silent revert with no failing check.

Then verify, and paste the output:

```bash
.venv/bin/python scripts/check_sahjhan_pin.py     # expect exit 0
bin/sahjhan --version                             # expect the new version
```

⚠️ **`update_sahjhan_pin.py` hashes whatever bytes sit in `bin_dir` without
checking they belong to the version being pinned** — that is item 46 (W27),
still open. A partially-failed vendor run therefore pins checksums for a
mismatched binary and `check_sahjhan_pin.py` passes. So run `bin/sahjhan
--version` yourself and compare it to the version you asked for. If W27 has
already landed by the time you read this, the tool refuses on its own and you
can skip the manual check.

## 1.3 Re-run the step-3 probe against the new binary

`/private/tmp/.../scratchpad/probe_since.py` from the last session is gone with
its scratchpad; rebuild it, it is ~120 lines. The shape that matters:

```
seq 1  probe_event
seq 2  marker_event
seq 3  probe_event
seq 4  state_transition
```

…so `last_transition` and `last_event_of_type:marker_event` give **different**
answers, and any anchor resolving to seq 0 is visible as `allow`. Add a control
ledger with **no** matching event at all, which must `block` on every anchor —
without it, `allow` cannot be distinguished from "the gate never ran."

Confirm #34 is actually fixed: a garbage anchor (`"42"`, `""`, `LAST_TRANSITION`,
`last transition`) must now **error at config load**, not evaluate. Record the
before/after.

---

# Phase 2 — fix what was routed around

## 2.1 The thing to replace

`enforcement/hooks.toml`, the TDD gate. Currently:

```toml
[hooks.gate]
type = "query"
sql = "SELECT count(*) > 0 FROM events e WHERE e.type='tdd_evidence' AND e.agent_id='{{agent_id}}' AND NOT EXISTS (SELECT 1 FROM events r WHERE r.type='finding_resolved' AND r.id = e.finding_id AND r.seq > e.seq)"
expect = "true"
```

Replace with the declarative form the new engine supports. The **semantics must
not change** — they were ruled on and are correct:

> the actor holds authorisation while it has a `tdd_evidence` row whose
> `finding_id` has no later `finding_resolved`

Explicitly **not** "any evidence this run" — that satisfies the letter of
"scope it to the actor" while turning a per-fix gate into a
per-actor-per-run one. Jon declined that on 2026-08-27.

If the new engine primitive **cannot** express the consumption term, that is a
question for Jon, not a reason to keep the SQL and call it done. Say so and
stop.

## 2.2 Also remove, in the same commit

- **The long `hooks.toml` comment block justifying the SQL.** It argues for a
  workaround; once the declarative gate is in, most of it is a changelog. Keep
  only what is still true of the shipped gate. (`no-rationale-in-skill-files`
  is about skill files, not config — but the comment should describe the
  predicate, not narrate how it got there.)
- **The "forgeable" note**, if the declarative gate no longer reads
  `finding_resolved` directly. Re-run `scripts/enforcement_contract.py --write`
  and read the diff: if the row goes back to non-forgeable, delete the note; if
  it does not, keep it, because it is then still true.

## 2.3 The stale comment #34 exposed

`enforcement/transitions.toml`, the `#65` comment above `pattern_check`, says
`last_event_of_type:` "is a syntax that gate type does not understand: it
matched no event, silently fell back to 'since last state_transition'."

**That is stale.** sahjhan #31 fixed the parsing in July 2026, and driving it
confirms `last_event_of_type:marker_event` resolves correctly at 0.23.0. It is
also wrong about the fallback *direction*: an unresolvable anchor falls back to
**seq 0 (run start)**, not to the last transition.

Fix the comment. And check whether `transitions.toml`'s `set complete
perspective` (`since = "last_event_of_type:set_member_complete"`) can now be
trusted — it can, per the same probe, and sahjhan #31's own text says holtz
should switch to it once the fix landed. It already has, unknowingly.

## 2.4 What must not regress

`tests/test_tdd_courier_pairing.py` is the guard, and it already encodes the
right claims. All twelve must stay green, and in particular:

| Test | Why it is the one that matters |
|---|---|
| `test_the_gate_still_bites` | asserts **deny**. Without it, every neighbouring `allow` could mean "the gate never ran" — see handoff #1 §2a |
| `test_an_actor_survives_a_siblings_fix_commit` | item 1 itself |
| `test_an_actors_own_commit_consumes_its_authorisation` | the window must **close**, or the gate stops being per-fix |
| `test_the_orchestrator_is_an_actor_not_a_wildcard` | `""` is a real actor |
| `test_a_test_file_edit_is_still_exempt` | step 2 writes the failing test *before* recording it |

**Non-vacuity, both directions, as W04 did:** mutate the new gate back to a
run-global window and confirm `test_an_actor_survives_a_siblings_fix_commit`
goes red **while `test_the_gate_still_bites` stays green**. A mutation that
turns everything red proves less than one that turns exactly the right thing
red.

Regenerate `enforcement/trusted-callers.toml` before every `real_daemon` run,
including before each mutation — a stale hash makes the RED an artifact rather
than the thing under test.

## 2.5 Commit shape

`fix(enforcement): express the TDD window declaratively, on the engine's own anchor`

Say plainly in the message that this replaces a workaround, name #35, and name
the version it required. The commit is the record that the route-around was
undone.

---

# Phase 3 — resume the worklist

Order is unchanged from the worklist itself: **W05 → W06 → W07 → W22** (rest of
P1), then P2 starting at W08.

**W08 is the last release-gate unit.** If the goal is a cuttable release rather
than a good functional test, it is the one that matters — the other P1 units
block a functional run, not the truthfulness of a shipped-status row.

Two notes carried forward:

- **W05** is a one-line deletion whose entire risk is deleting one seat too
  many. `defer_medium`'s cap (`transitions.toml:268`) and the breaker seats
  (`:415`, `:458`) must not move; V5/V6 exist to prove they did not. Step 3
  says to confirm by diff that the commit touches exactly one line of gate
  config.
- **W08** should ask its step-2 question ("can the ledger say which commit a
  transition registered?") **by driving the binary**, not by inferring — and if
  the answer implies an engine change, *report it as an engine change* rather
  than finding a holtz-side expression of it. That is the mistake this handoff
  exists to correct.

---

## Standing facts

- **Gates, all observed green at `2b94345`:** full suite
  `pytest -p no:randomly -q` → **`FULL_EXIT=0`**, zero `FAILED`/`ERROR` lines,
  8 `machine_specific` skips; `-m hook_e2e` exit 0 (639 passed); `-m contract`
  exit 0 (324 passed); `ruff check .`; `mypy --explicit-package-bases …` (69
  files); `scripts/contract_gate.py` (100 commands, 30 field-checked, 0
  failing); `scripts/enforcement_lint.py` exit 0 (2 pre-existing warnings);
  `scripts/enforcement_contract.py --check` current; `check_sahjhan_pin.py`
  exit 0 at v0.23.0.
  **This is a `.venv` run, not a clean-environment one** — item 15 (W27) is
  precisely that a fresh checkout cannot collect `tests/test_property_based.py`
  because `hypothesis` is undeclared. So it is not a substitute for CI.
- **The README test badge is a gated derived number.** Any commit adding tests
  must move it or pre-commit refuses. 2659 → 2680 → 2696 → 2699 → 2712 so far.
- **`git` prints two `[dev …]` hashes and one is orphaned.** Position is not a
  rule — it was second for W02 and first for W03. Only
  `git merge-base --is-ancestor <hash> HEAD` distinguishes them.
- **Fast-subset flakes under concurrent load** (18 failures once, 0 the next
  run). Confirm 3× unchanged before treating a failure as real; that is item
  17/37's mechanism, which W13 fixes.
- **CI has never run on any of this.** Do not claim it has.

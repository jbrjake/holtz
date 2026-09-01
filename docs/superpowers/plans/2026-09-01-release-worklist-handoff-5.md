# Release worklist — handoff #5

**Supersedes handoff #4.** Its account of W01–W08 is still accurate. What
changed: **sahjhan v0.25.0 shipped both filed issues**, the pin moved, W32 is
effectively closed, and **item 43 is still blocked — the blocker moved from the
gate to the emit** and is filed as sahjhan#48.

**Read in this order:**

1. **This file** — what moved, and the three questions waiting on Jon.
2. **`2026-08-27-release-worklist.md`** — the working document. Do the work from
   this. W32's validation section and W08's *"Re-probed on sahjhan 0.25.0"* are
   new.
3. **`2026-08-27-release-worklist-ORIGINAL.md`** — Jon's text byte-for-byte.
4. **`…-handoff-1.md` §2, §2a, §3** — still the best account of the fixtures and
   the stale-cache trap.

---

## Where things stand

| Unit | Items | Status | Commit |
|---|---|---|---|
| W01–W05 | fixtures, 29, 31, 19, 1, 2 | `DONE` | see handoff #4 |
| W08 | **32** | `DONE` | `780ba47` (v0.169.7) |
| W08 | **43** | **`BLOCKED` on [sahjhan#48](https://github.com/jbrjake/sahjhan/issues/48)** | — |
| W32 | **51** | **`WIP`** — pin moved, V1–V4 driven; step 3 is a question | *this session* |
| W06 | 20 | `TODO` — **next**, but see Q3 | — |
| W07 | 3 | `TODO` — depends on W06 | — |
| W22 | 27 | `TODO` — rest of P1 | — |
| W31 | 50 | `TODO` | — |

**Nothing is pushed.** Everything is local on `dev`. **CI has never run on any
of it.** Do not claim it has.

---

## What this session did

### The pin moved to sahjhan v0.25.0

`_resolve.py`'s `SAHJHAN_VERSION` and all four `SAHJHAN_CHECKSUMS` moved
together via `scripts/vendor-sahjhan.sh 0.25.0` (which calls
`update_sahjhan_pin.py` — the step that stops the resolver silently reverting
the binary). All four hashes were checked against the release's published
`SHA256SUMS`, not just recomputed locally.

**The migration this release exists for is OWED and NOT DONE.** Read that before
anything else in this file. sahjhan#46 was filed *by this repo* so that
`fix_commit`'s commit-message gate could carry `anchor = "caller"` — without it
a fix subagent can never register its own commit. Moving that gate is the
migration, it is the point of the upgrade, and it is not in the tree. Why is
under *W08 item 43* below; the short version is that the ask was filed
incomplete and the other half is sahjhan#48.

Separately — and this is a *checklist*, not a verdict on the release's value —
0.25.0's three breaking-change items need no action here:

- **no `anchor` key anywhere** in `enforcement/*.toml`, so 0.25.0's new
  validation — which stops a config loading for *every* command — has nothing
  to refuse;
- **no `--ledger-path` threading** to delete (the `--path` hits are
  `ledger create`, a different flag);
- **nothing reads `gate_attestation`'s fields**, so the additive `working_dir`
  column changes no render and no query.

An earlier revision of this file summarised those three as *"the upgrade is
inert for this config"*. That was wrong and is corrected here rather than
deleted: a clean breaking-change checklist says nothing about whether the
release delivered what was asked for, and this one delivered exactly that.

### W32 (item 51) — fixed upstream, and now pinned by a test

sahjhan#47 shipped. `tests/test_worktree_ledger_anchor.py` (4 tests,
`integration`+`slow`) drives the shipped binary against **holtz's own
`enforcement/` config**: a sibling worktree reads *and writes* the main
checkout's ledger, a nested worktree still resolves by the plain walk-up, and a
non-repo directory still anchors on itself.

**The write half is the one that matters.** A sibling that grew its own ledger
would answer a count query just as happily and still be the bug — only reading
the event back *from the main checkout* by its marker value tells those apart.

**Non-vacuity, per test rather than per file:** the 0.24.0 binary was swapped in
at the path `ensure_sahjhan()` resolves and the same four tests re-run — V1's
two FAILED with the exact `I/O error (os error 2)` from the issue, V2 and V3
stayed green. Restored, and the restored binary's sha256 re-checked against
`SAHJHAN_CHECKSUMS`.

### W08 item 43 — the escape now passes and still does not discharge

**sahjhan#46 works.** `anchor = "caller"` is accepted, and a gate reading `git
log -1` passes from a worktree whose `HEAD` carries the item id while the
project root's does not. `gate_attestation.working_dir` names the worktree.

**Nothing was landed for 43, and the reason is measured, not argued.** A
transition runs two kinds of command and only one of them can be anchored. The
`emits` derivation still runs at the project anchor
(`machine.rs:289` → `self.working_dir`; `EmitConfig` has no `anchor`), so:

```
project HEAD : a131e39   worktree HEAD: afd0292
gate_attestation  working_dir = <proj>/.claude/worktrees/wt   exit_code = 0
finding_resolved  commit_hash = a131e39                        id = BH-101
```

The transition succeeds and registers **the wrong commit**. Two consequences:
the discharge is keyed on that hash, so the charge survives and the block does
not clear; and the ledger carries a resolution naming a commit that contains
none of the fix — a hash that is also `hardening_batch.py`'s "already spent"
set. **A false record is worse than the loud dead end it would replace**, which
is why adding `anchor = "caller"` to gate 2 — sahjhan#46's own migration advice
— was not taken.

Also found: **`anchor` on an emit validates clean and does nothing.**
`EmitConfig` does not `deny_unknown_fields`. Filed with the rest.

**This is a hole in the request, not in what shipped.** sahjhan#46's *"What
would resolve it"* asked for a per-gate opt-in and nothing else; v0.25.0
delivered exactly that, completely, including the validation and the
attestation field. The emit was described in that issue's own downstream
narrative and then left out of the ask. **A future session must not read the
paragraph above as sahjhan under-delivering.** Check the issue you filed before
characterising what came back.

**Filed: [sahjhan#48](https://github.com/jbrjake/sahjhan/issues/48).**

**⚠️ The process failure this session, recorded because the git log is what a
later session trusts.** Finding the emit gap was the moment to stop and tell
Jon — he owns sahjhan and turned #46 and #47 around overnight. Instead this
session filed #48 and kept going: wrote this handoff, surveyed W06, drafted a
three-option design question, and reported the release as *"inert."* The
correct sequence when an engine gap appears is: name the ask in one sentence,
**stop**, wait for the engine change. Not a handoff, and never a holtz-side
route around it (a gate-verified `commit_hash` argument was probed and works —
it is still the wrong answer, because the engine fix is coming).

---

## Three questions for Jon

None of them blocks the units below them; all three change what a later session
should build.

### Q1 — W32 step 3: is anything still owed for a sibling worktree?

The clause says *"decide what holtz does **in the meantime** … at minimum, a
diagnostic that names the cause"*. On the pinned engine the failure no longer
happens, so the floor has nothing to name. The one path that still reaches an
old engine is `_resolve._version_stale` returning False when
`bin/.sahjhan-version` is **absent** ("manual vendor — trust it").
**Recommended: nothing further; W32 closes with the pin plus V1–V4.** Not taken
as ruled.

### Q2 — is the release gate closed?

Carried forward unchanged from handoff #4: the gate's stated rationale names
only item 32, and that rationale is satisfied. Item 43 is a bad message on a
correct block. **Jon's call, and now a longer wait** — 43 needs an engine
release, not a session.

### Q3 — W06: the field is called `**Lens:**`, and the plan calls it `**Perspective:**`

**Stop here before writing W06's step 1.** The plan says *"`validate_punchlist.py`
errors on a missing `**Perspective:**`"* and V2 tests that literal string. The
product has no such field. What it has:

- `punchlist-format.md:15` declares **`**Lens:**`**, marked **optional**, with a
  **6-value** inline enumeration — while `[sets.perspective]` holds **13**.
- `justine-skill.md:250` and `phase-audit.md:67,94,100` already instruct
  *"tag all findings with a `**Lens:**` field"*. Archived real punchlists carry
  it.
- `validate_punchlist.py` names `Lens` in `FIELD_NAMES` — as a **section
  terminator only**. It is never extracted, `PunchlistItem` has no attribute for
  it, and `merge_punchlists.justine_findings` never passes one.

So the defect is one link longer than item 20 states: **the value Justine is
already told to write is parsed, discarded, and then defaulted to
`"unspecified"`, which no set contains and nothing refuses.** Step 3's premise —
that the skill must be taught to state the field — is stale; it is taught, it is
optional, and it is dropped.

Two readings, and the choice is Jon's because it is a name the product will
carry:

1. **Require `**Lens:**`** — the taught spelling, the one in real data and in
   the format spec. Parse it into `PunchlistItem.perspective`, validate
   membership against `[sets.perspective]`, make the format doc's entry required
   and replace its 6-value copy with a pointer to the set. Nothing has to be
   re-taught; the skill lines gain the enumeration and lose "optional".
2. **Require `**Perspective:**`** as the plan literally says — which introduces
   a second name for one fact, orphans the `**Lens:**` data and the three skill
   files that teach it, and is the "two spellings of one fact" shape this
   worklist keeps closing.

**Recommended: (1).** Everything else in W06 is unaffected — the required-field
mechanism, reading the 13 values from `[sets.perspective]` rather than restating
them, `merge_punchlists.py` carrying the stated value with `"unspecified"` kept
as an unreachable fallback, and the `merge-protocol.md` note are all identical
either way. Only the label differs.

**Design note for whoever builds it** (not a decision, just the constraint
found): `validate_punchlist.py` is deliberately Python 3.9-compatible
(`# PEP 604 unions run on Python 3.9 (issue #59)`), and `tomllib` is 3.11+. The
set has to be read from `enforcement/protocol.toml` without it. One scanner in
production, cross-checked in a **test** against `tomllib`'s parse of the same
file, keeps that to one derivation rather than two code paths that can drift.
The file locates the plugin root from `__file__` (`parents[3]`); the skill
invokes it as `python3 ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/…`.

---

## Standing facts

- **Gates observed at the pin commit** (`.venv`, not a clean environment):
  fast subset `pytest -m "not slow and not machine_specific"` exit 0, zero
  `FAILED`/`ERROR`; slow subset `pytest -m "slow or machine_specific"` exit 0,
  zero `FAILED`/`ERROR`; full suite re-run end to end after the tree was final —
  see the W32 section for the number. `ruff` exit 0. `mypy` exit 0 (69 files).
  `enforcement_lint.py` 0 errors / **2 pre-existing warnings** (the H1
  `prediction` pair). `contract_gate.py` PASS (100 commands, 30 field-checked).
  `enforcement_contract.py --check` current. `check_sahjhan_pin.py` exit 0 at
  **v0.25.0**, with `bin/sahjhan --version` agreeing. **No `--no-verify`.**
- **The full suite takes longer than ten minutes** (~40). Run it in the
  background and read the file; a partial `.....` line is not a result.
- **The README test badge is a gated derived number.** 2738 → **2742**.
- **`git` prints two `[dev …]` hashes and one is orphaned.** Only
  `git merge-base --is-ancestor <hash> HEAD` distinguishes them.
- **The binaries are not tracked.** `git ls-files bin/` is `.gitkeep` and the
  `sahjhan` symlink; the pin that ships is `_resolve.py`. Stage explicitly —
  `git add <paths>`, never `git add -A`: the tree carries untracked-by-design
  plan docs and four ~112MB binaries.
- **`sahjhan gate check <t> <args…> --json` binds `--json` as a positional
  template value.** Unchanged in 0.25.0.

---

## Suggested next step

**W06, once Q3 is answered.** It is next in worklist order and W07 depends on
it. Build the required-field mechanism once, here — W09 step 3 consumes the same
one for `reachability`, and if W09 finds itself writing a second, W06
under-built.

**Do not wait on sahjhan#48 for anything else.** Item 43 is the only thing
behind it, and W31 (item 50) — which touches the same discharge — has a design
decision of its own that is Jon's, not a session's.

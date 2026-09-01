# Release worklist — handoff #6

**Supersedes handoff #5.** What changed: **sahjhan v0.26.0 shipped #48**, the pin
moved, and **item 43 is `DONE`**, which closes W08.

## ⛔ Read this before writing a status line

**Release means all 49 items. RULED (Jon, 2026-09-01):** *"I ALREADY TOLD YOU A
WEEK AGO WE WERE DOING ALL OF THESE ITEMS BEFORE RELEASE."*

The **"four-unit release gate" was invented by a session**, written into Jon's
own working document, and is struck. Handoffs #4 and #5 and the first draft of
this one all reported against it, which is how a week of status reports said
"blocked only on item 43" while **44 items sat open behind it**. No sentence was
false; the frame was. Do not reconstruct it.

**Progress: 8 of 30 units, ~7 of 49 items. 44 items across 22 units remain.**
Report in those terms. Banned: "the release gate is closed", and "blocked only
on X" whenever a pile sits behind X.

**Read in this order:**

1. **This file** — what landed, and the one question left for Jon.
2. **`2026-08-27-release-worklist.md`** — the working document. Do the work from
   this. W08's *"Landed on sahjhan 0.26.0"* is new.
3. **`2026-08-27-release-worklist-ORIGINAL.md`** — Jon's text byte-for-byte.
4. **`…-handoff-1.md` §2, §2a, §3** — still the best account of the fixtures and
   the stale-cache trap.

---

## Where things stand

| Unit | Items | Status | Commit |
|---|---|---|---|
| W01–W05 | fixtures, 29, 31, 19, 1, 2 | `DONE` | see handoff #4 |
| W08 | **32** | `DONE` | `780ba47` (v0.169.7) |
| W08 | **43** | **`DONE`** | *this session* |
| W32 | 51 | `DONE` | `168413c` — closed by the 0.25.0 pin |
| W06 | 20 | `TODO` — **next, and unblocked**: the field is `Lens` (ruled) | — |
| W07 | 3 | `TODO` — depends on W06 | — |
| W22 | 27 | `TODO` — rest of P1 | — |
| W31 | 50 | `TODO` | — |

**Nothing is pushed.** Everything is local on `dev`. **CI has never run on any
of it.** Do not claim it has.

---

## What this session did

### The pin moved to sahjhan v0.26.0

Via `scripts/vendor-sahjhan.sh 0.26.0`, which calls `update_sahjhan_pin.py` —
the step that stops the resolver silently reverting the binary. All four
checksums were checked against the release's published `SHA256SUMS`, not just
recomputed locally. `check_sahjhan_pin.py` exit 0 at **v0.26.0**, and
`bin/sahjhan --version` agrees.

**The breaking change needed no migration, and that was checked rather than
assumed.** `EmitConfig` now denies unknown fields, which is a config **load**
error — an unrecognized key breaks every command, not just its own transition.
All eight emits in `transitions.toml` carry only `event`/`commands`/`fields`,
and `sahjhan --config-dir enforcement validate` is exit 0. That green was proved
non-vacuous by injecting `anchour = "caller"` into `fix_commit`'s emit: exit 3,
naming the key and the line. **A clean checklist is not a verdict on the
release's value** — 0.26.0 delivered exactly what this repo asked for.

### Item 43 — landed, and it took three anchors, not one

`fix_commit` runs **three** commands that read a tree, and the migration is only
correct if all three move together:

| site | before | after |
|---|---|---|
| gate 2 `git log -1 … grep '{{item_id}}'` | project `HEAD` | the caller's |
| gate 3 `verify_suite.py --check` | project tree hash | the caller's |
| emit `finding_resolved.commit_hash` | project `HEAD` | the caller's |

**Gate 3 is not scope added here** — sahjhan#46's own reproduction shows its
`tree_hash=202161fd…` identical from both directories, as part of the filed
defect. Left at the project anchor it is wrong in *both* directions: a
subagent's `suite_green` names its worktree's hash and never matches (a false
block), while the orchestrator's green on a tree that does not contain the fix
does match (a false pass). The four other transitions carrying that gate —
`fix_loop_start`, `iteration_boundary`, `set complete perspective`, `converge` —
are **orchestrator-only and untouched**, as are `merge_finding`'s two
`finding_resolved` emits.

**The emit is the half a future session must not drop.** Anchoring the gates
alone is worse than anchoring neither, and it is measured: with gates anchored
and the emit not, the transition **succeeds** and records the project's `HEAD`
(`1cd7568`) where the worktree's is `01318cb` — a false resolution replacing a
loud block, on a hash that is load-bearing in both `pending_commits_discharged`
and `hardening_batch.py`'s spent set.

**The orchestrator's path is unchanged by construction, not by care.** It runs
`fix_commit` from the project root after `git merge --ff-only`, so the caller
*is* the project anchor, `HEAD` is already the subagent's commit, and the
ff-merge left the tree byte-identical. Measured: with the anchor on, gate 2
still refuses from the project root.

### Two things made the escape unrunnable, in different files

The engine half is above. The other was never an engine problem: the block
printed `transition fix_commit` with **no `item_id`**, which is positional and
required, so the line it told the reader to run was refused by the CLI for
*every* actor — the orchestrator included. `commit_gate.py` now names the
commits this actor is charged for and spells the escape
`transition fix_commit BH-NNN`.

`references/phase-fix-loop.md` narrowed its blanket *"the subagent does **NOT**
run any `transition`"* to name this one exception. A brief that still said
otherwise would contradict the block a subagent is about to hit — the
unenforced-contradictory-contract shape of `800624f` — so per CLAUDE.md the
doc-consistency test moved in the same commit
(`test_the_subagent_is_taught_the_escape_from_its_own_commit_block`), and it
asserts the blanket **and** the exception, because a document that dropped the
blanket to make room would license a subagent to drive the loop.

### ⚠️ The process note this session owes its successor

Handoff #5 left three questions for Jon. **Two of them were already answered in
sahjhan#46 — an issue this repo wrote** — and asking them cost a turn and Jon's
patience: *"i can't fucking remember what we decided… pretty sure we already
settled this though. isn't this why you made that request to sahjhan."* He was
right. #46's *"Why it matters downstream"* states that the normal flow is
unchanged and the broken case is the subagent's **second** commit, and its
reproduction block shows the suite gate's hash as part of the defect.

**An ask this repo filed upstream is a decision record.** Read the filing, the
plan item and the handoff before putting a design question to anyone. Q1 and Q2
of handoff #5 were not open questions; they were unread ones.

---

## Nothing is waiting on Jon

**RULED (Jon, 2026-09-01): the field is `**Lens:**`.** *"they're lenses, they're
always lenses."* W06's plan text saying `**Perspective:**` is the outlier and
does not get built — a second name for one fact is the exact shape this worklist
keeps closing. W06 is **unblocked**; build it against `Lens`.

Concretely, and unchanged from handoff #5 §Q3 apart from the label now being
settled: `punchlist-format.md:15` declares `**Lens:**` optional with a 6-value
inline enumeration while `[sets.perspective]` holds 13; `justine-skill.md:250`
and `phase-audit.md:67,94,100` already instruct Justine to write it; and
`validate_punchlist.py` names `Lens` in `FIELD_NAMES` as a **section terminator
only** — never extracted, no attribute on `PunchlistItem`, then defaulted to
`"unspecified"`, which no set contains and nothing refuses. So the defect is one
link longer than item 20 states: **the value Justine is already told to write is
parsed, discarded, and defaulted.** Step 3's premise — that the skill must be
taught to state the field — is stale; it is taught, it is optional, and it is
dropped. Make the format doc's entry required, replace its 6-value copy with a
pointer to `[sets.perspective]`, and parse the value into
`PunchlistItem.perspective`.

**Design note found while surveying, not a decision:** `validate_punchlist.py`
is deliberately Python 3.9-compatible (`# PEP 604 unions run on Python 3.9
(issue #59)`) and `tomllib` is 3.11+. The 13 values have to be read from
`enforcement/protocol.toml` without it — one scanner in production,
cross-checked in a **test** against `tomllib`'s parse of the same file, so there
is one derivation rather than two code paths that can drift.

Handoff #5's Q1 (W32 step 3) and Q2 (is the release gate closed) are **withdrawn
as moot**: W32 closed with the pin, and the gate's four units are now all `DONE`.

---

## Standing facts

- **Gates observed on the final tree** (`.venv`, not a clean environment) — see
  the commit message for the full-suite number and exit code. `ruff` exit 0.
  `mypy` exit 0 (69 files). `enforcement_lint.py` 0 errors / **2 pre-existing
  warnings** (the H1 `prediction` pair). `contract_gate.py` PASS — **101**
  commands, up from 100, because the skill file's new escape line is itself
  contract-tested. `enforcement_contract.py --check` current.
  `check_sahjhan_pin.py` exit 0 at **v0.26.0**. **No `--no-verify`.**
- **The full suite takes ~40 min**, longer than the Bash cap. Run it with
  `run_in_background` and read the output file; a partial `.....` line is not a
  result.
- **Re-run the suite after the last edit, not before it.** The README badge is a
  gated derived number (2742 → **2752**) and a run that captured the file before
  it was corrected is not evidence — this is the second session to hit it.
- **A real daemon refuses `enforcement_write` from a test process**
  (`auth_failed`, `pid_resolution_failed`), so no test can write the
  `restricted` `suite_green` that gate 3 wants. That is why
  `test_fix_commit_caller_anchor.py` asserts *which tree the gate hashed* rather
  than whether it passed, and why its emit half runs against a config **derived
  from** `enforcement/` at test time — never a pasted copy, so deleting `anchor`
  from the real file still fails the test.
- **`git` prints two `[dev …]` hashes and one is orphaned.** Only
  `git merge-base --is-ancestor <hash> HEAD` distinguishes them.
- **The binaries are not tracked.** Stage explicitly — `git add <paths>`, never
  `git add -A`: the tree carries untracked-by-design plan docs and four ~112MB
  binaries.
- **Editing a daemon-calling hook requires `bash scripts/hash-trusted-callers.sh`**
  or enforcement silently stops. `commit_gate.py` changed here; the manifest was
  regenerated and its hash re-checked against the file.

---

## Suggested next step

**W06.** Next in worklist order, W07 depends on it, and it is unblocked — the
field is `Lens`. Build the required-field mechanism **once**, here: W09 step 3
consumes the same one for `reachability`, and if W09 finds itself writing a
second, W06 under-built.

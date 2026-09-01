# Convergence work queue — implementation handoff #5

**Written 2026-08-25**, at the end of the fifth implementing session. Paused at
Jon's request **before P4.1**, on a clean boundary: P0.5 closed except one
build, P0.3's gate change shipped, tree clean, no question outstanding.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `7b69b22`, version **0.163.0**. Full suite green
(2490 collected, `pytest` exit 0 observed, coverage 90.14%), `ruff`, `mypy`
(64 files), the
contract gate and the generated `ENFORCEMENT-CONTRACT.md` all current.
`enforcement_lint.py` baseline is **0 errors / 2 warnings** — both pre-existing
H1s on `prediction` / `prediction_outcome`. **No hook was bypassed — no
`--no-verify` in this session.**

Sister repo: **sahjhan v0.23.0 released** (`b564a07` + the version bump),
CI `conclusion=success`, four targets and `checksums.sha256` published.

---

## Six rulings this session (D28–D33)

Jon was walked through each with effort, impact and tradeoffs before ruling.

| # | Subject | Ruling |
|---|---|---|
| D28 | P0.5 severity derivation | **WON'T DO** — `blast_radius` arrives after filing, "public-API surface" has no ledger representation |
| D29 | P0.5 routing | **SHIP** eligibility gate + `theoretical` auto-defer courier; **finalize batching still owed a ruling** |
| D30 | P0.5 reopen-don't-refile | **WON'T DO** — rejection half is worse than nothing alone; reopen half rewrites seven openness predicates |
| D31 | H8's two false warnings | **NARROW** — quiet when an escape has no gates; session 4's argument-scoped exemption stands |
| D32 | P0.3's gate change | **EXTEND SAHJHAN** rather than move the predicate into Python |
| D33 | The actor on the TDD event | **COURIER** writes a host-attested event |

**P0.5 is now closed except D29's build.** Two clauses shipped (the
`reachability` field, D4's conjuncts), two ruled out with the falsified premise
on record.

---

## Shipped this session

| Item | What landed |
|---|---|
| D31 | H8 skips an escape with zero gates. Lint baseline 4 warnings → 2 |
| D32 | sahjhan: `hook eval --agent-id`, hook gates seeded with `state_params`, one `gate_filter()` resolving `{{var}}` (three copied blocks collapsed) |
| D33 | `tdd_evidence` event, `tdd_courier.py`, the `hooks.toml` gate switch, `pre_tool_hook.py` actor passthrough |
| — | `scripts/update_sahjhan_pin.py` + `vendor-sahjhan.sh` calling it — the pin hole below |

Every item was proven non-vacuous by mutating the implementation with `Edit`,
re-running, observing RED, and reverting.

---

## Next up

1. **P4.1 — script the merge.** Cheapest open item, ~2h, unblocked, untouched.
   `merge-protocol.md:11` calls it "mechanical… without judgment calls" and it
   ran 36.7 min as a subagent hand-writing throwaway `python3 -c` scripts.
2. **D29's build** — the `user_reachable` fix-loop eligibility gate (a plain
   named query of the `item_is_low` shape, ~1h), then the `theoretical`
   auto-defer courier (~half a session). **Bring finalize batching back as its
   own question first**: `location` is a `file:line` string, so "one hardening
   commit per module" has no ledger meaning until a module rule is chosen.
   Do not ship it as unenforced prose.
3. **P0.3's remaining half** — worktree isolation for fix subagents, and
   rewriting `phase-fix-loop.md:68` to serialize *commits, not findings*. The
   gate change the spec required to land first is done, so this is unblocked.
   Note it still needs the `hook_e2e` subagent-parity test CLAUDE.md mandates
   for any change to what a subagent may do.

---

## Working notes for the next session

Everything in handoff #4's notes still holds. New this session:

- **The sahjhan version is pinned in three places, and only one governs.**
  `bin/.sahjhan-version` is runtime state; `_resolve.SAHJHAN_VERSION` is what
  `ensure_sahjhan()` reads; `_resolve.SAHJHAN_CHECKSUMS` pins the binaries.
  `vendor-sahjhan.sh` used to write only the first, so vendoring 0.23.0 was
  undone by the next hook invocation — which restored 0.22.0 **and rewrote the
  marker to match**, leaving every pin agreeing on the version nobody asked
  for. `check_sahjhan_pin.py` could not see it: it compares the marker to the
  resolver, and the resolver is what rewrites the marker. Closed by making
  vendoring update the resolver; `test_vendor_script_updates_the_resolver_pin`
  fails the build if the step is dropped. **Symptom to recognise:** a gate that
  silently stops firing, and `bin/sahjhan --version` reporting different
  answers minutes apart.
- **Re-hash the trusted-callers manifest LAST.** Editing a daemon-calling hook
  after running `hash-trusted-callers.sh` leaves its hash stale; the daemon
  then refuses it, no cache comes back, `is_enforcement_fresh(None)` reads as
  "no active audit", and enforcement goes **permissive**. Every unit and
  `hook_e2e` test passed while the TDD gate was fully disabled — only
  `real_daemon` tests caught it. Finalize a hook's bytes, *then* re-hash.
- **A courier should take nothing from the working tree it can read from the
  ledger.** `tdd_courier.py` first named `project` from `repo_root(cwd)` and
  refused outside a git tree — which the `real_daemon` fixture is. The
  `test_failed_before_fix` row already carries `project`, `run` and `auditor`,
  so all three come from the query now. A test pins that `repo_root` stays out.
- **A malformed hook gate fails open.** `hook eval` returns `allow` on config
  or ledger errors by design, so a gate that fails to parse disables its hook
  silently. When a gate stops firing, check the config path before the logic.
- **Both README counts move on a new hook**, and adding tests moves the badge
  again afterwards — set the badge *last*, after no more tests will be added.
  This session it took three passes (2460 → 2487 → 2490).
- **`sahjhan hook eval` fails open on purpose.** Do not "fix" that; it is what
  keeps a broken config from bricking a session. It does mean a hook-gate bug
  presents as missing enforcement rather than an error.

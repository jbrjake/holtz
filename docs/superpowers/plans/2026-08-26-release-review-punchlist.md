# Release review — v0.141.3 → 0.169.1 (dev @ 48c72fd)

**Scope:** the full delta since the last release tag. 93 commits, 127 files,
+18,402 / −700. Reviewed as one change, not commit by commit.

**Method:** read the frozen spec (`docs/design/convergence-speed-proposals.md`),
the status record, and the shipped config/skill/hook tree; then drove a **real
daemon** to falsify four structural claims. Every "PROVEN" item below was
observed, not argued.

**Gates observed at review time:** `enforcement_lint.py` exit 0 (2 warnings,
pre-existing). `contract_gate.py` 38/38 PASS. `enforcement_contract.py --check`
fresh. Fast pytest subset (in `.venv`) exit 0. **Full suite, sequential
(`-p no:randomly`), observed at exit 0** — but see item 17: one earlier run
under concurrent load produced two failures.

**Three passes, in this order.** First: user-impact release notes as a
completeness check (items 1–17). Second: the adversarial question, *what can a
motivated agent do to this gate* (items 18–24). Third: the scope the second
pass declared unaudited, asking *what does the tooling break without being
asked* (items 25–28). A **fourth pass, 2026-08-27**, added items 29–49 — the
worktree runtime path, the two PreToolUse gates (`bash_guard.py`,
`commit_gate.py`), the shell parsers, courier attribution, the render templates
and the infra scripts, none of which the first three passes read. **Start at
"Tiers — consolidated priority (fourth pass)"** immediately below; it sorts
every item, old and new, by what a good-faith run hits first, and supersedes the
chronological "Suggested order" near the end of the file. The per-item sections
between are in pass order, not severity order.

---

## Fourth pass, 2026-08-27 — the runtime and the gates the first three passes did not read

The first three passes audited the config/predicate layer and the merge/courier
scripts. They shared one blind spot, and it is the same one twice: **they never
ran a hook with a cwd shaped like a git worktree, and they never read the two
highest-traffic PreToolUse gates** (`bash_guard.py`, `commit_gate.py`) or the
shell parsers those gates key on. That is exactly where the delta's headline
feature — the three-wide worktree fix loop — actually executes. The third pass
even named `bash_guard.py` and `commit_gate.py` as "the notable gap"; this pass
read them.

Two class statements, and everything new here is one of them:

1. **A path the system owns must resolve against the project anchor, never
   `cwd`.** `docs/holtz/.sahjhan/` is gitignored, so a linked worktree does not
   contain it. Five hooks probe `os.path.isdir(cwd/docs/holtz/.sahjhan)` to
   decide "is an audit active here," and in a subagent's worktree that probe is
   False while the daemon is fully reachable — so guards keyed on it silently
   no-op or flip to fail-**open**, for exactly the three actors doing the fixes.
   This is [[anchor-system-paths-at-project-root]] arriving in the hooks instead
   of the manifest: `_common.boundary_dir` already resolves the socket through
   `project_anchor` (worktree-aware, D40); the audit-active probe was left
   `cwd`-relative next to it.
2. **A guard that keys on a command's first token is defeated by any shell idiom
   the parser does not split on.** The `!` incident (#81,
   [[enforcement-human-attestation-channel]]) was this. A single `&` is this
   again, in the same file, past the token the `!` fix named — and so is
   `eval`/`$VAR` indirection reaching one guard and not the one protecting the
   hooks.

Both are the shape [[comment-argues-predicate-decides]] warns about: the
docstrings promise fail-closed and single-owner parsing; the predicates deliver
neither.

### Tiers — consolidated priority (fourth pass)

Sorted by *what a good-faith three-wide run against a real target hits* — the
run deadlocks, or enforcement silently stops measuring, or convergence is
unreachable. Motivated-agent bypasses are real and serious but do not derail a
cooperating functional test, so they sit in Tier C (fix before **release**, not
before the next test run). This supersedes "Suggested order" below.

**Tier A — a good-faith run hits these; fix before functional testing**
- **29** — worktree path resolution disables manifest checks + fails the TDD gate open for all three subagents *(new; PROVEN)*
- **31** — the taught `test_failed_before_fix` and the TDD block's own escape omit required fields, so the printed escape is unrunnable *(new; PROVEN)*
- **19** — the TDD courier stamps one actor's evidence onto another and starves the second *(existing P0)*
- **1** — a sibling's `fix_commit` revokes a still-working actor's TDD evidence *(existing P0)*
- **2** — fixing more than half your MEDIUMs strands `converge` forever *(existing P0)*
- **3** — `all_findings_closed` still gates lens completion, thirteen times — the empty-board non-termination the release exists to end *(existing P0)*

**Tier B — corrupts the run's record or weakens enforcement mid-run; fix before trusting results**
- **32** — `unregistered_commits` is cleared by matching command text, with no success check, over every actor's bucket *(new; PROVEN)*
- **25** — the merge re-files Justine's escalations as `theoretical` and makes them unfixable *(existing P0; only if the merge/Justine step is in the test)*
- **26** — nothing requires Justine to grade reachability, so her board can arrive `theoretical` and auto-defer *(existing P1)*
- **35** — `stale_sweep`'s population window is a run-global transition watermark (item-1 class, in a courier) *(new)*
- **42** — per-actor cache state is read-modify-written over the whole map, no compare-and-swap *(new)*
- **43** — the pending-commit block names an escape its own comment says the blocked subagent cannot run *(new)*
- **34** — couriers go silent when a script's CLI accepts what its recognizer refuses — extends item 28 to a third and fourth script *(new + item 28)*
- **37** — the primer's silent-degrade set is wider than item 17, and its ordering skips daemon-death detection *(new + item 17)*
- **5** — the amplification breaker sits on the path the skill file calls the exception *(existing P1)*
- **20** — every merged finding belongs to no lens, and the lens gate is about to be scoped by lens *(existing P1)*

**Tier C — integrity/bypass; must-fix before RELEASE, a good-faith test won't trigger them**
- **30** — a single `&` (and `eval`/`$VAR` indirection) bypasses every command-keyed guard, including the one protecting `enforcement/hooks/` *(new; PROVEN)*
- **18** — any CRITICAL can be closed with `reason=theoretical`, and the config argues it cannot *(existing P0)*
- **36** — the theoretical courier fires on read-only commands that merely name the merge script, and downloads the binary with no active-audit guard *(new)*
- **33** — `suite_courier` records `suite_green` for any script whose path ends `verify_suite.py`, with no second check *(new; PROVEN)*
- **9** — `merge_finding` has no relatedness or severity constraint *(existing P2)*
- **22** — no lint binds "a gate filters on this value" to "only a hook may write it" *(existing P1)*
- **21** — the round cap's population is an optional field the agent types *(existing P1)*
- **24** — a hardening batch's commit need not touch the module it closes *(existing P2)*
- **40** — `NotebookEdit` is an ungated source-edit path three files disagree about *(new)*
- **47** — `_sahjhan_bootstrap.py` calls a gated daemon op but is absent from the trusted-callers manifest; its bash-source-write path fails open *(new)*
- **41** — the boundary block precedes the freshness check, so an abandoned audit with a surviving daemon wedges the whole repo *(new)*
- **38** — `sed --in-place` and `git diff --output=` are classified read-only *(new)*

**Tier D — correctness / hygiene / recorded-decision; do not block the test**
- **4** — the fix-subagent contract contradicts itself across three files
- **6** — the `DEFERRED.md` conjunct is satisfied by filing one finding
- **7** — `phase-convergence.md` still says converge requires "zero open items"
- **8** — `SKILL.md`'s deferral rules predate P0.5
- **10** — the two converge conjuncts pull against each other
- **11** — gates that print no escape
- **12** — README contradicts itself, including on a security claim
- **13** — `docs/ARCHITECTURE.md` still lists `PUNCHLIST-MERGED.md`
- **14** — `step-10-fix-loop.md` Fast Path still mandates a third suite run
- **15** — `hypothesis` is undeclared in `pyproject` *(verify it doesn't break a fresh checkout's test collection — that would undercut the harness)*
- **16** — `CHANGELOG.md` `[Unreleased]` is empty
- **17** — the primer fails open on timeout and makes the suite load-flaky *(now part of item 37)*
- **23** — three-wide dispatch has no rework path when `--ff-only` refuses
- **28** — a courier's recognizer is narrower than its script's CLI *(now the head of item 34)*
- **39** — `post_tool_hook` silently records nothing on a non-zero eval exit; `AttributeError` on a JSON list *(new)*
- **44** — `DEFERRED.md` renders a deferred-then-fixed finding as still deferred; `STATUS.md` goes stale between transitions *(new)*
- **45** — `migrate_legacy.py`: `step`/`commit_hash` violate the schema; `--all` has no ledger boundary; `build_project` accumulates duplicate rows *(new)*
- **46** — `update_sahjhan_pin.py` never cross-checks the binary against the version it pins; the runtime resolver trusts a version marker and never re-hashes *(new)*
- **48** — the delta's new enforcement predicates ship with no direct unit tests *(new)*
- **49** — lower tail: fail-open comments inverted, transient-read state wipe, mid-flight-upgrade stall charge, `post_tool_hook` never passes `--agent-id`, wrong-escape messages, `resolve_indirection` mangling `--field` data *(new; bundle)*

### New items

Everything below was found by the fourth pass. Items 29, 30 and 31 were driven
by the reviewer directly (git, the real hook subprocess, an actual worktree);
the rest are VERIFIED against the tree at `48c72fd` by code reading, with the
few INFERRED links marked. Nothing from passes one through three is retracted;
items 1, 2, 3, 17, 19, 25 and 28 are extended, not replaced.

#### 29. The worktree fix loop runs with enforcement partly disabled for the three subagents · PROVEN · Tier A

`.gitignore:15` ignores `docs/holtz/.sahjhan/` (verified: `git ls-files` returns
0 tracked, `git check-ignore docs/holtz/.sahjhan/ledger.jsonl` confirms), so a
`git worktree add` checkout does not contain it (verified empirically — a linked
worktree of a repo with that gitignore has no such directory). `phase-fix-loop.md:37,43-48`
dispatches up to three subagents, each with `isolation: "worktree"`, each doing
its whole TDD cycle in its own worktree. Five hook sites decide "is an audit
active here" with a `cwd`-relative probe: `bash_guard.py:49`, `_common.py:171`
(`exit_enforcement_error`), `_common.py:427/458` (daemon-init pid, terminated
marker), `_sahjhan_bootstrap.py:367`. The socket, by contrast, resolves through
`project_anchor` and is correctly shared with the main daemon (D40). So in a
subagent's worktree the daemon is reachable but the dir probe is False, and:

- **`bash_guard.py:50-51` → `exit_ok()`** (verified): managed-file integrity
  verification is skipped for every Bash call the three subagents make — the
  actors doing all the writing.
- **`_common.py:171-172` fails open** (verified by subprocess: `nodir → allow`,
  `withdir → deny`): when `hook eval` times out (item 17 shows this suite goes
  load-flaky at the 5 s budget) or the daemon hiccups, the subagent's source
  edit is *allowed* with the TDD gate never evaluated. The module docstring
  (`pre_tool_hook.py:9`) promises "Fails closed during active audits if the
  daemon is unreachable" — false for exactly these actors.
- **the daemon-stop guard is off** (`_sahjhan_bootstrap.py:367`,
  `_daemon_stop_permitted`): a subagent may run `sahjhan daemon stop` mid-loop,
  which the block message itself says "destroys the HMAC session key and
  terminates the run."
- **`suite_courier` writes `run="0"`, `project=<worktree-dir>`** (the C1 half):
  `verify_suite._run_number(cwd)` reads the same missing marker, and
  `events.toml` accepts `"0"` against `^\d+$`. Because sahjhan's emit resolver
  inherits the newest ledger value (`emit.rs`), the *next* `fix_commit`'s
  emitted `finding_resolved` carries `run=0, project=<worktree-dir>` too, and so
  do the `defer_*` emits — corrupting run attribution and breaking
  `pattern_round._current_run` / `stale_sweep._current_run`, which then match no
  round and drop the round's population out of item 21's join.

**Why it shipped:** no test anywhere runs an enforcement hook with a
worktree-shaped `cwd`. **Fix:** resolve the audit-active probe and the courier's
`run`/`project` through `project_anchor` / the ledger — the way the socket and
`pattern_round`/`stale_sweep` already do — so the one anchor is defined once and
the others in terms of it ([[enforcement-name-the-fact-not-the-text]]). Add a
`hook_e2e` fixture whose `cwd` is a linked worktree; it is the missing test
class this whole item lives in.

#### 30. A single `&`, and `eval`/`$VAR` indirection, bypass every command-keyed guard · PROVEN · Tier C

Every command-keyed guard splits segments on `\s*(?:&&|\|\||[;|\n])\s*`
(`_sahjhan_bootstrap.py:416,668`, `_protocol_cache.py:292`, `commit_gate.py:46`),
which omits a single `&`. Bash's `&` is a separator, so `A & B` is one segment
whose first token is `A`, and every first-token guard inspects the wrong
command. Driven live through the real hook subprocess:

```
deny   sahjhan reseal --proof X
allow  true & sahjhan reseal --proof X
deny   sahjhan event quiz_exhausted_resolved --field project=holtz
allow  true & sahjhan event quiz_exhausted_resolved --field project=holtz
allow  true & rm -rf enforcement/hooks
```

One character reaches `reseal`/`sign`/`vault read`, the human-only
`quiz_exhausted_resolved` channel, the fix-loop commit gate, `is_git_commit`
(so the commit is invisible on both the gate and the `protocol_tracker` side),
and the self-protection guard on `enforcement/hooks/` — the file whose own
docstring is "DO NOT MODIFY. This hook protects itself." This is the `!`
incident's class (#81), past the token that fix named. Second face, same file:
`_check_bash_write` (`_sahjhan_bootstrap.py:668`) parses the **raw** command
while the sahjhan guard (`:416`) parses `resolve_indirection(...)`, so
`eval "rm -rf enforcement/hooks"` and `T=docs/holtz/.sahjhan; rm -rf $T` slip
past the protected-path guard the indirection module (`_shell_norm.py:23-25`)
claims to own. **Fix:** one owner for segmentation, splitting on `&` too, on the
resolved command, used by every guard — and rebuild the command-keyed branches
to scan the whole segment the way the surviving redirect/`tee` branches already
do. Add these idioms to the combinatorial matrix in `test_contract_commands.py`
(it carries `&` only as a trailing suffix, never as a separator).

#### 31. The taught TDD record and the gate's own escape omit required fields · PROVEN · Tier A

`events.toml:602-607`: `test_failed_before_fix` requires `finding_id, test_name,
project, run, auditor` (none marked `optional`). `phase-fix-loop.md:52` and the
TDD block message at `hooks.toml:30` teach only `--field finding_id= --field
test_name=`. `SKILL.md:156` teaches the full form for `fix_start` — the two
files disagree. `sahjhan event` does not inherit run-context (only `emits` do —
verified by the third pass's real-daemon check that a missing required field is
`error: missing field '<name>'`, exit 4), so the taught command exits non-zero
and the block prints an escape that cannot run as written — the #77
"unsatisfiable printed escape" shape, on the first fix of every run. Five more
inline-backtick `sahjhan event` commands in `phase-fix-loop.md` (`:7` reference_read,
`:50/:167` fix_start, `:55` blast_radius, `:57` hardening_complete, `:115`
finding) have the same omission. **Why it shipped:** `contract_gate.py` extracts
commands from fenced blocks only and asks only "does the hook allow it," never
"does the engine accept its fields," and `hooks.toml`'s message is not a skill
file so it is out of scope entirely. **Fix:** add `project/run/auditor` to the
taught forms and the block message; extend the contract gate to inline backticks
and to a field-validation check against the engine ([[test-the-taught-sequence-not-just-the-gate]]).

#### 32. `unregistered_commits` is cleared by command text, with no success check, over every actor · PROVEN · Tier B

`protocol_tracker.py:217-222` calls `_runs_transition(cmd, "fix_commit")` — pure
`cmd.split()` adjacency — and sets `cache["unregistered_commits"] = {}`, the
value `commit_gate.py:84` reads. `exit_code` is computed at `:250` and used only
in the git-commit branch; this path ignores it. Driven against the mock daemon
from `{"agent-a":["a1"],"agent-b":["b1"],"":["c1"]}`: a `transition fix_commit`
that the engine **refuses** (exit 1), and even `echo remember to run transition
fix_commit`, both clear the whole map. Two defects on top of each other, both
the shape [[enforcement-derive-from-ledger-not-mirror]] forbids and H7/H8
enforce five lines above for `pattern_analysis_overdue`:

- **No success check** — a refused fix_commit discharges the block; the commit
  was never registered and the gate stops asking.
- **Run-global clear** — D41 keyed the *charge* per actor and left the *clear*
  global (`_protocol_cache.py:610-612` argues only the merged subagent's bucket).
  One `fix_commit` grants the other two in-flight subagents a free unregistered
  commit each. The deny-direction coupling was fixed (item 1's class); the
  allow-direction — the one that loses enforcement — was not.
  `test_unregistered_commit_actor.py:164` asserts the global clear as intended
  and never seeds three buckets, a failed transition, or a second commit.

#### 33. `suite_courier` records `suite_green` for any script whose path ends `verify_suite.py` · PROVEN · Tier C

`verify_suite.py:371` — identity is the path **tail** (`endswith(_SCRIPT_TAIL)`),
and the courier never re-derives its payload: `scope` comes from command text,
`tree_hash`/`commit_hash` from git, and the only second opinion is the printed
`SUITE-GREEN:` line. It is the one courier with no ledger re-derivation (the
other four re-run their real check). Driven in a throwaway repo (socket pointed
at a dead path so nothing could be written), a two-line
`sub/enforcement/scripts/verify_suite.py` that only prints the marker passed the
recognizer, exit code, `repo_root`, `compute_tree_hash` and `_effective_scope` —
the sole thing that stopped the write was the daemon being absent. With a live
daemon this writes a `suite_green` naming the real tree having run zero tests,
which satisfies `verify_suite.py --check` and the suite gate on `fix_commit`.
`_effective_scope` re-derives only for `--scope affected`; `--scope full` — the
stronger claim three transitions demand — is passed straight through. **Fix:**
have the courier re-run the real check (as the other four do) or bind the marker
to a host-derived signal it cannot echo.

#### 34. Couriers go silent when a script's CLI accepts what its recognizer refuses · Tier B · extends item 28

Item 28 named two scripts; it is at least four, and one has a worse consequence:

- `hardening_batch.py:359` accepts `--cwd`; `module_of_command` rejects it →
  `hardening_batch_courier` `exit_ok()` with no warning while the module's
  `fault_injected` findings stay open and `no_open_fault_injected` blocks
  `converge` at Step 15 (verified: `--cwd .` → `None`, bare → `'tqdm'`).
- `tdd_courier.py:76-80` requires a **single** shell segment and exits silently
  otherwise (`:90`), and — unlike `verify_suite`/`pattern_round`/`stale_sweep`
  at `:69/:150/:174` — `phase-fix-loop.md` step 3 (`:52`) carries **no**
  "run it alone" warning. A subagent that chains `pytest …; sahjhan event
  test_failed_before_fix …` records nothing, and the silence sits *before*
  item 19's mis-attribution.
- All four recognizers accept only `python|python3|py` as the interpreter
  (`verify_suite.py:341` et al.), so `poetry run python …` / `uv run …` /
  `python3.12 …` — shapes `phase-fix-loop.md:230` explicitly invites via
  `HOLTZ_PYTEST` — record nothing, silently.

**Fix (item 28's, widened):** each script's parser refuses exactly what its
courier refuses, and each courier `exit_warn`s on the None path rather than
`exit_ok`.

#### 35. `stale_sweep`'s population window is a run-global transition watermark · Tier B · item-1 class

`stale_sweep.py:69-80` scopes "this sweep" to `seq > MAX(seq of any
state_transition)`. The docstring calls that "the same window
`defer_cant_reproduce`'s own gate uses" — but it is run-global, and in a
three-wide loop the orchestrator records a `fix_commit` transition every time a
subagent lands. A sibling landing mid-sweep advances the watermark past the
retirements already recorded, so `check` reports "verdicts name findings this
sweep does not cover," the courier warns, and nothing is recorded. Both the
script and the courier's re-derivation (`stale_sweep_courier.py:126`) read the
same window, so the courier cannot rescue it. This is D41 / item 1 a third time.

#### 36. The theoretical courier fires on read-only commands that name the merge script, and downloads the binary unguarded · Tier C

`theoretical_courier.py:54,73` wakes when any token *contains* `merge_punchlists.py`,
so `grep -n reachability …merge_punchlists.py`, `cat …`, and `git log -- …`
all trigger it (verified), and `echo event finding` trips the sibling branch —
the exact #77 shape the docstring at `:63-66` says it guards against, applied to
only one of its two branches (the sahjhan-verb branch is correct). The
population is re-derived so a real finding is not forged, but an agent can *time*
the auto-deferral sweep on demand, and combined with item 25 (merge re-files
escalations as `theoretical`) `grep`-ing the merge script auto-defers Justine's
escalations. Separately, `pending()` calls `ensure_sahjhan()` with no
active-audit guard (`:85`, reached from `:155`), unlike `primer.py:80-83`, so any
Bash line naming the merge script in any plugin-installed project triggers a
~100 MB binary download and a protocol warning injected into a non-audit session.

#### 37. The primer's silent-degrade is wider than item 17, and its ordering hides daemon death · Tier B · extends item 17

Item 17 names the `TimeoutExpired` fail-open at `primer.py:117-118`. Two more:
`:120-121` `exit_ok()` on any non-zero `status` exit (corrupt ledger, config
error), which item 17's proposed fix does not cover; and `:101-102` `exit_ok()`
when a `_recently_failed` marker suppresses the binary for an hour. The
aggravating fact: the daemon-death check (`:147-150`) and the enforcement-health
probe (`:152-153`) sit **after** the status subprocess, so a slow or failing
`status` skips the terminated-marker write and `auth_failed` detection entirely —
the hook whose job is reporting daemon death stays silent when the daemon dies
during a slow status. **Fix:** inject a degraded-mode notice on both the timeout
and the non-zero paths, and move the death/health checks before the status call.

#### 38. `sed --in-place` and `git diff --output=` are classified read-only · Tier C

`_protocol_cache.py:358` maps `sed` writing-flags to `("-i",)`, and
`"--in-place".startswith("-i")` is False, so `sed --in-place 's/a/b/' src.py` →
read-only (verified), accruing no stall — the `#70/#71` in-place-rewrite bypass,
reopened, with the function's own docstring naming this exact direction as the
unacceptable one. `git diff` is whitelisted with no writing-flag table, so
`git diff --output=/path HEAD` → read-only too. `test_hook_chains.py:527` tests
`sed -i` and `sed -i.bak` and omits `--in-place`.

#### 39. `post_tool_hook` records nothing, silently, on a non-zero eval exit · Tier D

`post_tool_hook.py:139-148`: on `returncode != 0` it falls through with
`eval_data = {}` — no `auto_records`, no `exit_enforcement_error`, no telemetry —
so a config/version fault stops `file_read`/`source_edit`/`file_search` being
recorded, and every predicate counting `source_edit` (the edit-accumulation
block, the stall monitor) reads zero forever. `pre_tool_hook.py:158-169` handles
the same case correctly; the two disagree. Secondary: a JSON **list** from
`result.stdout` makes `data.get` raise `AttributeError`, outside the except
tuple → uncaught traceback out of a PostToolUse hook.

#### 40. `NotebookEdit` is an ungated source-edit path three files disagree about · Tier C

`pre_tool_hook.py:99` believes it handles `NotebookEdit`, but `hooks/hooks.json`
registers `pre_tool_hook.py` under matcher `"Write|Edit"` only, while
`enforcement/hooks.toml`'s auto-record rule includes `NotebookEdit` and its TDD
gate does not. So a `NotebookEdit` records a `source_edit` (counting toward the
accumulation and stall gates) while being exempt from the TDD gate and the
managed-path guard, and `pre_tool_hook`'s branch for it is dead code. Zero
notebooks in this repo; the exposure is downstream-consumer.

#### 41. The boundary block precedes the freshness check, so an abandoned audit wedges the repo · Tier C

`pre_tool_hook.py:102-111` / `commit_gate.py:59-76` fire `exit_boundary_missing`
before `is_enforcement_fresh` — and the 30-minute freshness window is the only
thing that releases an abandoned audit. The daemon is `nohup`'d and torn down
only on `finalized`/`idle`. So a session killed mid-`fix_loop` with a surviving
daemon means every Bash/Write/Edit in every session in that repo (and every
linked worktree, since the socket is anchored) denies with "type `holtz-start`",
including sessions doing no audit. `holtz-stop` is a real escape, so this is a
wedge, not a deadlock — but the docstring's "cannot fire in a project that is
not being audited" is true only of a project that never had a daemon.

#### 42. Per-actor cache state is read-modify-written over the whole map · Tier B

`protocol_tracker.py` both writers send the entire actor map computed from a
snapshot read up to ~10 s earlier (`update_cache` with `stall_bumped`, and
`_apply_sahjhan_cmd`'s full `write_cache` after two 5 s subprocesses). The
daemon does a shallow top-level merge, so a sibling's bump/clear/commit landing
in that window is overwritten — the actor-keying the delta added is not
atomic. The docstrings claim "every other actor untouched," true of the returned
value and false of the write. No compare-and-swap and no concurrency test exist.

#### 43. The pending-commit block names an escape the blocked subagent cannot run · Tier B

`commit_gate.py:78-89`: the comment justifying actor-scoping ends "the escape
named below is the orchestrator's transition, which a subagent cannot run," and
the `exit_block` immediately below prints exactly that escape. Verified: a
subagent's second commit (the item-23 rework path) lands here with an
unreachable escape. D41 actor-scoped the block and left the escape orchestrator-only;
today it only clears as a side effect of someone else's merge (item 32).

#### 44. `DEFERRED.md` shows a deferred-then-fixed finding as still deferred; `STATUS.md` goes stale · Tier D

`deferred.md.tera:27-40` never computes a `resolved_ids` set (the other three
templates do and give it precedence), so a finding deferred then fixed anyway —
a legal path, `fix_commit` carries no `item_open` gate — is listed as deferred
forever; `renders.toml:25` compounds it by omitting `finding_resolved` from the
render trigger. Separately, `STATUS.md` renders `on_transition` while the
punchlist family renders `on_event`, so its Open/Resolved counts freeze between
transitions — the "two views, different answers" class at the render-timing
layer. Both are agent/human-read only; nothing gates on their content.

#### 45. `migrate_legacy.py`: schema-violating fields, no `--all` ledger boundary, duplicate project rows · Tier D

Every migrated `finding`/`finding_resolved` sets `step=""` and often
`commit_hash=""`, both failing their `events.toml` patterns — harmless because
`sahjhan ledger import` is schema-lax (verified via a passing import test), but
born non-compliant and untouched by the `5679f5c` reachability pass.
`--all` prints all runs' events with reused `BH-NNN` ids and no ledger boundary,
and its own usage line invites a single combined import that would collide
identically-numbered findings under D25's by-id latest-wins. `build_project_ledger`
re-run accumulates duplicate `run_registered`/`run_completed` rows. All
historical-tooling paths; none is gate-consumed.

#### 46. The sahjhan pin has no binary/version cross-check and no runtime re-hash · Tier D

The three pins are currently coherent (verified: `bin/.sahjhan-version`,
`_resolve.SAHJHAN_VERSION` and `bin/sahjhan --version` all `0.23.0`, all four
`SAHJHAN_CHECKSUMS` recomputed and matched). But `update_sahjhan_pin.py:39-47`
hashes whatever bytes sit in `bin_dir` without checking they belong to the
version being pinned, and `_resolve.ensure_sahjhan`'s fast path returns a binary
on a version-marker string match with no checksum re-verification (that happens
only on a fresh download). `check_sahjhan_pin.py` — which would catch a mismatch
— is wired only into `pre-release-check.sh`, not the git hooks, so a
partially-failed vendor run leaves an unverified binary trusted until the next
release. See [[sahjhan-version-pinned-in-three-places]].

#### 47. `_sahjhan_bootstrap.py` calls a gated daemon op but is absent from the trusted-callers manifest · Tier C

`_sahjhan_bootstrap.py` is a `hooks.json` PreToolUse entrypoint that calls
`read_cache` → `_daemon_request({"op": "enforcement_read"})` (a SO_PEERCRED-gated
op), added by `68ffd91` three months after the manifest's last completeness pass
(`5a39a90`) and never added to `TRUSTED_SCRIPTS`. Of its two uses of the result,
one fails closed (`_daemon_stop_permitted`) and one fails **open**
(`_bash_source_write_tdd_block:1059` returns `None` on `is_enforcement_fresh(None)`,
skipping the TDD gate for Bash-based source writes). The pre-commit auto-regen
fired on that commit but structurally cannot add a file not already in its own
list ([[trusted-callers-manifest-regen]]). The runtime consequence is INFERRED
(the one real-daemon test that touches `enforcement_read` fails auth for
environmental reasons, so it cannot isolate the manifest gap); the structural gap
is VERIFIED. **Fix:** add the path to `TRUSTED_SCRIPTS`, regenerate, and add a
`real_daemon` `hook_e2e` test that drives a Bash source-write with no failing
test recorded and asserts it is blocked.

#### 48. The delta's new enforcement predicates ship with no direct unit tests · Tier D

No test imports `is_read_only_cmd`, `_tdd_gate_exempt`, `project_anchor`,
`stall_bumped`/`stall_cleared`, `pending_commits_for`, `exit_boundary_missing`
or `query_named_predicate`. `is_read_only_cmd` is the notable one: a new
~40-line classifier with two hand-kept frozensets deciding whether a Bash line
escapes the stall counter, covered only by the parametrized subprocess cases in
`test_hook_chains.py` — which is where item 38 slipped through.

#### 49. Lower tail (bundle) · Tier D

Real, low blast radius, grouped so none is lost:
- `_common.py:271-273` — `boundary_dir`'s "fails closed" comment is inverted for
  consumer hooks: an unresolvable `~` yields a relative socket path →
  `connect` raises → `exit_ok` (fail open).
- `protocol_tracker.py:198-199,234-235` — a transient `enforcement_read` failure
  followed by a successful write constructs and persists an `empty_cache()`,
  erasing every pending commit and stall count.
- `_protocol_cache.py:565-575` — a mid-flight upgrade maps a pre-delta scalar
  stall onto `{ORCHESTRATOR: N}`, charging the orchestrator the whole run's
  stall (the audited run drove one number to 16 across 54 actors).
- `post_tool_hook.py:132-133` — never passes `--agent-id`, so every PostToolUse
  gate/monitor is structurally run-global (item-1/19 family); dormant only
  because no PostToolUse rule templates `{{agent_id}}` today.
- `commit_gate.py:109-121` — `blocks_all` is `any(...)` but the message is always
  `obligations[0]`, so a stall block can print the pending-commit remedy.
- `commit_gate.py:66` — the comment names `holtz-stop` (tears the boundary down)
  as the escape from a boundary-missing block whose message correctly says
  `holtz-start`.
- `bash_guard.py:99-122` — records `protocol_violation` under
  `contextlib.suppress` with no `returncode` check, then asserts "permanent";
  and hardcodes `auditor=holtz` three lines under a "derived, never mirrored"
  comment (harmless to the gate, wrong in the record).
- `_shell_norm.py:32-35` — `resolve_indirection` treats `--field k=v` as a shell
  assignment and rewrites `$k` inside quoted data, so downstream guards reason
  about a command string that was never typed (latent; no decision flip found).

---

## Third pass, 2026-08-27 — the scope the second pass declared unaudited

The second pass ended by naming what it had not read: `merge_punchlists.py`,
`stale_sweep.py`, `sandbox_control.py`, `boundary_check.py`, `findings.py`.
This pass read those, plus `pattern_round.py`, `hardening_batch_courier.py`,
`stale_sweep_courier.py` and `validate_punchlist.py`, and drove the results
against a real daemon.

**It found a P0 that outranks item 18, and the reason it outranks it is that no
agent has to want anything.** Item 18 needs a motivated agent to type a word.
Item 25 fires on the scripted, mandatory merge step, and it converts *Justine
raising the severity of a Holtz finding* into *that finding being auto-deferred
and unfixable.* The adversarial frame the second pass adopted — "what can a
motivated agent do to this gate" — is a better sampler than the release-notes
frame, and it is still a sampler: it looks for an attacker and therefore does
not look at the path where the tooling does the damage unprompted.

Three checks generated everything new here, and none of them mention an agent:

1. **For every script that re-files a ledger row: does it read back every field
   it is about to overwrite?** (found item 25)
2. **For every field a config comment calls required: is it required by the
   thing that produces it?** (found item 26 — `reachability` is required by
   `events.toml` and not by `validate_punchlist.py`)
3. **For every `except` that classifies an error: is the call that raises it
   inside the `try`?** (found item 27)

Everything the second pass marked PROVEN was re-checked at its cited line and
holds. Items 2, 3, 5, 6, 7, 12, 13, 14, 15, 16, 19 and 1 were verified against
the tree at the line numbers given; all are accurate as written. Item 20's
premise was driven against a real daemon and is confirmed — see the note under
item 20 below. Nothing from either earlier pass is retracted.

---

## Added 2026-08-27 — the third pass

### 25. The merge destroys the reachability grading of every finding Justine escalates · PROVEN · P0

`merge_punchlists.py:336-339`. `_HOLTZ_SQL` reads Holtz's board with:

```sql
SELECT id, severity, category, location, perspective, description, seq
FROM events WHERE type='finding' ORDER BY seq
```

`reachability` is not in that list. `pattern_id` and `predicted_by` are not
either. So `holtz_findings()` builds every `Finding` with the dataclass
default — `DEFAULT_REACHABILITY = "theoretical"` (line 66) — and
`apply_merge()` re-files the escalated finding with
`reachability=holtz_finding.reachability`, which is that default and never the
grading the run actually recorded.

The re-file happens **only on escalation**: `apply_merge` skips unless
Justine's severity outranks Holtz's. So the code path that exists to say *this
is worse than you thought* is the one path that destroys the finding.

Driven against a real daemon — Holtz files BH-001 `HIGH / user_reachable`,
Justine's punchlist grades the same location `CRITICAL`, then the merge runs
and its own PostToolUse courier fires on the merge command:

```
BEFORE   BH-001  HIGH      user_reachable
merged:  0 agreement… 1 severity disagreement(s)
AFTER    seq 1  BH-001  HIGH      user_reachable
         seq 2  BH-001  CRITICAL  theoretical      <-- the re-file
open_theoretical_findings        -> BH-001
all_critical_resolved (before)   -> false
theoretical_courier              -> exit 0
finding_deferred                 -> BH-001, reason=theoretical
all_critical_resolved (after)    -> true
```

Four things follow, and the chain is what makes it a P0 rather than a data-loss
annoyance:

- **D25 grades by latest filing.** The board now says BH-001 is `theoretical`.
- **`theoretical_courier.files_a_finding` matches `merge_punchlists.py` by
  name** (`_MERGE_SCRIPT`, line 54) — deliberately, so the merge's inner
  subprocess filings get swept. The escalated finding is swept with them, in
  the same Bash call.
- **`all_critical_resolved` reads `true`.** This is a **fourth** route to
  closing a CRITICAL with no fix, and the only one that needs no agent
  intention at all. Item 9's table should read four rows, not three.
- **`fix_commit` can no longer touch it.** `item_is_user_reachable` refuses a
  `theoretical` finding, so even an agent who notices cannot fix it under the
  protocol. Its only remaining route is re-filing it as a new id — which
  `punchlist-format.md:55` teaches for a *probe result*, not for a merge
  artifact, and which loses the escalation.

Two more fields go the same way and are worth fixing in the same edit:

- **`pattern_id`** is dropped, so an escalated sibling leaves its round's
  population — the `strpos(','||p.pattern_ids||',', …)` join in item 21 no
  longer matches it. The merge silently discharges round-cap pressure.
- **`predicted_by`** is hard-coded to `"none"` in `_record` (line 401), so an
  escalated finding loses its prediction link, which `SUMMARY.md`'s Prediction
  Accuracy table is computed from.

**The guard test asserts the one field that changed and none of the fields that
must not.** `test_a_higher_justine_severity_refiles_holtz_id`
(`tests/test_merge_punchlists.py:538`) files at `reachability=user_reachable`
via `_Board.file`, runs the merge, and asserts `len(filings) == 2` and
`severity == "HIGH"`. It never reads `reachability` off the second filing. This
is `mutation-proof-the-negatives-too` exactly: the test checks what the code
sets and is blind to what the code clobbers.

**Fix:** read the whole row. Add `reachability`, `pattern_id` and
`predicted_by` to `_HOLTZ_SQL`, carry them onto `Finding`, and have `_record`
pass them through rather than defaulting. `DEFAULT_REACHABILITY` should apply
only where a grading was genuinely never stated — Justine's punchlist — and
never to a Holtz row that has one on the ledger. Then assert, in the guard
test, that a re-file changes `severity` and **nothing else**.

### 26. Nothing requires Justine to grade reachability, so her whole board can arrive `theoretical` and auto-defer · PROVEN · P1

Item 25's second half, on the other side of the merge. `justine_findings()`
takes `item.reachability or DEFAULT_REACHABILITY`, so an ungraded item becomes
`theoretical` and is auto-deferred the moment it lands.

The field is required in exactly one place and not in the two that produce it:

| Where | Requires `reachability`? |
|---|---|
| `events.toml` `[events.finding]` | **yes**, and the comment argues it at length: *"Required, not optional: a grading nobody has to state is a grading the board will not carry"* |
| `punchlist-format.md` item template | present in the template; the prose says "Assess for every finding" |
| `validate_punchlist.py` | **no** — it errors on severity, category, status, Problem, Discovery Chain, acceptance criteria and validation command, and never mentions reachability |
| `justine-skill.md` | **no** — the word does not appear in the file at all |

Driven against a real daemon: a Justine-only CRITICAL with no `**Reachability:**`
line lands as `reachability=theoretical, perspective=unspecified` and is swept
by the courier on the same command. The shipped fixture reproduces it —
`_JUSTINE`'s BJ-002 carries no reachability, and
`test_an_unstated_reachability_is_theoretical` asserts the default as correct
while `test_a_justine_only_finding_lands_on_the_ledger_under_her_id` checks
only that the id is present.

The default is defensible in isolation — an unstated grading *is* unestablished
— but it stops being a grading and becomes an eraser once D29 auto-defers on
it. Two ends to close, and both are cheap:

- `validate_punchlist.py` should error on a missing `**Reachability:**`, which
  makes the merge's default unreachable in practice and matches `events.toml`'s
  own claim about the field.
- `justine-skill.md` should say the word once, next to its severity-calibration
  override — it is the file that tells her how to grade, and it is silent on
  the grading that decides whether anything gets fixed.

This is the same shape as **P1-8** (`SKILL.md`'s deferral rules predate P0.5)
and belongs in that commit.

### 27. `boundary_check.py` crashes on the one platform path its own docstring calls confinement · P1

`skills/holtz/scripts/boundary_check.py:45`. The socket is constructed
**before** the `try`:

```python
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(5)
try:
    sock.connect(sock_path)
except PermissionError:
    # …Linux's seccomp filter blocks socket(AF_UNIX) outright…
    return CONFINED
```

The comment names two mechanisms. macOS Seatbelt answers EPERM on `connect()`,
which the `try` catches. Linux's seccomp filter blocks `socket(AF_UNIX)`
*outright* — which raises on line 45, outside the `try`, and propagates out of
`probe()` and out of `main()` as an uncaught traceback.

Observed, simulating the seccomp shape:

```
socket.socket -> PermissionError(1, 'Operation not permitted')
probe()       -> RAISED: PermissionError [Errno 1] Operation not permitted
```

So on a correctly confined Linux session — the configuration `holtz-start`'s
own receipt tells the user to set up (*"On Linux the socket block additionally
needs the optional @anthropic-ai/sandbox-runtime seccomp filter"*) — recon Step
0 dies with a traceback. `SKILL.md:282` reads that as "it did not print
`BOUNDARY: confined`" and instructs the agent to *"stop and ask the user to
type `holtz-start`"*, which will not help, because the boundary is already up.
The strongest confinement produces the same instruction as no daemon at all.

**`test_boundary_check.py:119` patches `socket.socket.connect` only**, so the
suite exercises the macOS path and cannot see this.

**Fix:** move the constructor inside the `try` (or wrap it), and add the second
test — patch `socket.socket` itself to raise `PermissionError` and assert
`probe()` returns `CONFINED`. One line of code, one test, and it is the
difference between "confined" and "traceback" on Linux.

### 28. A courier's recognizer is narrower than its script's CLI, and the gap is silent · P2

`stale_sweep.py`'s parser accepts `--record` with `--present` and/or
`--retired` (`main`, line 276). `stale_sweep.verdicts_of` — the recognizer the
courier imports — returns `None` unless `--present` is present (line 205).

So `stale_sweep.py --record --retired BH-001,BH-002`, on a sweep that retired
everything, passes `check()`, prints `STALE-SWEEP:` and exits 0 — and
`stale_sweep_courier.main` reaches `if verdicts is None: exit_ok()` and records
**nothing, with no warning**. Every other failure on that path warns
(`exit_warn` at the missing-marker, non-repo, and coverage branches, all citing
"the round is still owed and iteration_boundary will block"); this one, which
produces the same outcome, is silent. `pattern_round.py --record
--siblings-found N --cwd X` has the identical shape — the script accepts
`--cwd`, `siblings_of` rejects any flag it does not know, and
`pattern_courier` exits ok.

The taught commands in `phase-fix-loop.md:152,176` both carry the required
flags, so this is not a live break — it is the failure mode with no telemetry
that item 17 and the spec's unstarted P5.2 are both about, in a third hook.

**Fix:** make the script's own argument parser refuse exactly what the courier
refuses (require `--present` with `--record`; drop `--cwd` from the recorded
form or teach the recognizer to accept it), so the two ends cannot disagree —
the same "one recognizer, imported not restated" discipline both files already
claim in their comments, extended to the parser.

### Item 20, confirmed against a real daemon

The second pass asserted that `unspecified` is not a member of
`[sets.perspective]`. Verified two ways, because the finding depends on the
daemon *accepting* the value rather than rejecting it:

- `[sets.perspective]` holds 13 values; `unspecified` is not among them.
- `sahjhan event finding --field perspective=unspecified` **exits 0**. A
  Justine-only finding landed on a real ledger carrying it.

So the set is decorative for this field — declaring a set does not validate
events written against it. That makes item 20 strictly worse than stated: it is
not only that no lens gate will name `unspecified`, it is that nothing
anywhere refuses it. Any misspelled perspective has the same effect, and
`merge_punchlists.py` writes one on every Justine finding by default.

---

## Second pass, 2026-08-27 — what the first pass got wrong

The first pass ranked findings by *how many user-facing claims they falsify*
and said so in `2026-08-26-release-notes-as-a-review-instrument.md`, including
the admission that the frame "is a good sort key for deliverability and a bad
one for integrity." It then shipped the punchlist sorted that way anyway. The
release-notes exercise was asked for as a **completeness check across
components**, not as a priority function.

This pass re-ran the adversarial question directly — *what can a motivated
agent do to this gate, and what breaks between two files that each look
correct alone?* — and drove every claim against a real daemon. It changed the
list in five ways:

1. **Two new P0s** (items 18 and 19), both proven, both invisible to the
   release-notes frame because neither has a user-facing sentence. Item 19 is
   a second, independent break in the *same* feature as P0-1, and it fires
   before any `fix_commit`.
2. **Item 2 was right but understated.** The threshold is exact, it is
   vacuous at N=1, and it must be spent *before* the MEDIUMs are fixed. Now
   stated as measured.
3. **Item 9's framing was wrong**, though the finding is real. It is not "a
   second way to close a CRITICAL without a fix" — there are already two
   easier ones, one of them a taught alias. Corrected in place.
4. **The `unspecified` perspective problem was buried** in the lens-gate
   ruling as an "open question." It is a punchlist item; it is now item 20.
5. **The order changed.** Forgeries first, then the feature that does not
   work, then the doc sweep.

Nothing from the first pass was deleted. Items 1, 3–8, 10–17 were re-checked
and every one of them holds; the P2 hygiene claims (12–16) were verified
line-by-line and are accurate as written.

---

## P0 — a real run hits these

### 18. Any CRITICAL can be closed with one command, and the config argues it cannot · PROVEN

`protocol.toml:410-425` justifies the one exclusion in `all_critical_resolved`
like this:

> `theoretical` is written by `theoretical_courier.py`, **not chosen by the
> agent** … Every other reason word still refuses. `low_priority`,
> `medium_budget` and `cant_reproduce` are discretionary acts, and refusing
> them is what this conjunct is for.

`finding_deferred` is `attestation = "agent"`, carries no `restricted = true`,
declares `agent:cli` as a producer, and its `reason` pattern admits
`^(cant_reproduce|low_priority|medium_budget|theoretical)$`. `event` is on the
bootstrap allowlist and `finding_deferred` is not in `BLOCKED_SAHJHAN_SUBSUB`.

Driven against a real daemon:

```
event finding … id=BH-001 severity=CRITICAL reachability=user_reachable
  all_critical_resolved -> false
event finding_deferred … id=BH-001 reason=theoretical      exit 0
  all_critical_resolved -> true
```

A CRITICAL the run **filed as `user_reachable`** — its own statement that the
defect is reachable — is closed by one agent-typed word, with no fix, no
re-grade, and no courier involved. The gate the protocol treats as
non-negotiable is opened by the cheapest command in the file.

Two separate defects sit on top of each other and each is worth fixing:

- **No provenance.** The word `theoretical` is treated as machine-written and
  is not. This is `enforcement-event-provenance` (#79) exactly: the gate
  filters on a field the agent controls. The remedy that memory names is to
  record from a signal that entails the fact — either `restricted = true` on
  the courier's path with a separate agent-writable spelling, or a
  provenance field on `finding_deferred` that only `record_authed_event` can
  set, with the conjunct filtering on *that*.
- **No correlation.** Even with honest provenance, the exclusion never checks
  that the finding it is excusing is actually graded `theoretical`. Add the
  latest-filing correlation the other conjuncts already carry:
  `AND EXISTS (… f2.type='finding' AND f2.id=d.id AND f2.reachability='theoretical'
  AND f2.seq = MAX(seq for that id))`. A `user_reachable` CRITICAL carrying a
  `theoretical` deferral is an internally contradictory board row and nothing
  today notices.

**The guard test demonstrates the hole and calls it correct.**
`test_fix_loop_eligibility.py:190` (`test_a_theoretical_critical_converges_on_its_deferral`)
and `test_theoretical_defer.py:272` both close the CRITICAL through
`_Board.defer`, which is literally
`sahjhan event finding_deferred --field reason=theoretical` — the forged path.
Their docstrings say "machine-written" while their bodies type it by hand.
`test_an_ordinary_deferral_still_does_not_converge` is the counterweight and
it only proves the *other three* words refuse; nothing asks whether the fourth
one is reachable by the agent.

`enforcement_lint.py` has no check for this shape. H5 asks "does an event
claiming above-`agent` attestation have an agent-writable path" — this event
claims `agent`, so H5 is silent. See item 22.

### 19. The TDD courier pairs the wrong actor's failing test, and starves the second one · PROVEN

`tdd_courier.py:61-66`. The courier finds the row to attribute with a
**run-global watermark**:

```sql
SELECT finding_id, test_name, run, auditor, project FROM events
WHERE type='test_failed_before_fix'
  AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='tdd_evidence'), 0)
ORDER BY seq DESC LIMIT 1
```

It never matches the row *this* Bash line wrote. It takes the newest unpaired
row on the whole ledger and stamps the caller's `agent_id` onto it. With more
than one actor in flight — which is the entire point of P0.3 —
`phase-fix-loop.md:43` dispatches **three**.

Observed against a real daemon, both `test_failed_before_fix` rows landing
before either courier fires (two concurrent Bash calls):

```
agent-A records BH-001 / test_A     seq 100
agent-B records BH-002 / test_B     seq 101

courier(agent-A) -> tdd_evidence { agent_id: agent-A, finding_id: BH-002,
                                   test_name: test_B }
courier(agent-B) -> warn: "the ledger holds no new test_failed_before_fix"

tdd_evidence where agent_id='agent-A'  -> 1
tdd_evidence where agent_id='agent-B'  -> 0
```

Three consequences, in order of severity:

1. **It is a TDD-gate bypass.** A's evidence row is for a test A never wrote.
   The `hooks.toml` gate filters on `agent_id` and nothing else, so A may now
   edit source having recorded nothing. Any actor can ride any other actor's
   unpaired failing test. In a 3-wide loop this is not an edge case, it is the
   normal interleaving.
2. **The second actor is starved.** B gets no evidence row and a warning that
   does not say why. Its next source edit is denied. Its retry works — the
   next unpaired row is its own — but the message tells it to "record the
   failing test again" without explaining that its first one was consumed by
   someone else.
3. **`LIMIT 1` loses rows permanently.** Two unpaired rows, one courier
   firing: the watermark jumps past both, so the older row is never paired by
   anyone.

This is independent of item 1. Item 1 is the gate's *window*; this is the
evidence row's *identity*. Fixing item 1 alone leaves this intact, and this
one fires earlier — before any `fix_commit` exists to revoke anything.

**Fix:** pair by the row, not by a global watermark. The command text carries
`--field finding_id=…`; the courier already refuses anything but a single
canonical segment, so parse the id and select
`WHERE type='test_failed_before_fix' AND finding_id=<id> AND seq >
COALESCE((SELECT MAX(seq) FROM events WHERE type='tdd_evidence' AND
finding_id=<id>), 0)`. Keep reading the remaining fields off the row so the
courier still invents nothing.

**The test file cannot see this.** Every assertion in `test_tdd_courier.py`
about `_UNPAIRED` is a string match on the SQL —
`test_it_takes_the_newest_unpaired_row` asserts the defect as intended
behaviour. No test drives two actors. Add one that does: two failing tests
recorded before either courier runs, then assert each actor holds evidence
naming its *own* finding. That is the `mutation-proof-the-negatives-too` and
`test-the-taught-sequence-not-just-the-gate` pair in one place.

### 1. A sibling's `fix_commit` revokes a still-working actor's TDD evidence · PROVEN

`enforcement/hooks.toml:32-36`. D33 scoped the gate's **filter** to
`agent_id`, but left the **window** at `since = "last_transition"`, which is
run-global. The orchestrator records a `fix_commit` every time any subagent
finishes, so every *other* in-flight subagent loses its own authorisation.

Observed against a real daemon: agent-B records its own failing test → `allow`;
an unrelated `fix_commit` state_transition is recorded → the same agent-B edit
returns **`deny`**, with the TDD-violation message, having committed nothing.

This is the same run-global-coupling defect **D41** fixed for the
pending-commit block (`_protocol_cache.pending_commits_for`), found in one gate
and not the other. P0.3's whole purpose — 3 subagents in flight — does not
work as designed; the second and third agents are blocked mid-fix on a
condition no skill file describes and whose escape (re-record a failing test)
is not reachable once their fix is already written.

**Fix:** scope the window to the actor, not the run — the evidence must be
newer than *this actor's* last `fix_commit`, not the run's. Add the missing
`hook_e2e` test: "an actor holding its own evidence survives a sibling's
transition."

### 2. Fixing more than half your MEDIUMs strands `converge` forever · PROVEN

`protocol.toml:259` + `transitions.toml:553`. `converge` requires
`medium_deferral_budget expect="false"` — the budget **spent**. The denominator
counts every MEDIUM ever filed, open or closed; `defer_medium` requires
`item_open`.

Observed: 4 MEDIUMs filed, 3 resolved (the virtuous outcome), the 4th deferred.
`medium_deferral_budget` reads `true` — unspent. `defer_medium` on a resolved
MEDIUM exits 1. No MEDIUM remains that can be deferred. `converge` is shut, and
`sweep_dirty` leads nowhere, because nothing in `fix_loop` can spend the budget
either. The only exit is filing new MEDIUM findings in order to defer them.

This is exactly the shape the project's own rule forbids — *a block's escape
must be guaranteed by construction* — arriving at the end of the run, which is
where #77 arrived.

**Measured, 2026-08-27** — the arithmetic is sharper than the first pass said,
and three properties of it are worth naming because each changes the fix:

- **The requirement is exact, not a floor.** `defer_medium`'s gate is
  `deferred < N/2` and `converge`'s is `deferred >= N/2`, over the same
  integer division. So converging requires **exactly `floor(N/2)` MEDIUM
  deferrals**, where N is every MEDIUM ever filed by latest grading, open or
  closed. Not "at most half" — *precisely* half, rounded down.
- **It is vacuous at N=1 and binding from N=2.** Driven against a real daemon:
  N=1 reads `false` (spent, converge passes, because `1/2 = 0`); N=2 through
  N=6 with zero deferrals all read `true` (blocked). A run with one MEDIUM
  never notices the gate exists; a run with two is under it immediately.
- **The budget must be spent *before* the MEDIUMs are fixed.** `defer_medium`
  requires `item_open`, and every fix removes a candidate. Observed at N=6:
  5 resolved, 1 deferred, `open_medium_findings` = `[]`, budget still `true`.
  The run has to decide to defer half its MEDIUMs at the point where it is
  least able to judge which half deserve it — and no skill file says so.

One more consequence nobody has written down: because the denominator is every
MEDIUM ever filed, **a MEDIUM filed after the budget was spent can re-block a
converge that was already open.** N=6 with 3 deferred is spent; file a 7th and
8th MEDIUM and it is unspent again, needing a fourth deferral from whatever is
still open. A late-breaking finding can therefore shut convergence in a way the
run cannot always answer.

**Fix:** the conjunct should assert the budget is *not under-spent relative to
what is still open*, or the denominator should count only findings that were
ever deferrable. Add the reachability test: "a run that fixes every MEDIUM can
still converge," plus the N=1 and post-spend-refile cases, so the whole domain
of N is covered rather than the one value that happened to be tried.

### 3. `all_findings_closed` still gates `set complete perspective` · PROVEN

`transitions.toml:472`. P0.1 removed `all_findings_closed == 0` from `converge`
because it was unreachable and would make the four conjuncts decoration —
`test_all_findings_closed_no_longer_gates_converge` asserts that. The identical
named query still sits on `set complete perspective`, which must pass **13
times** before `converge` is ever evaluated (`converge` gate 1 is
`set_covered perspective`).

So the unreachable requirement was not removed; it was moved one door upstream
and multiplied by thirteen. The four conjuncts are decoration in practice.

Second consequence, also observed: `all_findings_closed` carries no
reachability filter, so **one open `fault_injected` HIGH reads `1` and blocks
the lens**. That finding cannot be `fix_commit`'d (`item_is_user_reachable`
refuses it), and the hardening batch is taught only at Step 15 — after all 13
lenses. `TestEveryCriticalHasARoute` enumerates routes for `all_critical_resolved`
only; it never asks the same question of this gate.

Third: the gate has **no `intent` string at all**, so the block prints no
escape.

**RULED (Jon, 2026-08-26): a clean lens is not an empty board.** Clearing the
board is what made convergence take weeks — it is the disease, not the cure.
`set complete perspective` takes a balanced middle path, not `all_findings_closed`.

**Fix:** replace the conjunct with a lens-scoped package (exact predicate to be
confirmed — see the open question at the end of this file), give it an intent
that names a command, and extend `TestEveryCriticalHasARoute` to this
transition. The property to preserve: no grade of finding may be un-closable at
a gate the run must pass thirteen times.

### 4. The fix-subagent contract contradicts itself across three files

`phase-fix-loop.md` was rewritten for P0.3. `SKILL.md:233` and
`step-10-fix-loop.md:5` were not. They now say, of the same subagent:

| Claim | `SKILL.md` / `step-10` | `phase-fix-loop.md` (shipped) |
|---|---|---|
| Where it works | "in the enforced tree" | its own `isolation: "worktree"` |
| The TDD gate | "does not look at `agent_id`" / "agent-agnostic" | filters on `agent_id` |
| Committing | "**Never** let a fix subagent `git commit`" | step A.9: commit, then rebase |

`CLAUDE.md` rule 5 names this exact failure mode and cites `800624f`. The
guard that exists for it — `test_subagent_contract_consistency.py` — only
greps five retired phrases from the old incident, so it is blind to the new
drift and passes.

**Fix:** rewrite both files to the shipped contract, in one commit, and give
the consistency test a positive assertion (worktree, actor-scoped gate,
subagent commits) rather than a denylist of last year's wording.

---

## P1 — shipped, but the intent is not delivered

### 5. The amplification breaker sits on the path the skill file calls the exception

P0.1 is the spec's highest-value item ("the difference between terminating and
not"). Its block is on `pattern_done` (`transitions.toml:411`), reachable only
from `pattern_analysis`. But `phase-fix-loop.md:101` teaches:

> - **Stay in `fix_loop`** (usual). Do steps 1-5. Step 5 satisfies the
>   `iteration_boundary` gate.
> - **Enter `pattern_analysis`**, when `iteration_boundary` blocks you…

On the usual path `pattern_done` never runs, so the breaker never evaluates and
the mandatory batch deferral is never triggered — and per D3, `pattern_done`'s
escape is *the only place deferral is taught*. The round cap was given a second
seat on `iteration_boundary` for precisely this reason (see the D7 row); the
breaker was not.

**RULED (Jon, 2026-08-26): the breaker gets a second seat too.**

**Fix:** put the same `any_of` on `iteration_boundary`, referencing the same
named queries so the two seats cannot drift — the arrangement `round_item_cap_exceeded`
already has across `pattern_done` and `iteration_boundary`. Two things to get
right, both of which the round cap already had to solve:

- **The escape must be reachable from `fix_loop`.** `defer_low`/`defer_medium`
  are declared `fix_loop → fix_loop`, so `sahjhan defer batch` works there —
  this seat needs no new transition edges, unlike D2's `pattern_analysis` pair.
- **Deferral is taught in exactly one place today** (D3), and that place is the
  `pattern_done` block message. A second seat that prints the same escape means
  the escape now has two block sites; H8 checks that a block names the query
  its escape is gated on, so both must reference `medium_deferral_budget` and
  `open_low_count` by name.

Once it sits at the boundary the breaker fires on the path the docs actually
teach, which is what P0.1 was costed against.

### 6. The `DEFERRED.md` conjunct is satisfied by filing one finding

`renders.toml:21-26` renders `DEFERRED.md` on `finding` **and**
`finding_deferred`. So the file exists from the run's first finding, and
`test_it_is_written_once_the_run_has_findings` asserts that as correct. The
spec's conjunct meant "the batch deferral happened"; as shipped it is a
`file_exists` on a file the engine writes unconditionally.

**Fix:** either drop the render trigger to `finding_deferred` only, or replace
the conjunct with a ledger predicate over deferrals.

### 7. `phase-convergence.md` still tells the agent converge requires "zero open items"

Line 16, verbatim: *"Sahjhan checks all gates: all perspectives complete, suite
passes, linters pass, **zero open items**, no protocol violations."* That is
the gate P0.1 replaced. An agent following this doc will drive toward the
non-terminating behaviour the release exists to end.

### 8. `SKILL.md`'s deferral rules predate P0.5

`SKILL.md:37`: *"CRITICAL/HIGH must be fixed; LOW, budget-capped MEDIUM, and
can't-reproduce may be deferred."* No mention that only `user_reachable` is
fix-loop eligible, that `fault_injected` batches at Step 15, or that
`theoretical` auto-defers. `reachability` appears once in the whole file, as a
field in an example.

---

## P2 — correctness and hygiene

9. **`merge_finding` has no relatedness or severity constraint.** PROVEN:
   `merge_target_exists` for `BH-010` (CRITICAL) into `BH-011` (an unrelated
   LOW) reads `true` — the predicate requires only that the target is a filed
   finding and not the item itself. The merge emits `finding_resolved`, so it
   clears `all_critical_resolved`, and it lets a round discharge
   `round_opens_exceed_closes` by merging away every sibling it just found.

   **Framing corrected 2026-08-27.** The first pass called this "a second way
   to close a CRITICAL without a fix, next to the one the gate's intent says
   is the only one." That baseline is wrong, and the error matters because it
   over-rates this item and under-rates two others. Measured against a real
   daemon, three commands close a CRITICAL with no fix:

   | Command | Blocked? | Status |
   |---|---|---|
   | `sahjhan event finding_resolved --field id=… --field commit_hash=…` | no | pre-existing, taught (`sahjhan resolve` is an alias in `protocol.toml:54`, and `iteration_boundary`'s own comment calls it "the standalone path SKILL.md teaches") |
   | `sahjhan event finding_deferred --field reason=theoretical` | no | **new in this delta, and argued to be impossible** — item 18 |
   | `sahjhan transition merge_finding <crit> <unrelated>` | no | this item |
   | `merge_punchlists.py` re-filing an escalated finding | no | **added by the third pass — item 25, and the only route that needs no agent intent at all** |

   `commit_hash` is pattern-checked but never resolved, so `0000000` is
   accepted. The generated contract already names the posture honestly — *"21
   of 32 gate-consumed events are the agent's own word"* — so row 1 is a
   deliberate, documented choice and not a defect. Row 2 is the defect,
   because it is the one the config explicitly claims is closed. This item is
   row 3: real, worth constraining, and **below item 18**, not above the P1s.

   *Why it was mis-ranked the first time:* it was sorted by "how many
   user-visible claims does it falsify", and nobody writes the release note
   *"you can now close a CRITICAL by merging it into a typo."* The frame had
   no slot for it. But the same blindness hid items 18 and 19 completely, and
   those are worse — which is the actual lesson, and it is stronger than the
   one recorded in `2026-08-26-release-notes-as-a-review-instrument.md`.

10. **The two converge conjuncts pull against each other.** PROVEN: 3 findings
    filed in-loop, 3 deferred, board empty → `amplification_diverging` still
    `true`, because deferrals are not counted on the resolved side. The breaker's
    prescribed escape (`defer batch`) therefore moves the `pattern_done` block
    and not the `converge` conjunct that reads the same predicate. Converge's
    amplification gate names no escape at all.

11. **Gates that print no escape:** `all_findings_closed` (no `intent`),
    `quiz_exhaustions_resolved` (no `intent`), `amplification_diverging` on
    `converge`. And `medium_deferral_budget`'s intent is self-contradictory:
    *"the MEDIUM deferral budget must be spent — half the MEDIUMs get fixed,
    not deferred."* The gate requires half **deferred**.

12. **README contradicts itself, including on a security claim.**
    - Line 204: "Twelve hooks backed by the Sahjhan enforcement engine";
      line 222: "20 enforcement hooks". (`hooks.json` registers 22 entries.)
    - Line 204 says session keys are "inaccessible to the model or any
      same-user process **without kernel-enforced socket credentials**".
      Line 212, added in this delta, says that is provably false and explains
      why. The refuted claim is still in the document, eight lines above its
      refutation.

13. **`docs/ARCHITECTURE.md:272`** still lists `PUNCHLIST-MERGED.md` in the
    file layout. P0.4 deleted the concept and `fix_loop_start` now refuses to
    start while the file exists.

14. **P1.6 residue.** `step-10-fix-loop.md:53` Fast Path still says "Minimal
    fix. **Full suite.** Commit." — a third mandated tail run, at the wrong
    scope, in the file whose Per-Fix Hardening #3 was edited to say "Do not run
    the suite here."

15. **`hypothesis` is undeclared.** `.github/workflows/ci.yml:21` pip-installs
    it; `pyproject.toml` has no `[project]` table at all. A fresh checkout's
    "fast subset" dies at collection, so local and CI do not run the same set —
    the exact divergence `git-hooks/pre-commit` exists to prevent.

16. **`CHANGELOG.md` `[Unreleased]` is empty** across 93 commits. Expected
    pre-release, but it is step 5 of the release checklist and nothing has been
    drafted.

17. **The primer fails open on timeout, and it makes the suite load-flaky.**
    Observed: one `python -m pytest -q` run under concurrent load → 2 failures,
    `TestPrimerWithMockBinary::test_injects_lens_priming_in_audit` and
    `::test_warns_when_context_reset_fails`, both `assert '<state>' in ''`.
    The class passes in isolation, and two subsequent sequential
    `pytest -q -p no:randomly` runs over the whole suite passed — the second
    observed at **exit 0**. So the tree is not broken; the gate is not reliably
    green under load.

    The mechanism is the part that matters: `primer.py:108-118`
    runs `sahjhan status` with `timeout=5` and, on `TimeoutExpired`, calls
    `exit_ok()` — which emits **no `additionalContext` at all**. The primer is
    the hook whose entire job is re-injecting state after a `/clear`, and the
    `awaiting_clear → resume` design depends on it. A slow `status` (big
    ledger, loaded machine, cold binary) silently degrades it to injecting
    nothing, and nothing reports that it happened. The timeout predates this
    delta and is not a regression from it.

    Worth weighing against P5.2 in the spec — *"hook denials leave no
    telemetry"* — which is the same defect class one hook over: enforcement
    that stops working without saying so. P5.2 is unstarted.

    **Fix:** distinguish "timed out" from "nothing to say" — inject a short
    degraded-mode notice on `TimeoutExpired` rather than exiting silent. That
    also removes the flake, because the assertion would then have something to
    match.

---

## Added 2026-08-27 — the integrity pass

### 20. Every merged finding belongs to no lens, and the lens gate is about to be scoped by lens · P1

`merge_punchlists.py:108,363` default `perspective` to `"unspecified"`, which
is not a member of `[sets.perspective]` (13 values, verified — the word appears
nowhere in `protocol.toml`). So every Justine finding the merge writes onto the
board carries a perspective no `set complete perspective` gate will ever name.

The first pass found this and left it inside the P0-3 ruling as an "open
question." It is not a footnote to that ruling — it is the reason the ruling
needs a decision before it is implemented. Under the ruled lens-scoped package,
a merged CRITICAL is caught **only** at `converge`, run-wide, at the end.
On the audited run that is a large slice of the board arriving as a surprise at
the last gate, which is the shape D34 cost a day to learn (*enumerate every
escape a gate rejects* — here, enumerate the whole domain of the keyed field
and name each value's route).

**Decide, then write it down:** either attribute merged findings to a real lens
during the merge, or accept `unspecified` as deliberately converge-only and say
so in `merge-protocol.md`. Either way `[sets.perspective]` and the merge's
default must agree, and a test should assert that every value the merge can
write is either a set member or explicitly routed.

### 21. The round cap's population is an optional field the agent types · P1

`round_item_cap_exceeded` and `round_opens_exceed_closes` both count only
findings joined to a round by
`strpos(','||p.pattern_ids||',', ','||f.pattern_id||',') > 0`. `pattern_id` is
`optional = true` on `finding`, attestation `agent`. A NULL on either side
yields NULL and the row drops out of the join.

So the cap is opt-in. A round that files ten siblings and tags none of them, or
tags them `PAT-99` when the brief declares `PAT-1`, is never over the cap — and
`test_round_item_cap.py:105,117` assert exactly that as correct behaviour
(`test_findings_with_no_pattern_id_are_not_the_rounds`,
`test_a_pattern_id_no_round_ever_wrote_does_not_count`). Both tests are right
about the *mechanism*; nothing asks what the mechanism costs.

`protocol.toml`'s D6 comment argues under-reporting is safe — *"the direction
that forfeits the relief this conjunct grants, not the direction that dodges a
block."* True for the backpressure conjunct, which grants relief. **False for
D7's cap and for the two-dry-rounds clause, where under-reporting is the
block-dodging direction**: not writing `## PAT-NNN:` headings into the brief
twice in a row withdraws the pattern-round obligation outright, and it costs
less than the merge the cap's own block message names.

This does not have a clean fix and should not get a hasty one — capping
untagged findings would charge a round for blast-radius and lens findings, which
is the thing the comment correctly refuses. What it needs is the claim in
`protocol.toml` narrowed to the conjunct it is true of, and a decision recorded
about whether an untagged sibling is a gap worth closing.

### 22. No check binds "a gate filters on this value" to "only a hook may write it" · P1

Item 18 is a specific bug; this is why it shipped. `enforcement_lint.py` runs
H1–H10 and none of them ask the question item 18 fails:

- **H5** asks whether an event claiming *above* `agent` attestation has an
  agent-writable path. `finding_deferred` claims `agent`, so H5 is satisfied.
- **H7/H8** govern predicate copies and escape identity, not who may write the
  values a predicate reads.
- **H10** binds a delegated gate's named `evidence` event to what the invoked
  tool queries — the right idea, one level up from the field.

The missing rule: **when a gate's SQL constrains a field to a literal value,
that value must be reachable only by a path the gate's own prose claims.**
Mechanically checkable — the config already names both halves. Every conjunct
that filters on `reason=`, `trigger=`, `scope=`, `provenance=` or similar is in
scope; `context_reset`'s `trigger='session_start'` is the pattern done right
(`restricted` + `host` + a hash-pinned writer) and is what the check should
hold the others to.

Without it, the class recurs. `#79` was this; item 18 is this; the next one
will be too.

### 23. Three-wide dispatch has no rework path when `--ff-only` refuses · P2

`phase-fix-loop.md:44` launches three subagents; each rebases onto the branch
as it stood when *it* finished (line 58-63) and the orchestrator merges
`--ff-only` one at a time (line 77). When A's merge lands after B has already
rebased, B's branch no longer fast-forwards. The doc says "A refusal means the
subagent's rebase is stale; send it back" and stops there.

What "send it back" has to include is not written: B must re-rebase **and**
re-run `verify_suite.py --record`, because line 67 already establishes that the
rebase moves the tree and therefore invalidates the recorded `suite_green`. A
subagent sent back that only rebases produces a fix the orchestrator's step 11
will reject for a reason that looks like the fix being unreal.

Also on that path: line 60 is `git add -A && git commit`. In a worktree that is
usually fine, but it is the idiom this repo has a standing rule against, and it
means whatever else the subagent left in its tree rides the fix commit.

### 24. A hardening batch's commit need not touch the module it closes · P2

`hardening_batch.check()` refuses four things — an unfiled module, a partial
module, a commit naming another module's findings, and a commit already spent
or empty. It does not require the diff to be *in* the named module. So one
non-empty commit anywhere closes an entire directory's open `fault_injected`
findings.

That is arguably within D35's intent (batch closure is the point, and the
message must name every id). It is listed because the docstring's own summary —
*"a diff that has not been used before is the work"* — claims more than the
check enforces, and because `no_open_fault_injected` gates `converge`. If the
looseness is deliberate, say so where the four refusals are enumerated.

---

## Release-notes exercise: where it stops making sense out loud

Written as user-facing notes, the delta wants to say:

> **Fix loop now runs three-wide.** Each fix subagent gets its own worktree;
> the TDD gate is scoped to the agent that recorded the failing test.

Can't ship that sentence, for two independent reasons: **P0-1** (the second and
third agents get denied the moment the first one commits) and **item 19** (the
courier stamps one agent's name on another agent's failing test, and the loser
gets no evidence row at all). The second one was invisible to this exercise —
see the correction below.

> **Convergence no longer requires an empty board.** It now means: every
> CRITICAL resolved, every user-reachable HIGH closed, amplification under
> control, deferrals written down.

Can't ship that sentence: **P0-3**. Thirteen lens completions upstream still
require an empty board. And **P0-2**: a run that fixes its MEDIUMs instead of
deferring them can't converge at all.

> **Runaway audits stop themselves.** When the loop files faster than it fixes
> for three rounds, it blocks and makes you batch-defer.

Can't ship that sentence: **P1-5**. Only on the path the docs call the
exception.

> **Findings are graded by reachability and routed by it.**

~~This one survives~~ — **retracted 2026-08-27 by the third pass.** The
mechanism does work in isolation: `fix_commit` really does refuse a
non-`user_reachable` finding, the hardening batch really does close a module in
one commit, and `theoretical` really does auto-defer. But the sentence claims
findings *are graded*, and **item 25** proves the merge regrades them wrongly
— every finding Justine escalates is silently re-graded `theoretical` and
auto-deferred — while **item 26** proves nothing on Justine's side has to grade
them at all. A routing rule is only as good as the grading it routes on, and
this delta ships two producers that write the grading without reading it.

That this was the *one* headline the exercise certified as clean is the sharpest
result of the three passes. It survived because both frames asked whether the
gate honours the grade, and neither asked whether the grade is what the run
recorded. **P0-3** and **P1-8** still apply on top.

> **`holtz-start` / `holtz-stop`.**

This one survives intact and is the best-told story in the delta. The README
section is honest about why peer authentication cannot work and what replaced
it. It just needs the contradicting paragraph above it deleted (**P2-12**).

The pattern this exercise found: **the engine half of this release is largely
built and the teaching half is largely not.** Four of the five items above break
on a skill file or a doc that still describes the pre-release protocol, and two
break on a gate whose escape was never enumerated.

**Correction, 2026-08-27.** The paragraph that followed used to end *"Nothing
here is a bad design decision; it is a systematic under-delivery of the second
half of each change."* That was the frame flattering itself. Items 18 and 19 are
not under-delivered teaching; they are a gate that does not hold and a courier
that attributes evidence to the wrong actor, both in code, both shipped with
tests that assert the defect. Neither has a user-facing sentence, so neither
appeared anywhere above — and the diagnosis "it's all in the docs" was reached
by looking only where the frame could see.

The honest second half of the pattern is: **where this release's config
*argues* for a property, check whether anything enforces it.** Items 18, 21 and
24 are all the same shape — a long, correct-sounding comment next to a
predicate that is weaker than the comment. That is the epistemic hazard the
companion note identified in the *status doc* and did not think to look for in
`protocol.toml`, which is where the reasoning is densest and least tested.

**Extended 2026-08-27 by the third pass.** The shape generalises past
predicates. `events.toml`'s `reachability` comment argues *"Required, not
optional: a grading nobody has to state is a grading the board will not carry"*
— and the field is required by the schema, not required by
`validate_punchlist.py`, not mentioned in `justine-skill.md`, and not read back
by `merge_punchlists.py`'s own SQL. The comment is true about the one file it
lives in and false about the pipeline. So the check is not "does the predicate
below match the comment above" but **"does every producer of this value honour
the claim, and does every consumer read it back?"** Items 25 and 26 are both
that question asked once. Item 27 is the same discipline applied to an
`except` clause: the comment names two mechanisms and the `try` covers one.

---

## The lens gate, as ruled

**RULED (Jon, 2026-08-26): option (a), the lens-scoped package.**

`set complete perspective` requires every CRITICAL and every `user_reachable`
HIGH **whose finding carries `perspective = {{current_perspective}}`** to be
resolved-or-deferred. Not the whole board; not the run-wide set.

Lens 3 blocks on its own open CRITICALs. It ignores lens 1's open MEDIUMs —
and lens 1's open CRITICALs, which `converge` catches run-wide. `converge`
stays the backstop it was redefined to be; the lens gate stops being a
thirteen-times-repeated version of the predicate P0.1 removed.

**Accepted cost, stated so it is not rediscovered as a bug:** a finding filed
under an already-completed lens is only caught at `converge`. That is the
deliberate trade — it is what stops lens 7 being answerable for lens 2's board,
which is the board-clearing behaviour this ruling exists to end.

Implementation notes:

- Two new named queries in `protocol.toml [queries]`, both parameterised on
  `{{current_perspective}}` — the same binding `set complete perspective`
  already uses for its `iteration_complete` and quiz gates, so the argument is
  in scope. Shape them on `all_critical_resolved` /
  `all_user_reachable_high_closed` with one added `f.perspective = '…'` term
  and the same max-seq correlation, so severity and reachability are still
  graded by latest filing (D25).
- **`perspective` is required on `event finding` — verified, not assumed.**
  `events.toml` marks optionality with `optional = true` and nothing else;
  fields are required by default, and `perspective` on `finding` carries no
  such marker. Driven against a real daemon: omitting a required field is
  `error: missing field '<name>' for event 'finding'`, exit 4. (I initially
  read the absence of any `required =` key as meaning nothing was required and
  was wrong; the check is what corrected it. The same check confirms the status
  doc's claim that `reachability` is required.)

- **But the domain of `perspective` is 13 lenses *plus* `unspecified`, and
  that is the part to design for.** `merge_punchlists.py:108,363` defaults it
  to `"unspecified"` — not a member of `[sets.perspective]`. So every finding
  the merge writes for Justine belongs to no lens, and under (a) **no
  `set complete perspective` gate will ever ask about it.** On the audited run
  that is a large slice of the board.

  This is not fatal to the ruling — `converge`'s run-wide conjuncts are the
  stated backstop and they do catch these. But it has to be written down,
  because "a CRITICAL no lens gate will ever mention" is exactly the shape that
  becomes a surprise at the end of a run. Two options, worth a decision:
  attribute merged findings to a real lens during the merge, or accept
  `unspecified` as deliberately converge-only and say so in
  `merge-protocol.md`. Either way it is the same enumerate-the-whole-domain
  discipline D34 cost a day to learn.

  **Promoted to item 20 on 2026-08-27** — it is a blocking decision for this
  ruling's implementation, not an open question beside it. Tracked there.
- H8 note: these are parameterised, so `_run_wide()` drops them from escape
  identity — same treatment `item_open` gets. The `intent` still has to name a
  command; it just is not judged against a named query.
- Delete `all_findings_closed` from this transition. It then has **no consumer
  in `transitions.toml`** — decide whether to keep the query declared for
  `findings.py` / render use or drop it, and let `enforcement_lint` H1 tell you
  which.

Two invariants, either way:
- the gate gets an `intent` naming a command (it has none today);
- `TestEveryCriticalHasARoute` extends to this transition, so no grade of
  finding is un-closable at a gate the run must pass thirteen times. Drive it
  against a real daemon for all three reachability grades, as the `converge`
  version does.

---

## Suggested order

**Superseded 2026-08-27 by "Tiers — consolidated priority (fourth pass)" at the
top of this file, which folds in items 29–49 and sorts every item at once. This
section is kept for the reasoning behind the 1–28 ordering; use the tier list for
what to fix.**

Revised 2026-08-27 (third pass). Sorted by *what a run hits without anyone
trying* first, then by *what a motivated agent can do*, then by what a release
note would say. The first pass used only the third key and buried 18 and 19;
the second pass used the second key and did not look where the tooling breaks
things unprompted, which is where 25 lives.

1. **Item 25** — the merge's partial re-file. It needs no motivated agent, it
   fires on a mandatory step, and its effect is to auto-defer and permanently
   un-fix the findings Justine flagged as *worse* than Holtz did. Read the
   whole row; then make the guard test assert that a re-file changes `severity`
   and nothing else.
2. **Item 18** — the `theoretical` reason word. One command opens the gate the
   protocol calls non-negotiable, and the config argues at length that it
   cannot. Fix the provenance *and* add the reachability correlation; then fix
   the two tests that currently prove the hole and call it the feature. Doing
   it after 25 is deliberate: both end in an unearned `finding_deferred`
   carrying `reason=theoretical`, and 25 tells you what the provenance field
   has to survive.
3. **Items 19 and 1 together** — the fix loop's two independent breaks. Both
   live in P0.3, they interact, and 19 fires first. Pair `tdd_evidence` to the
   row its command wrote, then actor-scope the gate's window. One `hook_e2e`
   test drives two actors through record → edit → sibling `fix_commit` → edit
   and covers both.
4. **Item 22** — the lint rule. Do it here, while 18 and 25 are fresh: it is
   the check that would have failed the build, and doing it now means items 9
   and 21 get audited by machine rather than by the next reviewer.
5. **P0-4 with P1-7, P1-8, item 26, P2-13, P2-14** — the doc/validator sweep.
   Cheap, and it is what a real run reads. One commit, with
   `test_subagent_contract_consistency` rewritten to a positive assertion
   rather than a denylist of last year's wording, and
   `validate_punchlist.py` made to require `reachability` the way
   `events.toml` already claims it does.
6. **P0-3 and P1-5** — the lens gate as ruled, plus the breaker's second seat.
   Same two transitions, so one commit. **Item 20 must be decided before this
   lands**, not after: a lens-scoped package with `unspecified` unrouted moves
   the whole merged board to `converge` silently — and the third pass confirmed
   the daemon accepts `unspecified` without complaint, so nothing else will
   catch it.
7. **P0-2** — the MEDIUM budget. Fix the whole domain of N, not the case that
   was reported: N=1 vacuous, N≥2 exact, spend-before-fix, and re-block on a
   late filing.
8. **Item 9** — constrain `merge_finding`. Its table is now **four** rows, not
   three: item 25 added an automatic route.
9. **Item 27** — the `boundary_check.py` constructor. One line and one test,
   and it is the difference between "confined" and "traceback" on Linux.
10. **P1-6, P2-10, P2-11, item 24** — escape naming, the `DEFERRED.md`
    conjunct, and the hardening batch's stated-vs-enforced gap.
11. **Item 21, item 23, item 28** — the ones that want a recorded decision or a
    parser narrowed, more than a patch. Narrow the `protocol.toml` claim; write
    the rework path down; make each script's CLI refuse what its courier
    refuses.
12. **P2-12, P2-15, P2-16, P2-17** — hygiene and the primer fail-open, then
    draft the changelog.

**Do not cut the release before 1, 2 and 3.**
`docs/design/convergence-speed-status.md` now records P0.3 as shipped (commit
`48c72fd`, "the P0.3 row said OWED after it shipped"). With items 1 and 19 both
open, that row is wrong again, and it is the row a reader would trust. Item 25
puts the same question to P4.1's row: the merge script runs, exits 0 and writes
a valid report while silently un-grading the board it just escalated.

---

## Scope of the third pass, stated plainly

**Read closely and driven against a real daemon where a claim depended on it:**
`merge_punchlists.py` (all 694 lines), `stale_sweep.py`,
`stale_sweep_courier.py`, `pattern_round.py`, `hardening_batch_courier.py`,
`sandbox_control.py`, `boundary_check.py`, `findings.py`,
`validate_punchlist.py`'s required-field set, `validate_merge_report.py`
against a report `render_report()` actually produces (it passes — that seam is
clean), and the `[sets.perspective]` / event-validation question behind item 20.

**Re-checked at their cited lines, not re-driven:** items 1, 2, 3, 5, 6, 7, 12,
13, 14, 15, 16, 19. Every line reference and quoted string in those items is
accurate against the tree at `48c72fd`. I took the second pass's daemon
observations for items 2, 9 and 10 on trust after confirming the config they
rest on; if one of those is load-bearing for a fix, drive it again.

**Still unaudited at depth, by anyone, across three passes:**
`bash_guard.py`, `commit_gate.py`, `protocol_tracker.py`, `pre_tool_hook.py`,
`post_tool_hook.py`, `_protocol_cache.py`, `enforcement/hooks/_common.py`,
`migrate_legacy.py`, `update_sahjhan_pin.py`, and the four `.tera` templates.
`bash_guard.py` and `commit_gate.py` are the notable gap — both are PreToolUse
gates, both were modified in this delta, and the two P0s the second pass found
were both in gate-adjacent code.

**Gates observed by this pass:** none re-run. The second pass's gate
observations at the top of this file stand; no code was changed here, only this
document.

# Open-issues worklog — 2026-07-14 (resumable across /clear)

Working through open GitHub issues on `jbrjake/holtz` in priority + dependency
order. Authorized scope this session:
- Make changes in **sahjhan** directly, commit, cut GitHub releases as needed,
  and re-integrate into holtz autonomously.
- **Keep sahjhan generic** — no domain-specific (holtz) business logic baked into
  the engine. Request generic capabilities; file `jbrjake/sahjhan` issues as
  needed.
- Commit + document as we go; close issues with citations as soon as possible.

Repos: holtz `/Users/jonr/Documents/code/holtz` (branch `dev`), sahjhan
`/Users/jonr/Documents/code/sahjhan`. Don't run the plugin against itself
(install-hooks.sh defaults to dev mode — enforcement hooks NOT wired into this
repo's session). Gate/pre-commit hooks (ruff+mypy+fast pytest+contract) ARE
installed; do not `--no-verify` silently. `python3` not bare `python`.

## Priority ranking (from maintainer comments)
P0 convergence-blocking: **#67**, **#65**, **#63** (+ #70.5, same root cause).
P1: **#70** (grab-bag), **#71** (heredoc bypass), **#69** (stop-hook pause).
P2/P3 feature requests: #6 #8 #9 #10 #11 #12 #13 #26 (not started; lower prio).

## BRANCH STATE (v0.137.2 release PR #72) — NOT actually diverged
CORRECTION: an earlier note here claimed main/dev "diverged" by 817 commits.
That was a SHALLOW-CLONE artifact — the local clone had `.git/shallow`, so
`git log main --not dev` counted phantom commits across the truncated boundary.
After `git fetch --unshallow`, the real picture is a totally normal dev→main
flow: main-not-dev = 20 commits, ALL `chore: release …` + `Merge pull request
#NN from jbrjake/dev` housekeeping from prior release PRs; dev-not-main = 12,
exactly the work since v0.136.0. Merging origin/main into dev was a clean
ANCESTRY-ONLY merge (`git diff HEAD` empty — zero content change) that brought
dev up-to-date with main's release-merge commits. Lesson: on a shallow clone,
`git fetch --unshallow` BEFORE reasoning about branch topology.
main requires strict (up-to-date) status checks; enforce_admins=false. The
correct fix for BEHIND is `gh pr update-branch` / merge origin/main into dev
(done), NOT admin-bypass or force. Merge PR #72 via `gh pr merge --merge`.

## ✅ RELEASE v0.137.2 SHIPPED TO main (2026-07-15)
PR #72 merged (dev→main); Release Action succeeded; tag v0.137.2 + GitHub
Release published (not draft); main HEAD 9578af6 = plugin.json v0.137.2. All
P0/P1 fixes are now on main. dev is now "behind" main by the new `chore:
release v0.137.2` housekeeping commit — normal, handled at the next release.

## ✅ P0 + P1 COMPLETE (2026-07-15)
All P0 (#67, #65, #63) and P1 (#69, #70, #71) issues resolved and CLOSED on
GitHub with citations. holtz `dev` at v0.137.2 (HEAD 2f641ab), CI run
29444276033 = success. sahjhan v0.17.0 released + pinned. sahjhan #31 (engine
ledger_has_event_since fix) also closed. Remaining open issues are all P2/P3
feature requests (#6 #8 #9 #10 #11 #12 #13 #26) — per user directive, STOP here.
Course-correction this session: initially deferred the sahjhan
`ledger_has_event_since` fix (filed #31) — user called that out as a wrong
route-around; I fixed the engine bug properly in v0.17.0 instead (parse prefix,
min_count, field filter), repairing the live `set complete perspective` gate.

## STATUS

### ✅ #67 — fix_commit lifetime 15-cap → per-iteration. DONE, closed.
Commit `a51ef66` (v0.136.2, on dev, pushed). transitions.toml fix_commit
breaker now `seq > COALESCE((SELECT MAX(seq) ... command='iteration_boundary'),0)`.
Regression test `test_fix_commit_breaker_scoped_to_iteration_not_lifetime`.

### ✅ #65 — pattern_check chicken-and-egg. DONE, closed.
Same commit `a51ef66`. pattern_check gate rewritten from broken
`ledger_has_event_since since=last_event_of_type:...` to COALESCE query
`SELECT count(*) >= 3 FROM events WHERE type='finding_resolved' AND seq >
COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'),0)`.
Empirically validated with `sahjhan query`. Regression test
`test_pattern_check_bootstraps_from_zero`.

### SESSION 2026-07-15 PROGRESS (this session)
Holtz commits on dev: #70.1 (`db26689` v0.136.5), #71 (`d0d43f6`+`2528a41`
v0.136.6), #69 (`f3ef138` v0.137.0). Full-suite coverage 91% (CI-green).
Closed on GitHub: #71, #69 (with citations).
sahjhan v0.17.0 CONTENTS (commits on main): `2e4ad29` (#70.4 cwd-ledger
walk-up), `818d27c` (#70.7 event_count event-type filter), `0cf7b07` (bump),
`c2ff48e` + `7a64273` (sahjhan #31 ledger_has_event_since: parse
last_event_of_type: prefix, honor min_count, honor field `filter`, missing
baseline=seq0). This repairs the live holtz `set complete perspective` gate
(transitions.toml:203) which uses BOTH the prefix AND filter — previously both
were silently ignored (route-around territory). ledger_has_event_since fix is
NOT deferred — user (2026-07-15) called out the deferral as wrong; fixed in
this release. sahjhan #31 to be closed as fixed once v0.17.0 ships.
RELEASE INTEGRITY NOTE: v0.17.0 tag was re-pointed twice while builds were
in flight. FINAL tag/HEAD = `7a64273`. Before pinning, ensure the published
v0.17.0 release binaries are from 7a64273 (delete+re-cut once from stable HEAD
if any ambiguity), then pin + verify via check_sahjhan_pin.py.

### RE-PIN (do NOW that v0.17.0 is releasing) → closes #63 + #70
Re-pin holtz 0.15.0 -> 0.17.0 in ONE step. Steps:
1. `_resolve.SAHJHAN_VERSION` = "0.17.0".
2. `_resolve.SAHJHAN_CHECKSUMS` = the 4 sha256 from the v0.17.0
   checksums.sha256 (gh release download / raw URL).
3. `scripts/vendor-sahjhan.sh 0.17.0` (re-vendors bin/, writes untracked
   .sahjhan-version marker). Binaries are gitignored — only _resolve.py commits.
4. `python3 scripts/check_sahjhan_pin.py` must PASS.
5. `pytest tests/test_sahjhan_pin.py` (invariant tests, no version hardcode).
Then close #63 (+#70.5) and #70 (all items done: 1✅ 2✅ 3✅ 4✅ 5✅ 6✅ 7✅).
bin/.sahjhan-version is UNTRACKED (single source of truth = SAHJHAN_VERSION).
`bin/` active; `.claude-plugin/bin/` stale untracked leftover (ignore).

### 🔧 #63 (+ #70 item 5) — gate command env + surface stderr. HALF DONE.
- sahjhan v0.16.0 (`10cf274`, tag v0.16.0, RELEASED): command_succeeds/
  command_output now surface a bounded stderr (or stdout) tail on failure. Done.
- holtz (`33e7317`, v0.136.3): pytest/ruff gates now `${HOLTZ_PYTEST:-...}` /
  `${HOLTZ_LINT:-...}` (sh-expanded, overridable per target); docs in
  phase-fix-loop.md. Done.
- REMAINING to CLOSE #63/#70.5: re-pin holtz to the batched sahjhan release
  (>=0.16.0) so the stderr feature ships. Do at the final re-pin. THEN close
  #63 and #70 item 5.
- #70 item 6 (--item-id doc drift): DONE in `33e7317` (positional BH-NNN).
Root cause analysis done:
- `src/gates/command.rs` `eval_command_succeeds`/`eval_command_output` run
  `sh -c cmd` (NOT login shell) inheriting the CALLER's env. It **captures
  stderr then discards it** (`_stderr`), reporting only exit status → the
  30-min "missing pytest vs real failure" diagnosis. **Fix (generic, sahjhan):
  include captured stderr (tail) in the failure `reason`.** This is the XS win
  the maintainer flagged as do-immediately.
- Env/PATH: gates evaluate wherever `sahjhan transition`/`gate` runs (CLI
  process, not necessarily the daemon). Need to confirm daemon-vs-CLIeval path
  (see `src/cli/transition.rs`, `src/state/machine.rs`, daemon socket ops) and
  decide the generic fix (maintainer option 1: run gate commands with the
  daemon's env). `ruff check .` 127 (#70.5) is the same root cause.
- After sahjhan changes: bump `Cargo.toml`, add Rust tests, commit, tag/release
  on GitHub, then in holtz bump `enforcement/hooks/_resolve.py SAHJHAN_VERSION`
  (currently "0.15.0"; bundled bin `.claude-plugin/bin/.sahjhan-version`=0.13.0
  — there's drift to reconcile) + re-vendor binary (`scripts/vendor-sahjhan.sh`)
  + `tests/test_sahjhan_pin.py`.

### ⏳ Also needs generic sahjhan fix (found this session, folds into #65 follow-up):
`ledger_has_event_since` (src/gates/ledger.rs:101) does NOT parse the
`last_event_of_type:<type>` prefix (treats whole string as a literal event type,
falls back to last state_transition) and ignores `min_count`. Still used live by
the `set complete perspective` gate (transitions.toml:186,
`since=last_event_of_type:set_member_complete`) — that gate is silently
mis-scoped. **Generic sahjhan fix:** parse `last_event_of_type:<type>`, honor
`min_count`, treat missing baseline as run start (seq 0). File sahjhan issue +
implement in the same batch as #63. (holtz #65 itself already closed via the
query rewrite — this is the follow-up that repairs line 186.)

### ⏳ #70 — papercuts grab-bag. PARTIALLY DONE. Triage:
- item 6 ✅ DONE (`33e7317`): fix_commit positional BH-NNN doc fix.
- item 2 ✅ DONE (`db2d2c9`): TDD pre-edit gate now exempts docs/** + out-of-repo
  (pre_tool_hook.py `_tdd_gate_exempt`). Tests: TestPreToolHookTddPathScope.
- item 5 ✅ effectively DONE (env-override `${HOLTZ_LINT:-ruff check .}` in
  `33e7317` + sahjhan stderr). Closes with #63 at re-pin.
- item 1 ✅ DONE (`db26689`, v0.136.5): stall block was in `_protocol_cache.py`
  `compute_obligations` (stall>15 → blocks_all) + `commit_gate.py`, not the bash
  guard. Added `contains_sahjhan_cmd` (any segment sahjhan) beside strict
  `is_sahjhan_cmd`; commit_gate lets a wrapped sahjhan re-sync through the stall
  block (never a git commit); protocol_tracker resets stall on wrapped re-sync via
  shared `_apply_sahjhan_cmd`. Message clarified. Tests: TestChickenAndEggStallBlock.
- item 7 ⏳ TODO (fold into sahjhan BATCH): "N events since last state transition"
  noise. Monitors live in `enforcement/hooks.toml` (fix_loop_stall threshold 20,
  audit_stall 30) + Edit-accumulation warn (threshold 8). Root cause: the trigger
  `event_count_since_last_transition` counts ALL ledger events incl. auto-recorded
  file_read/source_edit/file_search (reads dominate). Principled fix: add
  event-type filtering to the sahjhan trigger (generic), then count only
  `source_edit` in holtz. Depends on v0.17.0 + re-pin.
- item 4 ⏳ TODO (sahjhan BATCH): cwd-relative ledger resolution — a `cd` into a
  subdir breaks all sahjhan calls (`Cannot open ledger: No such file...`). Make
  ledger resolution walk up to the project/git root. sahjhan Rust
  (`open_targeted_ledger` / `resolve_data_dir` in src/cli/commands.rs) + maybe
  holtz `_resolve.py`. Generic → goes in the batched v0.17.0.
- item 3: already fixed (patterns-brief.md author-editable; not in MANAGED_DOCS,
  which is only STATUS/PUNCHLIST/SUMMARY).
- To CLOSE #70: finish items 1, 7, 4; then verify all and close.

### ✅ #71 — heredoc/redirection bypass of TDD gate. DONE (`d0d43f6`+`2528a41`, v0.136.6).
Managed-path half was already guarded (`_check_bash_write`). Remaining gap = TDD
gate not applied to bash source writes. Added to `_sahjhan_bootstrap.py`:
`_strip_heredoc_bodies` (drop inert data), quote-aware shlex target extraction
(`_bash_write_targets`: `>`/`>>`/heredoc/`tee`/`sed -i`; cp/mv excluded), and
`_bash_source_write_tdd_block` → routes in-repo source targets through
`sahjhan hook eval --tool Write` (same gate as Edit/Write); docs/out-of-repo
exempt; fails closed mid-audit. Tests: test_bash_source_write_gate.py
(over/under-block matrix + e2e gate + fail-closed unit branches). Close #71 now.
Historical (superseded) plan:
Extend the redirection-parser in `enforcement/hooks/_sahjhan_bootstrap.py` bash
guard to route ordinary-source writes (`cat >`, `>>`, `tee`, `sed -i`, `cp`,
`mv`, `dd`, `python -c open(...,'w')`) through the same TDD + managed-path
checks, WITHOUT over-blocking quoted heredoc *data* (the scanner currently
greps command text incl. heredoc bodies → false positives on issue prose). Do
#70 item 2 first. holtz-only. Test: `test_issue46_bypass_regression.py` is the
sibling pattern.

### ⏳ #69 — Stop hook no pause-for-human. NOT STARTED.
Add a lightweight reversible pause the Stop hook accepts (distinct from
terminal). states.toml + transitions.toml (a `paused`/`awaiting_human` state
with resume) + `enforcement/hooks/stop_hook.py`. Auto-resume. holtz-mostly.

### ✅ #73 — Lens quiz gate unsatisfiable (vault never populated). DONE (2026-07-17).
Convergence-blocking on every target: nothing populated the daemon vault, so
lens_quiz posed no quiz, quiz_posed/quiz_answered never written, `set complete
perspective`/converge unsatisfiable. Rebuilt around the maintainer's design
(temporal integrity, NOT answer-hiding — see [[issue-73-quiz-channel-design]]).

sahjhan v0.19.0 (`60bd4aa`, main, RELEASED): generic **state-gated vault keys**
— `vault.toml` `[[policy]] name writable/readable/deletable_in_states`; daemon
derives current state from the active ledger and rejects out-of-state
vault_store/read/delete. Sealed as the 8th config file. Backward compatible
(no policy = unrestricted). Rust unit + real-daemon e2e tests.

holtz `2551cbe` (v0.138.0, dev) + `9413b95` (test):
- Recon Step 5: a generation subagent derives per-lens questions from the impact
  graph, stages each via `skills/holtz/scripts/quiz_stage.py`; trusted PostToolUse
  courier `quiz_capture.py` appends to the `quiz-bank` vault key (freshness-verified
  → forces code-anchored questions). Vault-only (ledger is cat-readable).
- `enforcement/vault.toml`: quiz-bank writable only in recon, readable only in
  sweep states → channel closes at recon_complete. `recon_complete` gate now
  requires `quiz_bank_generated` (can't leave recon bankless).
- `enforcement/hooks/quiz_vault.py` (store/read/append/read_safe); lens_quiz reads
  the vault + reads agent_transcript_path OR transcript_path (Defect B) + actionable
  stale message (Defect C). Removed the old disk-source `quiz_bank_loader`.
- Re-pinned sahjhan 0.18.0→0.19.0. New hook wired in hooks.json + manifest +
  trusted-callers. Verified: sahjhan suite (35 bins) + vault-policy e2e; holtz fast
  + slow (real-daemon) + contract; `sahjhan validate` on the config; full coverage
  89.82%; dev CI run 29607998884 = success.
NOT run: a full end-to-end audit (recon→sweep→converge) — component + integration
verified, but the whole-run convergence claim rests on those, not an observed run.

### ✅ #79 — awaiting_clear gate satisfied without a real /clear. DONE (2026-07-25).
P1 enforcement integrity, opposite in direction to #73: a gate satisfied when it
shouldn't be. `primer.py` recorded `context_reset` on **every**
`UserPromptSubmit` — including automated background-task notifications — so the
`awaiting_clear -> fix_loop` (`resume`) gate opened on whatever prompt arrived
next, with the entire recon+audit+merge context intact. Silent, and it *looked*
like success (`status` printed `resume: ready`).

Root cause is a category error about what the hook event means:
`UserPromptSubmit` answers "did a turn begin?", not "was the context wiped?".
Fix moves the write to a new `SessionStart` hook, which is **host-driven** (no
tool call can produce one, so an agent cannot manufacture the evidence) and
carries `source`, which names *how* the session started.

Full design + spec citations: `docs/superpowers/plans/2026-07-25-issue-79-context-reset-provenance.md`.

- `enforcement/hooks/session_start.py` (new, trusted caller): records
  `context_reset` only for `source ∈ {clear, compact, startup}`. Silent on
  success; emits AUDIT TERMINATED / ENFORCEMENT FAILURE on a failed write.
- **`startup` included deliberately** — the issue suggested `{clear, compact}`.
  A user who quits and relaunches at `awaiting_clear` has a genuinely empty
  context; refusing it would trade #79 for #73's failure mode (unsatisfiable
  gate). `resume`/`fork` excluded: both carry the prior transcript forward.
- `events.toml`: `trigger` pattern narrowed `^user_prompt_submit$` →
  `^session_start$`, plus a required `source` patterned to the reset sources.
  The daemon validates fields on `record_event`, so the old provenance is now
  **unwritable**, not merely unused.
- `transitions.toml`: `resume` gate gained `filter = { trigger = "session_start" }`.
  Block condition ≡ evidence; `user_prompt_submit` events already in live
  ledgers cannot satisfy it.
- `primer.py`: stopped recording. Its two failure signals used to be side
  effects of that write, so they were replaced with direct probes — init-PID
  liveness (strictly better: no longer needs a write to fail) and a
  non-mutating `enforcement_read`.
- `_common.py`: added `DaemonError(RuntimeError)` carrying the wire `error`
  code. `_daemon_request` was collapsing every refusal into the prose message,
  which would have forced the probe to string-match `"caller not authenticated"`
  — the brittle-mirror pattern that caused #77. Subclassing RuntimeError keeps
  every existing handler unchanged.

**No sahjhan change needed.** Every primitive already ships in 0.19.0:
`restricted` events + the daemon `record_event` op, per-field pattern validation
(`handle_record_event` → `validate_event_fields`), and `ledger_has_event_since`
with a payload `filter` (`entry_matches_filter`). Teaching the engine about
`SessionStart`/`source` would push Claude Code host-lifecycle semantics into a
generic state machine — the pollution the project forbids.

Verified: `session_start.py` run against a live real daemon authenticated as
`hooks/session_start.py` and appended `context_reset` with
`trigger=session_start, source=clear` to the run-1 ledger (daemon log
`recorded: context_reset`; fields read back from the ledger). 3 real-daemon
tests, 13 hook_e2e tests, 6 declarative-config tests. Full suite + coverage
gate, ruff, mypy, contract gate all observed green.
NOT run: a full end-to-end audit through an actual `/clear` boundary in a live
Claude Code session — the SessionStart wiring is verified by hook subprocess +
real daemon, not by an observed live clear.

## Test/verify commands (holtz)
```
source .venv/bin/activate
python3 -m pytest -q                    # fast (subagents)
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ scripts/ enforcement/scripts/
python3 scripts/contract_gate.py
```
sahjhan binary for empirical gate/SQL checks:
`/Users/jonr/Documents/code/holtz/.claude-plugin/bin/sahjhan-aarch64-apple-darwin`
`sahjhan --config-dir <holtz>/enforcement query "<SQL>"` (needs an init'd ledger;
record events with `event <type> --field ...`; auditor must be holtz|justine,
commit_hash `^[0-9a-f]{7,40}$`, finding_resolved needs phase/step/id/commit_hash/
evidence_path).
</content>

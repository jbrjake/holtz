# Case study: the tqdm run that could not converge

> **Genre note.** The other files in this directory profile *bugs Holtz found*. This one
> profiles *Holtz itself*. It is a process post-mortem of a single halted run, written
> from session telemetry and the run ledger rather than from memory.
>
> **Proposals derived from this post-mortem live in
> [`docs/design/convergence-speed-proposals.md`](../design/convergence-speed-proposals.md).**
> This document is diagnosis only.

**Target:** [tqdm](https://github.com/tqdm/tqdm) — mature, widely-deployed Python progress-bar library, ~5k lines of library code
**Plugin:** holtz v0.141.3, protocol `holtz/1.0.0`, run `1`
**Window:** 2026-08-11 14:31 UTC → 2026-08-18 07:48 UTC
**Final state:** `awaiting_human` (paused) — **not converged**

---

## 1. The headline

Holtz audited a small, mature library. It found and fixed every CRITICAL bug it
identified, and it did so in the first day. Then it ran for six more days, fixed no
criticals, and **grew its own backlog from 124 findings to 273**. It halted with no
reachable path to convergence.

The audit was good. The **fix loop diverged** — it filed 2.43 new findings for every one
it closed, and the convergence gate requires zero open findings.

| Measure | Value |
|---|---:|
| Sessions | 11 (10 non-empty) |
| Wall-clock span | 6 d 17 h |
| **Agent-active elapsed** (some agent working) | **1,351 min / 22.5 h** |
| Total agent-labour (parallel work summed) | ~2,131 min / 35.5 h |
| **Output tokens** | **6,675,091** |
| **Cache-read tokens** | **761,854,973** |
| API calls | 6,510 (avg prefix **117,028 tok/call**) |
| Read : write ratio | **114 : 1** |
| Subagents launched | 107 — **85% of output, 78% of cache-read** |
| Fix commits | 62 |
| Findings created / resolved / **deferred** | 353 / 81 / **0** |
| Protocol violations | 81 recorded (36 unresolved) |
| Perspectives marked complete | **0 of 13** |
| Compactions | **0** |

---

## 2. Phase timeline

From `docs/holtz/runs/1/ledger.jsonl` (8,391 events).

| Boundary | Time (UTC) | Elapsed |
|---|---|---|
| `run_start` | 08-11 14:34 | — |
| `recon_complete` | 08-11 15:19 | 45 min |
| `audit_complete` | 08-11 16:20 | 61 min |
| `merge_complete` | 08-11 16:57 | 37 min |
| `fix_loop_start` | 08-11 16:58 | — |
| first fix committed | 08-11 17:34 | **3.0 h wall from run start** |
| **last CRITICAL closed** | **08-11 23:49** | — |
| halted, `awaiting_human` | 08-18 07:48 | — |

**The front-load is not the problem.** Recon, a full 13-lens audit, a parallel Justine
audit and the merge took 143.7 min of wall clock (503.6 agent-min at 3.5× parallelism)
and produced 156 findings including all 20 criticals. That is a good return.

**62% of all agent-active time came after the last CRITICAL was fixed.**

| | Day 1 (5 sessions) | Days 7–8 (6 sessions) |
|---|---:|---:|
| Fixes delivered | 25 | 56 |
| **CRITICAL fixes** | **20 (all of them)** | **0** |
| Findings *created* | 193 | 161 |
| Net backlog change | +168 | **+105** |
| Also included | recon + audit + Justine + merge | nothing but the fix loop |

---

## 3. Why it could not converge

### 3.1 Amplification: 2.43 new findings per fix

| Origin | Created | Resolved | Yield | Still open |
|---|---:|---:|---:|---:|
| Audit (Steps 6–8, pre-fix) | 157 | 38 | 24% | — |
| **Pattern-analysis windows** | **133** | **28** | **21%** | **105** |
| Elsewhere in fix loop | 63 | 15 | 24% | — |

**46% of all findings were generated during the fix loop**, at a *lower* hit rate than the
audit they supplemented. Pattern analysis was not finding better bugs; it was finding
more, worse bugs. Its output is **38% of the 273-item open backlog**.

Open count by session, monotonic except once: 124 → 151 → 160 → 168 → 200 → 198 → 214 →
231 → 255 → **273**. Generation ran at ~31 findings/agent-h against retirement at ~7.
**The loop was already divergent at pattern round 1.**

On days 7–8, **41 of 56 resolutions (73%) were of findings the fix loop had generated
about its own prior fixes.**

### 3.2 The convergence gate demands a state the loop cannot produce

`enforcement/transitions.toml:347` requires **all** of:

| Gate | Actual |
|---|---|
| all 13 lenses complete | **0 of 13** |
| full suite green | achievable |
| lint clean | achievable |
| `all_findings_closed` expect `0` | **273 open** |
| `no_violations` | **36 unresolved** |

Then `phase-convergence.md:45` mandates Step 16 resweep — *"Full re-run of Steps 6–8"* —
the phase that produced 124 findings in 143.7 min. **Even if zero-open were reached, the
exit ritual regenerates the backlog.**

### 3.3 The 81 protocol violations are one infrastructure bug — and it is what killed the run

Every record has the same shape — `manifest hash mismatch: expected …, actual missing`
against `.sahjhan/ledger.jsonl`, `PUNCHLIST.md`, `STATUS.md`, with `project: "holtz",
run: "0"` (the active run is `tqdm` / run 1 — the same wrong-root derivation, so the
poisoned records aren't even attributable to the run they killed). This is the
cwd/manifest-anchoring defect fixed *after* this run by holtz #85 / sahjhan 0.20.1.
**Not one is a discipline failure.**

**They are not spread across the run — they are its last 24 minutes.** All 81 sit at
`seq 8276–8390`, between `07:46:06Z` and `08:10:42Z` on 08-18. The preceding **8,275
events are clean**. The first violation lands **18 seconds after** the run's last
successful `fix_commit` (07:45:43) and `finding_resolved` (BH-337, 07:45:48); `pause`
follows at 07:48:37.

The trigger was a `cd /Users/jonr/Documents/3rd-party-code/tqdm/docs/holtz` at
`023e20f4` 07:19:45Z — issued to shorten paths while reading the 34–52 KB
`pattern-round-15-axis-*.md` files. 26 minutes later the `no_violations` gate
(`transitions.toml:313,353`, on `set complete perspective` **and** `converge`) became
permanently unsatisfiable, and `SKILL.md:29` ("Cannot advance through a legitimate
transition → STOP") correctly halted the run.

So there are two distinct failures, and it matters not to conflate them: the run was
**already non-convergent** from pattern round 1 (§3.1), and separately it was
**terminated** by an infrastructure bug that an oversized artifact provoked.

### 3.4 The escape hatch was functional and never touched

`transitions.toml:163–195` — `defer_low` gates only on *exists + severity=LOW + open*;
`defer_medium` adds a 50%-of-MEDIUM budget. This run had 58 LOW and 152 MEDIUM.
**133 of 273 open findings (49%) were legally batch-closable for ~133 one-line commands,
roughly 5 agent-minutes.** `finding_deferred` count: **zero**.

Nothing blocked it. The cause is rhetorical:

- `SKILL.md:37` — *"Work every finding."*
- All **21** Rationalization Red Flags push toward more work. *"This codebase is small,
  skip convergence"* → *"Convergence is faster, not optional."*
- The persona — *"Meticulous, adversarial, relentless… You stop when the codebase
  converges. Not when the developer is satisfied."*
- `step-10-fix-loop.md`'s flowchart only reaches `defer` **after** dispatching a fix
  subagent, and `phase-fix-loop.md:59` frames deferral as *"the subagent could not reach
  HIGH confidence"* — i.e. **failure, not triage**.

There is no red flag reading *"I should fix this MEDIUM"* → *"You have 143 open MEDIUMs
and 75 open HIGHs. Defer it."*

### 3.5 Severity is assigned once and never re-graded

0 of 354 findings differ between the `finding` ledger event and the final punchlist. One
defect class decayed **by discovery order, not impact**:

`TqdmDefaultWriteLock` exception-safety → BH-002 **CRITICAL** → BH-196 **HIGH** →
BH-245/246 **MEDIUM** → BH-258 **LOW**. All five received a full TDD fix cycle.

Fix order *was* severity-ordered — that is not the bug. The queue is **LIFO within a
severity band**: mean **45.4** older still-open CRIT/HIGH findings were skipped at each
fix; 33 of 81 fixes worked a finding under 2 h old. **51 of the 75 open HIGHs (68%) were
on the board before the first fix commit** and were never worked in ~16 h of later
sessions — including BH-029 (`cli.cast()` eval `SyntaxError`), BH-030 (`--update` crashes
mid-stream), BH-054 (unescaped `desc` → ipywidgets HTML injection).

---

## 4. Where the time actually went

### 4.1 Three hypotheses that died on contact with the data

- **Session re-onboarding is cheap.** `/clear` → first productive action: **32.5 agent-min
  across 10 sessions** (median 2.2 min). The resume primer works.
- **Test execution is negligible.** 1,116 pytest executions = **110 min** of the 1,351.
  Full suite median 24.6 s. Fix subagents are only **13% tool-wait; 87% model generation** —
  latency tuning cannot help this run, only concurrency can.
- **Context never compacted.** Zero `isCompactSummary` / `compact_boundary` records in any
  of the 117 transcripts. The entire Context Survival Protocol is insurance on a fire that
  never started — and its "re-read before every step" remedy is the run's **second-largest
  cost driver** (~24M cache-read of redundant re-reads).

### 4.2 Pattern analysis costs more than fixing, and blocks the commit

| Activity | n | Median | Share of in-loop elapsed |
|---|---:|---:|---:|
| Fix cycle (`fix_start`→`fix_commit`) | 58 | **9.7 min** | 57% |
| Pattern round (`pattern_check`→`pattern_done`) | 24 | **17.9 min** | **43%** |

Pattern subagents alone burned **474 agent-min, 1.96M output and 425M cache-read — 31% of
the run's total cache-read.**

It is **mechanically unskippable**. `protocol.toml:90-92` defines
`pattern_analysis_overdue` = "3+ findings resolved since the last pattern analysis";
`transitions.toml:289` makes `pattern_check` require it *true*, and `transitions.toml:217`
makes `iteration_boundary` require it *false* — **you cannot `/clear` without running a
round.** 81 resolutions therefore forced ≥27 rounds.

Worse, it fires **inside the commit path**. Session `c30f4d6b` 20:52:14: `git commit` for
BH-245 returned `BLOCKED: Pattern analysis overdue`. A **4.9-min fix took 24.0 min** because
an 18-min pattern round was injected mid-cycle. Same shape for BH-187 (19.8 min for a
6.1-min fix).

**And the gate is yield-blind.** `patterns-brief.md` states verbatim, four times, that
rounds 12, 13, 14 and 15 added **no new pattern**. Those four rounds cost **268 agent-min**.
Cost per eventually-fixed finding by band: rounds 1–8 **24.9 min** → 9–15 **16.0** →
16–21 **13.9** → **rounds 14–15: 108.9 min.** A 7× collapse, and the gate never noticed.

The `patterns_found` field that gates `pattern_done` is **unverified self-report and is
wrong**: rounds 14/15 recorded `patterns_found=5` and `=2` while the brief says both added
none.

### 4.3 The run's own paperwork outweighs the code it audits

Cache-read attributed to what put the bytes in context:

| Source | Carried cache-read |
|---|---:|
| **Holtz bookkeeping artifacts** | **65.0 M** |
| tqdm source + tests | 57.5 M |
| Protocol docs | 14.6 M |

`patterns-brief.md` alone carried 21.7M; `PUNCHLIST-MERGED.md` 17.1M.

**Two caps guard the wrong dimension.** `phase-fix-loop.md:116` caps the patterns brief at
**20 entries** — it sat at 20 entries and **181 KB**, mean 8.5 KB/entry against a 4-line
(~400 B) format spec. **21× spec.** By round 14 a single entry no longer fit one call:
one subagent made **5 paginated reads totalling 159 KB in 90 seconds**.

The de-duplication tool exists and works: `pattern_brief_compact.py` renders 179 KB down to
**6,748 chars — 26×**. It was invoked **once** in the entire run, because
`phase-fix-loop.md` — the doc governing every pattern round — **never mentions it**.

Meanwhile `phase-fix-loop.md:91` mandates *"read the **full** punchlist (no filter)"* —
325 KB / 81k tokens, of which 23% is already-resolved rows.

### 4.4 The fix loop read a worklist frozen seven days earlier

`phase-fix-loop.md:28` — *"If `PUNCHLIST-MERGED.md` exists, use it."*

`PUNCHLIST-MERGED.md` is 574 KB, written **exactly once** at 08-11 17:53, and **no doc
anywhere re-renders it**. At halt it still held **178 findings, every one marked
`Status: OPEN`** — including all 81 that had been fixed. The live `PUNCHLIST.md` had 354
findings and 81 RESOLVED.

Session `c35c9091` (08-17, 2.4 h) ran **4 pattern rounds grepping `PUNCHLIST-MERGED.md`
exclusively** — blind to 176 findings and to all 25 fixes already committed. This is the
mechanical root of the "moot / stale / already fixed" reconciliation work.

**111 subagent-min and 489k output tokens went to reconciling bookkeeping against
reality** rather than fixing bugs.

Related dead letters, none gated:
- `step-10-fix-loop.md:55` mandates updating PUNCHLIST.md after each commit. **Zero** such
  edits occurred in 23 sampled cycles — and a hook *blocks* the mandated write
  (`BLOCKED: Bash command modifies protected path 'docs/holtz/STATUS.md'`). The instruction
  is un-followable and points at a stale file.
- The orchestrator never `Read` the punchlist at all. It ran `sahjhan query --type finding
  --format jsonl` and **wrote its own filter scripts** — `show_findings.py` was written from
  scratch in **three separate sessions**, `mutate.py` in three, `remap_ids.py` in two.
- The load-bearing resume artifact is not Holtz's. A hand-rolled note at
  `~/.claude/projects/…/memory/holtz-tqdm-run-fresh-0138.md` (16.7 KB) was read in **9 of 10
  sessions**, because STATUS.md + a 180-token injection + a stale punchlist could not carry
  the run.

### 4.5 The fix loop is serial by mandate — and the mandate is correct

`phase-fix-loop.md:68` — *"Dispatch subagents **one finding at a time** — the ledger is a
single hash chain and commits land on one branch."*

The deeper cause is `enforcement/hooks.toml:18-20`: the TDD pre-edit gate is
`ledger_has_event_since / test_failed_before_fix / since = last_transition` — **run-global,
not finding-scoped.** Two concurrent fix subagents would satisfy *each other's* gate. So
the serialization is load-bearing **given the current gate**.

| Subagents in flight | Wall-clock min |
|---:|---:|
| **1** | **1,010** |
| 2 | 23 |
| 3 | 36 |
| 4 | 30 |
| 5–8 | 31 |

**89% of subagent wall-clock had exactly one agent working.** Sessions 3–9 ran at max
concurrency 1 for **857 consecutive minutes** — 14.3 agent-hours of zero parallelism.

Yet **74% of pairs among any 4 consecutive fix commits touch disjoint source files.**
`tqdm/std.py` is the genuine hot spot (25 of 62 commits) and needs a serial lane;
everything else could fan out.

The orchestrator **invented** the missing idiom on its own: at `023e20f4` 04:39:13 it
split pattern round 15 into four disjoint axes (*"Pattern brief is 63K tokens — delegating
rather than reading it into my context"*), achieving 2.4× speedup with near-zero payload
overlap. **Nothing in any skill file suggests this.** Its axis prompts also say *"Do NOT run
`sahjhan event`"* — a hand-rolled workaround for the ledger concurrency constraint.

### 4.6 The loop generated its own regressions

**30% of all source-line deletions were the run deleting its own fresh code.** Of 449 lines
deleted from `tqdm/*.py`, 135 had been written by an earlier commit of the same run.
**13 of 62 commits (21%) deleted ≥50% run-authored lines; 9 deleted 100%.** Those 13 cost
169 subagent-min and 709k output tokens.

- `PUNCHLIST.md`, BH-335: *"**REGRESSION OPENED BY THIS RUN'S OWN COMMIT ed17a33**… anchored
  ONE STATEMENT TOO LATE."* Introduced 00:25, found 4 h 20 m later, fixed by `d5084fa`
  which deleted 14 of 14 run-authored lines.
- The `tqdm | head` BrokenPipe behaviour took **5 commits**; the monitor `atexit` hook **3**;
  the `ensure_lock`/`mp_lock` cluster **13 fix windows / 196.8 min**.
- BH-248 is an open regression the run introduced and never fixed: `32bd5cb` widened
  `except OSError`, so `tqdm(file=open(p,'rb'))` now silently never draws.

Each follow-up was filed as a **new** HIGH finding entering a full TDD cycle, rather than
reopening the original.

### 4.7 Would a tqdm maintainer merge this?

62 commits: `tqdm/` **+1,505 / −311**; `tests/` **+10,772 / −57**. Suite 147 → 569 tests.
A **7:1 test-to-source line ratio.**

- **~14 genuine user-facing defects** — bot token printed on request failure
  (`9fcb5d1`, `d61406e`), `TQDM_MININTERVAL=abc` crashes `import tqdm` (`8b9a132`), rates
  ignore `unit_divisor` (`e361004`), rich `Live` leak (`f185a3e`), dask `self.bar` never
  exists (`9406e92`), multi-byte `--delim` (`b8ce885`).
- **~18 defensive hardening** — e.g. `0369df3`: 67 source lines and **431 test lines** to
  replace `self._lock` with `self.get_lock()` at 7 sites.
- **~22 fault-injection-only, unmergeable as-is** — reachable only by making some other call
  raise. BH-258's own text concedes: *"reachability on CPython 3.12 is uncertain… needs a
  reachability probe before any fix"* — and it was filed as a punchlist item requiring a
  fix cycle regardless.

### 4.8 Machinery that ran and was never consumed

- **The lens quiz bank.** A hard gate on `recon_complete` (`phase-recon.md:134`: *"you
  cannot leave recon without a bank"*). 108 `quiz_stage.py` calls, 85 questions, 13 lenses,
  14.5 agent-min. **Zero `quiz_challenge` / `quiz_answer` invocations in the entire run.**
  Perspectives: 0/13.
- **Recon artifacts are write-only.** Across the 10 sessions after the first, **zero tool
  calls** read any `docs/holtz/recon/step*` file. All 21 predictions in
  `step4-predictions.md` still read `**Outcome:** UNCONFIRMED`, though five separate
  `phase-audit.md` clauses order the update. (Prediction hit rate was 8/21 strict — but
  predictions 2 and 8 alone foreshadowed ~35 of 63 fix commits.)
- **Justine.** 114.0 agent-min / 377k tokens for 33 unique findings of 156 merged, of which
  **2 were ever resolved** — **~57 agent-min per shipped finding.** `merge-protocol.md:11`
  calls the merge *"mechanical… without judgment calls"* and `:165` *"deterministic"*, yet
  it ran as a 36.7-min subagent hand-writing throwaway `python3 -c` scripts. **This is a
  script running as an LLM.**
- **Three protocol-mandated artifacts were never produced and nothing noticed**:
  `MERGE-REPORT.md`, `justine/SUMMARY.md` (Justine's own completion signal), and the
  archive step. No gate checks any of them.
- **97 of 107 subagents ran Opus.** `phase-audit.md:55` has model-routing guidance;
  `phase-fix-loop.md` has **none**, so all 59 fix agents and all 23 pattern agents ran on
  the largest model regardless of triage path.

### 4.9 Enforcement friction: 7% of the time, but three of the cheapest fixes available

Across 5,024 Bash calls: **187 hard denials, 152 recovery episodes, 63.3 agent-min, 232k
output tokens.** Orchestrator share is **~50 agent-min (7.3%)**. Real, but not why the run
was slow — it is why the run *stopped*. Zero daemon deaths, socket errors, stale pids or
trusted-caller mismatches.

Three of the denial classes are outright contract bugs — the plugin blocking commands it
teaches:

1. **The out-of-tree-script gate blocks the plugin's own documented commands.** 58 denials
   / 7.5 min. `_sahjhan_bootstrap.py:214` never calls `os.path.expandvars`, so
   `os.path.isabs("$CLAUDE_PLUGIN_ROOT/skills/…")` is False, it joins against the target
   repo, cannot read it, and blocks. **13 hits are invocations taught verbatim** by
   `phase-fix-loop.md:49,53`, `phase-recon.md:142,149`,
   `impact-graph-operations.md:11`. Same legitimate shape, blocked across 9 sessions.
2. **The stall gate punishes read-only subagents.** 114 denials / 20.4 min / 138k tok —
   **108 of them in subagents, across 54 distinct actors, 112 at exactly `stall=16`.**
   Audit subagents running `grep`/`sed -n`/`ls` tick a counter they have no protocol event
   to clear. The prescribed escape is a bare `sahjhan status` whose output is never read:
   **115 pure re-sync calls, 5.4 min, zero information gained.** It climbs in the first
   place because `_segment_is_sahjhan` (`_protocol_cache.py:312-317`) matches only a
   literal token, so **70 of 498 sahjhan invocations (14%)** — `"$SAH" … event …`,
   `eval "…sahjhan… status"` — *increment* the stall instead of clearing it. The agent
   invents that indirection because `SKILL.md:103-138` teaches bare `sahjhan …` while
   `bin/` is never on `PATH`. Worst case (`288e9c63` 17:59:49): the command was blocked,
   the documented escape was blocked by the same gate, and only a third form worked.
3. **`pattern_analysis_overdue` goes stale and holds finished work hostage.** 11 denials /
   35.0 min. **7 of 11 fired within 6.6 min of a *completed* pattern round** —
   `9b6b5384` recorded `pattern_analysis → fix_loop` at 20:24:20Z and was blocked at
   20:24:32, 20:25:09, 20:25:16, 20:25:19. `_protocol_cache.py:400` reads a cached flag
   that `protocol_tracker._refresh_from_status` only re-derives on an *observed* sahjhan
   command, so the transition that satisfies the gate never clears it atomically. Blocked
   commits were held **12–25 min** each while the heredoc was re-composed from scratch.

**Instrumentation warning:** a hook that calls `exit_block` produces **no attachment
record at all**. All 2,419 `PreToolUse:Bash` attachments say `permissionDecision: "allow"`;
the only trace of a denial is a `BLOCKED:` string in the tool result. Any dashboard reading
`hookSpecificOutput` will report zero enforcement activity. Relatedly, `BLOCKED: N
unregistered commits` is **advisory** — 44 occurrences, every one `allow` — and 142
injections of "N source edits since last state transition" were never acted on.

### 4.10 The one thing that worked, and it is instructed nowhere

`stale-sweep-round14.md`: examined **all 68 open HIGH findings in 14 agent-min**, retired 4
(BH-078, BH-016, BH-017, BH-177 — all now RESOLVED) plus 2 partial. **4 of the run's 81
resolutions came from one 14-minute sweep that wrote no code.**

That is the best minutes-per-resolution figure in the entire run — roughly 3.5 agent-min
per finding retired, against 9.7 for a fix cycle and 23.4 for pattern analysis. It appears
in no skill file.

---

## 5. Unit economics

At observed unit cost — 9.7 min per fix, one blocking 12.8-min subagent, ~53k output
tokens, ~5.6M cache-read tokens — the full 353-finding punchlist projects to **~57
agent-hours** of fix loop alone, before the ~43% pattern-analysis surcharge, and still
would not terminate because working the list generates more list.

Even under **maximum permitted deferral** (58 LOW + 76 MEDIUM = 134 items), 219 findings
remain mandatory — **~35 agent-hours for a 5k-line library.**

The protocol has no budget, no size scaling (a keyword sweep of `SKILL.md` and all
`references/` for project size / LOC / defect density returns only *context-token* budgets),
and no honorable terminal state short of zero open findings.

---

## 6. What this run proves about the design

1. **A discovery mechanism inside a completion loop is a divergence engine.** Pattern
   analysis is sound as an audit technique. Running it *during* the fix loop, gated so it
   cannot be skipped, with an exit condition of "zero open," makes termination impossible
   by construction.
2. **The audit is calibrated; the fix loop is not calibrated at all.** Three hours produced
   every critical bug in the library. Nothing scales fix-loop ambition to project size,
   defect density, or remaining value.
3. **Severity was recorded and then not used to decide anything.** All 353 findings carry a
   severity. A LOW got the same TDD cycle, blast radius, hardening test and full-suite
   verification as a CRITICAL.
4. **Enforcement did not slow the run down; it shut the run down.** Friction is 7.3% of
   orchestrator time. But a path-anchoring defect, provoked by a `cd` the agent made only
   because an artifact had grown to 52 KB, poisoned `no_violations` and terminated a run
   that had just committed a fix 18 seconds earlier. Artifact bloat and enforcement
   fragility are the same failure here, not two.
5. **The prose fights the protocol.** The deferral transitions are correct, permissive, and
   unused, because 21 red flags and a "relentless" persona frame stopping as
   rationalization.
6. **The protocol's memory model cost more than the amnesia it prevented.** Context never
   compacted once. "Re-read before every step; assume prior context is gone" produced 24M
   tokens of redundant reads and three from-scratch rewrites of the same helper script.

---

## 7. Instrumentation note

Every number here came from `docs/holtz/runs/1/ledger.jsonl` (8,391 events) and 117 session
transcripts. Holtz already writes a complete process-telemetry database as a side effect of
enforcement — `fix_start`, `fix_commit`, `pattern_check`, `pattern_done`, `suite_green`,
`finding`, `finding_resolved`, all timestamped.

**It had never been queried for performance.** A `sahjhan report --timing` surfacing cycle
time, pattern-round cost, the generation-vs-retirement ratio and severity mix would have
made this run's divergence visible **on day 1, at pattern round 1**, from data the engine
was already collecting.

### A measurement trap, for whoever instruments this next

Claude Code writes **multiple jsonl records per assistant message** as it streams, all
sharing one `message.id`. Summing `output_tokens` across records over-counts (~7.7M here);
taking the *first* record per id under-counts badly (~1.8M) because early partials carry
`output_tokens: 1`. **Reduce with `max` per `message.id`** → 6,675,091. `cache_read` is set
at request time and is constant across partials, so it is safe either way (761,854,973).
And `<session-id>/subagents/*.jsonl` must be walked explicitly — it holds **85% of output
and 78% of cache-read**, and is invisible to any tool that only globs top-level sessions.

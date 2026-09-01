# Holtz Evaluation Harness — Design Proposal

**Date:** 2026-07-27
**Status:** proposal — nothing built
**Purpose:** a regression benchmark for Holtz itself.

---

## 1. What the harness asserts

Three claims about a Holtz release, checked on every run:

| # | Assertion | Evidence |
|---|---|---|
| 1 | **It completes.** A run reaches convergence and finalizes. | Protocol depth from the run ledger |
| 2 | **It finds everything it should.** | Findings matched against the known defects at the target's tag |
| 3 | **It hasn't regressed in coverage or performance.** | Impact graph contents and time spent, compared against prior versions |

The three tracked metrics map one-to-one onto those assertions:

- **bugs found** → assertion 2, detection quality
- **impact graph contents** → assertion 3, coverage — how much of the codebase Holtz actually mapped
- **time spent** → assertion 3, performance

They are one measurement taken together, per run, tagged with the Holtz version
that produced it. A run is a datapoint in a time series, not a pass/fail event.

Out of scope: Holtz's own defects. Those are what interrupt runs; they get filed
as issues. The harness records *that* a run stopped and where, because assertion
1 depends on it, but diagnosing them is not its job.

---

## 2. Why no run completes today

Measured from 25 Claude Code session transcripts for
`/Users/jonr/Documents/3rd-party-code/tqdm` (2026-07-13 → 2026-07-27). Phase
attribution comes from the agent's own `sahjhan` calls, which stamp
`--field phase=<x>` on every event. Gaps over 5 minutes are treated as human
idle and excluded from "active".

| Phase | Active h | % | Wall h |
|---|---:|---:|---:|
| pre (setup, skill load) | 2.23 | 8.8% | 4.05 |
| recon | 3.92 | 15.5% | 4.33 |
| audit | 4.84 | 19.1% | 5.76 |
| merge | 2.07 | 8.2% | 12.98 |
| fix_loop | 12.28 | 48.4% | 25.07 |
| **total** | **25.3** | | **52.2** |

Protocol commands issued across all 25 sessions: 11 `run_start`, 9
`recon_complete`, 10 `audit_complete`, 8 `merge_complete`, 8 `fix_loop_start`,
**108 `fix_commit`**, 5 `set complete perspective`, **0 `lens_rotate`**.

Dividing phase time by the runs that reached each phase gives a cost model:

```
run_active_time  ≈  70 min  +  6.8 min × findings
                    ^^^^^^     ^^^^^^^^^^^^^^^^^^
                    recon 26 + audit 29 + merge 15    per fix_commit
                    (paid again on every restart)     (12.28 h / 108)
```

tqdm at v4.67.0 is **9,035 LOC** (5,385 source + 3,650 test) across 108 files,
and its first audit produced **90 findings** — about **10 findings per kLOC**.
At 6.8 min each that is ~10 hours of active agent time to work the punchlist
*once*, before a single lens rotation. Convergence needs all thirteen lenses to
rotate and then a final sweep.

So assertion 1 has never been observed, and assertions 2 and 3 have no baseline
to compare against. **The target is too large to finish.** Everything below
follows from that.

---

## 3. A target that can finish

Same method as tqdm — a real third-party project, branched from a historical
tag with known defects. The selection criteria are tqdm's own, made explicit:

1. **Popular.** Real code with real users, as tqdm was chosen to be.
2. **Small.** The cost model makes this the dominant term.
3. **A historical tag with known defects** — releases after the tag, so the
   upstream fixes form an answer key.
4. **A fast test suite.** A hidden multiplier: the `fix_commit` gate runs
   `${HOLTZ_PYTEST:-python3 -m pytest --tb=short -q}` on *every fix*
   (`enforcement/transitions.toml`, 120 s timeout), and `set complete
   perspective` runs it again plus `ruff`. A 60-second suite adds ~1.5 h across
   90 fixes.
5. **Pure Python, light dependencies**, so a fresh clone runs green immediately
   and recon isn't spent on environment problems that aren't findings.

Measured candidates (LOC via `git ls-files '*.py' | xargs wc -l`; stars and
issue counts via the GitHub API):

| Target | Stars | Src LOC | Test LOC | **Total** | Py files | Tags | Est. findings | Est. first pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| python-slugify | 1,622 | 1,101 | 657 | **1,758** | 7 | 48 | ~18 | **~3.0 h** |
| parse | 1,789 | 1,091 | 1,418 | **2,509** | 9 | 10 | ~25 | ~4.0 h |
| python-dotenv | 8,832 | 1,105 | 2,138 | **3,243** | 20 | 51 | ~32 | ~4.8 h |
| humanize | 739 | 1,664 | 1,718 | **3,382** | 13 | 58 | ~34 | ~5.0 h |
| python-tabulate | 2,579 | 3,222 | 6,078 | 9,300 | 13 | 26 | ~93 | ~11.6 h |
| **tqdm (current)** | 31,254 | 5,385 | 3,650 | **9,035** | 108 | — | 90 (actual) | ~11.4 h |

Estimated findings apply tqdm's observed 10/kLOC to total LOC; estimated first
pass applies the §2 cost model. Both are extrapolations from a single
observation and should be treated as ranking signals, not forecasts.

**Recommendation: `python-slugify`, with `humanize` as the second target.**

- python-slugify is ~5× smaller than tqdm at 1,758 LOC in 7 files, which is the
  single biggest lever on run length, and at 1,622 stars it is a real,
  widely-used package. Its risk is tag cadence: 48 tags exist but none fell in
  the 2024-06 → 2025-06 window I sampled, so the specific tag needs choosing by
  hand.
- humanize is the cleanest ground-truth story — 58 tags with releases every few
  months (4.10.0 2024-07-08, 4.11.0 2024-10-05, 4.12.0 2025-02-14), so
  "defects fixed after tag X" is a well-bounded set, and 4.11.0 is almost
  exactly contemporary with tqdm v4.67.0 (2024-10-28). It costs ~2 h more per
  run and is less popular.

There is a genuine trade-off here rather than a dominant option: python-dotenv
is by far the most popular of the small candidates (8,832 stars) but has sparse
tags; humanize has the best tags but the fewest stars. If popularity is
weighted as heavily as it was for tqdm, python-dotenv displaces slugify at a
cost of ~1.8 h per run.

**tqdm stays in the registry** as the realism target — periodic, accepted as
long. The fast target becomes the default for per-version regression runs.

---

## 4. Ground truth: the known defects at a tag

Choosing a historical tag is what makes assertion 2 checkable. The known
defects are whatever upstream fixed after it:

```bash
git log <tag>..<next-tag> --oneline
gh issue list --repo <owner>/<name> --state closed --search "closed:><tag-date>"
```

Each upstream fix maps to files, symbols, and usually a linked issue, giving
`eval/ground-truth/<target>-<tag>.toml`:

```toml
[[defect]]
id = "SL-001"
upstream_fix = "abc1234"
upstream_issue = 142
files = ["slugify/slugify.py"]
symbols = ["slugify"]
summary = "…"
```

Scoring matches `finding.location` against `defect.files` / `defect.symbols`:

- **recall** — known defects found ÷ known defects present ← *assertion 2*
- **precision proxy** — findings matching a known defect ÷ total findings
- **novel findings** — findings matching no known defect

The third bucket is not noise. Holtz audits documentation, test quality,
naming, and architecture; most of what it reports was never an upstream issue.
Report the three separately; never collapse them into one score. A version that
trades novel findings for recall has regressed even if recall rose.

**Contamination caveat.** Any popular public repo's post-tag fixes are likely in
training data. Work on benchmark memorisation finds exactly this — older,
widely-mirrored bug corpora show high n-gram reproduction and low negative
log-likelihood while newer ones do not, and the recommendation is to pair an
old benchmark with a fresher one rather than trust either. Recall is therefore
an optimistic bound. It is still valid for *regression* detection, which is
assertion 3's job: contamination is constant across Holtz versions, so a drop
in recall between versions is real signal even if its absolute level is
inflated.

---

## 5. The run record

One JSON per run, committed to this repo, tagged with the versions that
produced it:

```json
{
  "run_id": "2026-07-27-slugify-01",
  "target":   {"name": "python-slugify", "tag": "v8.0.1", "loc": 1758, "files": 7},
  "versions": {"holtz": "0.140.1", "sahjhan": "…", "claude_code": "…",
               "model": "claude-opus-5"},

  "completion": {"finalized": false, "stopped_at_state": "fix_loop",
                 "reason": "holtz_bug", "issue": 81,
                 "phases_reached": ["recon","audit","merge","fix_loop"],
                 "perspectives_completed": 0, "lens_rotations": 0},

  "bugs":     {"findings": 18, "by_severity": {...}, "by_category": {...},
               "resolved": 11, "deferred": 2,
               "ground_truth": {"known": 9, "found": 6, "recall": 0.67,
                                "novel": 12}},

  "coverage": {"graph_nodes": 96, "graph_edges": 141,
               "by_edge_type": {"calls": 70, "tests": 38, "imports": 18,
                                "assumes": 12, "diverges_from": 3},
               "by_node_type": {...}},

  "time":     {"wall_h": 5.1, "active_h": 3.0,
               "by_phase": {"recon": 0.5, "audit": 0.6, "merge": 0.2, "fix_loop": 1.7},
               "min_per_fix": 6.8,
               "tokens": {"output": 449653, "cache_read": 83246768}},

  "sessions": ["3579bb23", "f3cfa1d2"]
}
```

Every run is recorded, including partial ones. Runs stop when Holtz hits a bug —
measured: 11 `run_start`, 0 completions — so a harness that only records
finished runs would have no data at all. Partial runs still carry valid
coverage, timing, and per-fix rate.

### How each assertion is evaluated

| Assertion | Rule |
|---|---|
| 1. Completes | `completion.finalized` true. Until one run achieves it, the interim measure is depth: phases reached, perspectives completed, lens rotations. |
| 2. Finds what it should | `bugs.ground_truth.recall` against the tag's answer key, reported beside novel-finding count. |
| 3. No coverage regression | `coverage.graph_nodes` / `graph_edges` and the semantic edge types (`assumes`, `diverges_from`) versus the previous version on the same target+tag. A thinner graph on identical code means Holtz mapped less of it. |
| 3. No performance regression | `time.active_h` and `time.min_per_fix` versus previous versions on the same target+tag. |

Comparisons are only valid **within a target+tag**. Cross-target numbers rank
cost; they do not detect regressions.

---

## 6. Where the data comes from

All three metrics are already written to disk by a normal run. Nothing needs the
Claude Code SDK or an API key — which is what makes the no-SDK constraint cost
nothing but post-hoc collection.

**Bugs found** — `<target>/docs/holtz/runs/<N>/ledger.jsonl`, queried with
`sahjhan query --path <file> "<SQL>"`. Event types `finding` (with `id`,
`severity`, `category`, `location`, `perspective`, `predicted_by`),
`finding_resolved`, `finding_deferred`, `recon_finding`, `blast_radius`.
Verified against the tqdm run-1 ledger: 90 `finding`, 13 `recon_finding`, 150
events total.

**Impact graph** — `<target>/docs/holtz/impact-graph.json`, summarised by the
existing `skills/holtz/scripts/impact_graph.py … stats`. Verified: tqdm 298
nodes / 441 edges (`calls` 220, `tests` 122, `imports` 57, `assumes` 20,
`diverges_from` 8); Holtz's own graph 62 / 76 for comparison.

**Time spent** — `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`. Records
carry `timestamp`; assistant records carry `message.usage` with input/output/
cache token counts; records also carry `version`, `gitBranch`, `cwd`,
`sessionId`, `isSidechain`. The phase-attribution script that produced §2 is the
working prototype and becomes `eval/collect/timing.py`.

---

## 7. Layout and workflow

```
eval/
  README.md                    # the runbook: exactly what you type, in order
  targets.toml                 # repo, tag, ground-truth file, notes
  ground-truth/
    python-slugify-<tag>.toml
    tqdm-v4.67.0.toml
  bin/holtz-eval               # new-run | collect | score | report | bug
  collect/{ledger,graph,timing}.py
  score/match.py
  results/<target>/<run-id>.json
  REPORT.md                    # generated: the three time series
```

```bash
holtz-eval new-run slugify   # fresh clone at the tag, branch holtz-audit,
                             # record versions, print the command to run
# → open Claude Code in that directory, run /holtz
# → /clear when told, /holtz again          ← unchanged

holtz-eval bug               # when it breaks: bundle sahjhan status, recent
                             # ledger events, failing transition, versions,
                             # transcript excerpt into a filled-in issue
holtz-eval collect           # ledger + graph + transcripts → results/
holtz-eval score             # findings vs ground truth
holtz-eval report            # regenerate REPORT.md
```

How you drive Holtz does not change. The harness wraps the run rather than
automating it.

---

## 8. Variance

With a model in the loop, the same target at the same version gives different
results each run. 2026 agent-evaluation work quantifies this: single-trial
numbers hide large run-to-run spread, and reporting all-of-k reliability beside
any-of-k performance exposes gaps up to ~25 points.

For regression detection this matters concretely — a single run showing recall
0.67 → 0.55 is not evidence of a regression. `REPORT.md` should plot spread
across runs at a version, not a point, and a regression claim needs more than
one run behind it. On a ~3 h target that is affordable in a way it never was on
an 11 h one.

---

## 9. Open questions

1. **Which target**, given the popularity-vs-tag-cadence trade-off in §3, and
   **which tag** on it.
2. **Test-suite runtime** for each candidate — criterion 4, and the one number
   in §3 I did not measure, since it needs dependency installation. It multiplies
   by the fix count.
3. **Ground-truth scope** — every upstream fix after the tag, or a curated
   subset? Someone has to decide what counts as "present at the tag".
4. **Location matching granularity** — file-level is easy and noisy;
   symbol-level is accurate and needs name resolution.
5. **Retention** — tqdm transcripts alone are 178 MB. Results JSON is committed;
   raw transcripts probably should not be.

---

## Sources

- [Are Large Language Models Memorizing Bug Benchmarks?](https://arxiv.org/html/2411.13323)
- [SWE-bench Goes Live!](https://openreview.net/forum?id=OGWkr7gXka) — contamination-resistant, continuously refreshed tasks
- [Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents](https://arxiv.org/pdf/2603.29231)
- [ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions](https://arxiv.org/html/2601.06112)
- [Terminal-Bench 2.0](https://github.com/harbor-framework/terminal-bench) — pinned, reproducible environments with executable verifiers
- [AI Code Review Benchmark 2026: Precision, Recall, and F1](https://www.codeant.ai/blogs/ai-code-review-benchmark-results-from-200-000-real-pull-requests)
- [BugsInPy](https://dl.acm.org/doi/abs/10.1145/3368089.3417943) — per-bug Python checkouts, if a second ground-truth source is wanted

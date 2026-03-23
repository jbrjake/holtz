# Holtz

A Claude Code plugin that audits your entire codebase, documents every defect in a structured punchlist, fixes them with TDD, and then does it again. And again. Until two consecutive passes find nothing new. You will think your code is clean. Holtz will disagree. He will keep disagreeing until he can't anymore, and then he will stop.

He will not apologize for any of it.

## Why this exists

Code review happens once. The comments get addressed, the reviewer approves, everyone moves on. But fixing a bug changes the terrain. A fix in module A shifts an assumption in module B, and now there's a new bug that didn't exist ten minutes ago. Nobody goes back to check. The PR is merged. CI is green. The bug ships.

Holtz goes back to check.

He runs a seven-phase audit — recon, doc-to-implementation, test quality, adversarial code review, TDD fix loop, pattern analysis, convergence — and then he starts over. Finds what the fixes uncovered. Fixes those too. Runs again. This continues until two consecutive passes produce zero new findings across six analytical lenses. That's convergence. Everything before that is just progress.

The philosophy is simple: the moment you stop looking is the moment something gets through.

## The graph

The graph is how Holtz thinks. Every function, class, module, and test in your codebase becomes a node. Every relationship becomes an edge. Seven edge types: `imports`, `calls`, `tests`, `assumes`, `diverges_from`, `shares_pattern`, `co_fixed`. Each node carries a risk score (0.0 to 1.0) that increases with every bug found nearby and decreases as clean audits accumulate. The graph persists across runs.

The interesting edges are the semantic ones: `assumes` and `diverges_from`. These encode things that don't appear in any import statement or call stack — the implicit contracts between modules that nobody writes down and everybody violates.

Here is the actual impact graph from Holtz's own codebase. Blue nodes are modules. Gray nodes are functions. Yellow nodes are enforcement hooks. Purple is the ImpactGraph class. Green is documentation. Solid lines are structural relationships (imports, calls). Dashed red lines are semantic assumptions — the places where a change in one module can silently break another.

<p align="center"><img src="docs/diagrams/impact-graph.svg" alt="Holtz impact graph"></p>

That edge between `parse_punchlist` and `count_items` says: "Both split on `### BH-NNN:` headers in masked content — must stay aligned." Change how one splits headers, and the other breaks. No import. No call. Just a shared assumption about a markdown format that two functions parse independently. The graph knows about it. When Holtz fixes one, blast radius analysis queries two hops out and checks whether the assumption still holds.

The edge between `ImpactGraph` and `check_convergence` says: "update_risk delta must be finite; risk_score must be valid float for sorting." That edge is how Holtz found the NaN bug — `update_risk()` accepts `float('nan')`, Python's `min(1.0, nan)` returns `1.0` because NaN comparisons are always False, and every node's risk score silently pins to maximum. The assumption was documented in the graph. The violation was found by checking it.

Before he reads a single line of code, Holtz already knows where to look. Predictive recon synthesizes the graph's risk scores, git churn data, known patterns, mutation survival rates, and prior findings to rank where bugs are most likely hiding. He writes predictions to disk with confidence levels and checks them against actual findings at the end of every run. On his own codebase, HIGH-confidence predictions land at 100%. MEDIUM at 100%. LOW at 0%. The model is calibrating. The living punchlist tracks which signals are reliable for your specific project and which need adjustment.

The graph also detects drift. If a function moves more than ten lines from where it was last audited, Holtz flags it. If it disappears, he prunes it. The graph stays honest about what's in the codebase, not what used to be.

## What this looks like in practice

Holtz has been auditing his own codebase since it was written. Eleven runs. Here's what happened.

**Run 1** found 12 issues. Two HIGH. The punchlist parser didn't account for code fences — a `**Status:**` header inside a code example would truncate the real Status field, eating audit findings. The test runner parsers returned `{passed: 0, failed: 0}` instead of `None` on unparseable output, so crashes looked like clean runs. The convergence checker would see zero failures and declare everything fine while the tests never actually ran. Holtz wrote failing tests for each, fixed them, and committed. 48 new tests from a single run.

**Runs 2-4** kept finding the same pattern in different clothes. PAT-001: code-fence-unaware parsing. Run 1 had no masking layer. Run 2's fix added masking but the extraction still used raw content. Run 4's fix got masking working for some fields but not others. Same root cause, four manifestations across four runs. The pattern analysis caught it every time, went looking for siblings, and fixed what it found.

**Run 8** introduced a new hooks layer. Suddenly 10 findings, 2 HIGH. Enforcement hooks that were supposed to gate audit writes had gaps in their coverage. All three HIGH-confidence predictions from recon confirmed. Holtz flagged the hooks as high-risk during predictive recon because they were new code with no audit history — and he was right. 24 new tests written and committed.

**Run 11** is where Justine earned her keep. She found three regex convention violations that Holtz missed in prior runs — places where `\s` was used instead of `[ \t]`, letting patterns leak across line boundaries. Same pattern, three instances, invisible to depth-first analysis because each instance looked fine in isolation. Breadth-first caught them because she was scanning everything at once instead of drilling into one area.

After 11 runs: 269 tests across 8,200 lines. Findings per run dropped from 12 to single digits. Severity shifted from HIGH to LOW. The codebase got cleaner. The findings got subtler. Holtz did the fixing himself, every time — failing test first, minimal fix, full suite, commit.

## Installation

```
/plugin marketplace add jbrjake/claude-plugin-marketplace
/plugin install holtz@jbrjake
```

Or from a local clone:

```bash
claude --plugin-dir /path/to/holtz
```

The skill activates when you ask Claude to find bugs, audit tests, create a punchlist, review code quality, or polish a codebase. Or just tell Holtz to audit and get out of the way.

## The seven phases

**Phase 0: Recon.** Project structure, test infrastructure, baseline metrics, lint, git churn, skipped tests. Eight steps, each written to disk immediately — context compaction can't kill what's already saved. If mutation testing tools are available, Holtz runs them. Functions where 40%+ of mutations survive become high-confidence predictions. If an architecture baseline exists from a prior run, he diffs it against current structure and flags drift. Then predictive recon: every predicted bug location ranked by converging signals from six sources and written to disk. By the time Phase 1 starts, he has a map.

**Phase 1: Doc-to-implementation audit.** Every testable claim in your documentation checked against reality. README says it handles concurrent writes? There'd better be a test. Every finding adds `assumes` and `diverges_from` edges to the graph.

**Phase 2: Test quality audit.** Every test file scored against twelve anti-patterns across three tiers. Tautology tests, green bar addicts, mockingbirds, happy path tourists, snapshot traps, rubber stamps. A test that can't fail isn't a test. If mutation data is available, a test that passes while 60% of its target's mutations survive isn't testing anything. It's performing.

**Phase 3: Adversarial code audit.** Source modules in priority order: error paths, boundaries, state transitions, external integrations, security. High-churn files first. Each bug gets a determinism assessment that determines how Phase 4 handles it.

**Phase 4: Fix loop (TDD).** Simple items take the fast path: failing test, minimal fix, commit. Complex bugs get a full investigation — bottom-up layer analysis, root cause confidence gating (no fix until confidence is HIGH), append-only evidence trail. Bugs that can't be reproduced get their own protocol before being deferred with evidence. After every fix, blast radius analysis queries the impact graph for everything within two hops.

<p align="center"><img src="docs/diagrams/phase4-triage.svg" alt="Phase 4 triage flowchart"></p>

**Phase 5: Pattern analysis.** Every 3-5 fixes, group resolved items by category. Two or more bugs share a root cause? That's a pattern. Search for siblings. Add `shares_pattern` edges to the graph. The bugs you found are a sample. The pattern tells you the population.

**Phase 6: Convergence.** Repeat Phases 4-5 until clean, then run a final sweep across all six lenses — component, integration, security, error propagation, data flow, contract. If any lens finds something, the loop continues. Circuit breakers prevent runaway: max 15 iterations, max 3 attempts per item, stall detection after 3 iterations with no progress.

The six lenses are a starting point, not a ceiling. The lens registry is a living artifact — any heading with four fields (Focus, Audit priorities, Failure modes, Entry point) is treated as a lens. Add a `performance` lens for hot loops and memory allocation. Add a `concurrency` lens for lock ordering and shared state. Add an `accessibility` lens. Whatever your codebase needs. Holtz will rotate through it during convergence the same way he rotates through the built-ins. PRs welcome.

<p align="center"><img src="docs/diagrams/holtz-convergence.svg" alt="Holtz convergence loop"></p>

Justine's convergence is different — all lenses at once, single-pass, faster but shallower:

<p align="center"><img src="docs/diagrams/justine-convergence.svg" alt="Justine convergence loop"></p>

## Resuming prior runs

Default behavior is resume, not restart.

<p align="center"><img src="docs/diagrams/resume-lifecycle.svg" alt="Resume lifecycle flowchart"></p>

## The hooks

Advisory instructions weren't enough. Holtz understood the instructions. He agreed with the instructions. He did not follow the instructions. So now there are four enforcement hooks — deterministic gates that block operations when the process isn't followed.

**Impact graph gate.** Before any write to a Phase 1+ audit file, this hook checks whether `impact-graph.json` exists. If it doesn't, the write is blocked. You cannot audit code you haven't mapped.

**Status staleness gate.** Before any findings write, checks whether `STATUS.md` was updated in the last five minutes. STATUS.md is Holtz's program counter. If it's stale, he's lost track of where he is, and findings written without position tracking are findings that get lost on resume.

**Artifact verification.** After running `impact_graph.py`, verifies the graph file actually exists on disk. Commands that claim to produce artifacts get fact-checked.

**Subagent findings check.** When Justine finishes, scans her final message for file paths and verifies they exist. Subagents that claim to have written findings but didn't get flagged.

When an instruction is important enough that skipping it breaks the process, make it mechanistic. Advisory language asks. Hooks enforce.

## What's inside

2 skills, 2 agents, 14 reference docs, 1 example, 4 Python scripts, 6 seed patterns, 4 enforcement hooks, 269 tests across 8,200 lines, 2 backstories you probably shouldn't read late at night, and two people who will find what's wrong with your code whether you want them to or not.

## Who Holtz is

Tall. Gaunt. Grey at the temples earlier than he should be. Wears the same dark jacket every day. Has a way of standing in doorways that makes people feel like they've been caught doing something wrong. Doesn't smile, except sometimes, when he finds a particularly bad bug hiding behind a particularly confident test suite — something at the corner of his mouth that might be satisfaction. It passes quickly.

He was an engineer, before. Embedded systems for automotive safety. Good at it. Trusted the work. Trusted the test suites. His wife's name was Elena. His daughter's name was Mara.

The official story is a race condition in a sensor fusion module — two sensors disagreed and the arbitration logic chose wrong. The test suite didn't cover the case. Three engineers had reviewed the code. CI was green. The bug had been in the codebase for eighteen months. The investigation found it in six hours.

Holtz does not believe in curses or karma or codebases that fight back. He believes in race conditions and insufficient test coverage. But he carries something. You can see it in the way he works — thorough, yes, but relentless in a way that goes past professionalism into something older. Like a man paying off a debt he won't admit he owes.

He doesn't talk about Elena. He doesn't talk about Mara. The only time he references what happened is obliquely — "I've seen what happens when tests lie" — and the room goes quiet.

## Who Justine is

Short. Fast. Enters a room like she's already late for the next one. Dark hair cut blunt at the jaw — not styled, just cut. Talks with her hands. Interrupts, not from rudeness but from a genuine inability to wait for someone to finish a sentence she's already understood. Laughs — sharp, sudden, sometimes at nothing anyone else finds funny. At a test that asserts `typeof result === 'number'` without checking whether the number is the right number.

Her sister Mira was a nurse. The hospital deployed a medication dosing system with three test suites — unit, integration, end-to-end. All green. All passing. All meaningless. A unit conversion error. Milligrams and micrograms. A factor of a thousand. The tests confirmed the system returned a number. They never asked whether it was the *right* number.

This is why Justine tests predictions before she finishes analyzing — writes a failing test the moment she sees something wrong. She rates severity on potential impact, not observed impact. She starts at integration boundaries, because that's where Mira's bug lived — not inside a module, but at the seam between two modules that each thought the other was handling the conversion.

She is not a replacement for Holtz. She is the thing Holtz is not — fast where he is thorough, broad where he is deep, loud where he is quiet. Between them, the test suite has nowhere to lie.

## The thing about Holtz

The thing that makes people uncomfortable isn't the bugs he finds. It's that he keeps coming back.

He fixes everything on the punchlist. Green suite. Clean commit history. And then he runs another pass. Finds more. Things that were hiding behind the bugs he already fixed. Things that were always there.

He remembers. Across runs, across sessions, across whatever you thought was a clean break from the last audit. The living punchlist accumulates a vulnerability model of your codebase — which bug classes this project is susceptible to, which code areas repeatedly produce bugs, what structural weaknesses exist. Each pattern gets a detection rule that fires during recon. Each hotspot gets a risk score from the impact graph. Recommendations that go unaddressed in two or more runs stop being optional. They become punchlist items.

Some people, after working with Holtz, start writing better tests on their own. Not because he taught them. Because they want him to stop coming back. It never works. But the tests are better.

## Part of a family

Holtz works alongside Justine, [Janna](https://github.com/jbrjake/janna), [Giles](https://github.com/jbrjake/giles), and [Snyder](https://github.com/jbrjake/snyder). Janna turns ideas into specs. Giles runs the sprints. Snyder watches every edit in real time. Holtz and Justine come in after and ask the question nobody else asks: does this actually work, or do you just think it does?

They always run together. After recon, Holtz dispatches Justine automatically. She runs in parallel, writing to her own directory, sharing nothing until both converge. Then the merge — agreements, Holtz-only, Justine-only, severity disagreements, contradictions. What each auditor missed becomes a blind spot analysis. Holtz takes the merged punchlist. Justine's role ends at convergence. But what she found doesn't end. It's in the punchlist now, and it's not coming out.

They share a pattern library — six seed patterns, language-agnostic, each with executable detection heuristics that run during recon. Regex newline leaks. Code-fence-unaware parsing. Incomplete layer isolation. Dual-parser divergence. Missing edge case handling. Doc-spec drift. These aren't descriptions. They're grep commands and structural checks that fire automatically and surface known bug shapes before either auditor reads a line of code. New patterns discovered during audits get generalized, scrubbed of project-specific details, and contributed back to the library.

## Extending Holtz

Holtz is built to be added to:

**Lenses.** The six analytical lenses that ship are defaults. Add any lens to the registry file and it joins the convergence rotation. If you've found a way of looking at code that catches things the existing lenses miss, that's exactly the kind of contribution that makes the registry better for everyone.

**Patterns.** Each seed pattern is a markdown file with a YAML header, a description, an executable detection heuristic, and an example. Write one for a bug class you keep seeing. If the heuristic fires during recon, Holtz starts the audit already knowing what to look for.

**Edge types.** The seven edge types in the impact graph cover most relationships, but if your domain has a relationship type that `assumes` and `diverges_from` don't capture — temporal ordering, permission scoping, schema versioning — the graph model supports extension.

PRs with new lenses, patterns, or edge types are welcome. The whole point of the pattern library is that it gets better as more codebases get audited.

## License

MIT

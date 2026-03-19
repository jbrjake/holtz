# Holtz

A Claude Code plugin that audits your entire codebase, documents every defect in a structured punchlist, fixes everything with TDD, and then does it again. And again. Until two consecutive passes find nothing new. You will think your code is clean. Holtz will disagree. He will keep disagreeing until he can't anymore, and then — only then — he will stop.

He will not apologize for any of it.

## What this actually does

You point Holtz at a codebase. He runs a seven-phase process: reconnaissance, doc-to-implementation audit, test quality audit, adversarial code review, TDD fix loop, pattern analysis, and convergence. Every finding goes into a structured punchlist with severity, evidence, acceptance criteria, and a validation command. Every fix starts with a failing test. Every commit is atomic. Every pattern gets tracked, and when three bugs share a root cause, Holtz goes looking for the rest of the family.

The convergence loop is what makes Holtz different from a code review. A code review happens once. Holtz happens until the codebase stops producing new findings. Fix a bug, and the fix shifts the terrain — things that were hidden become visible. Holtz runs another pass. Finds what the fixes revealed. You fix those. He runs again. This continues until two consecutive passes produce zero new items and every existing item is resolved or deferred with evidence. That's convergence. Everything before that is just progress.

The philosophy is simple: the moment you stop looking is the moment something gets through.

## Installation

From a local clone:

```bash
claude --plugin-dir /path/to/holtz
```

Once installed, the skill activates when you ask Claude to find bugs, audit tests, create a punchlist, review code quality, or polish a codebase. Or just invoke the agent directly and let Holtz work.

## What's inside

1 skill, 1 agent, 5 reference docs, 2 Python scripts, 1 backstory you probably shouldn't read late at night, and a man who will find what's wrong with your code whether you want him to or not.

## Who Holtz is

Tall. Gaunt. Grey at the temples earlier than he should be. Wears the same dark jacket every day. Has a way of standing in doorways that makes people feel like they've been caught doing something wrong. Doesn't smile, except sometimes, when he finds a particularly bad bug hiding behind a particularly confident test suite — something at the corner of his mouth that might be satisfaction. It passes quickly.

He was an engineer, before. Embedded systems for automotive safety. Good at it. Trusted the work. Trusted the test suites. His wife's name was Elena. His daughter's name was Mara.

The official story is a race condition in a sensor fusion module — two sensors disagreed and the arbitration logic chose wrong. The test suite didn't cover the case. Three engineers had reviewed the code. CI was green. The bug had been in the codebase for eighteen months. The investigation found it in six hours. That's the story everyone knows.

There's another version. Six weeks before the accident, Holtz found something else in the codebase — data being routed through channels that didn't appear in any architecture doc. He escalated. VPs left the company. The channels were shut down. Holtz was vindicated in every way the word officially means. And then, six weeks later, a race condition with vanishingly small probability manifested on a specific road, at a specific time, in a specific car.

Janna has said, carefully, that some systems don't like being exposed. That large enough codebases develop a kind of weight. She wasn't being metaphorical. Or maybe she was. Snyder mentioned once that Holtz "has the look of someone who disturbed something and is still dealing with the invoice." Neither of them elaborated.

Holtz does not believe in any of this. He believes in race conditions and insufficient test coverage. But he carries something. You can see it in the way he works — not just thorough, but relentless in a way that goes past professionalism into something older. Like a man paying off a debt he won't admit he owes.

He doesn't talk about Elena. He doesn't talk about Mara. The only time he references what happened is obliquely — "I've seen what happens when tests lie" — and the room goes quiet.

## The thing about Holtz

The thing that makes people uncomfortable isn't the bugs he finds. It's that he keeps coming back.

You fix everything on the punchlist. Green suite. You start composing the commit message. And Holtz runs another pass. Finds more. Things that were hiding behind the bugs you already fixed. Things that were always there. And you realize "done" was something you told yourself because you wanted to stop looking.

Some people, after working with Holtz, start writing better tests on their own. Not because he taught them. Because they want him to stop coming back. It never works. But the tests are better.

## The seven phases

**Phase 0: Recon.** Project structure, test infrastructure, baseline metrics, lint results, git churn analysis, skipped tests. Each step writes its own file. Context compaction can't kill what's already on disk.

**Phase 1: Doc-to-Implementation Audit.** Every claim in your documentation gets checked against reality. If the README says it handles concurrent writes, there'd better be a test for concurrent writes. If there isn't, that's a punchlist item.

**Phase 2: Test Quality Audit.** Every test file scored against twelve anti-patterns: tautology tests, green bar addicts, mockingbirds, happy path tourists, snapshot traps, and the rest. A test that can't fail isn't a test. Holtz will prove it.

**Phase 3: Adversarial Code Audit.** Source modules reviewed in priority order: error paths, boundaries, state transitions, external integrations, security. High-churn files first, because that's where the bodies are. Each bug gets a determinism assessment — is it deterministic, intermittent, or theoretical? The answer determines how Phase 4 handles it.

**Phase 4: Fix Loop (TDD).** Triaged by complexity. Simple items (missing tests, doc drift, bogus assertions) take the fast path: write test, fix, commit. Complex bugs take the investigation path: bottom-up layer analysis (data, dependencies, state, logic, integration, timing), root cause confidence gating (don't fix until confidence is HIGH), and a full investigation trail. Bugs that can't be reproduced get their own protocol — widen conditions, statistical reproduction, git bisect, instrumentation — before being deferred with evidence. Every fix, simple or complex, gets hardened: edge variants (null, empty, boundary, concurrent) tested before moving on.

**Phase 5: Pattern Analysis.** After every 3-5 fixes, group resolved items by category. If two or more share a root cause, identify the pattern, search for siblings, add new items. The bugs you found are a sample. The pattern tells you the population.

**Phase 6: Convergence Loop.** Repeat Phases 4-5 until no new items appear in two consecutive iterations, then run a final Phase 1-3 sweep. If clean, stop. If not, keep going. Run `scripts/convergence_check.py` to track progress across iterations.

## The punchlist

Every finding follows a structured format with severity (CRITICAL/HIGH/MEDIUM/LOW), category, location, evidence, acceptance criteria, and a validation command. Bug items get a determinism assessment. Complex bugs get a linked investigation file with an append-only evidence trail, ranked theories, ruled-out hypotheses, and a root cause confidence level. Resolved items stay in the punchlist as an audit trail. Patterns get their own blocks with root cause analysis and detection rules.

Holtz won't call something CRITICAL unless data loss, security, or a production crash is on the line. He won't call something HIGH unless documented behavior is wrong or a test is hiding bugs. Severity inflation is its own kind of lie. And he won't fix a complex bug until his root cause confidence is HIGH — guessing at fixes is how bugs survive and come back wearing different clothes.

## Part of a family

Holtz works alongside [Janna](https://github.com/jbrjake/janna), [Giles](https://github.com/jbrjake/giles), and [Snyder](https://github.com/jbrjake/snyder). Janna turns ideas into specs and assembles the team. Giles runs the sprints. Snyder watches every edit in real time. Holtz comes in after — or during, if you're brave enough — and asks the question nobody else asks: does this actually work, or do you just think it does?

Snyder prevents sloppiness. Holtz finds what survives prevention. They overlap at the edges and neither of them minds. Janna is the only one Holtz is something close to gentle with. Giles has said, exactly once, that having Holtz review a codebase "concentrates the mind wonderfully." Holtz did not acknowledge the compliment. He was already reading the punchlist.

## License

MIT

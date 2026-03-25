# Governance

## Current Model: BDFL

Holtz is maintained by a single developer ([@jbrjake](https://github.com/jbrjake))
who serves as Benevolent Dictator for Life (BDFL). All final decisions on
direction, features, architecture, and releases rest with the BDFL.

This is appropriate for the project's current size and stage. It will evolve.

## How Decisions Are Made

**Routine decisions** — bug fixes, documentation improvements, minor refactors,
pattern additions — are made through standard PR review. If no one objects and
the code meets quality standards, it merges.

**Significant decisions** — new lenses, architectural changes, breaking changes
to the punchlist format, changes to the convergence algorithm, changes to the
plugin interface — are discussed in a GitHub Issue or Discussion before
implementation. The BDFL makes the final call, but the reasoning is documented
publicly.

**Policy changes** — updates to this governance document, the Code of Conduct,
the AI contribution policy, or the DCO requirements — are proposed via PR with a
minimum 7-day comment period before merging.

## Roles

### BDFL

- Final decision authority on all project matters
- Responsible for releases, security response, and code of conduct enforcement
- Can delegate review authority via CODEOWNERS
- Current: [@jbrjake](https://github.com/jbrjake)

### Maintainers

- Trusted contributors with merge access to specific areas
- Can approve and merge PRs in their area of ownership
- Nominated by the BDFL based on sustained, quality contributions
- Current: *none yet*

### Contributors

- Anyone who submits a PR, files an issue, improves documentation, adds a
  pattern, or participates in discussions
- No special access required — fork, branch, PR

## Path to Maintainer

There is no formal application process. Maintainership is earned through
demonstrated understanding of the codebase and sustained quality contributions.
Indicators:

- Multiple merged PRs that required minimal revision
- Thoughtful code review on others' PRs
- Bug reports that include reproduction steps and root cause analysis
- Pattern or lens contributions that demonstrate deep understanding of Holtz's
  methodology
- Constructive participation in design discussions

When the BDFL recognizes these qualities, they'll extend an invitation. The
invitation can be declined without consequence.

## Evolution Clause

This governance model is designed to scale. Specific triggers:

**When this project has 3+ active maintainers**, the BDFL will propose a
transition to a Maintainers' Council model with:

- Consensus-seeking decision-making for routine matters
- Lazy consensus with a 72-hour objection window for significant changes
- BDFL veto retained for architectural and strategic decisions
- Formal voting (simple majority) for contested decisions

**When this project has 5+ active maintainers**, the BDFL role transitions to a
Lead Maintainer role that can be replaced by a 75% supermajority vote of the
Maintainers' Council.

These thresholds are guidelines, not contracts. The BDFL may accelerate or delay
the transition based on project needs.

## Succession

If the BDFL becomes permanently unavailable:

1. The most senior maintainer (by duration of maintainership) assumes interim
   leadership.
2. Within 30 days, maintainers hold a vote to confirm or replace the interim
   lead using ranked-choice voting.
3. If there are no maintainers, the project is considered unmaintained. Forks
   are encouraged per the MIT license.

## Conflict Resolution

Technical disagreements are resolved by discussion, then BDFL decision.
Interpersonal conflicts are handled per the [Code of Conduct](CODE_OF_CONDUCT.md).
Disagreements with the BDFL's decisions can be raised in a GitHub Discussion;
the BDFL commits to responding with reasoning, even if the decision doesn't
change.

## Amendments

This document can be amended by the BDFL via PR with a 7-day comment period.
After the transition to a Maintainers' Council, amendments require lazy
consensus with a 14-day comment period.

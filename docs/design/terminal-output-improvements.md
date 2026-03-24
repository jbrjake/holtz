# Design Doc: Terminal Output Improvements

**Author:** Claude (Holtz run 14)
**Date:** 2026-03-24
**Status:** Proposal

## Problem

Holtz's terminal output is functional but flat. A user watching a run sees:
- Short status sentences ("Phase 0 complete. All 11 artifacts verified on disk.")
- Tool call indicators (collapsed in Claude Code UI)
- No structured visual hierarchy between phases, findings, or milestones

For a 7-phase audit that runs 30-60 minutes, the output doesn't give users a sense of progress, severity, or what matters. Someone scrolling back through a completed run can't quickly find where bugs were confirmed or what the final verdict was.

The reconstructed asciinema recording of run 14 made this obvious: the interesting moments (bug confirmations, prediction checks, merge blind spot analysis) look the same as the mundane ones (writing recon files, updating STATUS.md).

## Goals

1. A user watching a live run can tell at a glance: what phase they're in, what's been found so far, and whether the audit is going well or badly
2. A user reviewing a completed run can quickly find: findings, predictions, merge results, and convergence state
3. The output is useful in both interactive Claude Code (with expandable tool calls) and raw terminal playback (asciinema)
4. No changes to Holtz's actual behavior — this is purely output formatting

## Non-Goals

- Changing the SKILL.md or reference docs (those are instructions to the LLM, not user-facing output)
- Adding interactive UI elements (progress bars, TUIs) — Claude Code controls the chrome
- Real-time dashboards or web views

## Proposal

### Phase banners

At the start of each phase, emit a visually distinct banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PHASE 0: RECON                                          [103K tokens]
  8 steps — map the codebase before reading a line of code
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

When a phase completes, emit a summary line:

```
  ✓ Phase 0 complete — 37 nodes, 35 edges, 2 items escalated, 5 predictions
```

### Finding callouts

When a finding is confirmed (especially a bug), make it visually prominent:

```
  ██ BUG CONFIRMED: BH-004 (MEDIUM, bug/logic)
  ██ parse_brief field extraction leaks across fields on empty values
  ██ Predicted by: Prediction 1 (HIGH) — regex-newline-leak pattern library
```

Versus the current output which is just:
```
Both bugs confirmed. Let me add the actual code bugs to the punchlist.
```

### Prediction scorecard

After Phase 3, before the merge, show how predictions did:

```
  Predictions: 2/5 confirmed
    ✓ P1 (HIGH)  regex-newline-leak in parse_brief:53     → BH-004
    ✗ P2 (MED)   CRLF in header regex                     → not a bug
    ✓ P3 (MED)   code-fence-unaware in parse_brief        → BH-005
    ✗ P4 (HIGH)  README counts stale                      → counts correct
    ✗ P5 (LOW)   hook coverage artifact                   → not a real gap
```

### Merge summary

After adversarial merge, show the classification:

```
  ┌─ ADVERSARIAL MERGE ─────────────────────────────────────────┐
  │  Agreements:   2  (both found README metrics + \s convention)│
  │  Holtz-only:   3  (the actual code bugs)                    │
  │  Justine-only: 3  (doc ambiguity + design concerns)         │
  │  Contradictions: 0                                          │
  │                                                             │
  │  Blind spots:                                               │
  │    Holtz missed: README wording, hook design                │
  │    Justine missed: actual bugs (tested wrong edge cases)    │
  └─────────────────────────────────────────────────────────────┘
```

### Fix loop progress

During the TDD fix loop, show a running tally:

```
  FIX 1/8: BH-004 — parse_brief regex leak
    ✗ test_parse_brief_empty_field_value      FAIL (expected — TDD red)
    ✓ Fix: \s* → [ \t]* in _extract regex
    ✓ test_parse_brief_empty_field_value      PASS
    ✓ Full suite: 322 passed, 0 failed
```

### Convergence verdict

At the end:

```
═══════════════════════════════════════════════════════════════════════════
  CONVERGED

  8 findings (6 MEDIUM, 2 LOW) — all resolved
  324 tests passing | ruff clean | mypy clean | 67% coverage
  3 commits: f1b715b, e5e8b5b, cfcf762

  Context: 207,110 tokens | Cost: $110.99 (main) + $53.39 (subagents)
═══════════════════════════════════════════════════════════════════════════
```

## Implementation approach

This is entirely about what text Holtz emits between tool calls. The changes would go in the SKILL.md as output format instructions, similar to how the punchlist format is specified. No Python code changes needed.

Specifically, add a `references/output-format.md` that specifies:
- Phase banner format
- Finding callout format
- Prediction scorecard format
- Merge summary format
- Fix loop progress format
- Convergence verdict format

Then reference it from the main SKILL.md with: "Before emitting phase transitions, findings, or convergence results, read `references/output-format.md` for the required terminal output format."

## Tradeoffs

**Pro:** Makes runs watchable, reviewable, and demo-ready without post-processing. The asciinema of a run becomes a product showcase for free.

**Con:** Adds ~500 tokens to context for the output format reference. Adds 1-2 output lines per phase transition. Marginal context cost for significant UX improvement.

**Risk:** LLMs don't always follow formatting instructions precisely. Enforcement hooks could verify banner format but that's overkill. A "best effort" approach where the format is specified but not enforced is probably fine — occasional deviations in a live session don't matter.

## Open questions

1. Should phase banners include elapsed time? (Requires tracking, adds complexity.)
2. Should the convergence verdict include a diff link to the commits? (Nice but requires git remote detection.)
3. Should there be a "quiet mode" that suppresses banners for targeted/single-phase runs?

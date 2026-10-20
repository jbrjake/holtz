# Building release notes as a review instrument — what it actually did

**Written 2026-08-26**, after reviewing the v0.141.3 → 0.169.1 delta (93
commits) and being asked to build user-impact release notes "as an exercise"
and make sure they made sense said out loud.

This is an honest account of what that exercise changed, including where it
misled me. It is not a claim that the technique found the bugs. Mostly it
didn't.

---

## What actually happened, in order

Reconstructed from the session, not tidied:

1. Read the frozen spec, then `convergence-speed-status.md`.
2. Read `protocol.toml` and `transitions.toml`. Noticed the MEDIUM-budget
   arithmetic looked one-directional, and that `all_findings_closed` was still
   on `set complete perspective`.
3. Read `phase-fix-loop.md`. Noticed Step 11 calls staying in `fix_loop` the
   *usual* path, which means `pattern_done` — where the breaker sits — is the
   exception.
4. Read `step-10-fix-loop.md`. Found it contradicting `phase-fix-loop.md` on
   three points about the fix subagent.
5. **From that contradiction**, asked what an actor-scoped TDD gate means with
   three agents in flight, and hypothesised the `since = "last_transition"`
   window was still run-global.
6. Proved four things against a real daemon.
7. *Then* wrote the release notes.

So the notes did not generate the findings. Every P0 was already on the page
when I started writing them. Any account that says otherwise is a story fitted
after the fact, which is the failure mode this repo has a memory about.

What the notes did was different, and worth naming precisely.

---

## What the exercise actually contributed

### 1. It supplied a ranking principle where I had none

Before the notes I had roughly seventeen findings and no ordering except my own
sense of severity, which is unreliable and unauditable. The notes gave an
external one: **a finding matters in proportion to how many user-visible claims
it falsifies.**

`all_findings_closed` on `set complete perspective` moved from "an
inconsistency I noticed while reading TOML" to P0 under that rule, because it
falsifies the headline claim of the whole release. Nothing about the finding
changed. The rule for sorting did.

### 2. It forced claims to be *complete*, which exposed coupling

A correctness question is local: is this gate right? A release-notes sentence
is global: *"convergence no longer requires an empty board."* That sentence is
falsified by any door to convergence that still requires one — so writing it
compelled me to enumerate every door, not just the one the commit touched.

The ×13 multiplication (thirteen lens completions upstream of `converge`) was
visible in `transitions.toml` the whole time. It only became *the point* when a
sentence depended on it.

### 3. It made the through-line visible

As a list, the seventeen items are unrelated. As release notes, four of five
headline sentences break on the same thing: a skill file that still describes
the pre-release protocol. "The engine half shipped and the teaching half
didn't" is not a property of any individual finding. It is only visible after
sorting by user-facing claim, and it changes the fix strategy — one doc sweep
commit instead of seven scattered patches.

### 4. It changed what counted as "done"

A defect list lets you mark something SHIPPED when the code works and the tests
pass. P0.3 genuinely is that: implemented, tested, proven against a real
daemon and a real pair of worktrees. The status doc is not lying.

But you cannot write P0.3's release note truthfully. **The gap between "works"
and "is narratable" is where three of the four P0s live**, and only the second
standard finds them.

### 5. "Say it out loud" did specific, non-decorative work

The written sentence *"Fix loop now runs three-wide"* looks fine on the page.
It breaks when you ask the next question a listener would ask — *"and what
happens when the first one finishes?"* Reading aloud imposes a listener, and a
listener asks the obvious follow-up that a reader skips. That is the whole
mechanism; it is not a style note.

### 6. It gave the good parts somewhere to live

A defect list has no slot for "this part is fine," so a review that produces
only a defect list implies everything is broken. The notes let me record that
reachability routing and `holtz-start`/`holtz-stop` survive intact — and that
mattered, because it is what licensed the diagnosis "systematic, in the docs"
rather than "diffuse, in the quality." A failure that has a shape is a failure
you can schedule.

---

## Correction, 2026-08-27

This note was written after one pass. A second, adversarial pass — the one §5
of "What I would keep" says to do and which the first pass did not actually run
— found two P0s the release-notes frame could not see, and both are worse than
anything the frame ranked:

- **Any CRITICAL closes with one agent command** (`sahjhan event
  finding_deferred --field reason=theoretical`), while `protocol.toml` argues
  at length that the word is machine-written. Two shipped tests exercise the
  forged path and assert it is correct.
- **The TDD courier stamps one agent's `agent_id` onto another agent's failing
  test**, and the second agent gets no evidence row at all — a bypass of the
  gate P0.3 exists to make actor-specific, firing on the first pair of
  concurrent fix subagents.

That changes two of this note's conclusions, and understates a third.

**§"It gave the good parts somewhere to live" over-claimed.** It says recording
what survives is "what licensed the diagnosis *systematic, in the docs* rather
than *diffuse, in the quality*." That diagnosis was wrong, and the licence was
the problem: a survey that can only see user-facing claims will always conclude
the defects are in the teaching layer, because the teaching layer is the only
layer it looks at. A frame that cannot see a class of defect will reliably
report that class is absent.

**§"Where the exercise misled me" understated the failure.** It says the frame
"biases toward user-visible defects and buries latent ones," and offers
`merge_finding` as the example — a finding it did at least *rank*. The real
failure is stronger: the frame did not surface items 18 and 19 **at all**.
`merge_finding` being sorted to P2 is a mis-ranking; those two are an omission,
and an omission is not fixed by re-weighting.

**The sharpest lesson generalises further than this note took it.** §"The
sharpest thing I learned" is about the *status doc* — a well-reasoned
justification discouraging the reader from checking whether the reasoning was
applied everywhere it holds. The same hazard is worse in `protocol.toml`, where
the comments are longest, densest, and sit directly above the predicate they
describe. Items 18, 21 and 24 are all one shape: **a long correct-sounding
comment next to a predicate weaker than the comment.** The comment is what a
reviewer reads; the predicate is what runs. Reading them as two independent
claims and diffing them is a cheap, mechanisable pass, and it is the one that
found the two P0s.

---

## Where the exercise misled me, and I should say so

### It biases toward user-visible defects and buries latent ones

`merge_finding` has no relatedness or severity constraint, so a CRITICAL can be
closed by merging it into any unrelated finding, and `all_critical_resolved`
clears. That is an integrity hole in the gate the protocol treats as
non-negotiable.

It got ranked **P2**.

Why: nobody writes the release note *"you can now close a CRITICAL by merging
it into a typo."* There is no user-facing sentence for it, so the ranking
principle from §1 had nothing to weigh, and it fell to the bottom. On integrity
grounds it belongs well above several P1s.

**The lesson is that the release-notes frame is a good sort key for
deliverability and a bad one for integrity.** A review that uses it needs a
second pass that asks the adversarial question directly — *what can a
sufficiently motivated agent do to this gate?* — because the frame is
structurally blind to answers nobody would advertise.

### It rewards a tidy narrative, and I nearly wrote one

Section "what actually happened" above was, in draft, a much better story in
which the notes discovered the TDD-window bug. They didn't. The frame's pull
toward a clean causal arc is real and it points away from accuracy.

---

## The sharpest thing I learned, which is about the status doc

`convergence-speed-status.md` says of P0.1:

> `all_findings_closed` is **removed** from `converge` — leaving it would keep
> the unreachable requirement and make the conjuncts decoration; a test fails
> the build if it returns.

Every clause is true. The reasoning is correct. There is a test enforcing it.
And the conclusion — that the conjuncts are therefore not decoration — is
false, because the argument was applied at one site and holds at two.

This is a specific epistemic hazard, and it is more dangerous than a wrong
justification: **a well-reasoned justification for a change discourages the
reader from asking whether the reasoning was applied everywhere it holds.** The
better the argument, the more completely it closes the question in the reader's
mind. I read that row three times before I checked whether the same predicate
appeared elsewhere, and I only checked because a *different* frame — the
release note — required me to enumerate every door.

That generalises past this review: **two descriptions of the same work in
different registers disagree in useful places.** The status doc and the release
notes describe the same 93 commits. Where they disagree is where the work is
not actually finished. That disagreement is cheap to produce and it is not
something a test can generate, because both descriptions are written by people
who believe them.

Concretely, for this repo: the status doc's per-clause register is excellent
for accountability and structurally unable to catch a gate deleted from one
transition and left on another. Something has to hold the whole state machine
at once. A release-notes pass is one cheap way; so is a generated "every route
to state X" report, which would be the mechanised version of the same idea and
would have found P0-3 without a human reading anything.

---

## What I would keep

1. Write the notes **after** the findings, not before. They are a sort and a
   completeness check, not a discovery method.
2. Write one sentence per headline claim, then try to falsify each one against
   the tree. The falsification is the whole product.
3. Read them aloud. The listener's next question is the test.
4. Record which claims **survive**. It is what turns a list into a diagnosis.
5. **Then do a second, adversarial pass that ignores user-visibility entirely**,
   because step 2 cannot see the defects nobody would ever advertise. This is
   not optional and it is not a tiebreak for ranking — it is where the worst
   findings come from. Run it before the punchlist is ordered, not after.
   Concretely, three questions the notes cannot ask:
   - For every gate that filters on a literal field value: *can the agent type
     that value?* (found item 18)
   - For every courier that writes evidence: *what happens with two actors?*
     (found item 19)
   - For every long justifying comment: *does the predicate below it do what
     the comment says?* (found items 18, 21, 24)
6. **Do not let the notes produce the diagnosis.** They produce a *sample* of
   defects, biased by construction. "The engine shipped and the teaching
   didn't" was a true statement about the sample and a false statement about
   the release.

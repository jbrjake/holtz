# Case study: How an AI bug hunter found a GPU race condition in an epilepsy protection system

**Date:** 2026-03-22
**Project:** Timbre (real-time macOS music visualizer)
**Holtz version:** Pre-enforcement (no Sahjhan)
**Discovery:** Phase 3 adversarial subagent, lateral pivot off priority list

## What happened before

Three days before this audit, the developer had been running AI-assisted sprint
sessions to build Timbre, a real-time macOS music visualizer. The app captures
microphone audio, runs spectral analysis, and renders GPU-driven visuals at
60fps via Apple's Metal framework.

After three sprints, the project had 624 passing tests and zero failures.

The app launched to a black screen.

The developer's messages to the AI assistant during that session:

> *"I still get a blank window when I open the app"*
>
> *"Still a black screen"*
>
> *"Even now, it's still broken. There are new messages in the log. The log
> which I guess you didn't look at... immediately after I told you always to
> look at the logs."*
>
> *"You don't check anything. You just say you understand."*

Every subsystem had been individually built and tested. None of them had been
wired together into a working pipeline. The test suite verified that each
component ran without crashing, but never checked whether the full app produced
visual output. 624 tests, a green CI badge, and nothing on screen.

---

## The invocation

The developer launched Holtz, an autonomous bug-hunting agent, with this command:

```
/holtz:holtz focus on integration and end to end issues until the app is
displaying correctly on screen and that can be programmatically validated
without a human in the loop
```

That prompt says: focus on integration, make the display work, make validation
automatic.

It says nothing about AccessibilityClampPass. Nothing about buffer counts.
Nothing about race conditions, semaphores, flash rate limiting, or epilepsy
protection.

The GPU race condition was found without any direction from the user.

---

## What Holtz is, briefly

Holtz is a Claude Code plugin that runs structured, multi-phase code audits. It
dispatches subagents for parallel work, writes findings to disk as it goes, and
iterates until consecutive passes produce no new findings. For this audit, it
dispatched 8 subagents:

| Phase | What it does | Time |
|-------|-------------|------|
| 0a-0f | Recon: map architecture, catalog tests, analyze git churn, find skipped tests | 4 min |
| 1 | Check whether documentation claims match the code | 4 min |
| 2 | Audit test quality: find rubber stamps, shallow tests, missing integration tests | 5 min |
| 3 | Adversarial code review: race conditions, error paths, state consistency, resource leaks | 9 min |
| Justine | Independent parallel audit by a second auditor | 7 min |

The Phase 3 adversarial subagent is the one that found the GPU race. It was
given 8 priority files to review. AccessibilityClampPass was not one of them.

---

## The bug

Timbre's rendering pipeline includes a component called AccessibilityClampPass.
It enforces WCAG 2.3.1 compliance: the web accessibility standard that protects
people with photosensitive epilepsy from rapid brightness changes. Each frame,
the clamp reads back a luminance value from the GPU and dampens the output if
brightness is changing too fast.

If this component fails silently, the visualizer can produce unclamped strobing,
which is the kind of content that triggers seizures.

The clamp uses **2 GPU readback buffers** (double-buffered). The rendering
pipeline allows **3 frames in flight** simultaneously (triple-buffered via a
semaphore). Two buffers cannot safely serve three concurrent frames. When frame 3
begins encoding while frame 1 is still running on the GPU, the CPU reads a
buffer that the GPU hasn't finished writing to. The luminance value is corrupted.

A second bug on the same root cause: the CPU zeros the write buffer before each
frame. With 2 buffers and 3 inflight frames, the CPU can zero a buffer the GPU
is still performing atomic additions into.

Both bugs corrupt the luminance value that feeds the flash rate limiter. A wrong
value means the limiter either misses a flash event (dangerous) or triggers when
it shouldn't (annoying but harmless).

---

## How it was found: step by step

This is reconstructed from the subagent's JSONL session log
(`agent-a8ee6809859785f1b.jsonl`, 241 lines).

### Step 1: Read the recon summary

Phase 0 had already mapped the architecture. The recon summary describes the
rendering pipeline:

> *"...renders at 60Hz via CADisplayLink (RenderCoordinator -> RenderPipeline ->
> FeedbackWarpCore + post-processing -> AccessibilityClampPass -> P3 blit ->
> TimbreView)"*

AccessibilityClampPass shows up in the pipeline description. The auditor now
knows it exists, but it's not a priority target.

### Step 2: Read the 8 priority files

The subagent reads all 8 assigned files in parallel batches. While reading
RenderCoordinator.swift, it sees:

```swift
private let inflightSemaphore = DispatchSemaphore(value: 3)
// Triple-buffer semaphore: allows up to 3 frames in flight
```

The number 3 is in memory. The auditor doesn't know it matters yet.

### Step 3: Work through other integration bugs

The subagent runs grep searches across the codebase for error paths, teardown
patterns, delegate lifecycle issues, audio threading concerns. It finds bugs in
other components (ARC violation in MicrophoneCapture, missing orchestrator
teardown, silent frame degradation on encoder failure). It has not yet looked at
AccessibilityClampPass.

### Step 4: The lateral pivot

While examining TripleBuffer for a large-struct copy concern, the auditor's
reasoning shifts:

> *"Now let me examine the TripleBuffer more carefully for the large-struct copy
> concern, and also check what happens in the accessibilityClamp pass."*

This is the moment. The auditor is not following its checklist. It's following
the data flow through the pipeline. TripleBuffer feeds RenderPipeline, which
calls AccessibilityClampPass. The chain pulls it to the next component.

AccessibilityClampPass was reached by following the pipeline, not from the
priority list.

### Step 5: Read AccessibilityClampPass.swift

The subagent reads the full file. In the code, these comments appear:

```swift
/// Double-buffered luminance sum buffers for GPU readback.
/// We use two buffers to avoid reading a buffer that the GPU is currently writing to.
/// On frame N, the GPU writes to buffer[N % 2]; the CPU reads from buffer[(N-1) % 2].
```

The number 2 is in memory. And the auditor already has the number 3 from
40+ tool calls ago in a different file.

### Step 6: Suspicion crystallizes

The auditor's reasoning:

> *"The CPU reads the previous frame's buffer, but the GPU command buffer for
> that previous frame might not have completed yet."*

2 buffers. 3 frames in flight. The auditor recognizes the mismatch.

### Step 7: Read the encode method

The subagent reads the critical section (lines 349-393):

```swift
func encode(into commandBuffer: MTLCommandBuffer, frameCount: UInt64, ...) {
    let readIndex = Int((frameCount - 1) % 2)
    let readBuffer = luminanceSumBuffers[readIndex]
    let luminanceSum = readBuffer.contents().load(as: Float.self)  // CPU reads

    // ... luminance comparison and clamping logic ...

    let writeIndex = Int(frameCount % 2)
    let writeBuffer = luminanceSumBuffers[writeIndex]
    writeBuffer.contents().storeBytes(of: Float(0), as: Float.self)  // CPU zeros

    // ... GPU shader dispatched to write luminance sum ...
}
```

### Step 8: Frame-by-frame arithmetic proves the race

```
Frame 0: GPU writes buffer [0%2 = 0].  CPU reads nothing (first frame).
Frame 1: GPU writes buffer [1%2 = 1].  CPU reads buffer [(1-1)%2 = 0].  Frame 0 done by now. Fine.
Frame 2: GPU writes buffer [2%2 = 0].  CPU reads buffer [(2-1)%2 = 1].  Frame 1 still running.
```

With 3 frames in flight, frames 0, 1, and 2 can all be executing at once. When
frame 2 encodes, it reads buffer 1, which frame 1 is still writing to. The race
condition is proven by arithmetic.

### Step 9: Discover the second bug

The same root cause creates a write-write race. Before encoding frame N, the CPU
zeros the write buffer. The write buffer for frame N uses index `N%2`. The write
buffer for frame N-2 uses index `(N-2)%2`, which equals `N%2`. Same buffer. If
frame N-2's GPU work hasn't finished, the CPU zeros a buffer the GPU is actively
adding to.

### Step 10: Classify and write findings

Both bugs written to the punchlist as BH-200 and BH-214. Classified HIGH
severity, bug/concurrency, intermittent. The status file notes: "Safety-critical
BH-200/214 recommended as next fix."

---

## Why this is hard to find

**Invisible to unit tests.** AccessibilityClampPass has its own tests. They
pass. Unit tests process one frame at a time and never create the 3-inflight
condition that exposes the race.

**Invisible to single-file code review.** The bug is the interaction between
two numbers in two different files: `DispatchSemaphore(value: 3)` in
RenderCoordinator.swift and 2 luminance buffers in AccessibilityClampPass.swift.
Neither file is wrong on its own. The mismatch only appears when you hold both
numbers and do the math.

**Intermittent.** The race fires when frame N-2's GPU work hasn't finished by
the time frame N starts encoding. On a fast GPU with light shaders, it might
never happen. Under load, it could happen every few seconds.

**Silent.** No crash, no error, no assertion. The luminance value is just wrong:
too high, too low, or partially written. The flash limiter makes a slightly wrong
decision. Unless you're photosensitive, you wouldn't notice.

**Requires knowledge of three systems.** Metal's asynchronous GPU scheduling,
semaphore-based frame pacing, and double-buffered CPU readback. The bug lives in
the interaction between all three.

---

## What the auditor did that a human reviewer might not

**Followed the pipeline off-list.** The 8-file priority list didn't include
AccessibilityClampPass. The auditor followed the data flow from TripleBuffer
through RenderPipeline and naturally arrived at a file that wasn't assigned.

**Connected numbers across files.** The semaphore value (3) was read 40+ tool
calls earlier in a different file. When the buffer count (2) appeared, the
auditor connected them. That's cross-file correlation over a long context window.

**Checked the code's claim against the math.** The comment says "we use two
buffers to avoid reading a buffer the GPU is writing to." The auditor didn't
trust the comment. It traced the modular arithmetic through 3 frames and proved
the comment's guarantee doesn't hold.

**Found the second bug on the same root cause.** After proving the read-write
race (BH-200), the auditor looked at the CPU zero-before-write and recognized
the same buffer overlap applies there too (BH-214).

---

## The fix

Match the buffer count to the inflight frame count:

```swift
// Before: 2 buffers for 3 inflight frames
luminanceSumBuffers = [makeBuffer(), makeBuffer()]

// After: 3 buffers for 3 inflight frames
luminanceSumBuffers = [makeBuffer(), makeBuffer(), makeBuffer()]
```

Or add fence synchronization so the CPU waits for the GPU to finish before
reading or zeroing a buffer.

---

## What else the audit found

In the same session, Holtz and Justine produced 30 punchlist items total:

| Category | Count | Highlights |
|----------|-------|-----------|
| Test quality | 14 | All 21 rendering tests check "did it run" but never "what did it render" |
| Adversarial | 16 | GPU race (this case study), missing teardown, ARC on audio thread, resize never propagated |
| Integration gaps | 3 | No full-pipeline test, orchestrator untested, CI skips all GPU tests |
| Systemic patterns | 3 | GPU Rubber Stamp, Tested-But-Unwired, Missing Resize Propagation |

The "624 tests pass, app shows black screen" problem from the prior session was
explained by PAT-002: Tested-But-Unwired. Subsystems were individually tested
but never connected through the composition root.

---

## Appendix A: Technical detail on the race condition

### Buffer indexing

```
AccessibilityClampPass maintains:
  luminanceSumBuffers: [MTLBuffer]  // .shared Metal buffers (CPU+GPU visible)
  Count: 2 (double-buffered)

Per frame N:
  writeIndex = N % 2        // GPU writes luminance sum here
  readIndex  = (N-1) % 2    // CPU reads previous frame's result here

RenderCoordinator maintains:
  inflightSemaphore = DispatchSemaphore(value: 3)
  // Up to 3 command buffers in flight at once
```

### The read-write race (BH-200)

```
Time ->

Frame 0: [GPU writes buf 0]  [completes]
Frame 1: [GPU writes buf 1]  [still running...]
Frame 2: [CPU reads buf 1 <-- RACE]  [GPU writes buf 0]

Frame 2 begins encoding while Frame 1 is still on the GPU.
Frame 2's CPU read targets buffer (2-1)%2 = 1.
Frame 1's GPU write targets buffer 1%2 = 1.
Same buffer. CPU reads partially-written data.
```

### The write-write race (BH-214)

```
Before encoding frame N, CPU zeros the write buffer:
  writeBuffer.contents().storeBytes(of: Float(0), as: Float.self)

Write buffer for frame N:   index N%2
Write buffer for frame N-2: index (N-2)%2 = N%2  (same buffer)

If frame N-2 is still executing on GPU:
  CPU zeros buffer -> GPU atomic-adds to buffer -> partial sum corrupted
```

### Metal memory model

The buffers use `.shared` storage mode: unified memory accessible to both CPU
and GPU. On Apple Silicon, this is physically the same RAM. There is no implicit
synchronization between CPU and GPU access. Synchronization only comes from
command buffer completion handlers or MTLFence, neither of which is used here.

---

## Appendix B: The subagent's exact prompt

The Phase 3 adversarial subagent received this:

> You are running Phase 3 of a Holtz audit on the Timbre project (Swift/Metal
> real-time music visualizer for macOS). Focus: adversarial review of
> INTEGRATION code paths.
>
> Perform an adversarial code review of the integration seams. For each file,
> look for:
> - Error paths that silently swallow failures
> - Race conditions or thread safety issues
> - State that can become inconsistent
> - Resource leaks (Metal textures, command buffers)
> - Assumptions that could be violated by upstream changes
> - Missing validation at boundaries
>
> Priority files to review:
> 1. TimbreOrchestrator.swift
> 2. TimbreAppMain.swift
> 3. RenderPipeline.swift
> 4. RenderCoordinator.swift
> 5. TripleBuffer.swift
> 6. SPSCRingBuffer.swift
> 7. FeedbackWarpCore.swift
> 8. PingPongFramebuffer.swift

AccessibilityClampPass.swift is not in this list. The prompt mentions "race
conditions" as one of six categories, but says nothing about buffers, semaphores,
inflight frames, luminance, or flash rate limiting.

---

## Appendix C: What the invocation asked for vs. what was found

| What the user asked about | What Holtz found |
|---------------------------|------------------|
| "integration issues" | 30 integration-seam findings |
| "app displaying correctly" | All rendering tests are rubber stamps |
| "programmatically validated" | Built a full-pipeline integration test |
| (nothing about safety) | GPU race in epilepsy protection system |
| (nothing about buffers) | 2 vs 3 buffer mismatch via lateral exploration |
| (nothing about AccessibilityClamp) | Found it by following the pipeline chain |

---

## Appendix D: Session artifacts and file locations

| Artifact | Path |
|----------|------|
| Main session | `~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-timbre/ee2f6877-e934-43b0-b4bc-ea9e564458a3.jsonl` |
| Phase 3 subagent (found the bug) | `ee2f6877.../subagents/agent-a8ee6809859785f1b.jsonl` |
| Justine subagent (parallel audit) | `ee2f6877.../subagents/agent-ab75e287536f97306.jsonl` |
| Adversarial audit writeup | `timbre/docs/holtz/audit/3-adversarial.md` (lines 9-28, 258-274) |
| Punchlist | `timbre/docs/holtz/PUNCHLIST.md` (BH-200 at line 65, BH-214 at line 68) |
| Recon summary | `timbre/docs/holtz/recon/0g-recon-summary.md` |
| Predictions | `timbre/docs/holtz/recon/0h-predictions.md` |
| Churn analysis | `timbre/docs/holtz/recon/0e-churn.md` |
| Test infrastructure map | `timbre/docs/holtz/recon/0b-test-infra.md` |
| Status file | `timbre/docs/holtz/STATUS.md` |
| Preceding session (black screen) | `~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-timbre/743ac269-0d92-4438-a190-1ff32f79afce.jsonl` |

---

## Appendix E: Timeline

```
2026-03-19  Sprint sessions. 624 tests pass. App shows black screen.
            "still a black screen", "you don't check anything"

2026-03-22
  22:26     /holtz:holtz invoked
            "focus on integration and end to end issues..."

  22:26     Phase 0 recon dispatched (4 subagents in parallel)
            Project overview, test infra, git churn, skipped tests

  22:28     Recon complete. 8 predictions generated.
            None mention AccessibilityClampPass.

  22:33     Phase 1 (doc claims), Phase 2 (test quality), Justine dispatched

  22:34     Phase 3 adversarial subagent dispatched
            Given 8 priority files. AccessibilityClampPass not on the list.

  22:35     Reads all 8 priority files
            Notes DispatchSemaphore(value: 3) in RenderCoordinator.swift

  22:37     Investigating TripleBuffer copy cost
            Lateral pivot: "also check what happens in the accessibilityClamp pass"

  22:38     Reads AccessibilityClampPass.swift
            2 buffers vs 3 inflight frames
            "The CPU reads the previous frame's buffer, but the GPU command buffer
             for that previous frame might not have completed yet."

  22:39     Confirms inflight count via grep
            Frame-by-frame arithmetic proves overlap at frame 3

  22:40     Writes BH-200 (read-write race) and BH-214 (write-write race)
            HIGH severity, intermittent, safety-critical

  22:43     Phase 3 completes. 16 findings total.

  23:05     STATUS.md written.
            "Safety-critical BH-200/214 recommended as next fix."
            30 punchlist items across all phases. 3 systemic patterns.
```

Invocation to discovery: ~12 minutes.
Lateral pivot to confirmed race: ~3 minutes.

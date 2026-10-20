---
id: ho-nkq5p22
title: Run one Holtz audit end to end on v0.170.15
category: functional
labels: [owner-call]
seq: 30
needs: [ho-83hj0mk]
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#p1--before-functional-testing
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-nkq5p22-run-one-holtz-audit-end-to-end-on-v0-170-15.md /^- 2026-\d\d-\d\d owner confirmed/
---
No audit has run end to end on this release; the release notes say so under
"known gaps". P1's band is "before functional testing", and that run is still
owed.

Owed to this run by their own units:

- **W22 / item 27** — on the seccomp-confined Linux session (the `needs`
  edge). D-h: every other P1 unit runs on that configuration too, in particular
  W02's worktree fixture (F1) and W22's own probe path. A macOS-only run leaves
  item 27's reason for being untested.
- **W11 / item 42** — drive one real per-actor `enforcement_merge`. The
  interleave tests run against `MockEnforcementDaemon`, a case-by-case port of
  `sahjhan/src/daemon/enforcement.rs` pinned by `TestTheMockMergesLikeTheEngine`.
  No test can do better: the daemon authenticates callers by content hash, so a
  test process is refused (`auth_failed`), and the only authenticated route is
  a hook subprocess whose read and write are atomic end to end.
- **GitHub #73's quiz path** waits on this run.

Also carried, with no route named:

- **W07 / item 3** — `fix_commit` as an escape is asserted structurally, never
  driven. A real daemon refuses `enforcement_write` from a test process, so no
  test can write the `suite_green` its gate reads. Its other two routes
  (`theoretical`'s courier, `fault_injected`'s hardening batch) are driven end
  to end against the real daemon.

Do not read the green suite as having covered any of these.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

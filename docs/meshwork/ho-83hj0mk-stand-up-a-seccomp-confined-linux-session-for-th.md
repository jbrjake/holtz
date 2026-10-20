---
id: ho-83hj0mk
title: Stand up a seccomp-confined Linux session for the functional run
category: functional
labels: [owner-call]
seq: 20
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w22--item-27-boundary_checkpy-crashes-on-the-one-platform-path-its-docstring-calls-confinement
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-83hj0mk-stand-up-a-seccomp-confined-linux-session-for-th.md /^- 2026-\d\d-\d\d owner confirmed/
---
D-h (RULED, Jon, 2026-08-27) put item 27 in Tier A, which makes Linux with the
optional `@anthropic-ai/sandbox-runtime` seccomp filter a target for the next
functional run. W22's unit treats standing that session up as a prerequisite
of the functional run.

Nothing says how the session gets stood up or who does it — that is the first
question here, and it is the owner's.

CI is `ubuntu-latest` (`.github/workflows/ci.yml`), which covers Linux and not
seccomp: the filter is not installed there. W22's fix (`6852e0d`) and its two
tests inject the errno on macOS; nothing has executed under a real seccomp
filter.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

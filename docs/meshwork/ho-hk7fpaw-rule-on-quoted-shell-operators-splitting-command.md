---
id: ho-hk7fpaw
title: Rule on quoted shell operators splitting command segments
category: rulings
labels: [owner-call]
seq: 190
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w15--item-30-a-single--and-evalvar-indirection-bypass-every-command-keyed-guard
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-hk7fpaw-rule-on-quoted-shell-operators-splitting-command.md /^- 2026-\d\d-\d\d owner ruled/
---
Left by W15, not a W15 gap. `git commit -m "a & b"` yields two segments,
exactly as `"a; b"` always has. Uniform, pre-existing, and fail-closed for the
guards — more segments read, not fewer. The one shape it bites is an
allowlist, where over-segmentation denies: `sahjhan daemon start --config-dir
"a & b"` would be refused recovery. No test pins the quoted case in either
direction. `_shell_norm.shell_segments` is the sole segmentation owner.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

---
id: ho-e7twdah
title: Rule on the noclobber redirect splitting on its pipe
category: rulings
labels: [owner-call]
seq: 200
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w15--item-30-a-single--and-evalvar-indirection-bypass-every-command-keyed-guard
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-e7twdah-rule-on-the-noclobber-redirect-splitting-on-its-p.md /^- 2026-\d\d-\d\d owner ruled/
---
Left by W15, not a W15 gap. `>|` (noclobber override) splits on its `|`:
`foo >| bar` becomes `foo >` and `bar`. Measured identical before and after
W15. It is the same defect class as the `&` W15 fixed, and wants its own unit
rather than a silent widening of a closed one.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

---
id: ho-h6tj6ra
title: Rule on the __pycache__ tree-hash hazard
category: rulings
labels: [owner-call]
seq: 130
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w18--items-36--33-courier-triggers-and-the-suite-marker
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-h6tj6ra-rule-on-the-pycache-tree-hash-hazard.md /^- 2026-\d\d-\d\d owner ruled/
---
Recorded in W18: a project that does not ignore `__pycache__` changes its own
tree hash by running its suite. Pre-existing; not fixed.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

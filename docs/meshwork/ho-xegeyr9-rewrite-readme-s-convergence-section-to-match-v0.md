---
id: ho-xegeyr9
title: Rewrite README's Convergence section to match v0.170.15
category: rulings
labels: [owner-call]
seq: 100
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w28--items-12--16-readme-contradiction-then-the-changelog
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-xegeyr9-rewrite-readme-s-convergence-section-to-match-v0.md /^- 2026-\d\d-\d\d owner confirmed/
---
README's Convergence section contradicts the release: it says "max 15 fix
commits enforced by the Sahjhan gate" (`README.md:138`), and the README's
description of convergence says "until two consecutive passes find nothing
new" (`README.md:9`, `:26`; `:38` has "two consecutive passes produce zero new
findings"). The release left it unchanged because the README's voice is Jon's.
W28 (item 12) removed the README's other contradictions.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

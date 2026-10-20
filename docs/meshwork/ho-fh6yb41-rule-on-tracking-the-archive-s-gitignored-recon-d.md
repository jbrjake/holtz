---
id: ho-fh6yb41
title: Rule on tracking the archive's gitignored recon/ directories
category: rulings
labels: [owner-call]
seq: 110
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w27--items-15--45--46-dependency-declaration-migration-tooling-pin-checks
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-fh6yb41-rule-on-tracking-the-archive-s-gitignored-recon-d.md /^- 2026-\d\d-\d\d owner ruled/
---
`.gitignore:9`'s bare `recon/` matches at any depth, so 488 of
`docs/holtz/archive`'s 802 files — and 11 of the 31 mapped runs — are absent
from a clean clone. W27's V4 (`test_every_migrated_event_validates_against_events_toml`)
sees 2810 events in the working copy that has them and 923 in a clean clone;
`218724f` made it judge per directory so it holds on both. Whether to track
them is the owner's call.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

---
id: ho-8pgmnbn
title: Rule on H11's declaration-side gap between declared and stamped producer ids
category: rulings
labels: [owner-call]
seq: 160
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w17--item-22-no-lint-rule-binds-a-gate-filters-on-this-value-to-only-a-hook-may-write-it
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-8pgmnbn-rule-on-h11-s-declaration-side-gap-between-decla.md /^- 2026-\d\d-\d\d owner ruled/
---
A candidate item, unruled. `events.toml` declares
`hook:enforcement/hooks/theoretical_courier.py` and `engine:emits:defer_low`,
while the engine stamps `hook:hooks/theoretical_courier.py` and
`engine:emit:defer_low`. `ENFORCEMENT-CONTRACT.md` prints the declared
spelling, which matches no ledger row.

`sahjhan lint` L8 covers the gate side — a `recorded_by` filter naming a script
the manifest does not list is an error. Nothing covers the declaration side:
H2 checks the declared path against the filesystem, which is why the repo-root
form is right there and wrong everywhere a `recorded_by` value is compared.
H11 asks whether a gate excusing itself on an escape-qualifier literal names a
writer it may trust; it is not a check on how writers are spelled.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

---
id: ho-95c2s4y
title: Rule on asking sahjhan to let an event field name its declared set
category: rulings
labels: [owner-call]
seq: 150
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w06--item-20-every-merged-finding-belongs-to-no-lens
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-95c2s4y-rule-on-asking-sahjhan-to-let-an-event-field-nam.md /^- 2026-\d\d-\d\d owner ruled/
---
W06's V8, measured on the pinned engine: `sahjhan event finding --field
perspective=not-a-lens` exits 0 and the row lands with that value.
`events.toml` gives `perspective` no `pattern` while `reachability` right below
it has one, and no field can reference a declared `[sets.*]` — so
`[sets.perspective]` decorates rather than validates.

Closing it holtz-side means restating the 13 values in 8+ places; closing it
properly means letting a field name its set, which is an engine change.
Justine's side is already closed by `f21620e`; this is the Holtz side, which
the merge reads back from the ledger.

Closes on a dated line the owner appends to this file; an ask becomes a
`--to sahjhan` task.

## log
- 2026-10-20T19:35Z created

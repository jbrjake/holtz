---
id: ho-gadqmyz
title: "Rule on W21 step 2's openness term — a named merge_target_open query, or inline"
category: rulings
labels: [owner-call]
seq: 170
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w21--item-9-merge_finding-has-no-relatedness-or-severity-constraint
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-gadqmyz-rule-on-w21-step-2-s-openness-term-a-named-merge.md /^- 2026-\d\d-\d\d owner ruled/
---
W21's step 2 says "reuse the existing `item_open` predicate for the openness
term". That mechanism does not exist: `item_open` is written against
`{{item_id}}`, the openness needed is the target's (`{{merged_into}}`), and a
named-query gate resolves `queries.<name>.sql` and interpolates its own
transition's vars (`sahjhan/src/gates/query.rs`, `resolve_gate_sql` feeding
`eval_query_gate`). There is no argument rebinding and no query-in-query.

It shipped spelled inline as the two `NOT IN`s, which `all_findings_closed`
and the three `open_*_findings` predicates already do. The unit raised it
rather than decided it: if the intent was a new named query
(`merge_target_open`) consumed by both `merge_finding` seats, it is a rename.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

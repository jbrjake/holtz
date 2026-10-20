---
id: ho-jb2pkyj
title: Rule on making the coverage gate's rounding agree with its summary line
category: rulings
labels: [owner-call]
seq: 120
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w28--items-12--16-readme-contradiction-then-the-changelog
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-jb2pkyj-rule-on-making-the-coverage-gate-s-rounding-agre.md /^- 2026-\d\d-\d\d owner ruled/
---
pytest-cov decides the exit with `should_fail_under(total, 80, precision=0)`,
so the 80% gate trips only below 79.5%, while its summary line compares the
raw number and can print "FAIL" over an exit 0. Setting
`[tool.coverage.report] precision = 2` in `pyproject.toml` would make the two
agree. Not changed: it makes a release gate stricter, and nobody asked for
that.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

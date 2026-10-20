---
id: ho-t6y4jz0
title: Cut the release that follows v0.170.15
status: open
category: release
verify: contains CHANGELOG.md /## \[0\.(170\.(1[6-9]|[2-9][0-9])|(17[1-9]|1[89][0-9])\.[0-9]+)\] - 2026-/
docs:
  - CLAUDE.md#cutting-a-release
seq: 15
created: 2026-10-20T20:30Z
needs: [ho-rd651pw]
---

Jon, 2026-10-20, this session: "when you're done, cut a new release of holtz,
with release notes in the same style as last time".

"Done" is this session's work: ho-rd651pw (the sahjhan pin move off 0.28.0 and
item 39's config-fault half). The notes follow v0.170.15's: diffed against
v0.170.15, every claim checked against the tree, a known-gaps section, and
published as the release PR's merge-commit body via `gh pr merge --body-file`
with no trailers. The PR description carries the attribution line.

Steps are CLAUDE.md's "Cutting a Release": pre-release check, changelog via
`scripts/generate-changelog.py --write`, release PR dev → main, CI green on the
PR, merge, and the release Action tags it. Push over HTTPS with gh as the
credential helper; SSH to origin is refused from this machine.

## log
- 2026-10-20T20:30Z created

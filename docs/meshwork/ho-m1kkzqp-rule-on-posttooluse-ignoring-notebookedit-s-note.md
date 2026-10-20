---
id: ho-m1kkzqp
title: Rule on PostToolUse ignoring NotebookEdit's notebook_path
category: rulings
labels: [owner-call]
seq: 140
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w19--items-40--47-notebookedit-registration-and-the-missing-manifest-entry
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-m1kkzqp-rule-on-posttooluse-ignoring-notebookedit-s-note.md /^- 2026-\d\d-\d\d owner ruled/
---
A fifth NotebookEdit disagreement, raised during W25 and unruled.
`enforcement/hooks/post_tool_hook.py:114` reads `tool_input.get("file_path", "")` alone;
W19 fixed `notebook_path` only on the PreToolUse side (`_write_target()`), so a
notebook edit reaches PostToolUse `hook eval` with no `--file`. `NotebookEdit`
sends `notebook_path` — confirmed in W19 by grepping the installed `claude`
binary.

Closes on a dated line the owner appends to this file; a "fix it" ruling
becomes its own task.

## log
- 2026-10-20T19:35Z created

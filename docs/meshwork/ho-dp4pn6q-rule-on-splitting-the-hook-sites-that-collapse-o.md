---
id: ho-dp4pn6q
title: Rule on splitting the hook sites that collapse OSError and TimeoutExpired
category: rulings
labels: [owner-call]
seq: 180
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w13--items-37--17-the-primers-silent-degrade-and-the-ordering-that-hides-daemon-death
status: open
created: 2026-10-20T19:35Z
verify: contains docs/meshwork/ho-dp4pn6q-rule-on-splitting-the-hook-sites-that-collapse-o.md /^- 2026-\d\d-\d\d owner ruled/
---
The load-flaky hook family (`TestPrimer`, `TestPrimerWithMockBinary`,
`TestProtocolTrackerDaemonTeardown`, `test_source_write_allowed_once_gate_satisfied`,
and others) surfaces as `ENFORCEMENT DEGRADED: Hook eval subprocess failed`,
from an `except (OSError, subprocess.TimeoutExpired)` that collapses the two.
They call for opposite responses: a timeout says load or a wedged daemon, an
`OSError` says the binary or socket is wrong. W13 split the primer's own
handler, and its one captured occurrence named `TimeoutExpired` on a trivial
`/bin/sh` mock — machine load, for that site only.

Five sites still collapse the pair at `1f72d30`, all in `enforcement/hooks/`:
`pre_tool_hook.py:180`, `bash_guard.py:84` and `:184`,
`_protocol_cache.py:597`, `_sahjhan_bootstrap.py:1113`. (`bash_guard.py:132`
catches the same pair but already records `type(exc).__name__`.) W13's section
calls them "the four remaining" — count before acting. Two
(`_protocol_cache.py:597`, `bash_guard.py:184`) return `None`/`set()` silently
and need a stderr line rather than a message.

Folding them into item 17 was put and declined (Jon, 2026-09-04); they stay a
separate, deliberately-untaken step. If taken: instrumentation only — no
timeout change in the same commit, or the next green run is unattributable.
`bash_guard.py`'s `timeout=10` is pinned by quiz-bank entry `[52]`, and these
are daemon-calling hooks, so `scripts/hash-trusted-callers.sh` must rerun.

Closes on a dated line the owner appends to this file.

## log
- 2026-10-20T19:35Z created

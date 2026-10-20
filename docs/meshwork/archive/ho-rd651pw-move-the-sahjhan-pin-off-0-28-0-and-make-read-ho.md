---
id: ho-rd651pw
title: Move the sahjhan pin off 0.28.0 and make read_hook_eval refuse a load-failure reply
category: enforcement
seq: 10
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w25--items-11--39--49-escapes-the-posttooluse-fall-through-and-the-lower-tail
verify: "all(lacks enforcement/hooks/_resolve.py 0.28.0, contains enforcement/hooks/_common.py /config_error|integrity_error/)"
status: done
created: 2026-10-20T19:35Z
---
Item 39's config-fault half (W25). sahjhan#51 shipped in sahjhan v0.28.1
(2026-09-24); v0.28.2 is the latest release (2026-09-30) — read its notes
before choosing the target. Holtz pins 0.28.0 at `enforcement/hooks/_resolve.py:14`.

The version fault already degrades loudly in both hooks. A config or
ledger-load fault still reads as a genuine allow on 0.28.0. From 0.28.1,
`hook eval` answers those with `ok: false` and no `data`:

| condition | 0.28.1 |
| --- | --- |
| `protocol.toml` doesn't parse, or the config dir is missing | `config_error`, exit 3 |
| `--ledger` names an unregistered ledger | `config_error`, exit 3 |
| ledger never initialised | `integrity_error`, exit 2 |
| sealed config file edited after `init` | `integrity_error`, exit 2 |

The change lands in `_common.read_hook_eval`: both tool hooks read the reply
there, and `TestTheTwoHooksAgree` is the tripwire against re-inlining the
parse in either. At `1f72d30` it takes `data.get("data", data)`
(`enforcement/hooks/_common.py:246`), so an `ok: false` reply with no `data`
becomes the payload itself instead of a reason. `exit_enforcement_error`
already decides block vs warn.

Move the pin with `scripts/update_sahjhan_pin.py` — `_resolve.SAHJHAN_VERSION`
governs, and the binary and marker self-heal to it. Editing a daemon-calling
hook needs `scripts/hash-trusted-callers.sh` rerun, or the `real_daemon` tests
go red with the write simply absent.

## log
- 2026-10-20T19:35Z created
- 2026-10-20T20:30Z open→doing — claimed by claude (78999082-3418-4c6e-8577-2c5fcaa9b10e)
- 2026-10-20T20:51Z doing→done — verify exit 0 @ 824c452+2

## comments
- 2026-10-20T20:51Z [claude (78999082-3418-4c6e-8577-2c5fcaa9b10e)] Landed in 824c452 (fix(enforcement): a config or ledger that fails to load is not an allow). Pin 0.28.0 -> 0.28.2: 0.28.1 carries sahjhan#51's ok:false reply; 0.28.2's fixes are to hook generate, init rollback and the seal refusal text, none of which holtz consumes or matched on. read_hook_eval checks ok before unwrapping data and passes the engine's message whole. Evidence: 7 new tests red on the unmodified tree; with the reader fixed and the pin at 0.28.0 only the 2 driven tests red (the engine allowed); 16 passed on 0.28.2; the ok-check mutation turns exactly the 7 red. Targeted real-binary hook-eval files: 347 passed. Full suite not run; it runs once at the release (ho-t6y4jz0). Found on the way: a freshly written script's first exec stalled 4-7 s in syspolicyd right after vendoring ~500 MB of new binaries, so stand-in hook tests hit the hooks' 5 s timeout until it settled (0.12 s a few minutes later). The first pre-commit attempt failed on that, and the retry passed.

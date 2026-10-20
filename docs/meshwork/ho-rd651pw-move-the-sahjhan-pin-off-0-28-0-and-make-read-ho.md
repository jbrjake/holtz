---
id: ho-rd651pw
title: Move the sahjhan pin off 0.28.0 and make read_hook_eval refuse a load-failure reply
category: enforcement
seq: 10
docs:
  - docs/superpowers/plans/2026-08-27-release-worklist.md#w25--items-11--39--49-escapes-the-posttooluse-fall-through-and-the-lower-tail
verify: "all(lacks enforcement/hooks/_resolve.py 0.28.0, contains enforcement/hooks/_common.py /config_error|integrity_error/)"
status: open
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

# Sahjhan Vault Authentication Flow

## Trusted Path: Hook Requests Signing or Vault Data

```
Claude Code                    Hook Process                    Daemon
    │                              │                              │
    │  PreToolUse event (stdin)    │                              │
    ├─────────────────────────────►│                              │
    │                              │                              │
    │                              │  connect(.sahjhan/sahjhan.sock)
    │                              ├─────────────────────────────►│
    │                              │                              │
    │                              │         ┌────────────────────┤
    │                              │         │ SO_PEERCRED:       │
    │                              │         │  get connecting PID│
    │                              │         │  read /proc/PID/   │
    │                              │         │   exe + cmdline    │
    │                              │         │  resolve script    │
    │                              │         │   path             │
    │                              │         │  SHA-256 script    │
    │                              │         │  check manifest    │
    │                              │         └────────────────────┤
    │                              │                              │
    │                              │  ✓ authenticated             │
    │                              │◄─────────────────────────────┤
    │                              │                              │
    │                              │  request: sign(event_type,   │
    │                              │           fields)            │
    │                              ├─────────────────────────────►│
    │                              │                              │
    │                              │         ┌────────────────────┤
    │                              │         │ HMAC-SHA256 with   │
    │                              │         │ in-memory key      │
    │                              │         └────────────────────┤
    │                              │                              │
    │                              │  proof: "a1b2c3d4..."       │
    │                              │◄─────────────────────────────┤
    │                              │                              │
    │  allow/block decision        │                              │
    │◄─────────────────────────────┤                              │
```

## Key Properties

- **Vault key**: exists only in daemon process memory, never on disk or in the binary
- **Memory protection**: `mlock()` (no swap), `PR_SET_DUMPABLE=0` (Linux), `PT_DENY_ATTACH` (macOS)
- **Caller authentication**: kernel-enforced socket peer credentials (`SO_PEERCRED` / `LOCAL_PEERCRED`)
- **Caller authorization**: script path + SHA-256 verified against static `enforcement/trusted-callers.toml`
- **Manifest immutability**: write-protected at runtime by existing `enforcement/` guard

# Sahjhan Daemon, Vault, and Signing Service

Spec for sahjhan binary changes. Intended audience: jbrjake/sahjhan.

## Problem

Sahjhan's current enforcement model stores secrets as plaintext files on disk (`session.key`, plus downstream consumer data like quiz banks). The PreToolUse hook system attempts to block reads via string-matching on tool call arguments, but an LLM agent with arbitrary code execution can bypass this trivially:

1. Write a Python script that constructs the path as a variable, then opens it
2. Run the script via Bash -- the hook sees `python3 script.py`, not the protected path
3. Secret is leaked to the agent's context

The string-matching approach has infinite bypasses: variables, indirection, encoded paths, heredocs, polyglot scripts. An embedded encryption key in the binary is also insufficient -- an LLM agent can reverse-engineer a compiled binary by disassembling it and reasoning about the output.

The only place a secret can live that is inaccessible to a same-user adversary with code execution is **in the memory of a protected process**.

## Solution: sahjhan as a daemon

sahjhan gains a daemon mode. During an audit, the daemon:
- Holds secrets exclusively in process memory (never on disk)
- Serves signing and vault operations over a Unix domain socket
- Authenticates every caller via kernel-enforced socket peer credentials
- Authorizes callers against a static manifest of trusted hook scripts

### Daemon lifecycle

`{data_dir}` refers to the sahjhan data directory for the current run -- resolved from `--config-dir`, the active run context, and the `--data-dir` override if provided. For Holtz, this is typically `docs/holtz/.sahjhan/` relative to the project root.

#### `sahjhan daemon start`

1. Fork into background (or stay in foreground with `--foreground`)
2. Generate `session.key`: 32 cryptographically random bytes, held in memory only
3. Bind Unix domain socket at `{data_dir}/sahjhan.sock` with permissions `0600`
4. Apply memory protections:
   - `mlock()` on pages holding secrets (prevents swap-out to disk)
   - `prctl(PR_SET_DUMPABLE, 0)` on Linux (blocks `/proc/pid/mem` reads from same UID)
   - `ptrace(PT_DENY_ATTACH)` on macOS (blocks debugger attachment)
5. Check for and refuse to run if `LD_PRELOAD` or `DYLD_INSERT_LIBRARIES` are set in environment
6. Write PID to `{data_dir}/sahjhan.pid`
7. Begin accepting connections

On startup, if a stale `sahjhan.sock` or `sahjhan.pid` exists from a prior unclean shutdown, remove them and proceed.

#### `sahjhan daemon stop`

1. Securely zero all in-memory secrets (explicit `memset` / `zeroize` crate, not just `drop`)
2. Close and remove the socket file
3. Remove PID file
4. Exit

#### Unclean death (kill, crash, OOM)

OS reclaims memory. Secrets are gone. Stale socket/PID files are detected and cleaned on next `sahjhan daemon start`.

### Caller authentication

Every connection to the daemon socket goes through this verification. There are two connection modes: **direct** (hook connects via socket library) and **CLI-mediated** (hook calls `sahjhan sign`, which connects internally). The daemon handles both.

#### Step 1: Get peer PID

Use `SO_PEERCRED` (Linux/WSL) or `LOCAL_PEERCRED` (macOS) on the accepted socket connection. These are kernel-provided -- the connecting process cannot spoof them.

#### Step 2: Identify the caller

**Direct connection** (recommended for hooks): the connecting PID *is* the hook process. Read its executable path and command-line arguments directly.

**CLI-mediated connection**: the connecting PID is the `sahjhan` CLI binary. The daemon detects this by checking if the connecting PID's executable matches its own binary path. If so, read the connecting PID's parent PID (`PPid` from `/proc/{pid}/status` on Linux, or `proc_pidinfo` on macOS), then read the *parent's* executable and command-line arguments.

In both cases, the target is the process running the hook script.

#### Step 3: Resolve the caller's script path

- Read the target PID's actual executable via `proc_pidpath()` (macOS) or `/proc/{pid}/exe` symlink (Linux). This gives the interpreter binary (e.g., `/usr/bin/python3`), not `argv[0]` (which is spoofable).
- Read the target PID's command-line arguments via `sysctl kern.procargs2` (macOS) or `/proc/{pid}/cmdline` (Linux). Extract the script path argument (first non-flag argument to the interpreter).
- Resolve the script path to an absolute, canonicalized path (resolve all symlinks).

#### Step 4: Check the trusted-callers manifest

- Load `{config_dir}/trusted-callers.toml`
- Look up the script's path (relative to the config directory's parent -- see manifest format below)
- If the path is not in the manifest: **reject**

#### Step 5: Verify script integrity

- Compute SHA-256 of the script file at the resolved path
- Compare against the hash in the manifest
- If mismatch: **reject**

#### Step 6: Accept

Connection is authenticated. Process all requests on this connection for its lifetime (no re-authentication per request).

### Manifest format

```toml
# enforcement/trusted-callers.toml
# Paths are relative to the config directory's parent (plugin root).
# Hashes are SHA-256 of the file contents at build/install time.

[callers]
"enforcement/hooks/_common.py" = "sha256:a1b2c3d4e5f6..."
"enforcement/hooks/lens_quiz.py" = "sha256:7890abcdef01..."
"enforcement/hooks/stop_hook.py" = "sha256:2345678901ab..."
"hooks/subagent_findings_check.py" = "sha256:cdef01234567..."
```

The manifest is a static file staged at plugin install time. There is no runtime API to mutate it. It lives under `enforcement/`, which downstream consumers already write-protect via PreToolUse hooks.

Downstream plugins that depend on a sahjhan-using plugin add their own hook entries to this file during their install/staging step, before any agent launches.

### Socket protocol

JSON-over-Unix-socket. Each request is a newline-delimited JSON object. Each response is a newline-delimited JSON object.

#### `sign` -- compute HMAC-SHA256 proof

Request:
```json
{"op": "sign", "event_type": "quiz_answered", "fields": {"perspective": "security", "answer": "B"}}
```

Response:
```json
{"ok": true, "proof": "a1b2c3d4..."}
```

The daemon computes the proof using its in-memory session key. Same HMAC-SHA256 algorithm as the current `compute_event_proof()`: null-byte-separated payload of `event_type\0field1=value1\0field2=value2\0...` with fields sorted lexicographically.

#### `vault store` -- store opaque data in memory

Request:
```json
{"op": "vault_store", "name": "quiz-bank", "data": "<base64-encoded content>"}
```

Response:
```json
{"ok": true}
```

Stores the data in the daemon's in-memory key-value store. Overwrites if the name already exists. The daemon does not interpret the data -- it is opaque bytes.

#### `vault read` -- retrieve stored data

Request:
```json
{"op": "vault_read", "name": "quiz-bank"}
```

Response:
```json
{"ok": true, "data": "<base64-encoded content>"}
```

Error if name not found:
```json
{"ok": false, "error": "not_found", "message": "No vault entry named 'quiz-bank'"}
```

#### `vault delete` -- remove stored data

Request:
```json
{"op": "vault_delete", "name": "quiz-bank"}
```

Response:
```json
{"ok": true}
```

Securely zeros the memory before freeing. No-op if name not found.

#### `vault list` -- list stored entry names

Request:
```json
{"op": "vault_list"}
```

Response:
```json
{"ok": true, "names": ["quiz-bank", "api-key"]}
```

Names only. Does not return data.

#### `status` -- daemon health check

Request:
```json
{"op": "status"}
```

Response:
```json
{"ok": true, "pid": 12345, "uptime_seconds": 3600, "vault_entries": 2}
```

### Error responses

All error responses follow the same format:
```json
{"ok": false, "error": "<error_code>", "message": "<human-readable detail>"}
```

Error codes:
- `auth_failed` -- caller authentication failed (path not in manifest, hash mismatch)
- `not_found` -- vault entry name not found
- `invalid_request` -- malformed JSON or missing required fields

### CLI integration

The existing CLI commands continue to work. Privileged commands (`sign`, `vault store`, `vault read`, `vault delete`) connect to the daemon socket internally:

```
$ sahjhan sign --event-type quiz_answered --field perspective=security --field answer=B
a1b2c3d4...

$ sahjhan vault store --name quiz-bank --file /dev/stdin < quiz-data.json
OK

$ sahjhan vault read --name quiz-bank
<raw content to stdout>
```

If the daemon is not running, privileged commands exit with a clear error:
```
Error: sahjhan daemon is not running. Start it with `sahjhan daemon start`.
```

Non-privileged commands (`status`, `event`, `transition`, `query`, `hook eval`, `manifest verify`, `guards`) continue to work without the daemon, reading directly from ledger files as before.

### Existing `authed-event` command

Currently, `authed-event` accepts a `--proof` flag with a pre-computed HMAC. This continues to work unchanged -- the proof is computed by the `sign` command (via the daemon) and passed to `authed-event` by the hook.

Alternatively, a new `--sign` flag could be added to `authed-event` that combines both steps (connect to daemon, get proof, record event). This is a convenience -- not required for the initial implementation.

## Adversarial attack resistance

| Attack | Defense |
|--------|---------|
| Agent calls `sahjhan sign` via Bash | Daemon checks connecting PID's parent. Parent is `bash`, not a trusted hook script. Rejected. |
| Agent writes a script that calls sahjhan | Script is at `/tmp/attack.py` or similar. Not in manifest. Rejected. |
| Agent writes a script into `enforcement/hooks/` | Downstream consumer's PreToolUse hook blocks writes to `enforcement/`. Script never created. |
| Agent modifies a trusted hook script | Write-blocked. Even if bypassed: SHA-256 hash doesn't match manifest. Rejected. |
| Agent copies a hook to another path | Path not in manifest. Rejected (both path AND hash must match). |
| Agent spoofs `argv[0]` | Daemon reads actual executable path (`proc_pidpath` / `/proc/exe`), not `argv[0]`. Defeated. |
| Agent reads daemon memory (`/proc/pid/mem`) | `PR_SET_DUMPABLE=0` blocks same-UID reads. Permission denied. |
| Agent attaches debugger | `PT_DENY_ATTACH` (macOS) / non-dumpable (Linux). Attach fails. |
| Agent uses `LD_PRELOAD` | Daemon checks environment at startup, refuses to run. Aborts. |
| Agent kills the daemon | Secrets vanish from memory. Denial of service, not exfiltration. |
| Agent reads encrypted vault files on disk | No vault files on disk. Vault is pure in-memory. Nothing to read. |
| Agent reverse-engineers the binary | No embedded encryption key. Session key is generated at runtime, exists only in memory. Nothing to extract from the binary. |

## Platform support

- **macOS (aarch64, x86_64)**: `proc_pidpath()` for executable resolution, `sysctl kern.procargs2` for command-line args, `LOCAL_PEERCRED` for socket peer credentials, `ptrace(PT_DENY_ATTACH)` for anti-debug
- **Linux (aarch64, x86_64)**: `/proc/pid/exe` for executable resolution, `/proc/pid/cmdline` for command-line args, `SO_PEERCRED` for socket peer credentials, `prctl(PR_SET_DUMPABLE, 0)` for memory protection
- **WSL**: covered by the Linux implementation

## Implementation notes

- Use the `zeroize` crate for secure memory cleanup of secrets on drop
- Use `mlock` / `mlock2` to prevent secret pages from being swapped
- Socket permissions should be `0600` (owner-only read/write)
- Consider `SOCK_SEQPACKET` for message boundaries, or length-prefixed JSON over `SOCK_STREAM`
- The daemon should handle `SIGTERM` gracefully (secure cleanup, then exit)
- On `SIGKILL`, OS reclaims memory -- secrets are gone, stale files cleaned on next start

# Holtz Vault Integration

Spec for Holtz plugin changes to use sahjhan's daemon-based vault and signing service. Depends on the sahjhan daemon spec (see `2026-04-03-sahjhan-daemon-vault-spec.md`).

## Problem

Holtz currently protects `session.key` and `quiz-bank.json` via string-matching in PreToolUse hooks. An LLM agent with code execution bypasses this through indirection (writing a script that reads the file, then running the script). Additionally, Grep and Glob tools are not hooked at all.

With the sahjhan daemon, secrets move to in-memory-only storage. Holtz needs to adapt its hooks to use the daemon's signing and vault APIs instead of reading files directly.

## Changes

### 1. Daemon lifecycle integration

Holtz's audit initialization must start the daemon, and audit teardown must stop it.

**Start**: wherever `sahjhan init` is invoked (currently in the skill/agent orchestration layer), add `sahjhan daemon start` immediately after. The daemon must be running before any hooks that need signing or vault access.

**Stop**: at audit end, `sahjhan daemon stop`. On unclean exit, the daemon dies with its parent process -- stale socket files are cleaned on next start.

### 2. Hook migration: signing

**Current** (`enforcement/hooks/_common.py`):
```python
def compute_event_proof(event_type, fields, key_path=None):
    if key_path is None:
        key_path = _get_session_key_path()
    with open(key_path, "rb") as f:
        key = f.read()
    # ... HMAC computation ...
```

**After** (direct socket connection -- recommended):
```python
import json
import socket

def compute_event_proof(event_type, fields, **kwargs):
    sock_path = _get_daemon_socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(sock_path)
    request = json.dumps({
        "op": "sign",
        "event_type": event_type,
        "fields": dict(sorted(fields.items())),
    })
    sock.sendall((request + "\n").encode())
    response = json.loads(sock.makefile().readline())
    sock.close()
    if not response.get("ok"):
        raise RuntimeError(f"sahjhan sign failed: {response.get('message', 'unknown error')}")
    return response["proof"]
```

Direct socket connection is preferred over `subprocess.run([sahjhan, "sign", ...])` because the daemon gets the hook's PID directly via `SO_PEERCRED` -- no parent-PID hop needed. Simpler auth, fewer moving parts.

The function signature stays the same (minus `key_path`, which becomes unused). All callers -- `record_authed_event()`, `lens_quiz.py`, `stop_hook.py` -- continue to work without changes.

`_get_session_key_path()` and the `key_path` parameter become dead code and can be removed. A new `_get_daemon_socket_path()` helper resolves the socket path from the data directory (same resolution logic as the current `_get_session_key_path()` but pointing at `sahjhan.sock` instead of `session.key`).

### 3. Hook migration: quiz bank

**Current** (`enforcement/hooks/lens_quiz.py`):
- Reads `enforcement/quiz-bank.json` directly
- Selects random questions per perspective
- Verifies answers against source code

**After**:
- At audit start, Holtz generates the quiz bank (domain logic -- analyze codebase, produce questions)
- Stores it via direct socket: `{"op": "vault_store", "name": "quiz-bank", "data": "<base64>"}`
- At quiz time, retrieves it via direct socket: `{"op": "vault_read", "name": "quiz-bank"}`, decodes, selects questions
- The quiz bank is ephemeral -- generated fresh each audit, dies with the daemon

The quiz generation logic can live in a new module (e.g., `enforcement/hooks/quiz_gen.py`) or in the existing `lens_quiz.py`. It runs once at audit start, not on every quiz event.

### 4. Trusted-callers manifest

New file: `enforcement/trusted-callers.toml`

Contains the path and SHA-256 hash of every hook script that calls `sahjhan sign` or `sahjhan vault read/store`. At minimum:

```toml
[callers]
"enforcement/hooks/_common.py" = "sha256:..."
"enforcement/hooks/lens_quiz.py" = "sha256:..."
"enforcement/hooks/stop_hook.py" = "sha256:..."
```

**Build step**: a script (e.g., `scripts/hash-trusted-callers.sh`) computes SHA-256 hashes and writes the manifest. This runs at release time, not at runtime. The manifest must be regenerated whenever a trusted hook script changes.

**CI gate**: a check that verifies the manifest is up to date (hashes match actual file contents). Prevents releasing with a stale manifest that would cause the daemon to reject its own hooks.

### 5. Read guard simplification

**Current `_sahjhan_bootstrap.py`**:
- ~260 lines of string-matching logic for read guards
- Bash command parsing for redirects, tee, cp, mv, sed, perl, curl, wget, dd, python, etc.
- Glob pattern detection
- Structural guards for `.sahjhan/**/session.key`

**After**:
- `session.key` no longer exists on disk -- structural guard becomes unnecessary
- `quiz-bank.json` no longer exists on disk (generated fresh, stored in vault) -- read guard becomes unnecessary
- The read-guard functions (`_is_read_guarded`, `_bash_references_guarded`, `_load_read_guards`) can be removed entirely or retained as defense-in-depth for the `.sahjhan/` directory structure

**Write guards remain unchanged** -- `enforcement/`, `bin/sahjhan*`, `hooks/hooks.json`, managed docs are still write-protected.

### 6. Hooks.json changes

Add matchers for Grep and Glob as defense-in-depth (even though there are no plaintext secrets to find, this prevents future regressions):

```json
{
  "matcher": "Grep|Glob",
  "hooks": [
    {
      "type": "command",
      "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_sahjhan_bootstrap.py\""
    }
  ]
}
```

The bootstrap hook would need minor changes to handle Grep/Glob tool_input format (Grep sends `pattern` and `path`; Glob sends `pattern` and optionally `path`).

### 7. Bash guard for daemon commands

Add blocking rules in `_sahjhan_bootstrap.py` for privileged sahjhan subcommands in Bash tool calls. This is defense-in-depth -- the daemon's caller authentication is the primary boundary.

Block patterns in Bash command text:
- `sahjhan sign`
- `sahjhan vault`
- `sahjhan daemon stop` (prevent agent from killing the daemon)

These are simple substring matches. Unlike the current read-guard system, this surface is small and stable -- three subcommand names, not arbitrary file paths.

## What gets deleted

| File/Code | Reason |
|-----------|--------|
| `enforcement/quiz-bank.json` | No longer shipped. Quiz bank generated fresh each audit. |
| `_common.py:_get_session_key_path()` | Session key no longer on disk. |
| `_common.py:compute_event_proof()` body | Replaced by `sahjhan sign` call. |
| `_sahjhan_bootstrap.py` read guard functions | No plaintext secrets to guard. |
| `.sahjhan/session.key` (runtime artifact) | Never created. Key lives in daemon memory. |
| `_sahjhan_bootstrap.py` Bash read-guard logic (~100 lines) | No files to protect from Bash reads. |

## What stays

| Component | Reason |
|-----------|--------|
| `enforcement/` write guard | Protects hook scripts, manifest, and config from agent modification |
| `bin/sahjhan*` write guard | Protects binary from tampering |
| Managed docs write guard | Protects STATUS.md, PUNCHLIST.md, etc. |
| `_sahjhan_bootstrap.py` as PreToolUse hook | Still needed for write guards + defense-in-depth Bash guards |
| `_resolve.py` bootstrap/download | Still needed to obtain the sahjhan binary |
| `hooks.json` hook registration | Still needed, with Grep/Glob matchers added |

## Migration path

This change depends on sahjhan binary changes (daemon, vault, sign commands). The migration is:

1. **sahjhan ships daemon support** -- new binary version with daemon, vault, and sign commands
2. **Update `_resolve.py`** -- bump `SAHJHAN_VERSION` and checksums to the new release
3. **Add `enforcement/trusted-callers.toml`** -- hash all hook scripts that need privileged access
4. **Add build script** -- `scripts/hash-trusted-callers.sh` to regenerate manifest
5. **Migrate `compute_event_proof()`** -- replace file-read HMAC with `sahjhan sign` call
6. **Migrate quiz bank** -- remove `quiz-bank.json`, add generation logic, use vault store/read
7. **Integrate daemon lifecycle** -- start daemon at audit init, stop at audit end
8. **Simplify read guards** -- remove dead code from `_sahjhan_bootstrap.py`
9. **Add Grep/Glob matchers** -- update `hooks.json`
10. **Add Bash guards for daemon commands** -- block `sahjhan sign/vault/daemon stop`

Steps 1-2 are blocked on the sahjhan release. Steps 3-10 can be prepared in parallel on a feature branch, gated on the new binary version.

## Authentication flow diagram

See `2026-04-03-vault-auth-flow.md` for the complete sequence diagram.

## Adversarial attack matrix

See the sahjhan daemon spec (`2026-04-03-sahjhan-daemon-vault-spec.md`) for the full attack/defense matrix. From Holtz's perspective, the key change is: the defense model shifts from "block every possible read path" (infinite attack surface) to "secrets only exist in daemon memory" (finite, auditable attack surface). The ~200 lines of read-guard string-matching code go from "the only thing standing between the agent and the secret" to "defense-in-depth that could be removed without compromising security."

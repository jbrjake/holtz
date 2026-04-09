# Sahjhan Daemon: Enforcement State Operations

Spec for sahjhan binary changes. Intended audience: jbrjake/sahjhan.

Related: [Holtz integration spec](2026-04-09-holtz-enforcement-state-migration-spec.md) | GitHub issue: #46

## Problem

The enforcement cache (`enforcement-cache.json`) stores audit state on the filesystem: `active`, `state`, `unregistered_commits`, `stall`, etc. The bootstrap hook (`_sahjhan_bootstrap.py`) uses literal substring matching to block writes to this file, but an agent can trivially bypass this by constructing the path dynamically at runtime:

```python
# pathlib construction — no literal "docs/holtz/.sahjhan/" in the command text
pathlib.Path('docs/holtz') / '.sahjhan' / 'enforcement-cache.json'
```

This was exploited in a live session to overwrite the enforcement cache directly, setting `state: finalized` and `active: false` to escape the stop hook. The bypass works with pathlib, `os.path.join`, string concatenation, f-strings, or base64 decoding — any technique that avoids embedding the protected path as a literal string.

Substring matching on command source text is not a sound defense against interpreter execution. The fix is to move enforcement state into daemon memory, where it is inaccessible to agents regardless of path construction technique.

## Solution: Enforcement state operations

Three new daemon operations, stored internally as a named vault entry but exposed only through dedicated ops (not accessible via generic `vault_store`/`vault_read`).

### `enforcement_read`

Returns the current enforcement state.

**Request:**
```json
{"op": "enforcement_read"}
```

**Response (state exists):**
```json
{"ok": true, "data": "<base64-encoded JSON dict>"}
```

**Response (no state):**
```json
{"ok": false, "error": "not_found", "message": "no enforcement state"}
```

### `enforcement_write`

Replaces the entire enforcement state. Used for initial cache creation and full refreshes after parsing `sahjhan status` output.

**Request:**
```json
{"op": "enforcement_write", "data": "<base64-encoded JSON dict>"}
```

**Response:**
```json
{"ok": true}
```

### `enforcement_update`

Atomic read-modify-write. Accepts a partial dict of fields to merge into the current state. The daemon reads the current state, applies the patch (top-level key replacement, equivalent to Python's `dict.update()`), sets `last_refresh` to the current UTC timestamp, and writes back — all under the vault mutex.

**Request:**
```json
{"op": "enforcement_update", "patch": "<base64-encoded JSON partial dict>"}
```

**Response (success — returns full state after merge):**
```json
{"ok": true, "data": "<base64-encoded JSON dict>"}
```

**Response (no state to update):**
```json
{"ok": false, "error": "not_found", "message": "no enforcement state to update"}
```

### Merge semantics

The patch merge is deliberately simple: top-level key replacement only. No nested merges, no array append operations. For list fields like `unregistered_commits`, the caller sends the full new list value.

This keeps the daemon free of domain knowledge about enforcement field semantics. The daemon treats the enforcement state as an opaque JSON dict with three operations: read it, replace it, or patch top-level keys.

The one exception: the daemon sets `last_refresh` to the current UTC ISO8601 timestamp on every `enforcement_write` and `enforcement_update`. This ensures the timestamp comes from a trusted source (the daemon clock) rather than the caller.

## Implementation

### Wire protocol (`protocol.rs`)

Add three new `Request` variants:

```rust
#[serde(rename = "enforcement_read")]
EnforcementRead,

#[serde(rename = "enforcement_write")]
EnforcementWrite { data: String },  // base64-encoded JSON

#[serde(rename = "enforcement_update")]
EnforcementUpdate { patch: String },  // base64-encoded JSON partial
```

### Vault storage

Enforcement state is stored as a vault entry named `"_enforcement"` (underscore prefix distinguishes it from user-created vault entries). No new data structures needed — it reuses the existing `Vault` struct and `Zeroizing<Vec<u8>>` wrapping.

The `_enforcement` entry is **not accessible** via generic `vault_read`, `vault_store`, or `vault_delete` operations. The request handler must reject vault ops that target names starting with `_`.

### Request handler (`mod.rs`)

Add match arms in `handle_request()`:

**`enforcement_read`:** Read `"_enforcement"` from vault. If present, base64-encode and return as `data`. If absent, return `not_found` error.

**`enforcement_write`:** Base64-decode the `data` field, parse as JSON to validate it's well-formed, inject `last_refresh` timestamp, re-serialize, and store as `"_enforcement"` in vault.

**`enforcement_update`:** Read `"_enforcement"` from vault. If absent, return `not_found` error. Otherwise: base64-decode both the stored state and the incoming `patch`, parse both as JSON objects, merge patch keys into state (`serde_json::Map::extend`), inject `last_refresh` timestamp, re-serialize, store back, and return the merged state as base64-encoded `data`.

All three operations require authentication (same as `sign`, `vault_store`, etc.).

### Protected vault namespace

Add a guard in the existing `VaultStore`, `VaultRead`, and `VaultDelete` handlers to reject names starting with `_`:

```rust
Request::VaultStore { name, data } => {
    if name.starts_with('_') {
        return Response::err("reserved", "vault names starting with '_' are reserved");
    }
    // ... existing logic
}
```

This ensures agents cannot access enforcement state through the generic vault CLI commands (`sahjhan vault read --name _enforcement`), even if the bootstrap hook were bypassed.

### CLI surface

No new CLI subcommands needed. These operations are consumed by Python hook scripts over the socket, not by humans at a terminal. The daemon status command should include enforcement state presence in its output:

```json
{"ok": true, "pid": 12345, "uptime_seconds": 3600, "vault_entries": 2, "enforcement_active": true, ...}
```

## Testing

1. **Unit test**: `enforcement_write` followed by `enforcement_read` returns the same data.
2. **Unit test**: `enforcement_update` merges patch correctly (top-level only, no nested merge).
3. **Unit test**: `enforcement_update` on missing state returns `not_found`.
4. **Unit test**: `enforcement_update` sets `last_refresh` to current time.
5. **Unit test**: `vault_read --name _enforcement` returns `reserved` error.
6. **Unit test**: `vault_store --name _enforcement` returns `reserved` error.
7. **Integration test**: Full round-trip — write, read, update, read — verifying state consistency.

## Version

This is a minor version bump (new operations, no breaking changes to existing ops). The Holtz integration spec describes the minimum sahjhan version required.

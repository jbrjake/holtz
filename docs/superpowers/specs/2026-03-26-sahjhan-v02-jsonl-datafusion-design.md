# Sahjhan v0.2.0 — JSONL Ledger + DataFusion Query Engine

**Date:** 2026-03-26
**Status:** Design
**Repo:** jbrjake/sahjhan
**Breaking:** Yes (ledger format change, multi-ledger API)

## Problem

Sahjhan v0.1.x uses a binary MessagePack ledger with custom framing. This format is:
- Not git-diffable (shows as "Binary files differ")
- Not human-readable (requires `sahjhan log dump` to inspect)
- Not queryable without the sahjhan binary
- Single-ledger only (one ledger.bin per protocol run)

Consumers (Holtz) need to accumulate hundreds of runs across projects, query them analytically, visualize trends, and keep everything in git with reviewable diffs.

## Solution

Replace the binary ledger with JSONL (one JSON object per line, hash-chained). Embed Apache DataFusion for SQL queries over JSONL files. Support multiple named ledgers per protocol instance.

## Ledger Format

### JSONL Event Envelope

Every line in every ledger file follows this schema:

```json
{
  "schema": 1,
  "seq": 0,
  "prev": "a1b2c3d4e5f6...",
  "hash": "f6e5d4c3b2a1...",
  "ts": "2026-03-26T07:47:36Z",
  "type": "finding",
  "engine": "sahjhan/0.2.0",
  "protocol": "holtz/1.0.0",
  "fields": {
    "id": "BH-001",
    "severity": "HIGH",
    "category": "doc/drift"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema` | int | Ledger schema version. Readers reject lines with `schema` > what they understand. |
| `seq` | int | Monotonic sequence number, 0-based, per ledger file. |
| `prev` | string | Hex-encoded SHA-256 of the previous line's `hash`. Genesis uses a CSPRNG nonce. |
| `hash` | string | Hex-encoded SHA-256 of all other fields in this event (see Hash Algorithm). |
| `ts` | string | ISO 8601 UTC timestamp. |
| `type` | string | Event type name (matches `events.toml` definitions). |
| `engine` | string | Sahjhan version that wrote this event (`sahjhan/X.Y.Z`). |
| `protocol` | string | Protocol name and version from `protocol.toml` (`name/version`). |
| `fields` | object | Event-type-specific key-value pairs. All values are strings. |

Everything domain-specific lives in `fields`. Sahjhan's schema is protocol-agnostic — the eight top-level columns are the same for any protocol.

### Hash Algorithm

```
hash = SHA-256(
  canonical_json({
    "schema": ...,
    "seq": ...,
    "prev": ...,
    "ts": ...,
    "type": ...,
    "engine": ...,
    "protocol": ...,
    "fields": { ... sorted keys ... }
  })
)
```

`canonical_json` follows RFC 8785 (JSON Canonicalization Scheme / JCS):
- Keys sorted alphabetically at all nesting levels
- No optional whitespace
- Integers serialized as decimal with no leading zeros, no decimal point, no exponent (e.g., `1` not `1.0`)
- Strings use UTF-8 literals for printable characters; only the JSON-required set is escaped (`"`, `\`, control characters U+0000-U+001F). Forward slashes are NOT escaped.
- No trailing commas, no comments

The `hash` field itself is excluded from the hash input. The `prev` field IS included (chains the hash to the prior event).

### Genesis Event

The genesis event (seq 0) has `prev` set to a 32-byte CSPRNG nonce, hex-encoded (64 characters, same format as SHA-256 output). No prefix or marker distinguishes it from a hash — the genesis is identified by `seq == 0`. Two ledgers will never share a genesis `prev` value.

### Verification

Three checks per ledger:
1. **Sequence contiguity:** `seq` values are 0, 1, 2, ... with no gaps
2. **Hash chain:** `event[i].prev == event[i-1].hash` for all i > 0
3. **Hash integrity:** recomputed hash matches stored `hash` for every event

Git provides a second, independent tamper-evidence layer. Legitimate appends show only new lines added at the end of the diff. A rewritten chain shows every line from the tamper point forward changed — an unmissable diff.

### File Locking and Concurrent Access

JSONL files use `fs2` advisory file locks (carried forward from v0.1.x):
- **Writes** (append, checkpoint): exclusive lock, 5-second timeout, error on timeout
- **Reads** (query, verify, render, status): shared lock
- Locks are per-file — writing to the run ledger does not block reading the project ledger

Cross-ledger operations (e.g., writing a run event then a project checkpoint) are NOT atomic. Each write acquires and releases its own file lock independently. If the process crashes between writes, the run ledger may have the event but the project ledger may not have the checkpoint. This is acceptable — checkpoints are performance optimizations, not correctness requirements. The project ledger can always be reconstructed from run ledgers.

Blank lines in JSONL files are silently skipped during reads. A partial line at EOF (from a crash during write) is detected as a JSON parse failure and reported as a warning — the partial line is not included in the chain, and the next append overwrites it.

### Checkpoints

The `_checkpoint` event type (underscore prefix = system/internal) captures materialized state at a point in the ledger:

```json
{"schema":1,"seq":499,"type":"_checkpoint","fields":{"scope":"findings","snapshot":"{\"open\":2,\"resolved\":45,\"total\":47}"}}
```

Written automatically at configurable intervals or explicitly via `sahjhan ledger checkpoint`. The render engine and query planner can scan backward from EOF to find the latest `_checkpoint` and only process events after it.

Checkpoint intervals are configured in `protocol.toml`:

```toml
[checkpoints]
interval = 100  # auto-checkpoint every 100 events (0 = disabled)
```

## Multi-Ledger Support

### Stateful vs Event-Only Ledgers

Sahjhan supports two ledger modes:

- **Stateful** (default): bound to a protocol config (`states.toml`, `transitions.toml`). Supports `status`, `transition`, `gate check`, `render`. This is what a run ledger uses.
- **Event-only**: no state machine. Supports `event`, `log`, `query`, `ledger checkpoint`. Used for accumulators like Holtz's project ledger. Created with `sahjhan ledger create --mode event-only`.

`sahjhan --ledger <name> status` on an event-only ledger returns ledger metadata (event count, last timestamp, chain status) without state machine fields. `sahjhan --ledger <name> transition` returns exit code 3 (config error) on an event-only ledger.

### Ledger Registry

Sahjhan manages multiple named ledgers via a registry at `.sahjhan/ledgers.toml`:

```toml
[[ledgers]]
name = "run-21"
path = "docs/holtz/runs/21/ledger.jsonl"
mode = "stateful"
created = "2026-03-26T07:47:36Z"

[[ledgers]]
name = "project"
path = "docs/holtz/project.jsonl"
mode = "event-only"
created = "2026-03-20T00:00:00Z"
```

The registry is a convenience layer, not a security boundary. All commands accept `--path <file>` to bypass the registry.

### CLI Changes

```bash
# Ledger management
sahjhan ledger create --name <name> --path <path>
sahjhan ledger list
sahjhan ledger remove --name <name>        # removes from registry, keeps file
sahjhan ledger verify --name <name>
sahjhan ledger verify --path <path>         # verify without registry
sahjhan ledger checkpoint --name <name>     # write explicit checkpoint
sahjhan ledger import --name <name> --path <path>  # import JSONL from stdin, wrap in chain

# All existing commands gain --ledger / --path targeting
sahjhan --ledger <name> transition <cmd>
sahjhan --ledger <name> event <type> --field key=value
sahjhan --ledger <name> status
sahjhan --ledger <name> gate check <transition>
sahjhan --ledger <name> render
sahjhan --ledger <name> log tail [N]
sahjhan --ledger <name> log verify
sahjhan --ledger <name> log dump

# Query (new)
sahjhan query --ledger <name> "<SQL>"
sahjhan query --path <path> "<SQL>"
sahjhan query --glob "<pattern>" "<SQL>"
```

When `--ledger` is omitted, sahjhan uses the registry's first ledger (or errors if no registry exists). This preserves backward compatibility for single-ledger usage.

### Renders with Multiple Ledgers

`renders.toml` specifies which ledger a template reads from:

```toml
[[renders]]
target = "STATUS.md"
template = "templates/status.md.tera"
trigger = "on_transition"
ledger = "run-21"

[[renders]]
target = "LIVING-PUNCHLIST.md"
template = "templates/living-punchlist.md.tera"
trigger = "on_event"
event_types = ["_checkpoint"]
ledger = "project"
```

## DataFusion Query Engine

### Embedding

DataFusion is added as a library dependency (`datafusion` crate). JSONL files are registered as Arrow tables. The async runtime (`tokio`) is required by DataFusion — sahjhan gains a minimal tokio runtime for the query path only.

### Table Schema

DataFusion sees each JSONL file as:

```sql
events (
  schema    INT,
  seq       BIGINT,
  prev      VARCHAR,
  hash      VARCHAR,
  ts        TIMESTAMP,
  type      VARCHAR,
  engine    VARCHAR,
  protocol  VARCHAR,
  fields    VARCHAR   -- JSON string, queryable via ->>'key'
)
```

The eight top-level columns are native Arrow columns (fast filtering). `fields` is a JSON string column — DataFusion's JSON functions extract values.

When `--glob` is used, all matching JSONL files are UNION ALL'd into a single `events` table. A virtual `_source` column is added containing the file path, enabling queries to distinguish events by source file. Cross-file JOINs work naturally since all events share the same table.

### Query Command

```bash
# Full SQL
sahjhan query --ledger run-21 "SELECT fields->>'severity', count(*) FROM events WHERE type='finding' GROUP BY 1"

# Glob across ledgers (UNION ALL)
sahjhan query --glob "docs/holtz/runs/*/ledger.jsonl" "SELECT fields->>'run' as run, count(*) FROM events WHERE type='finding' GROUP BY 1"

# Convenience flags (build SQL internally)
sahjhan query --ledger run-21 --type finding --count
sahjhan query --ledger run-21 --type finding --field severity=CRITICAL --json

# Output formats
sahjhan query ... --format table    # default
sahjhan query ... --format json     # JSON array
sahjhan query ... --format csv
sahjhan query ... --format jsonl
```

### Query Gate Type

A new `query` gate type evaluates SQL against the current ledger:

```toml
{ type = "query", sql = "SELECT count(*) < 15 FROM events WHERE type='state_transition' AND fields->>'command'='fix_commit'", expect = "true" }
```

This subsumes several proposed gate types (`max_count`, `ledger_event_count`) in a single extensible mechanism. The existing specific gate types (`ledger_has_event`, etc.) remain as convenience aliases — they're more readable for common patterns.

## Ledger Import

`sahjhan ledger import` reads bare JSONL from stdin (events without `seq`, `prev`, `hash`) and wraps them in a hash chain:

```bash
echo '{"type":"finding","fields":{"id":"BH-001","severity":"HIGH"}}' | \
  sahjhan ledger import --name migrated --path output.jsonl
```

The import command:
1. Reads JSON objects from stdin (one per line)
2. Adds `schema`, `seq`, `prev`, `hash`, `ts` (from input or current time), `engine`, `protocol`
3. Computes hash chain
4. Writes to the output JSONL file

This enables external migration tools to produce domain-specific events without knowing about chain mechanics.

## Dependency Changes

| Action | Crate | Reason |
|--------|-------|--------|
| Remove | `rmp-serde` | MessagePack no longer used |
| Add | `datafusion` | SQL query engine |
| Add | `tokio` | Async runtime (required by DataFusion) |
| Keep | `serde`, `serde_json`, `toml`, `sha2`, `tera`, `clap`, `chrono`, `thiserror`, `regex`, `getrandom`, `fs2` | Unchanged roles |

Binary size impact: ~5MB → ~20MB (DataFusion + Arrow + tokio). Compile time increase: significant but CI-only cost since binaries are pre-compiled for distribution.

## Migration Path

v0.2.0 does not read v0.1.x binary ledgers. Two migration paths:

**Path 1: Binary export (requires v0.1.2 patch release).** A v0.1.2 patch adds `--jsonl` output mode to `log dump`:

```bash
sahjhan-0.1.2 log dump --jsonl | sahjhan-0.2.0 ledger import --name migrated --path new-ledger.jsonl
```

The v0.1.2 patch is minimal (one new output format flag on an existing command) and should ship before v0.2.0 development begins.

**Path 2: Abandon binary data.** For Holtz specifically, the binary ledger from the shakedown run (run 21) contains only 18 events that are already documented in `run-21-sahjhan-shakedown.md`. The Holtz migration script can reconstruct these events from the markdown report without needing the binary export. This path is lossy (synthetic timestamps, synthetic chain) but pragmatic for a shakedown run that was never a production audit.

Consumers with production binary ledgers they need to preserve should use Path 1.

This requires the v0.1.x `log dump` command to gain a `--jsonl` output mode (a patch release, v0.1.2). The v0.2.0 `ledger import` then chains the events.

## What Stays the Same

- TOML config format (protocol.toml, states.toml, transitions.toml, events.toml, renders.toml)
- All 11 existing gate types (plus new `query` gate)
- Tera template rendering (same context shape from `render --dump-context`)
- Manifest tracking (JSON file with SHA-256 hashes)
- Hook generation (`sahjhan hook generate`)
- CLI structure (new subcommands added, existing ones gain `--ledger`)
- Exit codes (0 success, 1 gate blocked, 2 integrity error, 3 config error)

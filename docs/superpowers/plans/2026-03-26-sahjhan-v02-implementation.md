# Sahjhan v0.2.0 Implementation Plan

**Goal:** Replace the binary MessagePack ledger with JSONL + SHA-256 hash chain (RFC 8785 canonical JSON), add multi-ledger support with a TOML registry, embed Apache DataFusion for SQL queries over ledger files, and add checkpoints, ledger import, and a query gate type.

**Architecture:** 8 existing modules (`ledger`, `config`, `state`, `gates`, `render`, `manifest`, `hooks`, `cli`) plus 1 new module (`query`). The ledger module is gutted and rebuilt around JSONL. Config gains multi-ledger registry parsing. Gates gain a `query` type. CLI gains `ledger` and `query` subcommands plus `--ledger`/`--path` targeting on all existing commands.

**Tech Stack:**
- Rust edition 2021, Rust 1.70+
- New deps: `datafusion = "45"`, `tokio = { version = "1", features = ["rt-multi-thread", "macros"] }`
- Removed dep: `rmp-serde`
- Kept: `serde`, `serde_json`, `toml`, `sha2`, `tera`, `clap`, `chrono`, `thiserror`, `regex`, `getrandom`, `fs2`
- Dev: `tempfile`, `assert_cmd`, `predicates`

**Spec:** `2026-03-26-sahjhan-v02-jsonl-datafusion-design.md`

**Branch:** `feat/v0.2.0-jsonl-datafusion` off `main`

---

## Task 0 — v0.1.2 Patch: `--jsonl` Flag on `log dump`

This ships separately on a `fix/v0.1.2-jsonl-export` branch off `main`, before v0.2.0 work begins. It gives existing users a migration path from binary ledgers to JSONL.

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` |
| Modify | `src/cli/log.rs` (or wherever `log dump` is handled) |
| Modify | `tests/integration_tests.rs` |
| Modify | `Cargo.toml` (bump to 0.1.2) |

### Steps

- [ ] **0.1 Write failing test:** Add an integration test `test_log_dump_jsonl` that runs `sahjhan log dump --jsonl` after initializing a ledger with a few events. Assert exit code 0 and that each stdout line is valid JSON with keys `seq`, `ts`, `type`, `fields`.

```rust
// tests/integration_tests.rs
#[test]
fn test_log_dump_jsonl() {
    let dir = setup_initialized_dir();
    // Record a couple of events
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "event", "finding", "--field", "id=BH-001", "--field", "severity=HIGH"])
        .assert().success();

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "log", "dump", "--jsonl"])
        .output().unwrap();
    assert!(output.status.success());

    let stdout = String::from_utf8(output.stdout).unwrap();
    let lines: Vec<&str> = stdout.trim().lines().collect();
    assert!(lines.len() >= 2); // genesis + finding

    for line in &lines {
        let v: serde_json::Value = serde_json::from_str(line)
            .expect("each line must be valid JSON");
        assert!(v.get("seq").is_some());
        assert!(v.get("ts").is_some());
        assert!(v.get("type").is_some());
        assert!(v.get("fields").is_some());
    }
}
```

- [ ] **0.2 Add `--jsonl` flag to `log dump` CLI definition.** In the `LogDump` (or equivalent) clap struct, add:

```rust
/// Output events as JSONL (one JSON object per line)
#[arg(long)]
jsonl: bool,
```

- [ ] **0.3 Implement JSONL output.** In the `log dump` handler, when `jsonl` is true, iterate over ledger entries and emit one JSON object per line to stdout:

```rust
fn dump_jsonl(entries: &[LedgerEntry]) -> Result<()> {
    for entry in entries {
        let payload: HashMap<String, String> =
            rmp_serde::from_slice(&entry.payload)?;
        let obj = serde_json::json!({
            "seq": entry.seq,
            "ts": chrono::DateTime::from_timestamp_millis(entry.timestamp)
                .map(|dt| dt.to_rfc3339())
                .unwrap_or_default(),
            "type": entry.event_type,
            "fields": payload,
        });
        println!("{}", serde_json::to_string(&obj)?);
    }
    Ok(())
}
```

- [ ] **0.4 Run tests, verify pass.**

```bash
cargo test test_log_dump_jsonl -- --nocapture
```

- [ ] **0.5 Bump version to 0.1.2 in `Cargo.toml`.**

```
commit: fix(cli): add --jsonl flag to log dump for binary-to-JSONL migration
```

---

## Task 1 — Dependency Changes and Project Scaffolding

### Files

| Action | Path |
|--------|------|
| Modify | `Cargo.toml` |
| Create | `src/query/mod.rs` |
| Modify | `src/lib.rs` |

### Steps

- [ ] **1.1 Create the feature branch.**

```bash
git checkout main
git checkout -b feat/v0.2.0-jsonl-datafusion
```

- [ ] **1.2 Update `Cargo.toml`.** Remove `rmp-serde`. Add `datafusion`, `tokio`, and `serde_json_canonicalizer` (for RFC 8785):

```toml
[dependencies]
# ... existing deps ...
# REMOVE this line:
# rmp-serde = "1"

# ADD:
datafusion = "45"
tokio = { version = "1", features = ["rt-multi-thread", "macros"] }
```

Note: We will implement RFC 8785 canonicalization by hand (it's straightforward for our schema: sort keys, no whitespace, standard JSON encoding). No external crate needed -- `serde_json` with sorted keys plus a custom serializer handles it. If a `json-canonicalization` crate is available and trustworthy, use it; otherwise the manual approach in Task 2 is correct.

- [ ] **1.3 Create the `query` module stub.**

```rust
// src/query/mod.rs
//! DataFusion-based SQL query engine over JSONL ledger files.
```

- [ ] **1.4 Register the module in `src/lib.rs`.**

```rust
pub mod query;
```

- [ ] **1.5 Verify it compiles.**

```bash
cargo check
```

```
commit: chore: scaffold v0.2.0 — add datafusion/tokio deps, remove rmp-serde, add query module
```

---

## Task 2 — JSONL Ledger Entry (Core Format)

This is the foundational change. Everything else builds on this.

### Files

| Action | Path |
|--------|------|
| Modify | `src/ledger/entry.rs` |
| Modify | `tests/ledger_tests.rs` |

### Steps

- [ ] **2.1 Write failing tests for JSONL round-trip and hashing.**

```rust
// tests/ledger_tests.rs

use sahjhan::ledger::entry::LedgerEntry;
use std::collections::HashMap;

#[test]
fn test_jsonl_round_trip() {
    let mut fields = HashMap::new();
    fields.insert("id".to_string(), "BH-001".to_string());
    fields.insert("severity".to_string(), "HIGH".to_string());

    let entry = LedgerEntry::new(
        0,                           // seq
        "abc123".to_string(),        // prev (genesis nonce)
        "finding",                   // type
        "sahjhan/0.2.0",             // engine
        "holtz/1.0.0",               // protocol
        fields.clone(),
    );

    let jsonl_line = entry.to_jsonl();
    let parsed = LedgerEntry::from_jsonl(&jsonl_line).unwrap();

    assert_eq!(parsed.seq, 0);
    assert_eq!(parsed.event_type, "finding");
    assert_eq!(parsed.fields, fields);
    assert_eq!(parsed.hash, entry.hash);
    assert_eq!(parsed.prev, entry.prev);
}

#[test]
fn test_hash_excludes_hash_field() {
    let mut fields = HashMap::new();
    fields.insert("x".to_string(), "1".to_string());

    let entry = LedgerEntry::new(
        0,
        "0000".to_string(),
        "test",
        "sahjhan/0.2.0",
        "test/1.0.0",
        fields,
    );

    // Recompute hash from scratch -- must match
    let recomputed = LedgerEntry::compute_hash(
        entry.schema, entry.seq, &entry.prev, &entry.ts,
        &entry.event_type, &entry.engine, &entry.protocol, &entry.fields,
    );
    assert_eq!(entry.hash, recomputed);
}

#[test]
fn test_canonical_json_key_ordering() {
    // fields with keys that sort differently than insertion order
    let mut fields = HashMap::new();
    fields.insert("z_last".to_string(), "1".to_string());
    fields.insert("a_first".to_string(), "2".to_string());

    let entry = LedgerEntry::new(
        0, "nonce".to_string(), "test",
        "sahjhan/0.2.0", "test/1.0.0", fields,
    );

    let line = entry.to_jsonl();
    // In canonical JSON, "a_first" must appear before "z_last" inside fields
    let a_pos = line.find("\"a_first\"").unwrap();
    let z_pos = line.find("\"z_last\"").unwrap();
    assert!(a_pos < z_pos, "keys must be sorted alphabetically");
}

#[test]
fn test_hash_chain_linkage() {
    let mut fields = HashMap::new();
    fields.insert("x".to_string(), "1".to_string());

    let entry0 = LedgerEntry::new(
        0, "genesis_nonce".to_string(), "init",
        "sahjhan/0.2.0", "test/1.0.0", fields.clone(),
    );
    let entry1 = LedgerEntry::new(
        1, entry0.hash.clone(), "step",
        "sahjhan/0.2.0", "test/1.0.0", fields,
    );

    assert_eq!(entry1.prev, entry0.hash);
}
```

- [ ] **2.2 Rewrite `LedgerEntry` struct.** Replace the binary-oriented struct with the JSONL envelope:

```rust
// src/ledger/entry.rs

use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

/// Current ledger schema version.
pub const SCHEMA_VERSION: u64 = 1;

/// A single event in a JSONL ledger file.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct LedgerEntry {
    pub schema: u64,
    pub seq: u64,
    pub prev: String,
    pub hash: String,
    pub ts: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub engine: String,
    pub protocol: String,
    pub fields: BTreeMap<String, String>,
}
```

Note the switch from `HashMap` to `BTreeMap` for `fields`. `BTreeMap` iterates in sorted key order, which is required by RFC 8785 canonical JSON. This is the simplest way to guarantee sorted keys in the `fields` object without a custom serializer.

- [ ] **2.3 Implement `LedgerEntry::new()`.** Computes hash at construction time:

```rust
impl LedgerEntry {
    pub fn new(
        seq: u64,
        prev: String,
        event_type: &str,
        engine: &str,
        protocol: &str,
        fields: impl Into<BTreeMap<String, String>>,
    ) -> Self {
        let ts = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let fields = fields.into();
        let hash = Self::compute_hash(
            SCHEMA_VERSION, seq, &prev, &ts,
            event_type, engine, protocol, &fields,
        );
        Self {
            schema: SCHEMA_VERSION,
            seq,
            prev,
            hash,
            ts,
            event_type: event_type.to_string(),
            engine: engine.to_string(),
            protocol: protocol.to_string(),
            fields,
        }
    }
}
```

Provide a `new_with_ts()` variant (or a builder) for import and testing where timestamp is supplied externally.

- [ ] **2.4 Implement `compute_hash()` using RFC 8785 canonical JSON.**

```rust
impl LedgerEntry {
    /// Compute SHA-256 over canonical JSON of all fields except `hash`.
    pub fn compute_hash(
        schema: u64,
        seq: u64,
        prev: &str,
        ts: &str,
        event_type: &str,
        engine: &str,
        protocol: &str,
        fields: &BTreeMap<String, String>,
    ) -> String {
        // Build canonical JSON by hand for absolute control.
        // Keys are hardcoded in alphabetical order.
        // BTreeMap fields are already sorted.
        let fields_json = canonical_json_object(fields);
        let canonical = format!(
            r#"{{"engine":{},"fields":{},"prev":{},"protocol":{},"schema":{},"seq":{},"ts":{},"type":{}}}"#,
            json_string(engine),
            fields_json,
            json_string(prev),
            json_string(protocol),
            schema,          // integer, no quotes
            seq,             // integer, no quotes
            json_string(ts),
            json_string(event_type),
        );

        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        hex::encode(hasher.finalize())
    }
}

/// RFC 8785 JSON string encoding.
/// Only escapes the JSON-required set: `"`, `\`, and control chars U+0000-U+001F.
/// Forward slashes are NOT escaped.
fn json_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if (c as u32) < 0x20 => {
                // Control characters: \uXXXX
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Canonical JSON object from BTreeMap (keys already sorted).
fn canonical_json_object(map: &BTreeMap<String, String>) -> String {
    let mut out = String::from("{");
    for (i, (k, v)) in map.iter().enumerate() {
        if i > 0 { out.push(','); }
        out.push_str(&json_string(k));
        out.push(':');
        out.push_str(&json_string(v));
    }
    out.push('}');
    out
}
```

Note: `hex` is already available as a transitive dep, or add `hex = "0.4"` to `Cargo.toml`. Alternatively, use a manual hex-encode function:

```rust
fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}
```

- [ ] **2.5 Implement `to_jsonl()` and `from_jsonl()`.**

```rust
impl LedgerEntry {
    /// Serialize to a single JSONL line (no trailing newline).
    /// Uses serde_json with sorted keys for the outer object.
    pub fn to_jsonl(&self) -> String {
        // serde_json will serialize BTreeMap fields in sorted order.
        // For the outer object, we also need sorted keys.
        // Since our struct fields have known names, we build it explicitly
        // for canonical output:
        format!(
            r#"{{"engine":{},"fields":{},"hash":{},"prev":{},"protocol":{},"schema":{},"seq":{},"ts":{},"type":{}}}"#,
            json_string(&self.engine),
            canonical_json_object(&self.fields),
            json_string(&self.hash),
            json_string(&self.prev),
            json_string(&self.protocol),
            self.schema,
            self.seq,
            json_string(&self.ts),
            json_string(&self.event_type),
        )
    }

    /// Parse a JSONL line into a LedgerEntry.
    pub fn from_jsonl(line: &str) -> Result<Self, LedgerError> {
        let entry: LedgerEntry = serde_json::from_str(line.trim())
            .map_err(|e| LedgerError::ParseError(e.to_string()))?;
        if entry.schema > SCHEMA_VERSION {
            return Err(LedgerError::UnsupportedVersion(entry.schema));
        }
        Ok(entry)
    }
}
```

- [ ] **2.6 Remove old binary methods.** Delete `to_bytes()`, `from_bytes()`, `from_bytes_partial()`, the `Cursor` struct, `MAGIC`, `FORMAT_VERSION`, and all `rmp_serde` usage from `entry.rs`.

- [ ] **2.7 Update `LedgerError` variants.** Remove binary-specific variants (`InvalidMagic`, `Truncated`). Add/rename:

```rust
#[derive(Debug, thiserror::Error)]
pub enum LedgerError {
    #[error("JSON parse error: {0}")]
    ParseError(String),

    #[error("unsupported schema version: {0}")]
    UnsupportedVersion(u64),

    #[error("hash mismatch at seq {seq}: expected {expected}, got {actual}")]
    HashMismatch { seq: u64, expected: String, actual: String },

    #[error("chain break at seq {seq}: prev={prev}, previous hash={previous_hash}")]
    ChainBreak { seq: u64, prev: String, previous_hash: String },

    #[error("sequence gap: expected {expected}, got {actual}")]
    SequenceGap { expected: u64, actual: u64 },

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("lock timeout on {path}")]
    LockTimeout { path: String },
}
```

- [ ] **2.8 Run tests.**

```bash
cargo test ledger_tests -- --nocapture
```

```
commit: feat(ledger)!: replace binary entry format with JSONL + RFC 8785 hash chain
```

---

## Task 3 — JSONL Ledger Chain (File I/O)

### Files

| Action | Path |
|--------|------|
| Modify | `src/ledger/chain.rs` |
| Modify | `src/ledger/genesis.rs` |
| Modify | `tests/chain_integrity_tests.rs` |

### Steps

- [ ] **3.1 Write failing tests for JSONL chain operations.**

```rust
// tests/chain_integrity_tests.rs

#[test]
fn test_init_creates_jsonl_file_with_genesis() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let ledger = Ledger::init(&path, "test", "1.0.0").unwrap();
    assert_eq!(ledger.entries().len(), 1);
    assert_eq!(ledger.entries()[0].seq, 0);
    assert_eq!(ledger.entries()[0].event_type, "genesis");

    // File should be readable text
    let content = std::fs::read_to_string(&path).unwrap();
    let lines: Vec<&str> = content.lines().collect();
    assert_eq!(lines.len(), 1);
    let _: serde_json::Value = serde_json::from_str(lines[0]).unwrap();
}

#[test]
fn test_append_and_reload() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    let mut fields = BTreeMap::new();
    fields.insert("key".to_string(), "value".to_string());
    ledger.append("custom_event", fields).unwrap();

    // Reload from disk
    let reloaded = Ledger::open(&path).unwrap();
    assert_eq!(reloaded.entries().len(), 2);
    assert_eq!(reloaded.entries()[1].event_type, "custom_event");
}

#[test]
fn test_verify_detects_tampered_hash() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    let mut fields = BTreeMap::new();
    fields.insert("x".to_string(), "1".to_string());
    ledger.append("event", fields).unwrap();

    // Tamper: rewrite second line with a wrong hash
    let content = std::fs::read_to_string(&path).unwrap();
    let mut lines: Vec<String> = content.lines().map(String::from).collect();
    lines[1] = lines[1].replace(&ledger.entries()[1].hash, "deadbeef00000000");
    std::fs::write(&path, lines.join("\n") + "\n").unwrap();

    let result = Ledger::open(&path);
    // Should fail verification
    assert!(result.is_err() || {
        let l = result.unwrap();
        l.verify().is_err()
    });
}

#[test]
fn test_verify_detects_sequence_gap() {
    // ... similar: manually write JSONL with seq 0, 2 (skip 1)
}

#[test]
fn test_blank_lines_skipped() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    // Insert blank line into file
    let content = std::fs::read_to_string(&path).unwrap();
    std::fs::write(&path, format!("{}\n\n", content.trim())).unwrap();

    let reloaded = Ledger::open(&path).unwrap();
    assert_eq!(reloaded.entries().len(), 1); // blank line ignored
}
```

- [ ] **3.2 Rewrite `Ledger` struct for JSONL file I/O.**

```rust
// src/ledger/chain.rs

use std::path::{Path, PathBuf};
use std::io::{BufRead, BufReader, Write};
use fs2::FileExt;

pub struct Ledger {
    path: PathBuf,
    entries: Vec<LedgerEntry>,
    engine: String,
    protocol: String,
}

impl Ledger {
    /// Create a new ledger file with a genesis event.
    pub fn init(path: &Path, protocol_name: &str, protocol_version: &str) -> Result<Self, LedgerError> {
        let engine = format!("sahjhan/{}", env!("CARGO_PKG_VERSION"));
        let protocol = format!("{}/{}", protocol_name, protocol_version);

        // Genesis prev = CSPRNG nonce (64 hex chars)
        let mut nonce = [0u8; 32];
        getrandom::getrandom(&mut nonce).map_err(|e| LedgerError::Io(
            std::io::Error::new(std::io::ErrorKind::Other, e.to_string())
        ))?;
        let prev = hex_encode(&nonce);

        let mut genesis_fields = BTreeMap::new();
        genesis_fields.insert("protocol_name".to_string(), protocol_name.to_string());
        genesis_fields.insert("protocol_version".to_string(), protocol_version.to_string());

        let genesis = LedgerEntry::new(0, prev, "genesis", &engine, &protocol, genesis_fields);

        let file = std::fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(path)?;
        file.lock_exclusive()?;
        let mut writer = std::io::BufWriter::new(&file);
        writeln!(writer, "{}", genesis.to_jsonl())?;
        writer.flush()?;
        file.unlock()?;

        Ok(Self {
            path: path.to_path_buf(),
            entries: vec![genesis],
            engine,
            protocol,
        })
    }

    /// Open an existing JSONL ledger file.
    pub fn open(path: &Path) -> Result<Self, LedgerError> {
        let entries = Self::parse_file(path)?;
        // Extract engine/protocol from genesis
        let genesis = entries.first().ok_or_else(|| {
            LedgerError::ParseError("empty ledger file".to_string())
        })?;
        Ok(Self {
            path: path.to_path_buf(),
            entries,
            engine: genesis.engine.clone(),
            protocol: genesis.protocol.clone(),
        })
    }

    /// Append an event to the ledger file.
    pub fn append(
        &mut self,
        event_type: &str,
        fields: BTreeMap<String, String>,
    ) -> Result<&LedgerEntry, LedgerError> {
        let prev = self.entries.last()
            .map(|e| e.hash.clone())
            .unwrap_or_default();
        let seq = self.entries.len() as u64;
        let entry = LedgerEntry::new(seq, prev, event_type, &self.engine, &self.protocol, fields);

        let file = std::fs::OpenOptions::new()
            .append(true)
            .open(&self.path)?;
        file.lock_exclusive()?;
        let mut writer = std::io::BufWriter::new(&file);
        writeln!(writer, "{}", entry.to_jsonl())?;
        writer.flush()?;
        file.unlock()?;

        self.entries.push(entry);
        Ok(self.entries.last().unwrap())
    }

    /// Re-read entries from disk (picks up external appends).
    pub fn reload(&mut self) -> Result<(), LedgerError> {
        self.entries = Self::parse_file(&self.path)?;
        Ok(())
    }

    /// Verify chain integrity: sequence contiguity, hash chain, hash integrity.
    pub fn verify(&self) -> Result<(), LedgerError> {
        for (i, entry) in self.entries.iter().enumerate() {
            // Sequence contiguity
            if entry.seq != i as u64 {
                return Err(LedgerError::SequenceGap {
                    expected: i as u64,
                    actual: entry.seq,
                });
            }
            // Hash chain (i > 0)
            if i > 0 {
                let prev_hash = &self.entries[i - 1].hash;
                if entry.prev != *prev_hash {
                    return Err(LedgerError::ChainBreak {
                        seq: entry.seq,
                        prev: entry.prev.clone(),
                        previous_hash: prev_hash.clone(),
                    });
                }
            }
            // Hash integrity
            let recomputed = LedgerEntry::compute_hash(
                entry.schema, entry.seq, &entry.prev, &entry.ts,
                &entry.event_type, &entry.engine, &entry.protocol, &entry.fields,
            );
            if entry.hash != recomputed {
                return Err(LedgerError::HashMismatch {
                    seq: entry.seq,
                    expected: recomputed,
                    actual: entry.hash.clone(),
                });
            }
        }
        Ok(())
    }

    pub fn entries(&self) -> &[LedgerEntry] {
        &self.entries
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Parse a JSONL file into entries. Blank lines are skipped.
    fn parse_file(path: &Path) -> Result<Vec<LedgerEntry>, LedgerError> {
        let file = std::fs::File::open(path)?;
        file.lock_shared()?;
        let reader = BufReader::new(&file);
        let mut entries = Vec::new();
        for line in reader.lines() {
            let line = line?;
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue; // skip blank lines
            }
            match LedgerEntry::from_jsonl(trimmed) {
                Ok(entry) => entries.push(entry),
                Err(e) => {
                    // Partial line at EOF: warn but don't include
                    eprintln!("warning: skipping unparseable line: {}", e);
                    break;
                }
            }
        }
        file.unlock()?;
        Ok(entries)
    }
}
```

- [ ] **3.3 Rewrite `create_genesis()` in `genesis.rs`.** The genesis logic is now folded into `Ledger::init()` above. If `genesis.rs` is a separate file, either delete it and inline into `chain.rs`, or update it to construct a `LedgerEntry` with `seq=0`, `type="genesis"`, and a CSPRNG `prev` nonce. Remove all `rmp_serde` usage (the `GenesisPayload` struct is no longer needed -- genesis fields go into the `fields` BTreeMap).

- [ ] **3.4 Run tests.**

```bash
cargo test chain_integrity -- --nocapture
```

```
commit: feat(ledger)!: rewrite chain I/O for JSONL — init, open, append, reload, verify
```

---

## Task 4 — Update State Machine for JSONL

### Files

| Action | Path |
|--------|------|
| Modify | `src/state/machine.rs` |
| Modify | `tests/state_machine_tests.rs` |

### Steps

- [ ] **4.1 Write failing test for state machine with JSONL.**

```rust
#[test]
fn test_state_machine_transition_with_jsonl_ledger() {
    let dir = setup_initialized_dir(); // must now produce .jsonl
    let config = ProtocolConfig::load(dir.path()).unwrap();
    let mut sm = StateMachine::new(&config, dir.path()).unwrap();

    assert_eq!(sm.current_state(), "idle");
    sm.transition("start").unwrap();
    assert_eq!(sm.current_state(), "writing-tests");
}
```

- [ ] **4.2 Replace all `rmp_serde::from_slice()` calls.** The state machine currently deserializes payloads from binary with `rmp_serde::from_slice(&entry.payload)`. With JSONL entries, `entry.fields` is already a `BTreeMap<String, String>` -- no deserialization needed. Find every occurrence and replace:

```rust
// BEFORE:
let payload: HashMap<String, String> = rmp_serde::from_slice(&entry.payload)?;
let value = payload.get("command");

// AFTER:
let value = entry.fields.get("command");
```

The key change: `entry.fields` replaces `entry.payload` everywhere in the state machine. The state machine scans for `event_type == "state_transition"` entries and reads `fields.get("command")`, `fields.get("from_state")`, `fields.get("to_state")` to replay state.

- [ ] **4.3 Update `StateMachine::transition()` to use `BTreeMap` fields.**

```rust
// When appending a state_transition event:
let mut fields = BTreeMap::new();
fields.insert("command".to_string(), command.to_string());
fields.insert("from_state".to_string(), current.to_string());
fields.insert("to_state".to_string(), target.to_string());
self.ledger.append("state_transition", fields)?;
```

- [ ] **4.4 Update `StateMachine::record_event()` similarly.** Event fields are already key-value pairs; just ensure they're `BTreeMap<String, String>` instead of `HashMap<String, String>`.

- [ ] **4.5 Run tests.**

```bash
cargo test state_machine -- --nocapture
```

```
commit: refactor(state): update state machine to read fields directly from JSONL entries
```

---

## Task 5 — Update Gate Evaluators for JSONL

### Files

| Action | Path |
|--------|------|
| Modify | `src/gates/types.rs` |
| Modify | `tests/gate_tests.rs` |

### Steps

- [ ] **5.1 Write/update failing gate tests.** The test infrastructure for gates already exists. Update `setup` helpers to produce JSONL ledgers. Verify all 11 existing gate types still pass.

- [ ] **5.2 Replace `rmp_serde` deserialization in gate evaluators.** Same pattern as Task 4 -- gates that inspect ledger entries switch from `rmp_serde::from_slice(&entry.payload)` to directly accessing `entry.fields`:

```rust
// BEFORE (in ledger_has_event, set_covered, etc.):
let payload: HashMap<String, String> = rmp_serde::from_slice(&entry.payload)?;
if let Some(val) = payload.get(field_name) { ... }

// AFTER:
if let Some(val) = entry.fields.get(field_name) { ... }
```

- [ ] **5.3 Update `GateContext` if it carries payload references.** If `GateContext` stores deserialized payloads, update it to reference `BTreeMap<String, String>` fields.

- [ ] **5.4 Run all gate tests.**

```bash
cargo test gate_tests -- --nocapture
```

```
commit: refactor(gates): update all 11 gate evaluators for JSONL entry fields
```

---

## Task 6 — Update Render Engine for JSONL

### Files

| Action | Path |
|--------|------|
| Modify | `src/render/engine.rs` |
| Modify | `tests/integration_tests.rs` (render-related tests) |

### Steps

- [ ] **6.1 Update `EventSummary` construction.** The render engine builds `EventSummary` structs from ledger entries. Update to read from `entry.fields` instead of deserializing `entry.payload`:

```rust
// BEFORE:
let payload: HashMap<String, String> = rmp_serde::from_slice(&entry.payload)?;
EventSummary {
    seq: entry.seq,
    event_type: entry.event_type.clone(),
    timestamp: format_timestamp(entry.timestamp),
    fields: payload,
}

// AFTER:
EventSummary {
    seq: entry.seq,
    event_type: entry.event_type.clone(),
    timestamp: entry.ts.clone(),  // already ISO 8601 string
    fields: entry.fields.clone().into_iter().collect(), // BTreeMap -> HashMap if needed
}
```

- [ ] **6.2 Update timestamp handling.** Entries now carry ISO 8601 strings in `entry.ts` instead of `i64` Unix millis. The render context should pass these through directly.

- [ ] **6.3 Update `render --dump-context` output.** Verify the JSON dump still has the same shape (or document changes). The `fields` values should look the same to templates since they're still string key-value pairs.

- [ ] **6.4 Run render tests.**

```bash
cargo test -- --nocapture -k render
```

```
commit: refactor(render): update render engine for JSONL entry format
```

---

## Task 7 — Multi-Ledger Registry

### Files

| Action | Path |
|--------|------|
| Create | `src/ledger/registry.rs` |
| Modify | `src/ledger/mod.rs` |
| Modify | `src/config/mod.rs` (or appropriate config module) |
| Create | `tests/registry_tests.rs` |

### Steps

- [ ] **7.1 Write failing tests for the registry.**

```rust
// tests/registry_tests.rs

use sahjhan::ledger::registry::{LedgerRegistry, LedgerMode};
use tempfile::tempdir;

#[test]
fn test_create_and_list_ledgers() {
    let dir = tempdir().unwrap();
    let registry_path = dir.path().join(".sahjhan/ledgers.toml");

    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create("run-21", "docs/runs/21/ledger.jsonl", LedgerMode::Stateful).unwrap();
    registry.create("project", "docs/project.jsonl", LedgerMode::EventOnly).unwrap();

    let list = registry.list();
    assert_eq!(list.len(), 2);
    assert_eq!(list[0].name, "run-21");
    assert_eq!(list[1].name, "project");
}

#[test]
fn test_remove_from_registry() {
    let dir = tempdir().unwrap();
    let registry_path = dir.path().join(".sahjhan/ledgers.toml");

    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create("run-21", "docs/runs/21/ledger.jsonl", LedgerMode::Stateful).unwrap();
    registry.remove("run-21").unwrap();

    assert!(registry.list().is_empty());
    // File should still exist on disk (registry removal != file deletion)
}

#[test]
fn test_resolve_default_ledger() {
    let dir = tempdir().unwrap();
    let registry_path = dir.path().join(".sahjhan/ledgers.toml");

    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create("run-21", "docs/runs/21/ledger.jsonl", LedgerMode::Stateful).unwrap();

    let default = registry.resolve(None).unwrap();
    assert_eq!(default.name, "run-21"); // first entry is default
}

#[test]
fn test_resolve_named_ledger() {
    let dir = tempdir().unwrap();
    let registry_path = dir.path().join(".sahjhan/ledgers.toml");

    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create("run-21", "docs/runs/21/ledger.jsonl", LedgerMode::Stateful).unwrap();
    registry.create("project", "docs/project.jsonl", LedgerMode::EventOnly).unwrap();

    let found = registry.resolve(Some("project")).unwrap();
    assert_eq!(found.name, "project");
}

#[test]
fn test_event_only_rejects_transition() {
    // event-only ledgers cannot do transitions -- this is enforced at the CLI/state-machine level
    // Test that mode is correctly stored and retrievable
    let dir = tempdir().unwrap();
    let registry_path = dir.path().join(".sahjhan/ledgers.toml");

    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create("accum", "accum.jsonl", LedgerMode::EventOnly).unwrap();

    let entry = registry.resolve(Some("accum")).unwrap();
    assert_eq!(entry.mode, LedgerMode::EventOnly);
}
```

- [ ] **7.2 Implement `LedgerRegistry`.**

```rust
// src/ledger/registry.rs

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LedgerMode {
    Stateful,
    EventOnly,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerRegistryEntry {
    pub name: String,
    pub path: String,
    pub mode: LedgerMode,
    pub created: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct RegistryFile {
    ledgers: Vec<LedgerRegistryEntry>,
}

pub struct LedgerRegistry {
    file_path: PathBuf,
    entries: Vec<LedgerRegistryEntry>,
}

impl LedgerRegistry {
    pub fn new(file_path: &Path) -> Self {
        let entries = if file_path.exists() {
            let content = std::fs::read_to_string(file_path).unwrap_or_default();
            let registry: RegistryFile = toml::from_str(&content).unwrap_or(RegistryFile { ledgers: vec![] });
            registry.ledgers
        } else {
            vec![]
        };
        Self { file_path: file_path.to_path_buf(), entries }
    }

    pub fn create(&mut self, name: &str, path: &str, mode: LedgerMode) -> Result<(), String> {
        if self.entries.iter().any(|e| e.name == name) {
            return Err(format!("ledger '{}' already exists in registry", name));
        }
        let entry = LedgerRegistryEntry {
            name: name.to_string(),
            path: path.to_string(),
            mode,
            created: chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        };
        self.entries.push(entry);
        self.save()
    }

    pub fn remove(&mut self, name: &str) -> Result<(), String> {
        let before = self.entries.len();
        self.entries.retain(|e| e.name != name);
        if self.entries.len() == before {
            return Err(format!("ledger '{}' not found in registry", name));
        }
        self.save()
    }

    pub fn list(&self) -> &[LedgerRegistryEntry] {
        &self.entries
    }

    /// Resolve a ledger by name, or return the first entry if name is None.
    pub fn resolve(&self, name: Option<&str>) -> Result<&LedgerRegistryEntry, String> {
        match name {
            Some(n) => self.entries.iter().find(|e| e.name == n)
                .ok_or_else(|| format!("ledger '{}' not found in registry", n)),
            None => self.entries.first()
                .ok_or_else(|| "no ledgers in registry".to_string()),
        }
    }

    fn save(&self) -> Result<(), String> {
        let registry = RegistryFile { ledgers: self.entries.clone() };
        let content = toml::to_string_pretty(&registry)
            .map_err(|e| e.to_string())?;
        if let Some(parent) = self.file_path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        std::fs::write(&self.file_path, content).map_err(|e| e.to_string())?;
        Ok(())
    }
}
```

- [ ] **7.3 Export from `src/ledger/mod.rs`.**

```rust
pub mod registry;
```

- [ ] **7.4 Run tests.**

```bash
cargo test registry_tests -- --nocapture
```

```
commit: feat(ledger): add multi-ledger registry with create/list/remove/resolve
```

---

## Task 8 — Checkpoints

### Files

| Action | Path |
|--------|------|
| Modify | `src/ledger/chain.rs` |
| Modify | `src/config/mod.rs` (add `[checkpoints]` parsing) |
| Create | `tests/checkpoint_tests.rs` |

### Steps

- [ ] **8.1 Write failing tests.**

```rust
// tests/checkpoint_tests.rs

#[test]
fn test_explicit_checkpoint() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    // Add some events
    for i in 0..5 {
        let mut fields = BTreeMap::new();
        fields.insert("i".to_string(), i.to_string());
        ledger.append("finding", fields).unwrap();
    }

    // Write checkpoint
    ledger.write_checkpoint("findings", r#"{"open":2,"resolved":3,"total":5}"#).unwrap();

    let entries = ledger.entries();
    let last = entries.last().unwrap();
    assert_eq!(last.event_type, "_checkpoint");
    assert_eq!(last.fields.get("scope").unwrap(), "findings");
    assert!(last.fields.get("snapshot").is_some());
}

#[test]
fn test_auto_checkpoint_interval() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init_with_checkpoint_interval(&path, "test", "1.0.0", 5).unwrap();

    // Append 5 events (genesis is seq 0, so events are seq 1-5)
    for i in 0..5 {
        let mut fields = BTreeMap::new();
        fields.insert("i".to_string(), i.to_string());
        ledger.append("finding", fields).unwrap();
    }

    // Auto-checkpoint should have fired at event 5
    let checkpoints: Vec<_> = ledger.entries().iter()
        .filter(|e| e.event_type == "_checkpoint")
        .collect();
    assert_eq!(checkpoints.len(), 1);
}

#[test]
fn test_find_latest_checkpoint() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    for i in 0..3 {
        let mut fields = BTreeMap::new();
        fields.insert("i".to_string(), i.to_string());
        ledger.append("finding", fields).unwrap();
    }
    ledger.write_checkpoint("state", "{}").unwrap();

    for i in 3..5 {
        let mut fields = BTreeMap::new();
        fields.insert("i".to_string(), i.to_string());
        ledger.append("finding", fields).unwrap();
    }

    let (cp_seq, entries_after) = ledger.find_latest_checkpoint("state").unwrap();
    assert_eq!(entries_after.len(), 2); // only events after checkpoint
}
```

- [ ] **8.2 Add checkpoint config parsing.** In the config module, parse `[checkpoints]` from `protocol.toml`:

```rust
#[derive(Debug, Deserialize, Default)]
pub struct CheckpointConfig {
    #[serde(default)]
    pub interval: u64, // 0 = disabled
}
```

- [ ] **8.3 Add checkpoint methods to `Ledger`.**

```rust
impl Ledger {
    /// Write an explicit _checkpoint event.
    pub fn write_checkpoint(&mut self, scope: &str, snapshot: &str) -> Result<&LedgerEntry, LedgerError> {
        let mut fields = BTreeMap::new();
        fields.insert("scope".to_string(), scope.to_string());
        fields.insert("snapshot".to_string(), snapshot.to_string());
        self.append("_checkpoint", fields)
    }

    /// Find the latest _checkpoint for a scope and return events after it.
    pub fn find_latest_checkpoint(&self, scope: &str) -> Option<(u64, &[LedgerEntry])> {
        for (i, entry) in self.entries.iter().enumerate().rev() {
            if entry.event_type == "_checkpoint" {
                if let Some(s) = entry.fields.get("scope") {
                    if s == scope {
                        return Some((entry.seq, &self.entries[i + 1..]));
                    }
                }
            }
        }
        None
    }

    /// Append with auto-checkpoint support.
    /// Call this instead of raw append() when checkpoint_interval > 0.
    pub fn append_with_checkpoint(
        &mut self,
        event_type: &str,
        fields: BTreeMap<String, String>,
        checkpoint_interval: u64,
        checkpoint_fn: impl FnOnce(&[LedgerEntry]) -> Option<(String, String)>,
    ) -> Result<&LedgerEntry, LedgerError> {
        self.append(event_type, fields)?;

        if checkpoint_interval > 0 {
            let events_since_checkpoint = self.count_events_since_last_checkpoint();
            if events_since_checkpoint >= checkpoint_interval {
                if let Some((scope, snapshot)) = checkpoint_fn(self.entries()) {
                    self.write_checkpoint(&scope, &snapshot)?;
                }
            }
        }

        Ok(self.entries.last().unwrap())
    }

    fn count_events_since_last_checkpoint(&self) -> u64 {
        let mut count = 0u64;
        for entry in self.entries.iter().rev() {
            if entry.event_type == "_checkpoint" {
                break;
            }
            count += 1;
        }
        count
    }
}
```

- [ ] **8.4 Run tests.**

```bash
cargo test checkpoint -- --nocapture
```

```
commit: feat(ledger): add _checkpoint events with auto-checkpoint intervals
```

---

## Task 9 — Ledger Import

### Files

| Action | Path |
|--------|------|
| Create | `src/ledger/import.rs` |
| Modify | `src/ledger/mod.rs` |
| Create | `tests/import_tests.rs` |

### Steps

- [ ] **9.1 Write failing tests.**

```rust
// tests/import_tests.rs

use sahjhan::ledger::import::import_jsonl;
use std::io::Cursor;

#[test]
fn test_import_bare_jsonl() {
    let dir = tempdir().unwrap();
    let output = dir.path().join("imported.jsonl");

    let input = r#"{"type":"finding","fields":{"id":"BH-001","severity":"HIGH"}}
{"type":"finding","fields":{"id":"BH-002","severity":"LOW"}}
"#;

    import_jsonl(
        &mut Cursor::new(input.as_bytes()),
        &output,
        "holtz", "1.0.0",
    ).unwrap();

    let ledger = Ledger::open(&output).unwrap();
    // genesis + 2 imported events
    assert_eq!(ledger.entries().len(), 3);
    assert_eq!(ledger.entries()[0].event_type, "genesis");
    assert_eq!(ledger.entries()[1].event_type, "finding");
    assert_eq!(ledger.entries()[1].fields.get("id").unwrap(), "BH-001");
    assert_eq!(ledger.entries()[2].fields.get("id").unwrap(), "BH-002");

    // Verify chain integrity
    ledger.verify().unwrap();
}

#[test]
fn test_import_with_existing_timestamps() {
    let dir = tempdir().unwrap();
    let output = dir.path().join("imported.jsonl");

    let input = r#"{"type":"finding","ts":"2026-01-15T10:00:00Z","fields":{"id":"BH-001"}}
"#;

    import_jsonl(
        &mut Cursor::new(input.as_bytes()),
        &output,
        "holtz", "1.0.0",
    ).unwrap();

    let ledger = Ledger::open(&output).unwrap();
    assert_eq!(ledger.entries()[1].ts, "2026-01-15T10:00:00Z");
}

#[test]
fn test_import_preserves_extra_fields() {
    let dir = tempdir().unwrap();
    let output = dir.path().join("imported.jsonl");

    let input = r#"{"type":"snapshot","fields":{"key":"coverage","value":"87.3"}}
"#;

    import_jsonl(
        &mut Cursor::new(input.as_bytes()),
        &output,
        "holtz", "1.0.0",
    ).unwrap();

    let ledger = Ledger::open(&output).unwrap();
    let entry = &ledger.entries()[1];
    assert_eq!(entry.fields.get("key").unwrap(), "coverage");
    assert_eq!(entry.fields.get("value").unwrap(), "87.3");
}
```

- [ ] **9.2 Implement `import_jsonl()`.**

```rust
// src/ledger/import.rs

use crate::ledger::{chain::Ledger, entry::LedgerEntry};
use std::collections::BTreeMap;
use std::io::BufRead;
use std::path::Path;

/// Read bare JSONL from a reader and write a hash-chained ledger file.
///
/// Input events need only `type` and `fields`. Optional `ts` is preserved
/// if present; otherwise current time is used. `schema`, `seq`, `prev`,
/// `hash`, `engine`, `protocol` are computed/overwritten.
pub fn import_jsonl(
    reader: &mut dyn BufRead,
    output_path: &Path,
    protocol_name: &str,
    protocol_version: &str,
) -> Result<(), crate::ledger::entry::LedgerError> {
    let mut ledger = Ledger::init(output_path, protocol_name, protocol_version)?;

    for line in reader.lines() {
        let line = line?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let raw: serde_json::Value = serde_json::from_str(trimmed)
            .map_err(|e| crate::ledger::entry::LedgerError::ParseError(e.to_string()))?;

        let event_type = raw.get("type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| crate::ledger::entry::LedgerError::ParseError(
                "missing 'type' field in input".to_string()
            ))?
            .to_string();

        let fields: BTreeMap<String, String> = match raw.get("fields") {
            Some(obj) => {
                let map = obj.as_object()
                    .ok_or_else(|| crate::ledger::entry::LedgerError::ParseError(
                        "'fields' must be an object".to_string()
                    ))?;
                map.iter()
                    .map(|(k, v)| {
                        let val = match v {
                            serde_json::Value::String(s) => s.clone(),
                            other => other.to_string(),
                        };
                        (k.clone(), val)
                    })
                    .collect()
            }
            None => BTreeMap::new(),
        };

        // Use provided timestamp if available, otherwise append() will use now()
        // For custom timestamps, we need a variant that accepts ts
        if let Some(ts) = raw.get("ts").and_then(|v| v.as_str()) {
            ledger.append_with_ts(&event_type, fields, ts)?;
        } else {
            ledger.append(&event_type, fields)?;
        }
    }

    Ok(())
}
```

This requires adding an `append_with_ts()` method to `Ledger` that accepts an explicit timestamp string instead of using `Utc::now()`. Add it alongside `append()` in `chain.rs`:

```rust
/// Append with an explicit timestamp (for import/migration).
pub fn append_with_ts(
    &mut self,
    event_type: &str,
    fields: BTreeMap<String, String>,
    ts: &str,
) -> Result<&LedgerEntry, LedgerError> {
    let prev = self.entries.last().map(|e| e.hash.clone()).unwrap_or_default();
    let seq = self.entries.len() as u64;
    let entry = LedgerEntry::new_with_ts(seq, prev, event_type, &self.engine, &self.protocol, fields, ts);
    // ... same file write logic as append() ...
}
```

And `LedgerEntry::new_with_ts()` in `entry.rs`:

```rust
pub fn new_with_ts(
    seq: u64,
    prev: String,
    event_type: &str,
    engine: &str,
    protocol: &str,
    fields: impl Into<BTreeMap<String, String>>,
    ts: &str,
) -> Self {
    let fields = fields.into();
    let hash = Self::compute_hash(
        SCHEMA_VERSION, seq, &prev, ts,
        event_type, engine, protocol, &fields,
    );
    Self {
        schema: SCHEMA_VERSION, seq, prev, hash,
        ts: ts.to_string(),
        event_type: event_type.to_string(),
        engine: engine.to_string(),
        protocol: protocol.to_string(),
        fields,
    }
}
```

- [ ] **9.3 Export from `src/ledger/mod.rs`.**

```rust
pub mod import;
```

- [ ] **9.4 Run tests.**

```bash
cargo test import_tests -- --nocapture
```

```
commit: feat(ledger): add ledger import — stdin JSONL to hash-chained ledger file
```

---

## Task 10 — DataFusion Query Engine

### Files

| Action | Path |
|--------|------|
| Modify | `src/query/mod.rs` |
| Create | `tests/query_tests.rs` |

### Steps

- [ ] **10.1 Write failing tests.**

```rust
// tests/query_tests.rs

use sahjhan::query::QueryEngine;
use sahjhan::ledger::chain::Ledger;
use std::collections::BTreeMap;
use tempfile::tempdir;

#[tokio::test]
async fn test_query_count_by_type() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    for i in 0..3 {
        let mut fields = BTreeMap::new();
        fields.insert("id".to_string(), format!("F-{}", i));
        fields.insert("severity".to_string(), "HIGH".to_string());
        ledger.append("finding", fields).unwrap();
    }

    let engine = QueryEngine::new();
    let results = engine.query_file(
        &path,
        "SELECT count(*) as cnt FROM events WHERE type = 'finding'"
    ).await.unwrap();

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].get("cnt").unwrap(), "3");
}

#[tokio::test]
async fn test_query_fields_extraction() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.jsonl");
    let mut ledger = Ledger::init(&path, "test", "1.0.0").unwrap();

    let mut fields = BTreeMap::new();
    fields.insert("id".to_string(), "BH-001".to_string());
    fields.insert("severity".to_string(), "CRITICAL".to_string());
    ledger.append("finding", fields).unwrap();

    let engine = QueryEngine::new();
    let results = engine.query_file(
        &path,
        "SELECT fields->>'severity' as sev FROM events WHERE type = 'finding'"
    ).await.unwrap();

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].get("sev").unwrap(), "CRITICAL");
}

#[tokio::test]
async fn test_query_glob_multiple_files() {
    let dir = tempdir().unwrap();

    // Create two ledger files
    let path1 = dir.path().join("run1.jsonl");
    let path2 = dir.path().join("run2.jsonl");

    let mut l1 = Ledger::init(&path1, "test", "1.0.0").unwrap();
    let mut fields = BTreeMap::new();
    fields.insert("run".to_string(), "1".to_string());
    l1.append("finding", fields).unwrap();

    let mut l2 = Ledger::init(&path2, "test", "1.0.0").unwrap();
    let mut fields = BTreeMap::new();
    fields.insert("run".to_string(), "2".to_string());
    l2.append("finding", fields).unwrap();

    let engine = QueryEngine::new();
    let pattern = dir.path().join("*.jsonl").to_str().unwrap().to_string();
    let results = engine.query_glob(
        &pattern,
        "SELECT count(*) as cnt FROM events WHERE type = 'finding'"
    ).await.unwrap();

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].get("cnt").unwrap(), "2");
}

#[tokio::test]
async fn test_query_source_column() {
    let dir = tempdir().unwrap();
    let path1 = dir.path().join("run1.jsonl");
    let path2 = dir.path().join("run2.jsonl");

    let mut l1 = Ledger::init(&path1, "test", "1.0.0").unwrap();
    l1.append("finding", BTreeMap::new()).unwrap();

    let mut l2 = Ledger::init(&path2, "test", "1.0.0").unwrap();
    l2.append("finding", BTreeMap::new()).unwrap();

    let engine = QueryEngine::new();
    let pattern = dir.path().join("*.jsonl").to_str().unwrap().to_string();
    let results = engine.query_glob(
        &pattern,
        "SELECT DISTINCT _source FROM events WHERE type = 'finding' ORDER BY _source"
    ).await.unwrap();

    assert_eq!(results.len(), 2);
    // _source contains file paths
    assert!(results[0].get("_source").unwrap().contains("run1.jsonl"));
    assert!(results[1].get("_source").unwrap().contains("run2.jsonl"));
}
```

- [ ] **10.2 Implement `QueryEngine`.**

```rust
// src/query/mod.rs

use datafusion::prelude::*;
use datafusion::arrow::array::{
    StringArray, Int64Array, RecordBatch, ArrayRef,
};
use datafusion::arrow::datatypes::{DataType, Field, Schema};
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Arc;

pub struct QueryEngine;

impl QueryEngine {
    pub fn new() -> Self {
        Self
    }

    /// Query a single JSONL ledger file.
    pub async fn query_file(
        &self,
        path: &Path,
        sql: &str,
    ) -> Result<Vec<BTreeMap<String, String>>, Box<dyn std::error::Error>> {
        let ctx = SessionContext::new();
        self.register_jsonl_file(&ctx, path, None).await?;
        self.execute(&ctx, sql).await
    }

    /// Query multiple JSONL files matching a glob pattern (UNION ALL).
    pub async fn query_glob(
        &self,
        pattern: &str,
        sql: &str,
    ) -> Result<Vec<BTreeMap<String, String>>, Box<dyn std::error::Error>> {
        let ctx = SessionContext::new();
        let paths: Vec<_> = glob::glob(pattern)?
            .filter_map(|p| p.ok())
            .collect();

        if paths.is_empty() {
            return Err("no files match glob pattern".into());
        }

        // Register each file, UNION ALL into a single "events" table
        // by registering them as separate tables then creating a view
        let mut union_parts = Vec::new();
        for (i, path) in paths.iter().enumerate() {
            let table_name = format!("_events_{}", i);
            self.register_jsonl_file(&ctx, path, Some(&table_name)).await?;
            let source_path = path.to_str().unwrap_or("");
            union_parts.push(format!(
                "SELECT *, '{}' as _source FROM {}",
                source_path.replace('\'', "''"),
                table_name
            ));
        }
        let union_sql = union_parts.join(" UNION ALL ");
        ctx.sql(&format!("CREATE VIEW events AS {}", union_sql)).await?;

        self.execute(&ctx, sql).await
    }

    /// Register a single JSONL file as the "events" table (or custom name).
    async fn register_jsonl_file(
        &self,
        ctx: &SessionContext,
        path: &Path,
        table_name: Option<&str>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let name = table_name.unwrap_or("events");

        // Read JSONL and build Arrow record batches
        let entries = crate::ledger::chain::Ledger::parse_file_public(path)?;

        let schema = Arc::new(Schema::new(vec![
            Field::new("schema", DataType::Int64, false),
            Field::new("seq", DataType::Int64, false),
            Field::new("prev", DataType::Utf8, false),
            Field::new("hash", DataType::Utf8, false),
            Field::new("ts", DataType::Utf8, false),  // kept as string; TIMESTAMP casting done in SQL
            Field::new("type", DataType::Utf8, false),
            Field::new("engine", DataType::Utf8, false),
            Field::new("protocol", DataType::Utf8, false),
            Field::new("fields", DataType::Utf8, false),  // JSON string
        ]));

        let mut schema_vals = Vec::new();
        let mut seq_vals = Vec::new();
        let mut prev_vals = Vec::new();
        let mut hash_vals = Vec::new();
        let mut ts_vals = Vec::new();
        let mut type_vals = Vec::new();
        let mut engine_vals = Vec::new();
        let mut protocol_vals = Vec::new();
        let mut fields_vals = Vec::new();

        for entry in &entries {
            schema_vals.push(entry.schema as i64);
            seq_vals.push(entry.seq as i64);
            prev_vals.push(entry.prev.as_str());
            hash_vals.push(entry.hash.as_str());
            ts_vals.push(entry.ts.as_str());
            type_vals.push(entry.event_type.as_str());
            engine_vals.push(entry.engine.as_str());
            protocol_vals.push(entry.protocol.as_str());
            // Serialize fields as JSON string for ->>'key' access
            fields_vals.push(serde_json::to_string(&entry.fields).unwrap());
        }

        // Build string ref vectors for StringArray
        let fields_refs: Vec<&str> = fields_vals.iter().map(|s| s.as_str()).collect();

        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(Int64Array::from(schema_vals)) as ArrayRef,
                Arc::new(Int64Array::from(seq_vals)) as ArrayRef,
                Arc::new(StringArray::from(prev_vals)) as ArrayRef,
                Arc::new(StringArray::from(hash_vals)) as ArrayRef,
                Arc::new(StringArray::from(ts_vals)) as ArrayRef,
                Arc::new(StringArray::from(type_vals)) as ArrayRef,
                Arc::new(StringArray::from(engine_vals)) as ArrayRef,
                Arc::new(StringArray::from(protocol_vals)) as ArrayRef,
                Arc::new(StringArray::from(fields_refs)) as ArrayRef,
            ],
        )?;

        let provider = datafusion::datasource::MemTable::try_new(schema, vec![vec![batch]])?;
        ctx.register_table(name, Arc::new(provider))?;
        Ok(())
    }

    /// Execute SQL and return results as Vec<BTreeMap<String, String>>.
    async fn execute(
        &self,
        ctx: &SessionContext,
        sql: &str,
    ) -> Result<Vec<BTreeMap<String, String>>, Box<dyn std::error::Error>> {
        let df = ctx.sql(sql).await?;
        let batches = df.collect().await?;

        let mut results = Vec::new();
        for batch in &batches {
            let schema = batch.schema();
            for row_idx in 0..batch.num_rows() {
                let mut row = BTreeMap::new();
                for (col_idx, field) in schema.fields().iter().enumerate() {
                    let col = batch.column(col_idx);
                    let value = datafusion::arrow::util::display::array_value_to_string(col, row_idx)?;
                    row.insert(field.name().clone(), value);
                }
                results.push(row);
            }
        }
        Ok(results)
    }
}
```

Note: This implementation loads ledger entries into an in-memory Arrow MemTable. For the `fields` column, DataFusion's JSON functions (`->>'key'`) work on string columns containing JSON. The exact DataFusion version may require `json_get_str` or similar -- check the datafusion docs for the version pinned. If `->>'key'` isn't supported, use `json_extract_scalar(fields, '$.key')` instead.

You'll also need to expose `parse_file` publicly from `Ledger` (or add a public `parse_file_public` wrapper).

- [ ] **10.3 Add `glob` dependency if not already present.**

```toml
glob = "0.3"
```

- [ ] **10.4 Run tests.**

```bash
cargo test query_tests -- --nocapture
```

```
commit: feat(query): embed DataFusion query engine over JSONL ledger files
```

---

## Task 11 — Query Gate Type

### Files

| Action | Path |
|--------|------|
| Modify | `src/gates/types.rs` |
| Modify | `tests/gate_tests.rs` |

### Steps

- [ ] **11.1 Write failing test for the `query` gate.**

```rust
// tests/gate_tests.rs

#[test]
fn test_query_gate_pass() {
    let dir = setup_initialized_dir();
    // ... append some events ...

    let gate = GateConfig {
        gate_type: "query".to_string(),
        params: {
            let mut m = HashMap::new();
            m.insert("sql".to_string(), toml::Value::String(
                "SELECT count(*) < 10 as result FROM events WHERE type='finding'".to_string()
            ));
            m.insert("expect".to_string(), toml::Value::String("true".to_string()));
            m
        },
    };

    let ctx = build_gate_context(&dir);
    let result = evaluate_gate(&gate, &ctx).unwrap();
    assert!(result.passed);
}

#[test]
fn test_query_gate_fail() {
    let dir = setup_initialized_dir();
    // Append 10+ findings ...

    let gate = GateConfig {
        gate_type: "query".to_string(),
        params: {
            let mut m = HashMap::new();
            m.insert("sql".to_string(), toml::Value::String(
                "SELECT count(*) < 5 as result FROM events WHERE type='finding'".to_string()
            ));
            m.insert("expect".to_string(), toml::Value::String("true".to_string()));
            m
        },
    };

    let ctx = build_gate_context(&dir);
    let result = evaluate_gate(&gate, &ctx).unwrap();
    assert!(!result.passed);
}
```

- [ ] **11.2 Add `query` gate evaluator.** In the gate dispatch function, add the `"query"` match arm:

```rust
"query" => eval_query_gate(gate, ctx),
```

Implement:

```rust
fn eval_query_gate(gate: &GateConfig, ctx: &GateContext) -> Result<GateResult, GateError> {
    let sql = gate.params.get("sql")
        .and_then(|v| v.as_str())
        .ok_or_else(|| GateError::MissingParam("sql".to_string()))?;
    let expect = gate.params.get("expect")
        .and_then(|v| v.as_str())
        .unwrap_or("true");

    // Build a minimal tokio runtime for the query
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| GateError::Internal(e.to_string()))?;

    let ledger_path = ctx.ledger.path().to_path_buf();
    let results = rt.block_on(async {
        let engine = crate::query::QueryEngine::new();
        engine.query_file(&ledger_path, sql).await
    }).map_err(|e| GateError::Internal(e.to_string()))?;

    // The SQL should return a single row with a single column named "result"
    // (or the first column of the first row is used)
    let actual = results.first()
        .and_then(|row| row.values().next())
        .map(|v| v.to_string())
        .unwrap_or_else(|| "null".to_string());

    let passed = actual == expect;
    Ok(GateResult {
        passed,
        gate_type: "query".to_string(),
        message: if passed {
            format!("query returned '{}'", actual)
        } else {
            format!("query returned '{}', expected '{}'", actual, expect)
        },
    })
}
```

- [ ] **11.3 Run gate tests.**

```bash
cargo test gate_tests -- --nocapture
```

```
commit: feat(gates): add query gate type — SQL evaluation against ledger
```

---

## Task 12 — CLI: `ledger` Subcommand

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` |
| Create | `src/cli/ledger.rs` (or add to existing CLI module) |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **12.1 Write failing integration tests for ledger subcommands.**

```rust
#[test]
fn test_ledger_create_and_list() {
    let dir = setup_initialized_dir();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "run-1",
                "--path", "run1.jsonl"])
        .assert().success();

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "list"])
        .output().unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("run-1"));
}

#[test]
fn test_ledger_remove() {
    let dir = setup_initialized_dir();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "run-1",
                "--path", "run1.jsonl"])
        .assert().success();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "remove", "--name", "run-1"])
        .assert().success();

    // File still exists, just removed from registry
    assert!(dir.path().join("run1.jsonl").exists());
}

#[test]
fn test_ledger_verify() {
    let dir = setup_initialized_dir();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "verify", "--path",
                dir.path().join(".sahjhan/ledger.jsonl").to_str().unwrap()])
        .assert().success();
}

#[test]
fn test_ledger_checkpoint() {
    let dir = setup_initialized_dir();
    // ... add events ...

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "checkpoint", "--name", "default"])
        .assert().success();
}

#[test]
fn test_ledger_import() {
    let dir = setup_initialized_dir();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "import", "--name", "migrated",
                "--path", dir.path().join("migrated.jsonl").to_str().unwrap()])
        .write_stdin(r#"{"type":"finding","fields":{"id":"BH-001"}}"#)
        .assert().success();

    // Verify the imported ledger
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "verify", "--path",
                dir.path().join("migrated.jsonl").to_str().unwrap()])
        .assert().success();
}

#[test]
fn test_ledger_create_event_only() {
    let dir = setup_initialized_dir();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "project",
                "--path", "project.jsonl", "--mode", "event-only"])
        .assert().success();

    // Transition on event-only ledger should fail with exit code 3
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "--ledger", "project", "transition", "start"])
        .assert().code(3);
}
```

- [ ] **12.2 Define the `ledger` subcommand in clap.**

```rust
#[derive(clap::Subcommand)]
enum LedgerCommands {
    /// Create a new named ledger
    Create {
        #[arg(long)]
        name: String,
        #[arg(long)]
        path: String,
        #[arg(long, default_value = "stateful")]
        mode: String,
    },
    /// List all registered ledgers
    List,
    /// Remove a ledger from the registry (keeps the file)
    Remove {
        #[arg(long)]
        name: String,
    },
    /// Verify ledger chain integrity
    Verify {
        #[arg(long, group = "target")]
        name: Option<String>,
        #[arg(long, group = "target")]
        path: Option<String>,
    },
    /// Write an explicit checkpoint
    Checkpoint {
        #[arg(long)]
        name: String,
    },
    /// Import JSONL from stdin into a new ledger
    Import {
        #[arg(long)]
        name: String,
        #[arg(long)]
        path: String,
    },
}
```

- [ ] **12.3 Implement handlers for each subcommand.** Each handler delegates to the library functions built in Tasks 7-9:
  - `create` -> `LedgerRegistry::create()` + `Ledger::init()`
  - `list` -> `LedgerRegistry::list()` + formatted table output
  - `remove` -> `LedgerRegistry::remove()`
  - `verify` -> `Ledger::open()` + `Ledger::verify()`
  - `checkpoint` -> resolve ledger from registry, `Ledger::write_checkpoint()`
  - `import` -> `import_jsonl()` from stdin + `LedgerRegistry::create()`

- [ ] **12.4 Run integration tests.**

```bash
cargo test integration -- --nocapture
```

```
commit: feat(cli): add ledger subcommand — create, list, remove, verify, checkpoint, import
```

---

## Task 13 — CLI: `query` Subcommand

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` |
| Create | `src/cli/query.rs` (or add to CLI module) |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **13.1 Write failing integration tests.**

```rust
#[test]
fn test_query_command_table_output() {
    let dir = setup_initialized_dir();
    // Add some events
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "event", "finding", "--field", "id=BH-001", "--field", "severity=HIGH"])
        .assert().success();

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "query", "--ledger", "default",
                "SELECT count(*) as cnt FROM events WHERE type='finding'"])
        .output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("1"));
}

#[test]
fn test_query_command_json_output() {
    let dir = setup_initialized_dir();
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "event", "finding", "--field", "id=BH-001"])
        .assert().success();

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "query", "--ledger", "default", "--format", "json",
                "SELECT type FROM events WHERE type='finding'"])
        .output().unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert!(parsed.is_array());
}

#[test]
fn test_query_by_path() {
    let dir = setup_initialized_dir();
    let ledger_path = dir.path().join(".sahjhan/ledger.jsonl");

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["query", "--path", ledger_path.to_str().unwrap(),
                "SELECT count(*) as cnt FROM events"])
        .output().unwrap();
    assert!(output.status.success());
}

#[test]
fn test_query_convenience_flags() {
    let dir = setup_initialized_dir();
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "event", "finding", "--field", "id=BH-001", "--field", "severity=HIGH"])
        .assert().success();

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "query", "--ledger", "default",
                "--type", "finding", "--count"])
        .output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("1"));
}
```

- [ ] **13.2 Define the `query` subcommand.**

```rust
/// Run SQL queries against ledger files
#[derive(clap::Args)]
struct QueryArgs {
    /// Target ledger by registry name
    #[arg(long, group = "target")]
    ledger: Option<String>,

    /// Target ledger file directly
    #[arg(long, group = "target")]
    path: Option<String>,

    /// Glob pattern for multi-file queries
    #[arg(long, group = "target")]
    glob: Option<String>,

    /// SQL query (positional)
    sql: Option<String>,

    /// Convenience: filter by event type
    #[arg(long, name = "type")]
    event_type: Option<String>,

    /// Convenience: filter by field value (key=value)
    #[arg(long)]
    field: Vec<String>,

    /// Convenience: count matching events
    #[arg(long)]
    count: bool,

    /// Convenience: output as JSON
    #[arg(long)]
    json: bool,

    /// Output format
    #[arg(long, default_value = "table")]
    format: String,
}
```

- [ ] **13.3 Implement the query handler.** The handler:
  1. Resolves the target (registry name -> path, direct path, or glob)
  2. If convenience flags are set and no SQL provided, builds SQL internally
  3. Creates a tokio runtime and runs the query
  4. Formats output (table/json/csv/jsonl)

```rust
fn handle_query(args: &QueryArgs, config_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let sql = if let Some(ref sql) = args.sql {
        sql.clone()
    } else {
        // Build SQL from convenience flags
        build_convenience_sql(args)?
    };

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?;

    let engine = QueryEngine::new();

    let results = if let Some(ref glob_pattern) = args.glob {
        rt.block_on(engine.query_glob(glob_pattern, &sql))?
    } else {
        let path = resolve_ledger_path(args, config_dir)?;
        rt.block_on(engine.query_file(&path, &sql))?
    };

    match args.format.as_str() {
        "json" => println!("{}", serde_json::to_string_pretty(&results)?),
        "csv" => print_csv(&results),
        "jsonl" => {
            for row in &results {
                println!("{}", serde_json::to_string(row)?);
            }
        }
        _ => print_table(&results), // "table" default
    }

    Ok(())
}

fn build_convenience_sql(args: &QueryArgs) -> Result<String, Box<dyn std::error::Error>> {
    let mut conditions = Vec::new();
    if let Some(ref t) = args.event_type {
        conditions.push(format!("type = '{}'", t.replace('\'', "''")));
    }
    for f in &args.field {
        let (key, value) = f.split_once('=')
            .ok_or("--field must be key=value")?;
        conditions.push(format!(
            "fields->>'{}' = '{}'",
            key.replace('\'', "''"),
            value.replace('\'', "''"),
        ));
    }

    let where_clause = if conditions.is_empty() {
        String::new()
    } else {
        format!(" WHERE {}", conditions.join(" AND "))
    };

    if args.count {
        Ok(format!("SELECT count(*) as count FROM events{}", where_clause))
    } else {
        Ok(format!("SELECT * FROM events{}", where_clause))
    }
}
```

- [ ] **13.4 Run integration tests.**

```bash
cargo test integration -- --nocapture
```

```
commit: feat(cli): add query subcommand with SQL, glob, convenience flags, and output formats
```

---

## Task 14 — CLI: `--ledger` / `--path` Targeting on All Commands

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **14.1 Write failing integration tests.**

```rust
#[test]
fn test_status_with_ledger_flag() {
    let dir = setup_initialized_dir();
    // Create a named ledger via the registry
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "run-1",
                "--path", "run1.jsonl"])
        .assert().success();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "--ledger", "run-1", "status"])
        .assert().success();
}

#[test]
fn test_event_with_ledger_flag() {
    let dir = setup_initialized_dir();
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "project",
                "--path", "project.jsonl", "--mode", "event-only"])
        .assert().success();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "--ledger", "project", "event", "finding",
                "--field", "id=BH-001"])
        .assert().success();
}

#[test]
fn test_transition_on_event_only_returns_exit_3() {
    let dir = setup_initialized_dir();
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "ledger", "create", "--name", "accum",
                "--path", "accum.jsonl", "--mode", "event-only"])
        .assert().success();

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "--ledger", "accum", "transition", "start"])
        .assert().code(3);
}

#[test]
fn test_log_tail_with_ledger_flag() {
    let dir = setup_initialized_dir();
    // ... create ledger, add events ...

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(),
                "--ledger", "default", "log", "tail", "5"])
        .assert().success();
}
```

- [ ] **14.2 Add global `--ledger` and `--path` flags to the top-level CLI struct.**

```rust
#[derive(clap::Parser)]
struct Cli {
    #[arg(long)]
    config_dir: Option<String>,

    /// Target a specific named ledger from the registry
    #[arg(long, global = true)]
    ledger: Option<String>,

    /// Target a ledger file directly (bypasses registry)
    #[arg(long, global = true)]
    path: Option<String>,

    #[command(subcommand)]
    command: Commands,
}
```

- [ ] **14.3 Update the ledger resolution logic.** Before executing any command that needs a ledger, resolve it:

```rust
fn resolve_ledger(cli: &Cli, config_dir: &Path) -> Result<PathBuf, Error> {
    if let Some(ref path) = cli.path {
        return Ok(PathBuf::from(path));
    }

    let registry_path = config_dir.join(".sahjhan/ledgers.toml");
    if registry_path.exists() {
        let registry = LedgerRegistry::new(&registry_path);
        let entry = registry.resolve(cli.ledger.as_deref())?;
        return Ok(PathBuf::from(&entry.path));
    }

    // Backward compat: single ledger at .sahjhan/ledger.jsonl
    let default = config_dir.join(".sahjhan/ledger.jsonl");
    if default.exists() {
        return Ok(default);
    }

    Err(Error::Config("no ledger found; use --ledger, --path, or create one".to_string()))
}

fn resolve_ledger_mode(cli: &Cli, config_dir: &Path) -> Result<LedgerMode, Error> {
    if let Some(ref name) = cli.ledger {
        let registry_path = config_dir.join(".sahjhan/ledgers.toml");
        let registry = LedgerRegistry::new(&registry_path);
        let entry = registry.resolve(Some(name))?;
        return Ok(entry.mode.clone());
    }
    Ok(LedgerMode::Stateful) // default
}
```

- [ ] **14.4 Guard event-only ledgers.** In `transition`, `gate check`, and `render` handlers, check mode:

```rust
if resolve_ledger_mode(&cli, &config_dir)? == LedgerMode::EventOnly {
    eprintln!("error: '{}' is an event-only ledger; transitions are not supported", name);
    std::process::exit(3);
}
```

For `status` on event-only ledgers, return metadata (event count, last timestamp, chain status) without state machine fields.

- [ ] **14.5 Update all command handlers** (`transition`, `event`, `status`, `gate check`, `render`, `log tail`, `log verify`, `log dump`) to use `resolve_ledger()` instead of hardcoded ledger path.

- [ ] **14.6 Run integration tests.**

```bash
cargo test integration -- --nocapture
```

```
commit: feat(cli): add --ledger/--path targeting to all commands, enforce event-only restrictions
```

---

## Task 15 — Update `renders.toml` for Multi-Ledger

### Files

| Action | Path |
|--------|------|
| Modify | `src/config/mod.rs` (RenderConfig parsing) |
| Modify | `src/render/engine.rs` |
| Modify | `examples/minimal/renders.toml` |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **15.1 Write failing test for ledger-specific renders.**

```rust
#[test]
fn test_render_reads_from_specified_ledger() {
    // Setup with two ledgers and renders.toml pointing each template at a different ledger
    // Verify each rendered file contains data from the correct ledger
}
```

- [ ] **15.2 Add `ledger` field to `RenderConfig`.**

```rust
#[derive(Debug, Deserialize)]
pub struct RenderConfig {
    pub target: String,
    pub template: String,
    pub trigger: String,
    pub event_types: Option<Vec<String>>,
    pub ledger: Option<String>, // NEW: which ledger to read from
}
```

- [ ] **15.3 Update `RenderEngine` to resolve the ledger per render target.** When building context, use the specified ledger (or default) to read events:

```rust
fn build_context_for_render(&self, render: &RenderConfig) -> Result<tera::Context, Error> {
    let ledger_path = if let Some(ref name) = render.ledger {
        self.registry.resolve(Some(name))?.path.clone()
    } else {
        self.default_ledger_path.clone()
    };
    let ledger = Ledger::open(&PathBuf::from(&ledger_path))?;
    // ... build context from this ledger's entries ...
}
```

- [ ] **15.4 Run tests.**

```bash
cargo test integration -- --nocapture
```

```
commit: feat(render): support per-template ledger targeting in renders.toml
```

---

## Task 16 — Update `init` Command for JSONL

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` (init handler) |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **16.1 Write failing test.**

```rust
#[test]
fn test_init_creates_jsonl_ledger() {
    let dir = tempdir().unwrap();
    // Copy minimal config into dir
    copy_minimal_config(dir.path());

    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(), "init"])
        .assert().success();

    // Should create .sahjhan/ledger.jsonl (not ledger.bin)
    assert!(dir.path().join(".sahjhan/ledger.jsonl").exists());
    assert!(!dir.path().join(".sahjhan/ledger.bin").exists());

    // Should also create ledgers.toml registry with default entry
    assert!(dir.path().join(".sahjhan/ledgers.toml").exists());
}
```

- [ ] **16.2 Update `init` handler.** Change from creating `ledger.bin` to `ledger.jsonl`. Also create the registry with a default entry:

```rust
fn handle_init(config_dir: &Path) -> Result<(), Error> {
    let sahjhan_dir = config_dir.join(".sahjhan");
    std::fs::create_dir_all(&sahjhan_dir)?;

    let ledger_path = sahjhan_dir.join("ledger.jsonl");
    let config = ProtocolConfig::load(config_dir)?;
    Ledger::init(&ledger_path, &config.meta.name, &config.meta.version)?;

    // Create registry with default ledger
    let registry_path = sahjhan_dir.join("ledgers.toml");
    let mut registry = LedgerRegistry::new(&registry_path);
    registry.create(
        "default",
        ledger_path.to_str().unwrap(),
        LedgerMode::Stateful,
    )?;

    // ... manifest init, hook generate, etc. (unchanged) ...

    Ok(())
}
```

- [ ] **16.3 Run tests.**

```bash
cargo test test_init -- --nocapture
```

```
commit: feat(cli): update init to create JSONL ledger and registry
```

---

## Task 17 — Update `log` Subcommands for JSONL

### Files

| Action | Path |
|--------|------|
| Modify | `src/cli/mod.rs` (log handlers) |
| Modify | `tests/integration_tests.rs` |

### Steps

- [ ] **17.1 Write failing tests.**

```rust
#[test]
fn test_log_dump_outputs_jsonl() {
    let dir = setup_initialized_dir();
    // Add events ...

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(), "log", "dump"])
        .output().unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();

    // Each line should be valid JSON
    for line in stdout.trim().lines() {
        let _: serde_json::Value = serde_json::from_str(line).unwrap();
    }
}

#[test]
fn test_log_tail_shows_last_n() {
    let dir = setup_initialized_dir();
    // Add 5 events ...

    let output = Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(), "log", "tail", "3"])
        .output().unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    let lines: Vec<&str> = stdout.trim().lines().collect();
    assert_eq!(lines.len(), 3);
}

#[test]
fn test_log_verify_passes_clean_ledger() {
    let dir = setup_initialized_dir();
    Command::cargo_bin("sahjhan").unwrap()
        .args(&["--config-dir", dir.path().to_str().unwrap(), "log", "verify"])
        .assert().success();
}
```

- [ ] **17.2 Update `log dump`.** Now simply reads the JSONL file and prints each line. No format conversion needed (the file is already JSONL):

```rust
fn handle_log_dump(ledger_path: &Path) -> Result<(), Error> {
    let content = std::fs::read_to_string(ledger_path)?;
    print!("{}", content);
    Ok(())
}
```

Or, for a more structured approach, open the ledger and emit each entry's `to_jsonl()`.

- [ ] **17.3 Update `log tail`.** Read the file, take last N lines:

```rust
fn handle_log_tail(ledger_path: &Path, n: usize) -> Result<(), Error> {
    let ledger = Ledger::open(ledger_path)?;
    let entries = ledger.entries();
    let start = entries.len().saturating_sub(n);
    for entry in &entries[start..] {
        println!("{}", entry.to_jsonl());
    }
    Ok(())
}
```

- [ ] **17.4 Update `log verify`.** Delegates to `Ledger::verify()`:

```rust
fn handle_log_verify(ledger_path: &Path) -> Result<(), Error> {
    let ledger = Ledger::open(ledger_path)?;
    ledger.verify()?;
    println!("OK: {} events, chain intact", ledger.entries().len());
    Ok(())
}
```

- [ ] **17.5 Run tests.**

```bash
cargo test integration -- --nocapture
```

```
commit: refactor(cli): update log dump/tail/verify for JSONL format
```

---

## Task 18 — Update `examples/minimal/` Protocol Config

### Files

| Action | Path |
|--------|------|
| Modify | `examples/minimal/protocol.toml` |
| Possibly modify | `examples/minimal/renders.toml` |

### Steps

- [ ] **18.1 Add `[checkpoints]` section to `protocol.toml`.**

```toml
[checkpoints]
interval = 100
```

- [ ] **18.2 Update any ledger path references** in the example config if they reference `.bin` files.

- [ ] **18.3 Run examples manually to verify.**

```bash
cd /tmp && mkdir test-minimal && cd test-minimal
cp -r /path/to/sahjhan/examples/minimal/* .
sahjhan --config-dir . init
sahjhan --config-dir . status
sahjhan --config-dir . transition start
```

```
commit: chore: update minimal example config for v0.2.0 JSONL format
```

---

## Task 19 — Full Test Suite Update

### Files

| Action | Path |
|--------|------|
| Modify | `tests/ledger_tests.rs` |
| Modify | `tests/chain_integrity_tests.rs` |
| Modify | `tests/gate_tests.rs` |
| Modify | `tests/state_machine_tests.rs` |
| Modify | `tests/config_tests.rs` |
| Modify | `tests/manifest_tests.rs` |
| Modify | `tests/template_security_tests.rs` |
| Modify | `tests/hook_generation_tests.rs` |
| Modify | `tests/integration_tests.rs` |

### Steps

This task is a sweep to catch any remaining test failures from the format change. Individual tests were written/updated in earlier tasks, but some may have been missed.

- [ ] **19.1 Run the full test suite and collect failures.**

```bash
cargo test 2>&1 | tee test-results.txt
grep "FAILED" test-results.txt
```

- [ ] **19.2 Fix each failing test.** Common patterns:
  - Tests that create `LedgerEntry` with old binary constructor -> use `LedgerEntry::new()`
  - Tests that call `to_bytes()`/`from_bytes()` -> use `to_jsonl()`/`from_jsonl()`
  - Tests that read `entry.payload` -> read `entry.fields`
  - Tests that check for `ledger.bin` on disk -> check for `ledger.jsonl`
  - Tests that corrupt binary bytes -> corrupt JSONL text
  - Tests that deserialize with `rmp_serde` -> read `entry.fields` directly
  - `HashMap` -> `BTreeMap` for fields in test code

- [ ] **19.3 Update `setup_initialized_dir()` helper** in integration tests if it references old paths or formats.

- [ ] **19.4 Run full suite again.**

```bash
cargo test
```

- [ ] **19.5 Run clippy and fix warnings.**

```bash
cargo clippy -- -D warnings
```

```
commit: test: update all 9 test files for JSONL ledger format
```

---

## Task 20 — Final Verification and Cleanup

### Files

| Action | Path |
|--------|------|
| Modify | `Cargo.toml` (version bump to 0.2.0) |
| Modify | `src/lib.rs` (if any dead code remains) |

### Steps

- [ ] **20.1 Remove all `rmp_serde` references.** Grep the codebase:

```bash
grep -r "rmp_serde" src/ tests/
# Should return nothing
```

- [ ] **20.2 Remove all `rmp-serde` from `Cargo.toml`.** (Should already be done in Task 1, but verify.)

- [ ] **20.3 Bump version to `0.2.0` in `Cargo.toml`.**

- [ ] **20.4 Run the full test + lint + build pipeline.**

```bash
cargo test
cargo clippy -- -D warnings
cargo build --release
```

- [ ] **20.5 Verify binary size.** The spec predicts ~20MB (up from ~5MB due to DataFusion + Arrow + tokio):

```bash
ls -lh target/release/sahjhan
```

- [ ] **20.6 Smoke-test the release binary end-to-end.**

```bash
cd /tmp && mkdir v020-smoke && cd v020-smoke
cp -r /path/to/sahjhan/examples/minimal/* .
./sahjhan --config-dir . init
./sahjhan --config-dir . status
./sahjhan --config-dir . transition start
./sahjhan --config-dir . event finding --field id=BH-001 --field severity=HIGH
./sahjhan --config-dir . log dump
./sahjhan --config-dir . log verify
./sahjhan query --path .sahjhan/ledger.jsonl "SELECT * FROM events"
./sahjhan ledger list
./sahjhan ledger verify --path .sahjhan/ledger.jsonl

# Test import
echo '{"type":"finding","fields":{"id":"IMPORTED-001"}}' | \
  ./sahjhan ledger import --name imported --path imported.jsonl
./sahjhan query --path imported.jsonl "SELECT * FROM events"

# Test multi-ledger
./sahjhan ledger create --name project --path project.jsonl --mode event-only
./sahjhan --ledger project event finding --field id=BH-002
./sahjhan --ledger project status  # should show event-only metadata
./sahjhan --ledger project transition start  # should exit 3

# Test glob query
./sahjhan query --glob "*.jsonl" "SELECT _source, count(*) FROM events GROUP BY 1"
```

```
commit: chore: bump version to 0.2.0, final cleanup
```

---

## Dependency Graph

```
Task 0  (v0.1.2 patch — independent, ships first)
Task 1  (scaffolding)
  └─ Task 2  (JSONL entry format)
       └─ Task 3  (JSONL chain I/O)
            ├─ Task 4  (state machine update)
            │    └─ Task 5  (gate evaluators update)
            ├─ Task 6  (render engine update)
            ├─ Task 7  (multi-ledger registry)
            │    ├─ Task 8   (checkpoints)
            │    ├─ Task 9   (ledger import)
            │    ├─ Task 12  (ledger CLI)
            │    └─ Task 14  (--ledger targeting)
            │         └─ Task 15  (multi-ledger renders)
            └─ Task 10 (DataFusion query engine)
                 ├─ Task 11 (query gate)
                 └─ Task 13 (query CLI)
Task 16 (update init) — depends on Tasks 3, 7
Task 17 (update log commands) — depends on Task 3
Task 18 (update examples) — depends on Tasks 3, 8
Task 19 (test sweep) — depends on all above
Task 20 (final verification) — depends on Task 19
```

## Risk Notes

1. **DataFusion `->>'key'` syntax:** DataFusion may not support PostgreSQL-style `->>'key'` for JSON string extraction. If not, the alternative is `json_extract_scalar(fields, '$.key')` or `get_field(json_parse(fields), 'key')`. Check the exact DataFusion version's JSON function support early (Task 10) and adapt the query gate SQL syntax in the spec accordingly.

2. **Binary size:** DataFusion + Arrow + tokio will increase the binary from ~5MB to ~15-25MB. This is expected and acceptable per the spec.

3. **Compile time:** DataFusion is a large crate. First compile will be slow (~3-5 minutes). Incremental builds are unaffected for non-query changes.

4. **`BTreeMap` vs `HashMap`:** Switching `fields` from `HashMap` to `BTreeMap` affects every call site that constructs field maps. The compiler will catch all of these, but expect a cascade of type errors in Task 4/5/6 that need mechanical fixes.

5. **RFC 8785 correctness:** The manual canonical JSON implementation must be tested against edge cases: empty strings, strings with quotes/backslashes/control characters, empty fields map, integer zero. Add targeted unit tests in Task 2 for these.

6. **File locking:** The `fs2` locking semantics are unchanged, but the switch from binary append (seeking to end + writing bytes) to text append (opening in append mode + writing a line) may behave differently on some platforms. Test on both macOS and Linux.

# Token Profiling Playbook

A standalone guide to profiling any Claude Code session's token usage.
No spec reading required.

---

## 1. Quick Start

Profile the most recent session for the current project:

```bash
python -m token_profiler --latest --open
```

With the Holtz plugin (adds phase labels and Holtz-specific optimization patterns):

```bash
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py --open
```

Profile a session from a different project:

```bash
python -m token_profiler --latest --project ~/repos/other-project --open
```

Profile a specific session by path:

```bash
python -m token_profiler path/to/session.jsonl --open
```

List available sessions:

```bash
python -m token_profiler --list
python -m token_profiler --list --project ~/repos/other-project
```

---

## 2. What This Measures

### The core insight: session-spanning token cost

Every token you add to a Claude Code context window gets re-sent on every
subsequent API call until a compaction event resets the segment. A file read
that looks cheap in isolation can dominate your total bill depending on
*when* it happens.

Concrete example:

| Scenario | File size | Turn | Remaining turns | Session cost |
|---|---|---|---|---|
| Early read | 5,000 tokens | 20 | 256 | **1,280,000** |
| Late read | 5,000 tokens | 270 | 6 | **30,000** |

Same data. **42x different session impact.** The profiler makes this visible.

### Three cost layers

The profiler computes three progressively more specific views of cost:

1. **Token weight heat map** — The universal metric.
   `session_cost = delta x remaining_calls_in_segment` (inclusive).
   `delta` is how much the context window grew on a given turn.
   `remaining` counts from the current turn to the last turn in the
   segment (bounded by compaction events), inclusive — minimum 1.
   This metric is comparable across models and pricing tiers.

2. **Pricing-agnostic bucket breakdown** — Tokens split by billing bucket:
   `input`, `cache_creation`, `cache_read`, `output`. Shows where tokens
   flow without applying dollar rates. Useful for understanding cache
   behaviour and output volume independently of price.

3. **Dollar cost** — Model-specific pricing applied to each bucket. Uses
   longest-prefix matching for model names, so `claude-opus-4-6-20251101`
   resolves to the `claude-opus-4-6` pricing entry. Falls back to zero
   rates (with a warning) for unrecognised models.

---

## 3. Reading the Output

The profiler generates three files in the output directory (default: `./token-profile/`):

| File | Purpose |
|---|---|
| `profile.json` | Canonical data. Everything else renders from this. |
| `profile.md` | Markdown report for terminal viewing or git archival. |
| `profile.html` | Cyberpunk web viewer. Self-contained, open in any browser. |

Use `--json`, `--md`, or `--html` flags to emit only one format.
By default, all three are generated.

### HTML viewer views

**Timeline Heat Strip** — A horizontal bar where each API call is a cell
coloured by session cost: blue (cheap), magenta (expensive), white
(critical). Hover any cell for turn details. Compaction events appear as
red vertical lines separating segments.

**Turn Table** — Every turn in a sortable table. Columns include turn
index, phase, delta, remaining calls, session cost, and tools used.
Expand any row to see tool-level attribution. Default sort: hottest first.

**Phase Sunburst** — Two-ring chart. Inner ring = phases, outer ring =
tools within each phase. Sized by session cost. Quickly shows which phase
and which tools within it dominate.

**Cost Bucket Sankey** — Flow diagram from phases to billing buckets
(input, cache_creation, cache_read, output). Width = token volume. Reveals
whether a phase is expensive because of input growth, cache misses, or
output generation.

**Session Comparison** — Side-by-side cards for main and subagent sessions.
Each card shows total API calls, peak context window, session cost, and
dollar cost. Only appears when subagent sessions are present.

---

## 4. Optimization Patterns

### Pattern: Heavy Early Read

**Symptom:** A large file read in the first 20% of turns. Bright (magenta
or white) bar on the heat strip. High session cost for a single turn.

**Fix options:**
- Defer the read to a later turn when fewer calls remain
- Extract only the needed sections instead of reading the whole file
- Offload to a subagent — subagent context is isolated, so the file only
  persists for the subagent's lifetime, not the entire main session

### Pattern: Chatty Tool Loop

**Symptom:** Many small deltas that individually look cheap but accumulate
significant session cost. The heat strip shows a dense band of
moderate-colour cells rather than one bright spike.

**Fix:** Batch tool calls. Use parallel reads instead of sequential ones.
Each API round-trip adds overhead; fewer calls = less context accumulation.

### Pattern: Subagent Over-delegation

**Symptom:** A subagent's session cost exceeds the main session cost for
comparable work. Visible in the Session Comparison view where the subagent
card dominates.

**Fix:** Pass narrower context to the subagent. Subagents that receive
broad instructions tend to do their own reconnaissance, duplicating reads
that already happened in the main session.

### Pattern: Recon Bloat

**Symptom:** Phase 0 (reconnaissance/exploration) dominates the heat map.
Large file reads and broad grep searches at the start of the session
create high deltas that multiply across all remaining turns.

**Fix:** Audit which recon reads are actually referenced in later phases.
If a file is read early but never used, that is pure waste multiplied by
the full session length. Profile the dependency edges between recon and
execution phases.

---

## 5. Cross-Project Usage

The profiler works on any Claude Code session, not just Holtz runs.

```bash
# Point at any project on the same machine
python -m token_profiler --latest --project ~/repos/other-project

# List sessions for that project
python -m token_profiler --list --project ~/repos/other-project

# Profile a specific JSONL file directly (no project discovery needed)
python -m token_profiler ~/path/to/session.jsonl --open
```

The `--project PATH` flag maps the given path to Claude Code's
`~/.claude/projects/<mangled-path>/` directory (path separators become
dashes). Auto-detection works from git root or cwd when `--project` is
omitted.

Without a plugin, phases show as `"unknown"`. Per-turn and per-tool views
are still fully functional — you just lose phase-level aggregation and
phase-specific optimization patterns.

---

## 6. Using Plugins

Plugins provide domain-specific intelligence: phase detection, subagent
naming, profile enrichment, and optimization patterns.

### CLI flag

```bash
python -m token_profiler --latest --plugin path/to/plugin.py
```

Specify `--plugin` multiple times to load several plugins. The first
plugin whose `detect()` method returns `True` for the session becomes the
active plugin.

### Environment variable fallback

```bash
export TOKEN_PROFILER_PLUGINS="skills/holtz/scripts/profiler_plugin.py:path/to/another_plugin.py"
python -m token_profiler --latest
```

Colon-separated list of plugin paths. The `--plugin` CLI flag takes
precedence; the env var is only consulted when no `--plugin` flags are
provided.

### What plugins provide

| Method | Purpose |
|---|---|
| `detect(turns)` | Return `True` if the plugin recognises this session type |
| `label_phases(turns)` | Map turn indices to phase labels (e.g., `{0: "recon", 15: "analysis"}`) |
| `name_subagent(turns)` | Return a human-readable name for a subagent session |
| `enrich_profile(profile)` | Mutate the `SessionProfile` with plugin-specific data |
| `optimization_patterns()` | Return a list of known optimization pattern dicts |

A plugin class must have all five methods plus a `name` attribute.

---

## 7. Extending

### Adding pricing for new models

Edit `scripts/token_profiler/pricing.py` and add an entry to the `PRICING`
dict:

```python
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.00 / 1_000_000,
        "cache_creation": 18.75 / 1_000_000,
        "cache_read": 1.50 / 1_000_000,
        "output": 75.00 / 1_000_000,
    },
    # Add new model here:
    "claude-new-model": {
        "input": X / 1_000_000,
        "cache_creation": Y / 1_000_000,
        "cache_read": Z / 1_000_000,
        "output": W / 1_000_000,
    },
}
```

The lookup uses longest-prefix matching, so a key like `"claude-opus-4-6"`
matches `"claude-opus-4-6-20251101"` and any future date-suffixed variant.

### Custom milestones

Override phase boundaries with a JSON file:

```bash
python -m token_profiler --latest --milestones milestones.json
```

The milestones file is a JSON array. Each entry uses either turn-index
ranges or ISO 8601 timestamp ranges:

```json
[
  {"label": "recon", "start": 0, "end": 14},
  {"label": "analysis", "start": 15, "end": 80},
  {"label": "reporting", "start_time": "2025-01-15T10:30:00Z", "end_time": "2025-01-15T11:00:00Z"}
]
```

Ranges are inclusive on both ends. Plugin labels take precedence over
milestones when a plugin is active.

### Custom pricing

Override dollar rates without editing source:

```bash
python -m token_profiler --latest --pricing pricing.json
```

The pricing file uses the same format as the `PRICING` dict: model name
keys mapping to per-bucket dollar-per-token rates.

### Writing a plugin

Create a Python file with a class that satisfies the `ProfilerPlugin`
protocol:

```python
from token_profiler.models import RawTurn, SessionProfile


class MyPlugin:
    name = "my-plugin"

    def detect(self, turns: list[RawTurn]) -> bool:
        """Return True if this plugin should handle the session."""
        # Example: detect by checking for a specific tool pattern
        return any(
            block.tool_name == "MyCustomTool"
            for turn in turns
            for block in turn.content_blocks
        )

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Map turn indices to phase labels."""
        labels = {}
        for turn in turns:
            labels[turn.index] = "analysis"  # your logic here
        return labels

    def name_subagent(self, turns: list[RawTurn]) -> str | None:
        """Return a descriptive name for a subagent session."""
        return None

    def enrich_profile(self, profile: SessionProfile) -> None:
        """Add plugin-specific data to the profile."""
        pass

    def optimization_patterns(self) -> list[dict]:
        """Return optimization patterns this plugin can detect."""
        return [
            {
                "name": "my-pattern",
                "description": "Description of the anti-pattern",
                "symptom": "What it looks like in the profile",
                "fix": "How to address it",
            }
        ]
```

No base class inheritance needed — the profiler uses structural typing
(duck typing against the `ProfilerPlugin` protocol). Place the file
anywhere and pass it via `--plugin`.

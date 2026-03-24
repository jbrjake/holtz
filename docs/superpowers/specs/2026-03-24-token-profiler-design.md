# Token Profiler Design

> **Date:** 2026-03-24
> **Status:** Draft (rev 2 — post spec review)
> **Author:** Jon + Claude
>
> A general-purpose Claude Code session token profiler with an extensible plugin system. Analyzes session JSONL files to produce per-turn, per-tool token cost attribution with session-spanning heat metrics. Ships with a cyberpunk web viewer, markdown reports, and a JSON intermediate format.

---

## Problem

Claude Code sessions accumulate context monotonically (until compaction). Every token added to context gets cached and re-read on every subsequent API call. A 5K file read at turn 20 with 256 remaining turns costs 1.28M cache-read tokens across the session. The same read at turn 270 with 6 remaining turns costs 30K. Same file, 42x different session impact.

There is no tool that makes this visible. You can see the context window size in the status bar, but not which specific actions are responsible for the cumulative cost, or which phase of work is most expensive.

## Solution

A token profiler that works like a line profiler but puts heat on actions with the highest session-spanning token cost, not CPU time or memory. Three cost layers: token weight heat map (universal, comparable), pricing-agnostic bucket breakdown (cache vs input vs output), and dollar conversion (model-specific).

## Scope

### In scope
- Parse any Claude Code session JSONL (any project, any model)
- Multi-session profiling (main + subagents, discovered automatically)
- Cross-project session discovery (`--project` flag)
- Per-API-call and per-tool-call attribution
- Compaction-aware segment analysis
- Three cost layers: token weight, bucket breakdown, dollar cost
- Phase attribution via external plugin (e.g., Holtz)
- Self-contained HTML viewer with cyberpunk aesthetic
- Markdown report for terminal/git
- JSON intermediate format
- Repeatable playbook document
- Tracing hooks design (for Holtz to emit structured telemetry)

### Out of scope
- Real-time profiling during a session (future)
- Automatic optimization suggestions (the playbook documents patterns manually)
- Comparison across multiple runs (future — single run per invocation)

---

## Data Model

### Level 0 — Raw Turn

The atomic unit extracted from a session JSONL. One per API call (grouped by `requestId`).

```
RawTurn:
  request_id: str
  index: int                    # sequential within session
  timestamp: datetime
  usage:
    input_tokens: int           # stable across streaming chunks — take from any
    cache_creation_input_tokens: int  # stable across streaming chunks
    cache_read_input_tokens: int     # stable across streaming chunks
    output_tokens: int          # CUMULATIVE — must take from final chunk only
                                # (the chunk where stop_reason is non-null).
                                # Intermediate chunks have partial counts.
  stop_reason: str              # "tool_use" | "end_turn"
  content_blocks:
    - type: "text" | "thinking" | "tool_use"
      size: int                 # char length
      text_content: str?        # actual text for "text" blocks (needed by plugins
                                # for content-heuristic phase detection)
      thinking_content: str?    # actual thinking text (optional, may be empty)
      tool_name: str?           # if tool_use
      tool_input_summary: str?  # compact description
  tool_results:                 # from subsequent user message
    - tool_use_id: str
      content_type: str         # "text" | "tool_references" | "error" | "empty"
      content_size_chars: int   # for text content; 0 for non-text types
  assistant_text: str           # concatenation of all text blocks — convenience
                                # field for plugin phase detection
```

**Extraction note on `output_tokens`:** Within a single API call (grouped by `requestId`), the JSONL contains multiple streaming chunks. The `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` fields are stable across all chunks. However, `output_tokens` is cumulative and only the final chunk (the one with non-null `stop_reason`) contains the correct total. Intermediate chunks contain partial streaming counts. The extractor must use the final chunk's `output_tokens` value.

**Extraction note on `tool_results`:** Not all tool results contain text content. `ToolSearch` returns structured `tool_reference` objects (injecting tool definitions into context). Error results have `is_error: true`. The `content_type` field classifies the result so attribution logic can handle each case. For non-text content types, the profiler cannot measure the actual token size from the JSONL — the `_assistant_overhead` bucket absorbs this cost, which is acceptable but should be visible in the viewer as a note.

### Level 1 — Profiled Turn

Computed from consecutive raw turns.

```
ProfiledTurn:
  ...RawTurn
  context_window: int           # input + cache_creation + cache_read
                                # (excludes output_tokens — outputs become cached
                                # input on the next turn and are captured in the
                                # next turn's delta)
  delta: int                    # context_window - previous.context_window
  segment_id: int               # compaction segment (increments on negative delta)
  remaining_calls_in_segment: int  # inclusive — counts current turn as a reader
                                   # of its own additions. Minimum value is 1.
  session_cost_tokens: int      # delta x remaining_calls_in_segment
  tool_attributions: list[ToolAttribution]
  phase: str                    # from plugin, or "unknown"
```

**Note on `context_window` approximation:** This measure sums all billed input tokens (`input + cache_creation + cache_read`). In the steady state, this closely tracks the actual context window size shown in the Claude Code status bar. Edge cases: during the first few turns of a session (before cache stabilizes) and immediately after compaction (where the cache_creation/cache_read split changes abruptly), the delta may reflect cache bucket redistribution rather than actual context growth. The negative-delta compaction detector handles the common case. Unusual compaction patterns (e.g., compaction that removes content but the agent immediately re-reads it) may require manual segment inspection.

### Level 2 — Tool Attribution

Estimated from tool result content sizes within a turn.

```
ToolAttribution:
  tool_name: str
  description: str              # compact one-liner
  result_size_chars: int
  result_size_tokens_est: int   # chars / 4 (rough estimate)
  fraction_of_delta: float      # this tool's share of the turn delta
  attributed_delta: int         # fraction x turn delta
  attributed_session_cost: int  # fraction x turn session_cost
```

For the portion of delta not attributable to tool results (assistant text, thinking, system messages), a synthetic `"_assistant_overhead"` attribution entry captures the model's own additions to context.

### Level 3 — Cost Layers

Three views of the same data, computed per turn and aggregated per phase/session.

```
CostLayers:
  token_weight:                 # session-spanning heat
    session_cost: int           # delta x remaining_calls
    pct_of_total: float
  bucket_breakdown:             # pricing-agnostic
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int
  dollar_cost:                  # model-specific pricing
    input_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    output_cost: float
    total_cost: float
```

### Level 4a — Phase Profile

Aggregated metrics for one phase within a session.

```
PhaseProfile:
  phase: str
  turn_count: int
  turn_indices: list[int]
  delta_sum: int
  session_cost_sum: int
  top_tools: list[str]          # top 3 by attributed_session_cost
  bucket_breakdown:             # same structure as CostLayers.bucket_breakdown
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int
  dollar_cost:                  # same structure as CostLayers.dollar_cost
    input_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    output_cost: float
    total_cost: float
```

### Level 4b — Compaction Event

Recorded when a negative delta is detected between consecutive turns.

```
CompactionEvent:
  segment_id: int               # segment that was ended
  turn_index: int               # turn where negative delta was detected
  context_before: int           # context_window of previous turn
  context_after: int            # context_window of this turn
  reduction_tokens: int         # context_before - context_after
```

### Level 4c — Session Profile

Top-level container for one execution context.

```
SessionProfile:
  session_id: str
  session_type: "main" | "subagent"
  subagent_name: str?           # from plugin or heuristic
  model: str
  dispatched_from_session: str? # parent session_id, if subagent
  dispatched_at_turn: int?      # turn index in parent where Agent tool was called
  returned_at_turn: int?        # turn index in parent where tool result arrived
  turns: list[ProfiledTurn]
  phases: dict[str, PhaseProfile]
  compaction_events: list[CompactionEvent]
  summary:
    total_api_calls: int
    total_context_tokens: int
    total_output_tokens: int
    total_session_cost: int
    total_dollars: float
    hottest_turns: list[int]    # top 10 by session_cost
    hottest_tools: list[str]    # top 10 tool types by aggregate session_cost
```

The `dispatched_at_turn` / `returned_at_turn` fields link subagent sessions to specific turns in the main session. This allows the viewer's heat strip to show "Justine ran here" brackets and the Session Comparison view to place subagent cards in timeline context. Populated by matching the `Agent` tool_use in the main session whose `tool_use_id` corresponds to the subagent's creation, and the subsequent tool_result that returned the subagent's output.

### Level 5 — Run Profile

Multi-session rollup.

```
RunProfile:
  run_id: str
  sessions: list[SessionProfile]
  cross_session_summary:
    total_billed_tokens: int    # sum of all input + cache_creation + cache_read + output
    total_session_cost_tokens: int  # sum of all session_cost heat metrics
    total_dollars: float
    session_breakdown: dict[str, float]  # pct of total_billed_tokens per session
```

---

## Analysis Pipeline

Six stages, each a pure function. No side effects until final output.

### Stage 1 — Extract (`extract.py`)

Reads one or more session JSONL files. Groups `assistant` messages by `requestId` into `RawTurn` objects. For each turn, collects:

- Usage: `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` are stable across all streaming chunks of a request and may be taken from any chunk. `output_tokens` is cumulative and **must be taken from the final chunk only** — the chunk where `stop_reason` is non-null. All other chunks contain partial streaming values that will systematically undercount. Because output pricing is 5x input for Opus, this error compounds significantly.
- Content blocks merged across chunks (thinking, text, tool_use)
- Full text content of text blocks (stored in `assistant_text` for plugin consumption)
- Tool names and input summaries via compact description logic (reused from `session-to-cast.py`)

Extracts tool results from `user` messages (type=`tool_result`). Pairs with preceding `tool_use` by `tool_use_id` so each tool call gets its result size measured.

**Multi-session discovery:** Given a session JSONL path, checks for `<session-id>/subagents/*.jsonl` in the same directory. Each subagent JSONL is extracted as a separate `RawSession`. Subagent naming defers to the plugin; without a plugin, uses the agent filename.

**Cross-project:** The `--project` flag resolves a project root path to `~/.claude/projects/<mangled-path>/` using the same path-mangling convention as Claude Code (replace `/` with `-`). The `--latest` and `--list` flags scope to that project's sessions.

### Stage 2 — Delta (`analyze.py`)

Walks the turn sequence. For each turn:

```
context_window = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
delta = context_window - previous_context_window
```

If delta < 0: increment `segment_id`, record a `CompactionEvent` with before/after context sizes.

### Stage 3 — Attribution (`analyze.py`)

For each turn with tool calls, looks up corresponding tool results from the next user message. Distributes the turn's delta proportionally by result content size:

```
tool_fraction = tool_result_chars / sum(all_tool_result_chars_in_turn)
attributed_delta = tool_fraction * turn_delta
```

Remainder (delta not covered by tool results) goes to `"_assistant_overhead"` — the cost of the model's own text and thinking output being added to context.

### Stage 4 — Session Cost (`analyze.py`)

**Two-pass algorithm.** Pass 1 (forward): identify all compaction boundaries by detecting negative deltas, recording segment start/end turn indices. Pass 2 (backward or random-access): for each turn, compute remaining calls using the now-known segment boundaries.

For each turn within its compaction segment:

```
remaining = (last_turn_index_in_segment - current_turn_index) + 1
session_cost = delta * remaining
```

The `+1` makes `remaining` inclusive — the current turn counts itself as a reader of its own additions. This ensures the last turn in any segment (and single-turn sessions) gets `remaining = 1` and a non-zero session cost, rather than silently zeroing out. A single-turn session has `session_cost = delta * 1 = delta`.

This is the heat metric. Propagates to tool attributions: `attributed_session_cost = fraction * session_cost`.

### Stage 5 — Phase Attribution (`analyze.py`)

1. If a plugin is loaded and provides `label_phases()`, use it.
2. If `--milestones` JSON is provided, bucket by timestamp or turn-index ranges.
3. Otherwise, all turns get phase `"unknown"`.

**Milestones file schema** (`--milestones`):

```json
[
  {"phase": "recon",   "start_turn": 1,  "end_turn": 37},
  {"phase": "phase-1", "start_turn": 38, "end_turn": 48},
  {"phase": "phase-2", "start_turn": 49, "end_turn": 58}
]
```

Or timestamp-based (ISO 8601):

```json
[
  {"phase": "recon",   "start": "2026-03-24T05:20:46Z", "end": "2026-03-24T05:41:22Z"},
  {"phase": "phase-1", "start": "2026-03-24T05:41:22Z", "end": "2026-03-24T05:46:05Z"}
]
```

Ranges are inclusive on both ends. Gaps between ranges result in `"unknown"` phase for uncovered turns. Turn-index-based milestones take precedence over timestamp-based if both fields are present.

Aggregates per-phase: sum of deltas, sum of session costs, turn count, top tools.

### Stage 6 — Pricing (`pricing.py`)

Applies model-specific pricing to each turn's raw token buckets.

```python
PRICING = {
    "claude-opus-4-6": {
        "input":          15.00 / 1_000_000,
        "cache_creation": 18.75 / 1_000_000,  # 1.25x input
        "cache_read":      1.50 / 1_000_000,  # 0.1x input
        "output":         75.00 / 1_000_000,   # 5x input
    },
}
```

Detects model from the JSONL's `message.model` field. Pricing lookup uses **longest-prefix matching** — `claude-opus-4-6-20251101` matches the `claude-opus-4-6` key. If no prefix matches, falls back to an `"unknown"` key with zero pricing and emits a warning to stderr. Pricing table is a standalone dict. Override via `--pricing` flag with a JSON file.

---

## Plugin System

The profiler has zero built-in knowledge of any specific workflow. Domain-specific intelligence (phase detection, subagent naming, trace integration) comes from external plugins loaded at runtime.

### Protocol

```python
class ProfilerPlugin:
    name: str

    def detect(self, session: RawSession) -> bool:
        """Auto-detect whether this plugin applies to this session."""

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Map turn indices to phase names. Return empty dict to skip.

        RawTurn includes assistant_text (concatenated text blocks) for
        content-heuristic detection. Plugins can match on phrases like
        'Phase 0 complete' or 'Starting Phase 1' without re-parsing JSONL.
        """

    def name_subagent(self, session: RawSession) -> str | None:
        """Infer a human name for a subagent session. Return None to skip.

        session.turns[0].assistant_text contains the first text output,
        which typically identifies the subagent's purpose.
        """

    def enrich_profile(self, profile: SessionProfile) -> None:
        """Add plugin-specific annotations (findings, predictions, markers)."""

    def optimization_patterns(self) -> list[dict]:
        """Plugin-specific optimization patterns for the playbook/viewer."""
```

### Loading

```
--plugin PATH      Path to a Python file implementing ProfilerPlugin.
                   Can be specified multiple times.

TOKEN_PROFILER_PLUGINS=/path/to/plugin.py:/path/to/other.py
                   Env var fallback. Colon-separated paths.
```

Loaded via `importlib.util.spec_from_file_location`. The profiler scans the module for any class implementing the protocol, instantiates it, calls `detect()`, and uses it if it returns True.

### Holtz Plugin (lives in Holtz repo)

```
skills/holtz/scripts/profiler_plugin.py
```

Implements:
- `detect()`: checks for "Holtz" or "Phase 0" in assistant text, or `docs/holtz/` existence
- `label_phases()`: content-heuristic phase detection (recon, phase-1, phase-2, phase-3, merge, fix-loop, convergence)
- `name_subagent()`: first-text matching ("Running Justine" -> "justine", "I'll read all four test files" -> "test-audit")
- `enrich_profile()`: trace file integration if available, prediction/finding markers
- `optimization_patterns()`: Holtz-specific patterns (Heavy Early Read, Recon Bloat, etc.)

---

## Output Formats

### 1. JSON Profile (`profile.json`)

Complete `RunProfile` serialized as JSON. Canonical output — everything else renders from it. No lossy transformations. Estimated ~300-500KB for a run 14-scale session.

### 2. Markdown Report (`profile.md`)

```
# Token Profile: <run-id>

## Summary
  Total API calls, tokens, dollars, duration
  Per-session breakdown table

## Heat Map -- Top 20 Hottest Turns
  Ranked by session_cost, with tool attribution sub-rows

## Heat Map -- Top 20 Hottest Tools
  Aggregated across all turns by total attributed session cost

## Phase Breakdown
  Per phase: turn count, delta sum, session cost sum, top 3 tools

## Cost Buckets
  Phase x bucket table (input, cache_create, cache_read, output)

## Dollar Costs
  Same table with dollar amounts

## Compaction Events
  Listed if any occurred

## Methodology
  Brief description of how session_cost is computed
```

### 3. Web Viewer (`profile.html`)

Self-contained HTML file. `RunProfile` JSON embedded as `<script>const PROFILE_DATA = {...};</script>`.

**Five views:**

1. **Timeline Heat Strip** — horizontal bar spanning the session. Each API call is a vertical slice colored by session cost intensity (cold blue -> hot magenta -> white-hot). Hover for turn detail. Compaction events as red vertical lines. Phase boundaries as labeled dividers.

2. **Turn Table** — sortable table of all turns. Columns: index, timestamp, phase, delta, remaining, session_cost, tools, dollar_cost. Expandable rows for tool attribution sub-rows. Default sort: session_cost descending. Color-coded cells by heat.

3. **Phase Sunburst** — concentric rings: outer = tools, inner = phases, center = total. Sized by session cost. Click to zoom.

4. **Cost Bucket Sankey** — flow diagram from phases (left) to cost buckets (right). Band width = token volume.

5. **Session Comparison** — side-by-side cards for each session (main + subagents). Mini heat strip + summary stats per session.

**Cyberpunk Aesthetic:**

- Background: near-black (#0a0a0f) with subtle scan-line CSS overlay
- Primary text: #e0e0e0 (cool gray), monospace
- Accent palette: neon magenta (#ff00ff), electric cyan (#00ffff), hot green (#39ff14), warning amber (#ffb700)
- Heat scale: dark blue (#1a1a4e) -> magenta (#ff00ff) -> white (#ffffff)
- Font: JetBrains Mono from CDN with system monospace fallback
- Glow effects: text-shadow and box-shadow with neon colors on hot elements
- Hard edges (no border-radius), 1px solid neon borders at low opacity
- Table rows: alternating #0d0d14 / #111118, hover glow
- Phase labels: pill badges with neon border matching phase color
- Animations: heat strip pulses subtly on load, table rows fade in on scroll, glitch animation on "PROFILER" in the header

No external dependencies except font CDN (with local fallback). Vanilla JS, no frameworks. Charts via CSS grid + positioned divs (heat strip), SVG (sunburst, sankey).

---

## CLI Interface

```
python -m scripts.token_profiler [session] [options]

positional:
  session              Path to session JSONL or session UUID.

session discovery:
  --latest             Use most recent session for the project.
  --list               List available sessions and exit.
  --project PATH       Project root path for session discovery.
                       Resolves to ~/.claude/projects/<mangled-path>/.
                       Default: current git root or cwd.

output:
  -o, --output DIR     Output directory (default: ./token-profile/).
  --json               Emit profile.json only.
  --md                 Emit profile.md only.
  --html               Emit profile.html only.
  --open               Open HTML in default browser after generation.

analysis:
  --milestones FILE    JSON file with phase timestamp overrides.
  --plugin PATH        Path to a ProfilerPlugin Python file.
                       Can be specified multiple times.
  --no-subagents       Skip subagent discovery.
  --pricing FILE       Pricing override JSON file.
  --run-id NAME        Label for the run (default: inferred from session).

environment:
  TOKEN_PROFILER_PLUGINS    Colon-separated plugin paths (fallback for --plugin).
```

**Output directory:**
```
token-profile/
  profile.json
  profile.md
  profile.html
```

---

## Module Structure

```
scripts/token_profiler/
  __init__.py              # version, public API
  cli.py                   # argument parsing, orchestration
  extract.py               # JSONL parsing, API call grouping, subagent discovery
  analyze.py               # delta, attribution, session cost, phase attribution
  report.py                # markdown generation
  viewer.py                # HTML generation from template
  viewer_template.html     # self-contained HTML/CSS/JS (cyberpunk viewer)
  pricing.py               # model pricing tables
  plugin_protocol.py       # ProfilerPlugin protocol definition
```

The Holtz plugin lives separately:
```
skills/holtz/scripts/profiler_plugin.py
```

---

## Token Tracing Plan (Holtz-specific)

A future enhancement where Holtz emits structured telemetry during runs, giving the profiler richer data than session JSONL alone.

### What the session JSONL lacks

- Phase identity (requires heuristic inference after the fact)
- Tool call purpose/category (recon read vs fix-loop read)
- Subagent dispatch context (prompt size, result size)
- Explicit compaction markers

### Proposed: Trace Events

Holtz writes a trace log during each run:

```
docs/holtz/trace.jsonl
```

Event types:

```json
{"event": "phase_start", "phase": "recon", "turn": 1, "timestamp": "..."}
{"event": "phase_end", "phase": "recon", "turn": 37, "context_window": 103136}
{"event": "subagent_dispatch", "name": "justine", "prompt_tokens_est": 4200}
{"event": "subagent_return", "name": "justine", "result_tokens_est": 1800}
{"event": "tool_purpose", "turn": 15, "tool": "Read", "purpose": "recon/project-scan"}
{"event": "compaction", "turn": 42, "before": 195000, "after": 120000}
{"event": "prediction", "id": 1, "confidence": "HIGH", "target": "pattern_brief_compact.py:53"}
{"event": "finding", "id": "BH-004", "severity": "MEDIUM", "turn": 73}
```

### Emission cost

8-12 additional Write calls per run (one per phase boundary + subagent dispatch/return). Negligible token overhead (<2K total).

### Profiler integration

```
python -m scripts.token_profiler --latest --plugin profiler_plugin.py
```

The Holtz plugin checks for `docs/holtz/trace.jsonl`. When present:
- Uses exact phase boundaries instead of content heuristics
- Labels tool purposes in the attribution view
- Shows prediction/finding markers on the heat strip timeline
- Correlates subagent dispatch/return with context window jumps

### Implementation order

1. Define trace event schema (this spec)
2. Add trace emission to Holtz skill phase instructions
3. Add trace consumption to the Holtz profiler plugin
4. Validate on next Holtz run

---

## Playbook Document

Delivered as `docs/token-profiling-playbook.md`. Documents the repeatable process:

1. **Quick Start** — one command to profile the latest session
2. **What This Measures** — explanation of session-spanning cost
3. **Reading the Output** — how to interpret each viewer view
4. **Optimization Patterns** — documented patterns (Heavy Early Read, Chatty Tool Loop, Subagent Over-delegation, Recon Bloat) with symptoms and fixes
5. **Running on Any Session** — cross-project usage, non-Holtz sessions
6. **Extending** — adding pricing, output formats, phase heuristics via plugins

---

## Run 14 as Validation

The first profile generated will be Run 14, using the data already explored:

- Main session: `8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl` (276 API calls, 31K->207K context at convergence, continues to 347K with post-audit work)
- Justine subagent: `agent-a919e2838d64ac37a.jsonl` (153 turns, 896KB)
- Test audit subagent: `agent-af4f3f271b39de28a.jsonl` (51 turns)
- Source audit subagent: `agent-af1027e3c957d8f46.jsonl` (31 turns) (note: filenames reversed vs turn counts based on content — test audit reads 4 test files, source audit reads 9 modules)
- 2 minor subagents (1 turn each, post-audit)

Known milestones from the walkthrough for validation:

| Phase | Context Window | API Call (approx) |
|-------|---------------|-------------------|
| Session start | 31,707 | #1 |
| Phase 0 complete | 103,136 | ~#37 |
| Justine dispatched | 104,084 | ~#38 |
| Phase 1 complete | 131,282 | ~#48 |
| Phase 2 complete | 142,164 | ~#58 |
| Phase 3 complete | 155,261 | ~#80 |
| Merge complete | 174,760 | ~#90 |
| Fix loop complete | 191,404 | ~#121 |
| Converged | 207,110 | ~#151 |

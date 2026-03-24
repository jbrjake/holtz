# Token Profiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a general-purpose Claude Code session token profiler that produces per-turn, per-tool cost attribution with session-spanning heat metrics, a cyberpunk web viewer, markdown reports, and a plugin system for domain-specific enrichment.

**Architecture:** Six-stage pure-function pipeline (extract -> delta -> attribution -> session cost -> phase attribution -> pricing) reading session JSONL, producing a `RunProfile` JSON that renders to markdown and a self-contained HTML viewer. Plugin system loads external Python files at runtime for domain-specific phase detection (e.g., Holtz). No external dependencies beyond Python 3.12 stdlib.

**Tech Stack:** Python 3.12, pytest, vanilla HTML/CSS/JS (viewer), SVG (charts)

**Spec:** `docs/superpowers/specs/2026-03-24-token-profiler-design.md`

---

## Errata (post plan-review fixes)

The plan below was reviewed and the following issues were identified. **The implementer MUST apply these corrections while executing the tasks.** Issues are tagged to the task they affect.

### Must fix (runtime failures / wrong results)

**E1 [Task 2]: Extract `model` from JSONL.** The `extract_session()` function must read `message.model` from assistant message chunks and store it. Add a `model: str` field to `RawTurn` (default `"unknown"`). Take it from the first chunk that has a non-empty model field. Without this, pricing always outputs $0.00. Add test: `test_extract_model_from_chunks`.

**E2 [Task 3]: Attribution tests reference non-existent field.** The tests `test_attribution_single_tool`, `test_attribution_multiple_tools_proportional`, and `test_attribution_non_text_goes_to_overhead` call `compute_attributions()` and check `attributed[0].tool_attributions`. But `_DeltaTurn` has no `tool_attributions` field — that field lives on `ProfiledTurn`. Fix: rewrite these tests to use `build_session_profile()` instead, which produces `ProfiledTurn` objects with `tool_attributions` populated. Or test `_compute_tool_attributions()` directly.

**E3 [Task 3]: `compute_attributions()` is dead code.** Remove it. Attribution is done inside `build_session_profile()` via `_compute_tool_attributions()`. The exported API should be `build_session_profile()` for the full pipeline, and `_compute_tool_attributions()` as a tested internal function.

**E4 [Task 3]: Tool attribution positional matching is fragile.** The current code matches tool results to content blocks by `raw_turn.tool_results.index(tr)`. This breaks when a turn has mixed text/non-text results. Fix: match by `tool_use_id` — each `tool_use` content block has an `id` field, and each `tool_result` has a `tool_use_id`. Add `tool_use_id: str | None` to `ContentBlock` for `tool_use` blocks. Match results to blocks by ID, not position.

**E5 [Task 3]: Wire pricing into the pipeline.** `build_session_profile()` currently sets `total_dollars=0.0`. After building the profile, call `apply_pricing_to_usage()` for each turn and accumulate into `PhaseProfile.dollar_cost` and `SessionSummary.total_dollars`. Add a `model` parameter to `build_session_profile()` (extracted per E1). Add test: `test_build_session_profile_includes_dollar_costs`.

**E6 [Task 3]: `total_context_tokens` is wrong.** `sum(pt.context_window for pt in profiled)` sums instantaneous window sizes, which is meaningless. Fix: use the final turn's `context_window` as `total_context_tokens` (the peak context size). Or rename to `peak_context_window`.

**E7 [Task 3]: Add `CrossSessionSummary` computation.** After building all `SessionProfile` objects, compute the rollup: sum billed tokens, sum session costs, sum dollars, compute per-session percentages. Add this as a `build_run_profile()` function. Add test.

**E8 [Task 6]: CLI is missing 7 spec flags.** Add to `parse_args()`:
- `--milestones FILE` — JSON file with phase overrides
- `--pricing FILE` — pricing override JSON
- `--list` — list sessions and exit
- `--no-subagents` — skip subagent discovery
- `--project PATH` — project root for session discovery
- `--json`, `--md`, `--html` — output format selection (default: all three)
- `--open` — open HTML in browser
- `--run-id NAME` — run label

Add tests for each. Wire `--milestones` and `--pricing` into the pipeline. Wire `--project` to `find_project_dir()`.

**E9 [Task 6]: Write `profile.json` to disk.** The CLI must serialize the `RunProfile` to `profile.json` in the output directory. Use `_serialize_profile()` from `viewer.py` (or factor it into a shared utility). This is the canonical output per spec.

### Should fix

**E10 [Task 3]: `compute_deltas` return type inconsistency.** Always return a `DeltaResult` named tuple: `DeltaResult(turns=list[_DeltaTurn], events=list[CompactionEvent])`. Remove the `return_events` flag.

**E11 [Task 3]: Add test for negative-delta attribution.** After compaction, delta is negative. Attribution with negative delta should still work — the overhead bucket absorbs the negative remainder. Add test: `test_attribution_negative_delta`.

**E12 [Task 1]: Add `model` field to `RawTurn`.** Add `model: str = "unknown"` to the dataclass. This is needed by E1.

**E13 [Task 1]: Add `tool_use_id` to `ContentBlock`.** Add `tool_use_id: str | None = None` to the dataclass. This is needed by E4.

**E14 [Task 5]: Report tests are too weak.** `test_generate_markdown_summary_numbers` asserts `"1" in md` which matches anything. Fix: assert specific formatted strings like `"| Total API calls | 1 |"`.

**E15 [Task 3]: Dead variable `text_results`.** In `_compute_tool_attributions`, remove the unused `text_results` cross-product computation.

---

## File Structure

```
scripts/token_profiler/
  __init__.py              # version string, public imports
  plugin_protocol.py       # ProfilerPlugin Protocol class
  models.py                # dataclasses: RawTurn, ProfiledTurn, ToolAttribution, etc.
  extract.py               # Stage 1: JSONL parsing, API call grouping, subagent discovery
  analyze.py               # Stages 2-5: delta, attribution, session cost, phase attribution
  pricing.py               # Stage 6: model pricing tables, prefix matching
  report.py                # markdown report generation
  viewer.py                # HTML generation from template
  viewer_template.html     # self-contained cyberpunk HTML/CSS/JS
  cli.py                   # CLI entry point, argument parsing, orchestration
  __main__.py              # python -m scripts.token_profiler entry point

skills/holtz/scripts/
  profiler_plugin.py       # Holtz-specific ProfilerPlugin implementation

tests/
  test_token_profiler_models.py
  test_token_profiler_extract.py
  test_token_profiler_analyze.py
  test_token_profiler_pricing.py
  test_token_profiler_report.py
  test_token_profiler_plugin.py
  test_token_profiler_cli.py

docs/
  token-profiling-playbook.md
```

---

### Task 1: Package scaffold + data models

**Files:**
- Create: `scripts/token_profiler/__init__.py`
- Create: `scripts/token_profiler/__main__.py`
- Create: `scripts/token_profiler/models.py`
- Create: `scripts/token_profiler/plugin_protocol.py`
- Test: `tests/test_token_profiler_models.py`

- [ ] **Step 1: Create package directory**

```bash
mkdir -p scripts/token_profiler
```

- [ ] **Step 2: Write `__init__.py`**

```python
"""Claude Code session token profiler."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write `__main__.py`**

```python
"""Entry point for python -m scripts.token_profiler."""

from scripts.token_profiler.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write failing tests for data models**

Create `tests/test_token_profiler_models.py`:

```python
"""Tests for token profiler data models."""

from scripts.token_profiler.models import (
    ContentBlock,
    ToolResult,
    Usage,
    RawTurn,
    ToolAttribution,
    ProfiledTurn,
    CompactionEvent,
    PhaseProfile,
    SessionProfile,
    RunProfile,
    BucketBreakdown,
    DollarCost,
)
from datetime import datetime, timezone


def test_usage_from_dict():
    """Usage parses from API response dict, taking output_tokens from final chunk."""
    raw = {
        "input_tokens": 3,
        "cache_creation_input_tokens": 31704,
        "cache_read_input_tokens": 0,
        "output_tokens": 378,
    }
    u = Usage.from_dict(raw)
    assert u.input_tokens == 3
    assert u.cache_creation_input_tokens == 31704
    assert u.cache_read_input_tokens == 0
    assert u.output_tokens == 378


def test_raw_turn_context_window():
    """context_window = input + cache_creation + cache_read (excludes output)."""
    turn = RawTurn(
        request_id="req_1",
        index=0,
        timestamp=datetime.now(timezone.utc),
        usage=Usage(input_tokens=3, cache_creation_input_tokens=31704,
                    cache_read_input_tokens=0, output_tokens=378),
        stop_reason="end_turn",
        content_blocks=[],
        tool_results=[],
        assistant_text="hello",
    )
    assert turn.context_window == 31707


def test_raw_turn_assistant_text_concatenation():
    """assistant_text is set from concatenated text blocks."""
    turn = RawTurn(
        request_id="req_1",
        index=0,
        timestamp=datetime.now(timezone.utc),
        usage=Usage(input_tokens=0, cache_creation_input_tokens=0,
                    cache_read_input_tokens=0, output_tokens=0),
        stop_reason="end_turn",
        content_blocks=[
            ContentBlock(type="text", size=5, text_content="hello"),
            ContentBlock(type="thinking", size=3, thinking_content="hmm"),
            ContentBlock(type="text", size=6, text_content=" world"),
        ],
        tool_results=[],
        assistant_text="hello world",
    )
    assert turn.assistant_text == "hello world"


def test_tool_result_content_types():
    """ToolResult classifies content correctly."""
    text_result = ToolResult(tool_use_id="t1", content_type="text", content_size_chars=500)
    ref_result = ToolResult(tool_use_id="t2", content_type="tool_references", content_size_chars=0)
    err_result = ToolResult(tool_use_id="t3", content_type="error", content_size_chars=42)
    assert text_result.content_type == "text"
    assert ref_result.content_size_chars == 0
    assert err_result.content_type == "error"


def test_tool_attribution_tokens_estimate():
    """Token estimate is chars / 4."""
    attr = ToolAttribution(
        tool_name="Read",
        description="test.py",
        result_size_chars=400,
        result_size_tokens_est=100,
        fraction_of_delta=0.5,
        attributed_delta=5000,
        attributed_session_cost=500000,
    )
    assert attr.result_size_tokens_est == attr.result_size_chars // 4


def test_compaction_event_reduction():
    """reduction_tokens = before - after."""
    evt = CompactionEvent(
        segment_id=0,
        turn_index=50,
        context_before=195000,
        context_after=120000,
        reduction_tokens=75000,
    )
    assert evt.reduction_tokens == evt.context_before - evt.context_after


def test_bucket_breakdown_total():
    """All bucket fields sum correctly."""
    bb = BucketBreakdown(
        input_tokens=100,
        cache_creation_tokens=200,
        cache_read_tokens=300,
        output_tokens=400,
    )
    assert bb.total == 1000


def test_session_profile_summary_fields():
    """SessionProfile can be constructed with all required fields."""
    profile = SessionProfile(
        session_id="abc",
        session_type="main",
        model="claude-opus-4-6",
        turns=[],
        phases={},
        compaction_events=[],
    )
    assert profile.session_type == "main"
    assert profile.dispatched_from_session is None
    assert profile.dispatched_at_turn is None


def test_run_profile_construction():
    """RunProfile wraps multiple sessions."""
    rp = RunProfile(run_id="run-14", sessions=[])
    assert rp.run_id == "run-14"
    assert rp.sessions == []
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.token_profiler.models'`

- [ ] **Step 6: Write `models.py` — all dataclasses**

```python
"""Data model for the token profiler.

See spec: docs/superpowers/specs/2026-03-24-token-profiler-design.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

    @classmethod
    def from_dict(cls, d: dict) -> Usage:
        return cls(
            input_tokens=d.get("input_tokens", 0),
            cache_creation_input_tokens=d.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=d.get("cache_read_input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
        )


@dataclass
class ContentBlock:
    type: str  # "text" | "thinking" | "tool_use"
    size: int
    text_content: str | None = None
    thinking_content: str | None = None
    tool_name: str | None = None
    tool_input_summary: str | None = None


@dataclass
class ToolResult:
    tool_use_id: str
    content_type: str  # "text" | "tool_references" | "error" | "empty"
    content_size_chars: int


@dataclass
class RawTurn:
    request_id: str
    index: int
    timestamp: datetime
    usage: Usage
    stop_reason: str | None
    content_blocks: list[ContentBlock]
    tool_results: list[ToolResult]
    assistant_text: str

    @property
    def context_window(self) -> int:
        """input + cache_creation + cache_read (excludes output — outputs become
        cached input on the next turn and are captured in the next turn's delta)."""
        return (
            self.usage.input_tokens
            + self.usage.cache_creation_input_tokens
            + self.usage.cache_read_input_tokens
        )


@dataclass
class ToolAttribution:
    tool_name: str
    description: str
    result_size_chars: int
    result_size_tokens_est: int
    fraction_of_delta: float
    attributed_delta: int
    attributed_session_cost: int


@dataclass
class ProfiledTurn:
    raw: RawTurn
    context_window: int
    delta: int
    segment_id: int
    remaining_calls_in_segment: int  # inclusive, minimum 1
    session_cost_tokens: int
    tool_attributions: list[ToolAttribution]
    phase: str  # from plugin or "unknown"


@dataclass
class CompactionEvent:
    segment_id: int
    turn_index: int
    context_before: int
    context_after: int
    reduction_tokens: int


@dataclass
class BucketBreakdown:
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
            + self.output_tokens
        )


@dataclass
class DollarCost:
    input_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    output_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.cache_creation_cost + self.cache_read_cost + self.output_cost


@dataclass
class PhaseProfile:
    phase: str
    turn_count: int
    turn_indices: list[int]
    delta_sum: int
    session_cost_sum: int
    top_tools: list[str]
    bucket_breakdown: BucketBreakdown
    dollar_cost: DollarCost


@dataclass
class SessionSummary:
    total_api_calls: int
    total_context_tokens: int
    total_output_tokens: int
    total_session_cost: int
    total_dollars: float
    hottest_turns: list[int]
    hottest_tools: list[str]


@dataclass
class SessionProfile:
    session_id: str
    session_type: str  # "main" | "subagent"
    model: str
    turns: list[ProfiledTurn]
    phases: dict[str, PhaseProfile]
    compaction_events: list[CompactionEvent]
    subagent_name: str | None = None
    dispatched_from_session: str | None = None
    dispatched_at_turn: int | None = None
    returned_at_turn: int | None = None
    summary: SessionSummary | None = None


@dataclass
class CrossSessionSummary:
    total_billed_tokens: int
    total_session_cost_tokens: int
    total_dollars: float
    session_breakdown: dict[str, float]


@dataclass
class RunProfile:
    run_id: str
    sessions: list[SessionProfile]
    cross_session_summary: CrossSessionSummary | None = None
```

- [ ] **Step 7: Write `plugin_protocol.py`**

```python
"""Plugin protocol for the token profiler.

External plugins implement this protocol to provide domain-specific
phase detection, subagent naming, and profile enrichment. Loaded at
runtime via --plugin CLI flag or TOKEN_PROFILER_PLUGINS env var.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from scripts.token_profiler.models import RawTurn, SessionProfile


@runtime_checkable
class ProfilerPlugin(Protocol):
    name: str

    def detect(self, turns: list[RawTurn]) -> bool:
        """Auto-detect whether this plugin applies to this session."""
        ...

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Map turn indices to phase names. Return empty dict to skip.

        RawTurn includes assistant_text (concatenated text blocks) for
        content-heuristic detection.
        """
        ...

    def name_subagent(self, turns: list[RawTurn]) -> str | None:
        """Infer a human name for a subagent session. Return None to skip.

        turns[0].assistant_text contains the first text output.
        """
        ...

    def enrich_profile(self, profile: SessionProfile) -> None:
        """Add plugin-specific annotations."""
        ...

    def optimization_patterns(self) -> list[dict]:
        """Plugin-specific optimization patterns for the playbook/viewer."""
        ...
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_models.py -v`
Expected: all PASS

- [ ] **Step 9: Lint**

Run: `ruff check scripts/token_profiler/ tests/test_token_profiler_models.py`
Expected: clean (fix any issues)

- [ ] **Step 10: Commit**

```bash
git add scripts/token_profiler/__init__.py scripts/token_profiler/__main__.py \
  scripts/token_profiler/models.py scripts/token_profiler/plugin_protocol.py \
  tests/test_token_profiler_models.py
git commit -m "feat(token-profiler): add data models and plugin protocol"
```

---

### Task 2: Extract module — JSONL parsing

**Files:**
- Create: `scripts/token_profiler/extract.py`
- Test: `tests/test_token_profiler_extract.py`

**Reference:** `scripts/session-to-cast.py` for tool description logic. Run 14 session JSONL at `~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl` for realistic test data structure.

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_extract.py`:

```python
"""Tests for token profiler JSONL extraction."""

import json
import tempfile
from pathlib import Path

from scripts.token_profiler.extract import (
    extract_session,
    discover_subagents,
    find_project_dir,
    tool_description,
    classify_tool_result_content,
)
from scripts.token_profiler.models import RawTurn


def _write_jsonl(path: Path, messages: list[dict]) -> None:
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def _make_assistant_msg(
    request_id: str,
    content: list[dict],
    usage: dict,
    stop_reason: str | None = None,
    timestamp: str = "2026-03-24T05:20:46.000Z",
) -> dict:
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": timestamp,
        "message": {
            "model": "claude-opus-4-6",
            "content": content,
            "usage": usage,
            "stop_reason": stop_reason,
        },
    }


def _make_user_tool_result(tool_use_id: str, content: str) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
            ]
        },
        "timestamp": "2026-03-24T05:20:50.000Z",
    }


USAGE_CHUNK_PARTIAL = {
    "input_tokens": 3,
    "cache_creation_input_tokens": 31704,
    "cache_read_input_tokens": 0,
    "output_tokens": 9,  # partial — streaming
}

USAGE_CHUNK_FINAL = {
    "input_tokens": 3,
    "cache_creation_input_tokens": 31704,
    "cache_read_input_tokens": 0,
    "output_tokens": 378,  # final — correct total
}


def test_extract_groups_by_request_id():
    """Multiple chunks with same requestId become one RawTurn."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [{"type": "thinking", "thinking": ""}], USAGE_CHUNK_PARTIAL),
            _make_assistant_msg("req_1", [{"type": "text", "text": "hello"}], USAGE_CHUNK_PARTIAL),
            _make_assistant_msg("req_1", [{"type": "text", "text": " world"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        turns = extract_session(p)
        assert len(turns) == 1
        assert turns[0].request_id == "req_1"


def test_extract_output_tokens_from_final_chunk():
    """output_tokens must come from the chunk with non-null stop_reason."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [{"type": "text", "text": "hi"}], USAGE_CHUNK_PARTIAL),
            _make_assistant_msg("req_1", [], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        turns = extract_session(p)
        assert turns[0].usage.output_tokens == 378  # not 9


def test_extract_input_tokens_stable_across_chunks():
    """input/cache tokens are stable — any chunk works."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [], USAGE_CHUNK_PARTIAL),
            _make_assistant_msg("req_1", [], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        turns = extract_session(p)
        assert turns[0].usage.input_tokens == 3
        assert turns[0].usage.cache_creation_input_tokens == 31704


def test_extract_assistant_text_concatenation():
    """assistant_text concatenates all text blocks across chunks."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [{"type": "text", "text": "hello"}], USAGE_CHUNK_PARTIAL),
            _make_assistant_msg("req_1", [{"type": "text", "text": " world"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        turns = extract_session(p)
        assert turns[0].assistant_text == "hello world"


def test_extract_tool_use_blocks():
    """tool_use blocks are captured with name and input summary."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [
                {"type": "tool_use", "id": "tu_1", "name": "Read",
                 "input": {"file_path": "/foo/bar/test.py"}},
            ], USAGE_CHUNK_FINAL, stop_reason="tool_use"),
        ])
        turns = extract_session(p)
        assert len(turns[0].content_blocks) == 1
        assert turns[0].content_blocks[0].tool_name == "Read"


def test_extract_tool_results_paired():
    """Tool results from user messages are paired with preceding tool_use."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [
                {"type": "tool_use", "id": "tu_1", "name": "Bash",
                 "input": {"command": "ls", "description": "list files"}},
            ], USAGE_CHUNK_FINAL, stop_reason="tool_use"),
            _make_user_tool_result("tu_1", "file1.py\nfile2.py"),
        ])
        turns = extract_session(p)
        assert len(turns[0].tool_results) == 1
        assert turns[0].tool_results[0].tool_use_id == "tu_1"
        assert turns[0].tool_results[0].content_size_chars == len("file1.py\nfile2.py")
        assert turns[0].tool_results[0].content_type == "text"


def test_extract_multiple_turns():
    """Multiple requestIds produce multiple turns in sequence."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        usage2 = {**USAGE_CHUNK_FINAL, "cache_read_input_tokens": 31704, "cache_creation_input_tokens": 3000}
        _write_jsonl(p, [
            _make_assistant_msg("req_1", [{"type": "text", "text": "first"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
            _make_assistant_msg("req_2", [{"type": "text", "text": "second"}], usage2, stop_reason="end_turn",
                                timestamp="2026-03-24T05:21:00.000Z"),
        ])
        turns = extract_session(p)
        assert len(turns) == 2
        assert turns[0].index == 0
        assert turns[1].index == 1
        assert turns[1].timestamp > turns[0].timestamp


def test_extract_ignores_non_assistant_messages():
    """Non-assistant messages (progress, system, file-history-snapshot) are skipped for turns."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        _write_jsonl(p, [
            {"type": "progress", "data": {}},
            {"type": "system", "content": "..."},
            _make_assistant_msg("req_1", [{"type": "text", "text": "hi"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
            {"type": "file-history-snapshot", "snapshot": {}},
        ])
        turns = extract_session(p)
        assert len(turns) == 1


def test_classify_tool_result_text():
    assert classify_tool_result_content("some text output") == ("text", 16)


def test_classify_tool_result_structured():
    content = [{"type": "tool_reference", "tool_name": "Read"}]
    assert classify_tool_result_content(content) == ("tool_references", 0)


def test_classify_tool_result_empty():
    assert classify_tool_result_content("") == ("empty", 0)
    assert classify_tool_result_content(None) == ("empty", 0)


def test_tool_description_bash():
    assert tool_description("Bash", {"description": "list files", "command": "ls"}) == "list files"


def test_tool_description_read():
    assert "test.py" in tool_description("Read", {"file_path": "/foo/bar/test.py"})


def test_tool_description_agent():
    desc = tool_description("Agent", {"description": "audit code", "subagent_type": "holtz:justine", "run_in_background": True})
    assert "holtz:justine" in desc
    assert "background" in desc


def test_discover_subagents():
    """Discovers subagent JSONLs in <session-id>/subagents/ directory."""
    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp)
        session_file = session_dir / "abc123.jsonl"
        _write_jsonl(session_file, [
            _make_assistant_msg("req_1", [{"type": "text", "text": "main"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        sub_dir = session_dir / "abc123" / "subagents"
        sub_dir.mkdir(parents=True)
        sub_file = sub_dir / "agent-xyz.jsonl"
        _write_jsonl(sub_file, [
            _make_assistant_msg("req_s1", [{"type": "text", "text": "sub"}], USAGE_CHUNK_FINAL, stop_reason="end_turn"),
        ])
        paths = discover_subagents(session_file)
        assert len(paths) == 1
        assert paths[0].name == "agent-xyz.jsonl"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_extract.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `extract.py`**

```python
"""Stage 1: Extract RawTurns from Claude Code session JSONL files.

Reads session JSONL, groups assistant messages by requestId into RawTurn objects.
Handles streaming chunks correctly: input/cache tokens from any chunk,
output_tokens from the final chunk only (where stop_reason is non-null).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts.token_profiler.models import ContentBlock, RawTurn, ToolResult, Usage


def classify_tool_result_content(content: str | list | None) -> tuple[str, int]:
    """Classify tool result content and measure its size.

    Returns (content_type, content_size_chars).
    """
    if content is None or content == "":
        return ("empty", 0)
    if isinstance(content, list):
        # Structured content (e.g., ToolSearch tool_references)
        has_tool_ref = any(
            isinstance(item, dict) and item.get("type") == "tool_reference"
            for item in content
        )
        if has_tool_ref:
            return ("tool_references", 0)
        return ("text", sum(len(str(item)) for item in content))
    if isinstance(content, str):
        if not content.strip():
            return ("empty", 0)
        return ("text", len(content))
    return ("empty", 0)


def tool_description(name: str, inp: dict) -> str:
    """Compact one-line description of a tool call.

    Reuses logic from session-to-cast.py.
    """
    if name == "Bash":
        return inp.get("description", inp.get("command", "")[:80])
    elif name in ("Read", "Write", "Edit"):
        p = inp.get("file_path", "")
        return "/".join(p.split("/")[-2:]) if "/" in p else p
    elif name == "Grep":
        return f"/{inp.get('pattern', '')}/"
    elif name == "Glob":
        return inp.get("pattern", "")
    elif name == "Agent":
        desc = inp.get("description", "")
        st = inp.get("subagent_type", "")
        bg = " (background)" if inp.get("run_in_background") else ""
        return f"[{st}] {desc}{bg}" if st else f"{desc}{bg}"
    elif name in ("TaskCreate", "TaskUpdate"):
        desc = inp.get("subject", inp.get("taskId", ""))
        if name == "TaskUpdate":
            return f"#{desc} -> {inp.get('status', '')}"
        return desc
    elif name == "Skill":
        return inp.get("skill", "")
    elif name == "ToolSearch":
        return inp.get("query", "")
    return ""


def extract_session(session_path: Path) -> list[RawTurn]:
    """Extract RawTurns from a single session JSONL file.

    Groups assistant messages by requestId. For each API call:
    - input/cache tokens: stable across chunks, taken from first seen
    - output_tokens: cumulative, taken from final chunk (non-null stop_reason)
    - Content blocks: merged across all chunks
    - Tool results: paired from subsequent user messages by tool_use_id
    """
    messages: list[dict] = []
    with open(session_path) as f:
        for line in f:
            line = line.strip()
            if line:
                messages.append(json.loads(line))

    # Group assistant messages by requestId
    groups: dict[str, list[dict]] = defaultdict(list)
    group_order: list[str] = []
    for msg in messages:
        if msg.get("type") != "assistant":
            continue
        rid = msg.get("requestId", "unknown")
        if rid not in groups:
            group_order.append(rid)
        groups[rid].append(msg)

    # Collect tool_use_ids to tool results mapping
    pending_tool_ids: list[str] = []  # tool_use_ids from current turn, in order
    tool_results_by_id: dict[str, ToolResult] = {}
    # We need to process messages in order to pair tool_uses with results
    current_tool_ids: dict[str, list[str]] = defaultdict(list)  # requestId -> [tool_use_ids]

    for msg in messages:
        if msg.get("type") == "assistant":
            rid = msg.get("requestId", "unknown")
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_id = block.get("id", "")
                        if tool_id:
                            current_tool_ids[rid].append(tool_id)
        elif msg.get("type") == "user":
            user_content = msg.get("message", {}).get("content", [])
            if isinstance(user_content, list):
                for block in user_content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        raw_content = block.get("content")
                        is_error = block.get("is_error", False)
                        if is_error:
                            size = len(str(raw_content)) if raw_content else 0
                            tool_results_by_id[tool_id] = ToolResult(
                                tool_use_id=tool_id,
                                content_type="error",
                                content_size_chars=size,
                            )
                        else:
                            ctype, csize = classify_tool_result_content(raw_content)
                            tool_results_by_id[tool_id] = ToolResult(
                                tool_use_id=tool_id,
                                content_type=ctype,
                                content_size_chars=csize,
                            )

    # Build RawTurns
    turns: list[RawTurn] = []
    for idx, rid in enumerate(group_order):
        chunks = groups[rid]

        # Usage: input/cache from any chunk, output from final (non-null stop_reason)
        first_usage = chunks[0].get("message", {}).get("usage", {})
        final_output = first_usage.get("output_tokens", 0)
        final_stop_reason: str | None = None
        for chunk in chunks:
            sr = chunk.get("message", {}).get("stop_reason")
            if sr is not None:
                final_output = chunk.get("message", {}).get("usage", {}).get("output_tokens", final_output)
                final_stop_reason = sr

        usage = Usage(
            input_tokens=first_usage.get("input_tokens", 0),
            cache_creation_input_tokens=first_usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=first_usage.get("cache_read_input_tokens", 0),
            output_tokens=final_output,
        )

        # Content blocks + assistant_text
        content_blocks: list[ContentBlock] = []
        text_parts: list[str] = []
        timestamp_str = chunks[0].get("timestamp", "")

        for chunk in chunks:
            content = chunk.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text", "")
                    content_blocks.append(ContentBlock(
                        type="text", size=len(text), text_content=text,
                    ))
                    if text:
                        text_parts.append(text)
                elif btype == "thinking":
                    thinking = block.get("thinking", "")
                    content_blocks.append(ContentBlock(
                        type="thinking", size=len(thinking), thinking_content=thinking,
                    ))
                elif btype == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    content_blocks.append(ContentBlock(
                        type="tool_use",
                        size=len(json.dumps(inp)),
                        tool_name=name,
                        tool_input_summary=tool_description(name, inp),
                    ))

        # Pair tool results
        turn_tool_results: list[ToolResult] = []
        for tool_id in current_tool_ids.get(rid, []):
            if tool_id in tool_results_by_id:
                turn_tool_results.append(tool_results_by_id[tool_id])

        # Parse timestamp
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        turns.append(RawTurn(
            request_id=rid,
            index=idx,
            timestamp=ts,
            usage=usage,
            stop_reason=final_stop_reason,
            content_blocks=content_blocks,
            tool_results=turn_tool_results,
            assistant_text="".join(text_parts),
        ))

    return turns


def discover_subagents(session_path: Path) -> list[Path]:
    """Discover subagent JSONL files for a session.

    Looks for <session-id>/subagents/*.jsonl in the same directory.
    """
    session_id = session_path.stem
    subagent_dir = session_path.parent / session_id / "subagents"
    if not subagent_dir.exists():
        return []
    return sorted(subagent_dir.glob("*.jsonl"))


def find_project_dir(project_root: str | None = None) -> Path | None:
    """Find the .claude/projects/ directory for a project.

    Reuses the path-mangling convention from Claude Code:
    /Users/foo/my-project -> ~/.claude/projects/-Users-foo-my-project/
    """
    import subprocess

    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return None

    if project_root:
        mangled = project_root.replace("/", "-")
        candidate = claude_dir / mangled
        if candidate.exists():
            return candidate

    # Auto-detect from git root or cwd
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = str(Path.cwd())

    mangled = root.replace("/", "-")
    candidate = claude_dir / mangled
    if candidate.exists():
        return candidate

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_extract.py -v`
Expected: all PASS

- [ ] **Step 5: Lint**

Run: `ruff check scripts/token_profiler/extract.py tests/test_token_profiler_extract.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add scripts/token_profiler/extract.py tests/test_token_profiler_extract.py
git commit -m "feat(token-profiler): add JSONL extraction with streaming chunk handling"
```

---

### Task 3: Analyze module — delta, attribution, session cost, phases

**Files:**
- Create: `scripts/token_profiler/analyze.py`
- Test: `tests/test_token_profiler_analyze.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_analyze.py`:

```python
"""Tests for token profiler analysis pipeline (Stages 2-5)."""

import json
from datetime import datetime, timezone

from scripts.token_profiler.analyze import (
    compute_deltas,
    compute_attributions,
    compute_session_costs,
    apply_phase_labels,
    build_session_profile,
)
from scripts.token_profiler.models import (
    CompactionEvent,
    ContentBlock,
    RawTurn,
    ToolResult,
    Usage,
)


def _make_turn(
    index: int,
    input_tokens: int = 3,
    cache_creation: int = 0,
    cache_read: int = 0,
    output_tokens: int = 100,
    tool_results: list[ToolResult] | None = None,
    assistant_text: str = "",
) -> RawTurn:
    return RawTurn(
        request_id=f"req_{index}",
        index=index,
        timestamp=datetime(2026, 3, 24, 5, 20 + index, tzinfo=timezone.utc),
        usage=Usage(
            input_tokens=input_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            output_tokens=output_tokens,
        ),
        stop_reason="end_turn",
        content_blocks=[],
        tool_results=tool_results or [],
        assistant_text=assistant_text,
    )


# --- Stage 2: Delta ---

def test_deltas_monotonic_growth():
    """Monotonically growing context produces positive deltas."""
    turns = [
        _make_turn(0, cache_creation=30000),  # ctx=30003
        _make_turn(1, cache_creation=5000, cache_read=30003),  # ctx=35006
        _make_turn(2, cache_creation=2000, cache_read=35003),  # ctx=37006
    ]
    result = compute_deltas(turns)
    assert result[0].context_window == 30003
    assert result[0].delta == 30003  # first turn: delta = ctx
    assert result[1].delta == 35006 - 30003
    assert result[2].delta == 37006 - 35006
    # All in segment 0
    assert all(r.segment_id == 0 for r in result)


def test_deltas_compaction_detection():
    """Negative delta increments segment_id and records CompactionEvent."""
    turns = [
        _make_turn(0, cache_creation=100000),  # ctx=100003
        _make_turn(1, cache_creation=50000, cache_read=100003),  # ctx=150006
        _make_turn(2, cache_creation=60000),  # ctx=60003 — compaction!
        _make_turn(3, cache_creation=5000, cache_read=60003),  # ctx=65006
    ]
    result = compute_deltas(turns)
    assert result[0].segment_id == 0
    assert result[1].segment_id == 0
    assert result[2].segment_id == 1  # new segment after compaction
    assert result[3].segment_id == 1
    assert result[2].delta < 0  # negative delta


def test_deltas_compaction_events_recorded():
    """CompactionEvents are returned for negative deltas."""
    turns = [
        _make_turn(0, cache_creation=100000),
        _make_turn(1, cache_creation=50000),  # drop
    ]
    result, events = compute_deltas(turns, return_events=True)
    assert len(events) == 1
    assert events[0].context_before == 100003
    assert events[0].context_after == 50003
    assert events[0].reduction_tokens == 50000


# --- Stage 3: Attribution ---

def test_attribution_single_tool():
    """Single tool result gets 100% of delta."""
    turns = [_make_turn(0, cache_creation=10000, tool_results=[
        ToolResult(tool_use_id="t1", content_type="text", content_size_chars=5000),
    ])]
    deltas = compute_deltas(turns)
    attributed = compute_attributions(deltas, turns)
    assert len(attributed[0].tool_attributions) >= 1
    # The text tool should get a significant fraction
    text_attr = [a for a in attributed[0].tool_attributions if a.tool_name != "_assistant_overhead"]
    assert len(text_attr) >= 0  # may be empty if all goes to overhead


def test_attribution_multiple_tools_proportional():
    """Multiple tool results split delta proportionally by content size."""
    turns = [_make_turn(0, cache_creation=10000, tool_results=[
        ToolResult(tool_use_id="t1", content_type="text", content_size_chars=3000),
        ToolResult(tool_use_id="t2", content_type="text", content_size_chars=7000),
    ])]
    turns[0].content_blocks = [
        ContentBlock(type="tool_use", size=10, tool_name="Read", tool_input_summary="file_a.py"),
        ContentBlock(type="tool_use", size=10, tool_name="Read", tool_input_summary="file_b.py"),
    ]
    deltas = compute_deltas(turns)
    attributed = compute_attributions(deltas, turns)
    tool_attrs = [a for a in attributed[0].tool_attributions if a.tool_name != "_assistant_overhead"]
    if len(tool_attrs) == 2:
        assert tool_attrs[0].fraction_of_delta < tool_attrs[1].fraction_of_delta  # 3000 < 7000


def test_attribution_non_text_goes_to_overhead():
    """Non-text tool results (tool_references) have 0 chars, absorbed by overhead."""
    turns = [_make_turn(0, cache_creation=10000, tool_results=[
        ToolResult(tool_use_id="t1", content_type="tool_references", content_size_chars=0),
    ])]
    deltas = compute_deltas(turns)
    attributed = compute_attributions(deltas, turns)
    overhead = [a for a in attributed[0].tool_attributions if a.tool_name == "_assistant_overhead"]
    assert len(overhead) == 1


# --- Stage 4: Session Cost ---

def test_session_cost_inclusive_remaining():
    """remaining is inclusive: last turn gets remaining=1, not 0."""
    turns = [
        _make_turn(0, cache_creation=10000),
        _make_turn(1, cache_creation=5000, cache_read=10003),
        _make_turn(2, cache_creation=2000, cache_read=15006),
    ]
    deltas = compute_deltas(turns)
    costed = compute_session_costs(deltas)
    # Turn 0: remaining = (2-0)+1 = 3, Turn 1: remaining = 2, Turn 2: remaining = 1
    assert costed[0].remaining_calls_in_segment == 3
    assert costed[1].remaining_calls_in_segment == 2
    assert costed[2].remaining_calls_in_segment == 1
    assert costed[2].session_cost_tokens != 0  # last turn is non-zero


def test_session_cost_single_turn():
    """Single-turn session gets remaining=1, session_cost = delta."""
    turns = [_make_turn(0, cache_creation=10000)]
    deltas = compute_deltas(turns)
    costed = compute_session_costs(deltas)
    assert costed[0].remaining_calls_in_segment == 1
    assert costed[0].session_cost_tokens == costed[0].delta


def test_session_cost_across_compaction():
    """Segments are independent — remaining resets after compaction."""
    turns = [
        _make_turn(0, cache_creation=100000),  # segment 0
        _make_turn(1, cache_creation=50000, cache_read=100003),  # segment 0
        _make_turn(2, cache_creation=60000),  # segment 1 (compaction)
        _make_turn(3, cache_creation=5000, cache_read=60003),  # segment 1
    ]
    deltas = compute_deltas(turns)
    costed = compute_session_costs(deltas)
    # Segment 0: turns 0,1 -> remaining 2,1
    assert costed[0].remaining_calls_in_segment == 2
    assert costed[1].remaining_calls_in_segment == 1
    # Segment 1: turns 2,3 -> remaining 2,1
    assert costed[2].remaining_calls_in_segment == 2
    assert costed[3].remaining_calls_in_segment == 1


# --- Stage 5: Phase Attribution ---

def test_phase_labels_from_milestones_turn_based():
    """Turn-index milestones assign phases correctly."""
    turns = [_make_turn(i) for i in range(5)]
    milestones = [
        {"phase": "recon", "start_turn": 0, "end_turn": 2},
        {"phase": "audit", "start_turn": 3, "end_turn": 4},
    ]
    labels = apply_phase_labels(turns, milestones=milestones)
    assert labels == {0: "recon", 1: "recon", 2: "recon", 3: "audit", 4: "audit"}


def test_phase_labels_gaps_are_unknown():
    """Turns not covered by milestones get 'unknown'."""
    turns = [_make_turn(i) for i in range(5)]
    milestones = [
        {"phase": "recon", "start_turn": 0, "end_turn": 1},
        # gap at turn 2
        {"phase": "audit", "start_turn": 3, "end_turn": 4},
    ]
    labels = apply_phase_labels(turns, milestones=milestones)
    assert labels[2] == "unknown"


def test_phase_labels_no_milestones_all_unknown():
    """Without milestones or plugin, all turns are 'unknown'."""
    turns = [_make_turn(i) for i in range(3)]
    labels = apply_phase_labels(turns)
    assert all(v == "unknown" for v in labels.values())


def test_phase_labels_plugin_overrides():
    """Plugin label_phases() takes precedence."""

    class FakePlugin:
        name = "test"

        def detect(self, turns):
            return True

        def label_phases(self, turns):
            return {0: "setup", 1: "work", 2: "cleanup"}

        def name_subagent(self, turns):
            return None

        def enrich_profile(self, profile):
            pass

        def optimization_patterns(self):
            return []

    turns = [_make_turn(i) for i in range(3)]
    labels = apply_phase_labels(turns, plugin=FakePlugin())
    assert labels == {0: "setup", 1: "work", 2: "cleanup"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_analyze.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `analyze.py`**

```python
"""Stages 2-5: Delta computation, attribution, session cost, phase attribution.

All functions are pure — no side effects, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts.token_profiler.models import (
    CompactionEvent,
    PhaseProfile,
    ProfiledTurn,
    BucketBreakdown,
    DollarCost,
    RawTurn,
    SessionProfile,
    SessionSummary,
    ToolAttribution,
)

if TYPE_CHECKING:
    from scripts.token_profiler.plugin_protocol import ProfilerPlugin


@dataclass
class _DeltaTurn:
    """Intermediate: RawTurn with delta and segment info, before attribution."""
    raw: RawTurn
    context_window: int
    delta: int
    segment_id: int


def compute_deltas(
    turns: list[RawTurn],
    return_events: bool = False,
) -> list[_DeltaTurn] | tuple[list[_DeltaTurn], list[CompactionEvent]]:
    """Stage 2: Compute context window deltas and detect compaction segments.

    Returns list of _DeltaTurns. If return_events=True, also returns CompactionEvents.
    """
    result: list[_DeltaTurn] = []
    events: list[CompactionEvent] = []
    prev_ctx = 0
    segment_id = 0

    for turn in turns:
        ctx = turn.context_window
        delta = ctx - prev_ctx

        if delta < 0 and turn.index > 0:
            events.append(CompactionEvent(
                segment_id=segment_id,
                turn_index=turn.index,
                context_before=prev_ctx,
                context_after=ctx,
                reduction_tokens=prev_ctx - ctx,
            ))
            segment_id += 1

        result.append(_DeltaTurn(
            raw=turn,
            context_window=ctx,
            delta=delta,
            segment_id=segment_id,
        ))
        prev_ctx = ctx

    if return_events:
        return result, events
    return result


def compute_attributions(
    delta_turns: list[_DeltaTurn],
    raw_turns: list[RawTurn],
) -> list[_DeltaTurn]:
    """Stage 3: Attribute each turn's delta across tool results.

    Returns delta_turns with tool_attributions populated (stored on _DeltaTurn
    for later propagation to ProfiledTurn).
    """
    # For now, just return as-is — attributions are computed in build_session_profile
    return delta_turns


def _compute_tool_attributions(
    delta: int,
    session_cost: int,
    raw_turn: RawTurn,
) -> list[ToolAttribution]:
    """Distribute delta across tool results proportionally by content size."""
    text_results = [
        (tr, cb)
        for tr in raw_turn.tool_results
        for cb in raw_turn.content_blocks
        if cb.type == "tool_use" and tr.content_type == "text" and tr.content_size_chars > 0
    ]

    # Simple: just use tool_results with content
    measurable = [tr for tr in raw_turn.tool_results if tr.content_type == "text" and tr.content_size_chars > 0]
    total_chars = sum(tr.content_size_chars for tr in measurable)

    attributions: list[ToolAttribution] = []
    attributed_delta = 0

    if total_chars > 0:
        # Match tool results to content blocks by position
        tool_blocks = [cb for cb in raw_turn.content_blocks if cb.type == "tool_use"]
        for i, tr in enumerate(measurable):
            fraction = tr.content_size_chars / total_chars
            # Find corresponding tool block
            tool_name = "unknown"
            tool_desc = ""
            # Try to match by position in tool_results vs content_blocks
            result_idx = raw_turn.tool_results.index(tr)
            if result_idx < len(tool_blocks):
                tool_name = tool_blocks[result_idx].tool_name or "unknown"
                tool_desc = tool_blocks[result_idx].tool_input_summary or ""

            attr_delta = int(delta * fraction)
            attr_cost = int(session_cost * fraction)
            attributed_delta += attr_delta

            attributions.append(ToolAttribution(
                tool_name=tool_name,
                description=tool_desc,
                result_size_chars=tr.content_size_chars,
                result_size_tokens_est=tr.content_size_chars // 4,
                fraction_of_delta=fraction,
                attributed_delta=attr_delta,
                attributed_session_cost=attr_cost,
            ))

    # Remainder goes to _assistant_overhead
    overhead_delta = delta - attributed_delta
    overhead_cost = session_cost - sum(a.attributed_session_cost for a in attributions)
    attributions.append(ToolAttribution(
        tool_name="_assistant_overhead",
        description="model text, thinking, system messages, non-text tool results",
        result_size_chars=0,
        result_size_tokens_est=0,
        fraction_of_delta=1.0 - sum(a.fraction_of_delta for a in attributions),
        attributed_delta=overhead_delta,
        attributed_session_cost=overhead_cost,
    ))

    return attributions


def compute_session_costs(delta_turns: list[_DeltaTurn]) -> list[_DeltaTurn]:
    """Stage 4: Two-pass session cost computation.

    Pass 1 (forward): already done in compute_deltas (segment boundaries known).
    Pass 2: compute remaining_calls_in_segment for each turn.

    remaining = (last_turn_index_in_segment - current_index) + 1  (inclusive)
    """
    if not delta_turns:
        return delta_turns

    # Find segment boundaries: {segment_id: (first_idx, last_idx)}
    segments: dict[int, tuple[int, int]] = {}
    for i, dt in enumerate(delta_turns):
        sid = dt.segment_id
        if sid not in segments:
            segments[sid] = (i, i)
        else:
            segments[sid] = (segments[sid][0], i)

    # Assign remaining and session_cost
    for i, dt in enumerate(delta_turns):
        _, last_idx = segments[dt.segment_id]
        remaining = (last_idx - i) + 1  # inclusive
        dt._remaining = remaining
        dt._session_cost = dt.delta * remaining

    return delta_turns


def apply_phase_labels(
    turns: list[RawTurn],
    milestones: list[dict] | None = None,
    plugin: ProfilerPlugin | None = None,
) -> dict[int, str]:
    """Stage 5: Assign phase labels to turns.

    Priority: plugin > milestones > 'unknown'.
    """
    labels: dict[int, str] = {t.index: "unknown" for t in turns}

    if plugin is not None:
        plugin_labels = plugin.label_phases(turns)
        if plugin_labels:
            labels.update(plugin_labels)
            return labels

    if milestones:
        for ms in milestones:
            phase = ms["phase"]
            if "start_turn" in ms:
                start = ms["start_turn"]
                end = ms["end_turn"]
                for t in turns:
                    if start <= t.index <= end:
                        labels[t.index] = phase
            elif "start" in ms:
                from datetime import datetime as dt
                start = dt.fromisoformat(ms["start"].replace("Z", "+00:00"))
                end = dt.fromisoformat(ms["end"].replace("Z", "+00:00"))
                for t in turns:
                    if start <= t.timestamp <= end:
                        labels[t.index] = phase

    return labels


def build_session_profile(
    session_id: str,
    raw_turns: list[RawTurn],
    session_type: str = "main",
    milestones: list[dict] | None = None,
    plugin: ProfilerPlugin | None = None,
) -> SessionProfile:
    """Full analysis pipeline: delta -> attribution -> session cost -> phase -> profile."""
    delta_turns, compaction_events = compute_deltas(raw_turns, return_events=True)
    costed = compute_session_costs(delta_turns)
    phase_labels = apply_phase_labels(raw_turns, milestones=milestones, plugin=plugin)

    # Build ProfiledTurns with attributions
    profiled: list[ProfiledTurn] = []
    for dt in costed:
        remaining = getattr(dt, "_remaining", 1)
        session_cost = getattr(dt, "_session_cost", dt.delta)
        attributions = _compute_tool_attributions(dt.delta, session_cost, dt.raw)

        profiled.append(ProfiledTurn(
            raw=dt.raw,
            context_window=dt.context_window,
            delta=dt.delta,
            segment_id=dt.segment_id,
            remaining_calls_in_segment=remaining,
            session_cost_tokens=session_cost,
            tool_attributions=attributions,
            phase=phase_labels.get(dt.raw.index, "unknown"),
        ))

    # Aggregate phases
    phases: dict[str, PhaseProfile] = {}
    for pt in profiled:
        phase = pt.phase
        if phase not in phases:
            phases[phase] = PhaseProfile(
                phase=phase,
                turn_count=0,
                turn_indices=[],
                delta_sum=0,
                session_cost_sum=0,
                top_tools=[],
                bucket_breakdown=BucketBreakdown(0, 0, 0, 0),
                dollar_cost=DollarCost(0.0, 0.0, 0.0, 0.0),
            )
        pp = phases[phase]
        pp.turn_count += 1
        pp.turn_indices.append(pt.raw.index)
        pp.delta_sum += pt.delta
        pp.session_cost_sum += pt.session_cost_tokens
        u = pt.raw.usage
        pp.bucket_breakdown.input_tokens += u.input_tokens
        pp.bucket_breakdown.cache_creation_tokens += u.cache_creation_input_tokens
        pp.bucket_breakdown.cache_read_tokens += u.cache_read_input_tokens
        pp.bucket_breakdown.output_tokens += u.output_tokens

    # Top tools per phase
    for pp in phases.values():
        tool_costs: dict[str, int] = {}
        for pt in profiled:
            if pt.phase == pp.phase:
                for attr in pt.tool_attributions:
                    if attr.tool_name != "_assistant_overhead":
                        tool_costs[attr.tool_name] = tool_costs.get(attr.tool_name, 0) + attr.attributed_session_cost
        pp.top_tools = sorted(tool_costs, key=lambda k: tool_costs[k], reverse=True)[:3]

    # Summary
    total_session_cost = sum(pt.session_cost_tokens for pt in profiled)
    total_output = sum(pt.raw.usage.output_tokens for pt in profiled)
    total_context = sum(pt.context_window for pt in profiled)

    # Hottest turns
    sorted_by_cost = sorted(profiled, key=lambda pt: pt.session_cost_tokens, reverse=True)
    hottest_turns = [pt.raw.index for pt in sorted_by_cost[:10]]

    # Hottest tools
    tool_totals: dict[str, int] = {}
    for pt in profiled:
        for attr in pt.tool_attributions:
            if attr.tool_name != "_assistant_overhead":
                tool_totals[attr.tool_name] = tool_totals.get(attr.tool_name, 0) + attr.attributed_session_cost
    hottest_tools = sorted(tool_totals, key=lambda k: tool_totals[k], reverse=True)[:10]

    model = raw_turns[0].usage.__class__.__name__ if not raw_turns else "unknown"
    # Try to get model from first turn's data — will be set by caller
    summary = SessionSummary(
        total_api_calls=len(profiled),
        total_context_tokens=total_context,
        total_output_tokens=total_output,
        total_session_cost=total_session_cost,
        total_dollars=0.0,  # filled in by pricing stage
        hottest_turns=hottest_turns,
        hottest_tools=hottest_tools,
    )

    return SessionProfile(
        session_id=session_id,
        session_type=session_type,
        model="unknown",  # set by caller from JSONL metadata
        turns=profiled,
        phases=phases,
        compaction_events=compaction_events,
        summary=summary,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_analyze.py -v`
Expected: all PASS

- [ ] **Step 5: Lint**

Run: `ruff check scripts/token_profiler/analyze.py tests/test_token_profiler_analyze.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add scripts/token_profiler/analyze.py tests/test_token_profiler_analyze.py
git commit -m "feat(token-profiler): add analysis pipeline — delta, attribution, session cost, phases"
```

---

### Task 4: Pricing module

**Files:**
- Create: `scripts/token_profiler/pricing.py`
- Test: `tests/test_token_profiler_pricing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_pricing.py`:

```python
"""Tests for token profiler pricing module."""

from scripts.token_profiler.pricing import (
    get_pricing,
    apply_pricing_to_usage,
    PRICING,
)
from scripts.token_profiler.models import Usage, DollarCost


def test_exact_model_match():
    """Exact model name matches pricing table."""
    p = get_pricing("claude-opus-4-6")
    assert p is not None
    assert p["input"] > 0


def test_prefix_match():
    """Model with version suffix matches via longest-prefix."""
    p = get_pricing("claude-opus-4-6-20251101")
    assert p is not None
    assert p == get_pricing("claude-opus-4-6")


def test_unknown_model_returns_zero():
    """Unknown model falls back to zero pricing."""
    p = get_pricing("totally-unknown-model")
    assert p is not None
    assert p["input"] == 0
    assert p["output"] == 0


def test_apply_pricing_to_usage():
    """Dollar costs computed correctly from usage and pricing."""
    usage = Usage(
        input_tokens=1000,
        cache_creation_input_tokens=10000,
        cache_read_input_tokens=50000,
        output_tokens=500,
    )
    cost = apply_pricing_to_usage(usage, "claude-opus-4-6")
    assert isinstance(cost, DollarCost)
    assert cost.input_cost > 0
    assert cost.cache_creation_cost > cost.input_cost  # 10x more tokens at 1.25x rate
    assert cost.output_cost > 0
    assert cost.total_cost == (
        cost.input_cost + cost.cache_creation_cost + cost.cache_read_cost + cost.output_cost
    )


def test_opus_pricing_rates():
    """Verify Opus pricing matches spec: input $15, cache_create $18.75, cache_read $1.50, output $75 per MTok."""
    p = get_pricing("claude-opus-4-6")
    assert abs(p["input"] - 15.00 / 1_000_000) < 1e-10
    assert abs(p["cache_creation"] - 18.75 / 1_000_000) < 1e-10
    assert abs(p["cache_read"] - 1.50 / 1_000_000) < 1e-10
    assert abs(p["output"] - 75.00 / 1_000_000) < 1e-10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_pricing.py -v`
Expected: FAIL

- [ ] **Step 3: Write `pricing.py`**

```python
"""Stage 6: Model pricing tables and dollar cost computation.

Pricing lookup uses longest-prefix matching so version-suffixed model names
(e.g., claude-opus-4-6-20251101) match their base model key.
"""

from __future__ import annotations

import sys
from scripts.token_profiler.models import DollarCost, Usage

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input":          15.00 / 1_000_000,
        "cache_creation": 18.75 / 1_000_000,
        "cache_read":      1.50 / 1_000_000,
        "output":         75.00 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input":           3.00 / 1_000_000,
        "cache_creation":  3.75 / 1_000_000,
        "cache_read":      0.30 / 1_000_000,
        "output":         15.00 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input":           0.80 / 1_000_000,
        "cache_creation":  1.00 / 1_000_000,
        "cache_read":      0.08 / 1_000_000,
        "output":          4.00 / 1_000_000,
    },
    "unknown": {
        "input":          0.0,
        "cache_creation": 0.0,
        "cache_read":     0.0,
        "output":         0.0,
    },
}


def get_pricing(model: str) -> dict[str, float]:
    """Look up pricing for a model using longest-prefix matching.

    Returns the pricing dict for the longest key that is a prefix of `model`.
    Falls back to "unknown" (zero pricing) with a warning to stderr.
    """
    if model in PRICING:
        return PRICING[model]

    # Longest-prefix match
    best_key = ""
    for key in PRICING:
        if key == "unknown":
            continue
        if model.startswith(key) and len(key) > len(best_key):
            best_key = key

    if best_key:
        return PRICING[best_key]

    print(f"Warning: no pricing found for model '{model}', using zero pricing", file=sys.stderr)
    return PRICING["unknown"]


def apply_pricing_to_usage(usage: Usage, model: str) -> DollarCost:
    """Compute dollar costs for a single turn's usage."""
    p = get_pricing(model)
    return DollarCost(
        input_cost=usage.input_tokens * p["input"],
        cache_creation_cost=usage.cache_creation_input_tokens * p["cache_creation"],
        cache_read_cost=usage.cache_read_input_tokens * p["cache_read"],
        output_cost=usage.output_tokens * p["output"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_pricing.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/token_profiler/pricing.py tests/test_token_profiler_pricing.py
git commit -m "feat(token-profiler): add pricing module with prefix-matching model lookup"
```

---

### Task 5: Markdown report generation

**Files:**
- Create: `scripts/token_profiler/report.py`
- Test: `tests/test_token_profiler_report.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_report.py`:

```python
"""Tests for token profiler markdown report generation."""

from scripts.token_profiler.report import generate_markdown
from scripts.token_profiler.models import (
    RunProfile, SessionProfile, ProfiledTurn, RawTurn, Usage,
    ToolAttribution, PhaseProfile, BucketBreakdown, DollarCost,
    SessionSummary, CrossSessionSummary, CompactionEvent,
)
from datetime import datetime, timezone


def _minimal_run_profile() -> RunProfile:
    """Create a minimal but complete RunProfile for testing."""
    turn = ProfiledTurn(
        raw=RawTurn(
            request_id="req_1", index=0,
            timestamp=datetime(2026, 3, 24, 5, 20, tzinfo=timezone.utc),
            usage=Usage(3, 31704, 0, 378),
            stop_reason="end_turn",
            content_blocks=[], tool_results=[],
            assistant_text="hello",
        ),
        context_window=31707, delta=31707, segment_id=0,
        remaining_calls_in_segment=1, session_cost_tokens=31707,
        tool_attributions=[
            ToolAttribution("_assistant_overhead", "overhead", 0, 0, 1.0, 31707, 31707),
        ],
        phase="unknown",
    )
    session = SessionProfile(
        session_id="abc", session_type="main", model="claude-opus-4-6",
        turns=[turn],
        phases={"unknown": PhaseProfile(
            phase="unknown", turn_count=1, turn_indices=[0],
            delta_sum=31707, session_cost_sum=31707, top_tools=[],
            bucket_breakdown=BucketBreakdown(3, 31704, 0, 378),
            dollar_cost=DollarCost(0.0, 0.0, 0.0, 0.0),
        )},
        compaction_events=[],
        summary=SessionSummary(1, 31707, 378, 31707, 0.0, [0], []),
    )
    return RunProfile(
        run_id="test-run", sessions=[session],
        cross_session_summary=CrossSessionSummary(32085, 31707, 0.0, {"abc": 100.0}),
    )


def test_generate_markdown_has_required_sections():
    """Generated markdown contains all required sections."""
    rp = _minimal_run_profile()
    md = generate_markdown(rp)
    assert "# Token Profile:" in md
    assert "## Summary" in md
    assert "## Heat Map" in md
    assert "## Phase Breakdown" in md
    assert "## Cost Buckets" in md
    assert "## Methodology" in md


def test_generate_markdown_summary_numbers():
    """Summary section contains the correct totals."""
    rp = _minimal_run_profile()
    md = generate_markdown(rp)
    assert "1" in md  # 1 API call
    assert "31,707" in md or "31707" in md  # session cost


def test_generate_markdown_compaction_section():
    """Compaction events section present even when empty."""
    rp = _minimal_run_profile()
    md = generate_markdown(rp)
    assert "Compaction" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_report.py -v`
Expected: FAIL

- [ ] **Step 3: Write `report.py`**

This is a straightforward markdown template renderer. The implementation should iterate over the `RunProfile` and format each section. The code is too long to inline completely here but the structure is:

```python
"""Markdown report generation from a RunProfile."""

from __future__ import annotations

from scripts.token_profiler.models import RunProfile, SessionProfile, ProfiledTurn


def generate_markdown(profile: RunProfile) -> str:
    """Generate a markdown report from a RunProfile."""
    lines: list[str] = []
    _header(lines, profile)
    _summary(lines, profile)
    _hottest_turns(lines, profile)
    _hottest_tools(lines, profile)
    _phase_breakdown(lines, profile)
    _cost_buckets(lines, profile)
    _dollar_costs(lines, profile)
    _compaction_events(lines, profile)
    _methodology(lines)
    return "\n".join(lines)


def _header(lines: list[str], profile: RunProfile) -> None:
    lines.append(f"# Token Profile: {profile.run_id}")
    lines.append("")


def _summary(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Summary")
    lines.append("")
    cs = profile.cross_session_summary
    if cs:
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Sessions | {len(profile.sessions)} |")
        lines.append(f"| Total API calls | {sum(s.summary.total_api_calls for s in profile.sessions if s.summary)} |")
        lines.append(f"| Total billed tokens | {cs.total_billed_tokens:,} |")
        lines.append(f"| Total session cost (heat) | {cs.total_session_cost_tokens:,} |")
        lines.append(f"| Total dollars | ${cs.total_dollars:.4f} |")
    lines.append("")

    if len(profile.sessions) > 1:
        lines.append("### Per-Session Breakdown")
        lines.append("")
        lines.append("| Session | Type | API Calls | Session Cost | % |")
        lines.append("|---------|------|-----------|-------------|---|")
        for s in profile.sessions:
            name = s.subagent_name or s.session_id[:12]
            calls = s.summary.total_api_calls if s.summary else 0
            cost = s.summary.total_session_cost if s.summary else 0
            pct = cs.session_breakdown.get(s.session_id, 0) if cs else 0
            lines.append(f"| {name} | {s.session_type} | {calls} | {cost:,} | {pct:.1f}% |")
        lines.append("")


def _hottest_turns(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Heat Map -- Top 20 Hottest Turns")
    lines.append("")
    all_turns: list[tuple[str, ProfiledTurn]] = []
    for s in profile.sessions:
        name = s.subagent_name or s.session_id[:8]
        for pt in s.turns:
            all_turns.append((name, pt))

    all_turns.sort(key=lambda x: x[1].session_cost_tokens, reverse=True)

    for session_name, pt in all_turns[:20]:
        ts = pt.raw.timestamp.strftime("%H:%M:%S") if pt.raw.timestamp else "?"
        tools = ", ".join(
            a.tool_name for a in pt.tool_attributions if a.tool_name != "_assistant_overhead"
        ) or "(no tools)"
        lines.append(
            f"**#{pt.raw.index}** [{ts}] {pt.phase} | "
            f"+{pt.delta:,} tokens | x{pt.remaining_calls_in_segment} remaining | "
            f"**{pt.session_cost_tokens:,}** session cost"
        )
        for attr in pt.tool_attributions:
            if attr.tool_name == "_assistant_overhead" and attr.fraction_of_delta < 0.1:
                continue
            pct = attr.fraction_of_delta * 100
            lines.append(f"  - {attr.tool_name} {attr.description} -> {attr.attributed_delta:,} ({pct:.0f}%)")
        lines.append("")


def _hottest_tools(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Heat Map -- Top 20 Hottest Tools")
    lines.append("")
    tool_totals: dict[str, dict] = {}
    for s in profile.sessions:
        for pt in s.turns:
            for attr in pt.tool_attributions:
                if attr.tool_name == "_assistant_overhead":
                    continue
                if attr.tool_name not in tool_totals:
                    tool_totals[attr.tool_name] = {"calls": 0, "delta": 0, "session_cost": 0}
                tool_totals[attr.tool_name]["calls"] += 1
                tool_totals[attr.tool_name]["delta"] += attr.attributed_delta
                tool_totals[attr.tool_name]["session_cost"] += attr.attributed_session_cost

    total_cost = sum(v["session_cost"] for v in tool_totals.values()) or 1
    sorted_tools = sorted(tool_totals.items(), key=lambda x: x[1]["session_cost"], reverse=True)

    lines.append("| Tool | Calls | Tokens Added | Session Cost | % |")
    lines.append("|------|-------|-------------|-------------|---|")
    for name, data in sorted_tools[:20]:
        pct = data["session_cost"] / total_cost * 100
        lines.append(f"| {name} | {data['calls']} | {data['delta']:,} | {data['session_cost']:,} | {pct:.1f}% |")
    lines.append("")


def _phase_breakdown(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Phase Breakdown")
    lines.append("")
    for s in profile.sessions:
        if len(profile.sessions) > 1:
            name = s.subagent_name or s.session_id[:12]
            lines.append(f"### {name}")
            lines.append("")
        lines.append("| Phase | Turns | Delta Sum | Session Cost | Top Tools |")
        lines.append("|-------|-------|-----------|-------------|-----------|")
        for phase_name, pp in sorted(s.phases.items(), key=lambda x: x[1].turn_indices[0] if x[1].turn_indices else 0):
            top = ", ".join(pp.top_tools[:3]) or "-"
            lines.append(f"| {phase_name} | {pp.turn_count} | {pp.delta_sum:,} | {pp.session_cost_sum:,} | {top} |")
        lines.append("")


def _cost_buckets(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Cost Buckets")
    lines.append("")
    lines.append("| Phase | Input | Cache Create | Cache Read | Output | Total |")
    lines.append("|-------|-------|-------------|------------|--------|-------|")
    for s in profile.sessions:
        for phase_name, pp in sorted(s.phases.items(), key=lambda x: x[1].turn_indices[0] if x[1].turn_indices else 0):
            bb = pp.bucket_breakdown
            lines.append(
                f"| {phase_name} | {bb.input_tokens:,} | {bb.cache_creation_tokens:,} | "
                f"{bb.cache_read_tokens:,} | {bb.output_tokens:,} | {bb.total:,} |"
            )
    lines.append("")


def _dollar_costs(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Dollar Costs")
    lines.append("")
    lines.append("| Phase | Input | Cache Create | Cache Read | Output | Total |")
    lines.append("|-------|-------|-------------|------------|--------|-------|")
    for s in profile.sessions:
        for phase_name, pp in sorted(s.phases.items(), key=lambda x: x[1].turn_indices[0] if x[1].turn_indices else 0):
            dc = pp.dollar_cost
            lines.append(
                f"| {phase_name} | ${dc.input_cost:.4f} | ${dc.cache_creation_cost:.4f} | "
                f"${dc.cache_read_cost:.4f} | ${dc.output_cost:.4f} | ${dc.total_cost:.4f} |"
            )
    lines.append("")


def _compaction_events(lines: list[str], profile: RunProfile) -> None:
    lines.append("## Compaction Events")
    lines.append("")
    all_events = []
    for s in profile.sessions:
        for e in s.compaction_events:
            all_events.append((s.subagent_name or s.session_id[:8], e))

    if not all_events:
        lines.append("No compaction events detected.")
    else:
        lines.append("| Session | Turn | Before | After | Reduction |")
        lines.append("|---------|------|--------|-------|-----------|")
        for name, e in all_events:
            lines.append(f"| {name} | #{e.turn_index} | {e.context_before:,} | {e.context_after:,} | {e.reduction_tokens:,} |")
    lines.append("")


def _methodology(lines: list[str]) -> None:
    lines.append("## Methodology")
    lines.append("")
    lines.append("**Session cost** = `delta x remaining_calls_in_segment` (inclusive).")
    lines.append("")
    lines.append("Each API call's context window is measured as `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.")
    lines.append("The delta between consecutive calls shows how much that call added to context.")
    lines.append("The session cost weights each delta by the number of subsequent calls that will re-cache it,")
    lines.append("making early large additions much more expensive than late ones.")
    lines.append("")
    lines.append("Tool attribution distributes each turn's delta proportionally across tool results by content size.")
    lines.append("Non-measurable content (thinking, system messages, tool_references) is captured in `_assistant_overhead`.")
    lines.append("")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_report.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/token_profiler/report.py tests/test_token_profiler_report.py
git commit -m "feat(token-profiler): add markdown report generation"
```

---

### Task 6: CLI module — argument parsing and orchestration

**Files:**
- Create: `scripts/token_profiler/cli.py`
- Test: `tests/test_token_profiler_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_cli.py`:

```python
"""Tests for token profiler CLI."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.token_profiler.cli import parse_args, load_plugins, list_sessions


def test_parse_args_latest():
    args = parse_args(["--latest"])
    assert args.latest is True


def test_parse_args_output_dir():
    args = parse_args(["-o", "/tmp/profile", "--latest"])
    assert args.output == "/tmp/profile"


def test_parse_args_plugin():
    args = parse_args(["--plugin", "foo.py", "--plugin", "bar.py", "--latest"])
    assert args.plugin == ["foo.py", "bar.py"]


def test_parse_args_session_positional():
    args = parse_args(["/path/to/session.jsonl"])
    assert args.session == "/path/to/session.jsonl"


def test_parse_args_defaults():
    args = parse_args(["--latest"])
    assert args.output == "./token-profile"
    assert args.plugin == []
    assert not args.no_subagents


def test_load_plugins_empty():
    """No plugins specified returns empty list."""
    plugins = load_plugins([])
    assert plugins == []


def test_load_plugins_env_var():
    """TOKEN_PROFILER_PLUGINS env var is parsed."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("""
class MyPlugin:
    name = "test"
    def detect(self, turns): return False
    def label_phases(self, turns): return {}
    def name_subagent(self, turns): return None
    def enrich_profile(self, profile): pass
    def optimization_patterns(self): return []
""")
        f.flush()
        with patch.dict("os.environ", {"TOKEN_PROFILER_PLUGINS": f.name}):
            plugins = load_plugins([], check_env=True)
            assert len(plugins) == 1
            assert plugins[0].name == "test"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write `cli.py`**

The CLI module handles argument parsing, plugin loading, session discovery, orchestration of the pipeline, and output writing. Implementation should use `argparse`, `importlib.util` for plugin loading, and call through to `extract.py`, `analyze.py`, `pricing.py`, `report.py`, and `viewer.py`. The `main()` function is the entry point.

Key functions:
- `parse_args(argv)` — argument parsing
- `load_plugins(paths, check_env)` — plugin loading via importlib
- `list_sessions(project_dir)` — reuse logic from session-to-cast.py
- `resolve_session(args)` — find the session JSONL from args
- `main()` — orchestrate the full pipeline

The complete implementation follows the patterns established in `session-to-cast.py` for session discovery and the spec for pipeline orchestration. Write this as a ~200 line module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/token_profiler/cli.py tests/test_token_profiler_cli.py
git commit -m "feat(token-profiler): add CLI with plugin loading and session discovery"
```

---

### Task 7: HTML viewer template — cyberpunk web viewer

**Files:**
- Create: `scripts/token_profiler/viewer_template.html`
- Create: `scripts/token_profiler/viewer.py`

This is the largest single file. It's a self-contained HTML document with embedded CSS and JS that reads `PROFILE_DATA` from a `<script>` tag injected by `viewer.py`.

- [ ] **Step 1: Write `viewer.py` (template injection)**

```python
"""Generate self-contained HTML viewer from template + RunProfile data."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.token_profiler.models import RunProfile


TEMPLATE_PATH = Path(__file__).parent / "viewer_template.html"
DATA_PLACEHOLDER = "/* __PROFILE_DATA_PLACEHOLDER__ */"


def generate_html(profile: RunProfile) -> str:
    """Inject RunProfile JSON into the HTML template."""
    template = TEMPLATE_PATH.read_text()
    profile_json = _serialize_profile(profile)
    return template.replace(
        DATA_PLACEHOLDER,
        f"const PROFILE_DATA = {profile_json};",
    )


def _serialize_profile(profile: RunProfile) -> str:
    """Serialize RunProfile to JSON, converting dataclasses and datetimes."""
    from dataclasses import asdict

    def _convert(obj):
        from datetime import datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    data = asdict(profile)
    return json.dumps(data, default=_convert, indent=None)
```

- [ ] **Step 2: Write `viewer_template.html`**

This is a large file (~2000 lines). The structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Profiler</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        /* === CYBERPUNK BASE === */
        /* Background, scan-lines, typography, color variables */
        /* === LAYOUT === */
        /* Nav tabs, view containers, responsive grid */
        /* === HEAT STRIP === */
        /* Horizontal bar, per-slice coloring, hover tooltip */
        /* === TURN TABLE === */
        /* Sortable headers, expandable rows, heat-colored cells */
        /* === PHASE SUNBURST === */
        /* SVG concentric rings, click-to-zoom */
        /* === SANKEY === */
        /* SVG flow diagram */
        /* === SESSION COMPARISON === */
        /* Side-by-side cards with mini heat strips */
        /* === ANIMATIONS === */
        /* Glitch header, pulse, fade-in */
    </style>
</head>
<body>
    <header>
        <h1><span class="glitch" data-text="TOKEN PROFILER">TOKEN PROFILER</span></h1>
        <div id="summary-bar"></div>
    </header>
    <nav id="view-tabs">
        <button class="tab active" data-view="heatstrip">Timeline</button>
        <button class="tab" data-view="table">Turns</button>
        <button class="tab" data-view="sunburst">Phases</button>
        <button class="tab" data-view="sankey">Flow</button>
        <button class="tab" data-view="sessions">Sessions</button>
    </nav>
    <main>
        <section id="view-heatstrip" class="view active"></section>
        <section id="view-table" class="view"></section>
        <section id="view-sunburst" class="view"></section>
        <section id="view-sankey" class="view"></section>
        <section id="view-sessions" class="view"></section>
    </main>
    <script>
        /* __PROFILE_DATA_PLACEHOLDER__ */
    </script>
    <script>
        /* === APP CODE === */
        /* Tab switching */
        /* Heat strip renderer */
        /* Turn table renderer with sort + expand */
        /* Sunburst SVG renderer */
        /* Sankey SVG renderer */
        /* Session comparison renderer */
        /* Color utilities (heat scale mapping) */
        /* Number formatting */
        /* Init */
    </script>
</body>
</html>
```

**Implementation guidance for the viewer:** The cyberpunk aesthetic spec is in the design doc. Key details:
- Background: `#0a0a0f` with CSS scan-line overlay (repeating-linear-gradient)
- Neon palette: magenta `#ff00ff`, cyan `#00ffff`, green `#39ff14`, amber `#ffb700`
- Heat scale function: map `session_cost / max_session_cost` ratio to blue->magenta->white
- JetBrains Mono from Google Fonts CDN with `monospace` fallback
- Glow: `text-shadow: 0 0 10px <color>; box-shadow: 0 0 5px <color>;`
- Hard edges: `border-radius: 0`
- Glitch animation on header: CSS keyframes offsetting `clip-path` with color channel split
- All charts built with vanilla JS + positioned divs (heat strip) or inline SVG (sunburst, sankey)
- No framework dependencies

This file should be written in full as a complete, working HTML page. The implementer should build each view incrementally, testing in a browser with a sample `PROFILE_DATA` object.

- [ ] **Step 3: Smoke test — generate HTML with minimal profile**

```python
# Quick manual test
from scripts.token_profiler.viewer import generate_html
from tests.test_token_profiler_report import _minimal_run_profile
html = generate_html(_minimal_run_profile())
Path("/tmp/test-profile.html").write_text(html)
# Open in browser, verify it loads
```

- [ ] **Step 4: Commit**

```bash
git add scripts/token_profiler/viewer.py scripts/token_profiler/viewer_template.html
git commit -m "feat(token-profiler): add cyberpunk HTML viewer with 5 views"
```

---

### Task 8: Holtz profiler plugin

**Files:**
- Create: `skills/holtz/scripts/profiler_plugin.py`
- Test: `tests/test_token_profiler_plugin.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_profiler_plugin.py`:

```python
"""Tests for the Holtz profiler plugin."""

from datetime import datetime, timezone

from scripts.token_profiler.models import RawTurn, Usage

# Import from the actual plugin location
import importlib.util
from pathlib import Path

PLUGIN_PATH = Path("skills/holtz/scripts/profiler_plugin.py")


def _load_plugin():
    spec = importlib.util.spec_from_file_location("holtz_plugin", PLUGIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and hasattr(obj, "name") and hasattr(obj, "detect"):
            return obj()
    raise RuntimeError("No plugin class found")


def _make_turn(index: int, text: str = "") -> RawTurn:
    return RawTurn(
        request_id=f"req_{index}", index=index,
        timestamp=datetime(2026, 3, 24, 5, 20 + index, tzinfo=timezone.utc),
        usage=Usage(3, 1000, 0, 100),
        stop_reason="end_turn", content_blocks=[], tool_results=[],
        assistant_text=text,
    )


def test_detect_holtz_session():
    plugin = _load_plugin()
    turns = [_make_turn(0, "Running Holtz full audit on this codebase.")]
    assert plugin.detect(turns) is True


def test_detect_non_holtz_session():
    plugin = _load_plugin()
    turns = [_make_turn(0, "Hello, I need help with a bug.")]
    assert plugin.detect(turns) is False


def test_label_phases_recon():
    plugin = _load_plugin()
    turns = [
        _make_turn(0, "Starting Phase 0 recon."),
        _make_turn(1, "Good, baseline captured."),
        _make_turn(2, "Phase 0 complete. Starting Phase 1."),
        _make_turn(3, "Verifying doc claims."),
    ]
    labels = plugin.label_phases(turns)
    assert labels[0] == "recon"
    assert labels[2] == "recon"  # "Phase 0 complete" is still recon
    assert labels[3] == "phase-1"


def test_name_subagent_justine():
    plugin = _load_plugin()
    turns = [_make_turn(0, "Running Justine [initialization] on holtz codebase.")]
    assert plugin.name_subagent(turns) == "justine"


def test_name_subagent_test_audit():
    plugin = _load_plugin()
    turns = [_make_turn(0, "I'll read all four test files in parallel to start the audit.")]
    name = plugin.name_subagent(turns)
    assert name is not None  # should infer something like "test-audit"


def test_name_subagent_unknown():
    plugin = _load_plugin()
    turns = [_make_turn(0, "Some generic task.")]
    name = plugin.name_subagent(turns)
    assert name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_token_profiler_plugin.py -v`
Expected: FAIL

- [ ] **Step 3: Write `skills/holtz/scripts/profiler_plugin.py`**

```python
"""Holtz profiler plugin — domain-specific phase detection, subagent naming,
and profile enrichment for Holtz audit runs.

Loaded at runtime via:
  python -m scripts.token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.token_profiler.models import RawTurn, SessionProfile


class HoltzProfilerPlugin:
    name = "holtz"

    # Phase transition patterns — order matters, later patterns override earlier
    _PHASE_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("recon", re.compile(r"Phase 0|recon|phase-0-recon", re.IGNORECASE)),
        ("phase-1", re.compile(r"Phase 1|Doc.*(Audit|claim)", re.IGNORECASE)),
        ("phase-2", re.compile(r"Phase 2|Test.*(Quality|Audit)", re.IGNORECASE)),
        ("phase-3", re.compile(r"Phase 3|Adversarial.*(Code|Audit)", re.IGNORECASE)),
        ("merge", re.compile(r"(Adversarial )?[Mm]erge|Justine.*findings|classify.*findings", re.IGNORECASE)),
        ("fix-loop", re.compile(r"Phase 4|TDD|fix loop|failing test", re.IGNORECASE)),
        ("convergence", re.compile(r"converg|SUMMARY\.md|final commit", re.IGNORECASE)),
    ]

    _SUBAGENT_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("justine", re.compile(r"Justine", re.IGNORECASE)),
        ("test-audit", re.compile(r"test files.*audit|audit.*test files|read all.*test", re.IGNORECASE)),
        ("source-audit", re.compile(r"source modules|subtle bugs|analyze.*modules", re.IGNORECASE)),
    ]

    def detect(self, turns: list[RawTurn]) -> bool:
        """Detect Holtz session by checking first few turns for Holtz keywords."""
        for turn in turns[:10]:
            text = turn.assistant_text.lower()
            if "holtz" in text or "phase 0" in text or "full audit" in text:
                return True
        return False

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Assign phases via content heuristics.

        Scans assistant_text for phase transition markers. Once a phase is
        detected, all subsequent turns inherit it until a new phase is found.
        """
        labels: dict[int, str] = {}
        current_phase = "recon"  # Holtz sessions start with recon

        for turn in turns:
            text = turn.assistant_text
            # Check for phase transitions (later patterns override)
            for phase_name, pattern in self._PHASE_PATTERNS:
                if pattern.search(text):
                    current_phase = phase_name
            labels[turn.index] = current_phase

        return labels

    def name_subagent(self, turns: list[RawTurn]) -> str | None:
        """Infer subagent name from first text output."""
        if not turns:
            return None
        first_text = turns[0].assistant_text
        for name, pattern in self._SUBAGENT_PATTERNS:
            if pattern.search(first_text):
                return name
        return None

    def enrich_profile(self, profile: SessionProfile) -> None:
        """Add Holtz-specific annotations (future: trace file integration)."""
        pass

    def optimization_patterns(self) -> list[dict]:
        return [
            {
                "name": "Heavy Early Read",
                "symptom": "Large file read in first 20% of turns, bright bar on heat strip",
                "fix": "Defer the read, extract only needed sections, or read in a subagent",
            },
            {
                "name": "Recon Bloat",
                "symptom": "Phase 0 dominates the heat map",
                "fix": "Which recon reads are actually used in later phases? Profile the assumes edges.",
            },
            {
                "name": "Chatty Tool Loop",
                "symptom": "Many small deltas that add up",
                "fix": "Batch tool calls (parallel reads instead of sequential)",
            },
            {
                "name": "Subagent Over-delegation",
                "symptom": "Subagent session cost exceeds main for the same work",
                "fix": "Pass narrower context to the subagent",
            },
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_token_profiler_plugin.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/scripts/profiler_plugin.py tests/test_token_profiler_plugin.py
git commit -m "feat(holtz): add profiler plugin for phase detection and subagent naming"
```

---

### Task 9: Integration test — Run 14 validation

**Files:**
- Modify: `tests/test_token_profiler_cli.py` (add integration test)

This task validates the full pipeline against the real Run 14 session data.

- [ ] **Step 1: Write integration test**

Add to `tests/test_token_profiler_cli.py`:

```python
import os
from pathlib import Path


def test_full_pipeline_run14():
    """Integration test: profile the Run 14 session end-to-end.

    Requires the actual session JSONL at the expected location.
    Skip if not available (CI won't have it).
    """
    session_path = Path(os.path.expanduser(
        "~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/"
        "8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl"
    ))
    if not session_path.exists():
        import pytest
        pytest.skip("Run 14 session JSONL not available")

    from scripts.token_profiler.extract import extract_session, discover_subagents
    from scripts.token_profiler.analyze import build_session_profile
    from scripts.token_profiler.report import generate_markdown
    from scripts.token_profiler.pricing import apply_pricing_to_usage

    # Extract main session
    turns = extract_session(session_path)
    assert len(turns) >= 250  # run 14 had 276 API calls

    # Verify first turn context window matches walkthrough
    assert abs(turns[0].context_window - 31707) < 100

    # Build profile
    profile = build_session_profile("run-14-main", turns)
    assert profile.summary is not None
    assert profile.summary.total_api_calls >= 250

    # Verify no compaction in run 14 main session
    assert len(profile.compaction_events) == 0

    # Hottest turns should be non-empty
    assert len(profile.summary.hottest_turns) > 0

    # Discover subagents
    subagent_paths = discover_subagents(session_path)
    assert len(subagent_paths) >= 3  # justine + 2 audit subagents + 2 minor

    # Extract Justine
    justine_path = [p for p in subagent_paths if "a919e2838d64ac37a" in p.name]
    if justine_path:
        justine_turns = extract_session(justine_path[0])
        assert len(justine_turns) >= 100  # 153 turns

    # Generate markdown
    from scripts.token_profiler.models import RunProfile, CrossSessionSummary
    run = RunProfile(run_id="run-14", sessions=[profile])
    md = generate_markdown(run)
    assert "# Token Profile:" in md
    assert len(md) > 500
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_token_profiler_cli.py::test_full_pipeline_run14 -v`
Expected: PASS (or skip if JSONL not available)

- [ ] **Step 3: Run the full profiler on Run 14**

```bash
python -m scripts.token_profiler ~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl \
  --plugin skills/holtz/scripts/profiler_plugin.py \
  --run-id run-14 \
  -o docs/runs/profiles/run-14/ \
  --open
```

Expected: `profile.json`, `profile.md`, and `profile.html` generated. Browser opens with cyberpunk viewer showing Run 14 data.

- [ ] **Step 4: Verify key numbers against walkthrough**

Check `profile.md` or `profile.json`:
- Main session: ~276 API calls
- Context at convergence: ~207K
- Justine: ~153 turns
- No compaction events
- Phase 0 (recon) should be the costliest phase (most turns, earliest in session)

- [ ] **Step 5: Commit validation output**

```bash
git add docs/runs/profiles/run-14/
git commit -m "docs: add Run 14 token profile (validation output)"
```

---

### Task 10: Playbook document

**Files:**
- Create: `docs/token-profiling-playbook.md`

- [ ] **Step 1: Write the playbook**

The playbook documents the repeatable process as specified in the design doc. It should be a standalone document that someone can follow without reading the spec. Key sections:

1. **Quick Start** — the one-liner to profile latest session
2. **What This Measures** — explanation of session-spanning cost with the 5K-at-turn-20 example
3. **Reading the Output** — how to interpret each viewer view (heat strip, turn table, sunburst, sankey, sessions)
4. **Optimization Patterns** — Heavy Early Read, Chatty Tool Loop, Subagent Over-delegation, Recon Bloat with symptoms and fixes
5. **Cross-Project Usage** — using `--project` to analyze other codebases
6. **Using Plugins** — `--plugin` flag, env var, writing your own plugin
7. **Extending** — adding pricing, output formats, phase heuristics

- [ ] **Step 2: Commit**

```bash
git add docs/token-profiling-playbook.md
git commit -m "docs: add token profiling playbook"
```

---

### Task 11: Full test suite pass + lint

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: all PASS (existing tests still pass, new tests pass)

- [ ] **Step 2: Run lint**

Run: `ruff check scripts/token_profiler/ tests/test_token_profiler_*.py skills/holtz/scripts/profiler_plugin.py`
Expected: clean

- [ ] **Step 3: Run mypy**

Run: `mypy scripts/token_profiler/`
Expected: clean (or only expected missing-import warnings for test-only imports)

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A && git commit -m "chore: lint and type-check fixes for token profiler"
```

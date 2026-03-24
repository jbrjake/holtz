"""Data models for the token profiler.

Every struct used across extraction, analysis, pricing, and reporting
lives here so that module boundaries stay clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Low-level API primitives
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    """Token usage counters from a single API response."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Usage:
        return cls(
            input_tokens=data.get("input_tokens", 0),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=data.get("cache_read_input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
        )


@dataclass
class ContentBlock:
    """A single block from the assistant's response (text, thinking, or tool_use)."""

    type: str  # "text" | "thinking" | "tool_use"
    size: int

    # Optional — depends on type
    text_content: str | None = None
    thinking_content: str | None = None
    tool_name: str | None = None
    tool_input_summary: str | None = None
    tool_use_id: str | None = None  # Errata E13: for matching results to blocks


@dataclass
class ToolResult:
    """A tool result message from the user turn that follows a tool_use."""

    tool_use_id: str
    content_type: str  # "text" | "tool_references" | "error" | "empty"
    content_size_chars: int


# ---------------------------------------------------------------------------
# Per-turn models
# ---------------------------------------------------------------------------


@dataclass
class RawTurn:
    """One API request→response round-trip, extracted from JSONL."""

    request_id: str
    index: int
    timestamp: str | None
    usage: Usage
    stop_reason: str
    content_blocks: list[ContentBlock]
    tool_results: list[ToolResult]
    assistant_text: str
    model: str = "unknown"  # Errata E12: model field, default "unknown"

    @property
    def context_window(self) -> int:
        """Context window = input + cache_creation + cache_read (excludes output)."""
        return self.usage.input_tokens + self.usage.cache_creation_input_tokens + self.usage.cache_read_input_tokens


@dataclass
class ToolAttribution:
    """How much of the context-window delta a single tool call is responsible for."""

    tool_name: str
    description: str
    result_size_chars: int
    result_size_tokens_est: int  # heuristic: chars // 4
    fraction_of_delta: float
    attributed_delta: int
    attributed_session_cost: int


@dataclass
class ProfiledTurn:
    """A RawTurn enriched with analysis-derived fields."""

    raw: RawTurn
    context_window: int
    delta: int
    segment_id: int
    remaining_calls_in_segment: int
    session_cost_tokens: int
    tool_attributions: list[ToolAttribution]
    phase: str


# ---------------------------------------------------------------------------
# Compaction / segment boundary
# ---------------------------------------------------------------------------


@dataclass
class CompactionEvent:
    """Records a context-window compaction (summarisation) between segments."""

    segment_id: int
    turn_index: int
    context_before: int
    context_after: int
    reduction_tokens: int


# ---------------------------------------------------------------------------
# Aggregation models
# ---------------------------------------------------------------------------


@dataclass
class BucketBreakdown:
    """Token totals split by billing bucket."""

    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens + self.output_tokens


@dataclass
class DollarCost:
    """Dollar costs split by billing bucket."""

    input_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    output_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.cache_creation_cost + self.cache_read_cost + self.output_cost


@dataclass
class PhaseProfile:
    """Aggregate statistics for a labelled phase within a session."""

    phase: str
    turn_count: int
    turn_indices: list[int]
    delta_sum: int
    session_cost_sum: int
    top_tools: list[tuple[str, int]]
    bucket_breakdown: BucketBreakdown
    dollar_cost: DollarCost


# ---------------------------------------------------------------------------
# Session-level models
# ---------------------------------------------------------------------------


@dataclass
class SessionSummary:
    """Roll-up statistics for one session."""

    total_api_calls: int
    peak_context_window: int  # Errata E6: peak, NOT sum
    total_output_tokens: int
    total_session_cost: int
    total_dollars: float
    hottest_turns: list[int]
    hottest_tools: list[tuple[str, int]]


@dataclass
class SessionProfile:
    """Full profile for a single Claude Code session."""

    session_id: str
    session_type: str  # "main" | "subagent"
    model: str
    turns: list[ProfiledTurn]
    phases: list[PhaseProfile]
    compaction_events: list[CompactionEvent]

    # Optional — populated for subagent sessions
    subagent_name: str | None = None
    dispatched_from_session: str | None = None
    dispatched_at_turn: int | None = None
    returned_at_turn: int | None = None

    # Populated after analysis
    summary: SessionSummary | None = None


# ---------------------------------------------------------------------------
# Cross-session / run-level models
# ---------------------------------------------------------------------------


@dataclass
class CrossSessionSummary:
    """Aggregate statistics across all sessions in a run."""

    total_billed_tokens: int
    total_session_cost_tokens: int
    total_dollars: float
    session_breakdown: list[dict[str, Any]]


@dataclass
class RunProfile:
    """Top-level container for an entire Holtz run (main + subagent sessions)."""

    run_id: str
    sessions: list[SessionProfile]
    cross_session_summary: CrossSessionSummary | None = None

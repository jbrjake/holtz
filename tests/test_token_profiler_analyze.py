"""Tests for token_profiler analysis pipeline (stages 2-5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from token_profiler.analyze import (
    apply_phase_labels,
    build_run_profile,
    build_session_profile,
    compute_deltas,
    compute_session_costs,
    compute_tool_attributions,
)
from token_profiler.models import (
    ContentBlock,
    RawTurn,
    ToolResult,
    Usage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_turn(
    index=0,
    input_tokens=1000,
    cache_creation=0,
    cache_read=0,
    output_tokens=200,
    content_blocks=None,
    tool_results=None,
    model="claude-sonnet-4-20250514",
    timestamp=None,
    request_id=None,
):
    return RawTurn(
        request_id=request_id or f"req_{index:03d}",
        index=index,
        timestamp=timestamp,
        usage=Usage(
            input_tokens=input_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            output_tokens=output_tokens,
        ),
        stop_reason="end_turn",
        content_blocks=content_blocks or [],
        tool_results=tool_results or [],
        assistant_text="",
        model=model,
    )


# ---------------------------------------------------------------------------
# Stage 2: compute_deltas
# ---------------------------------------------------------------------------


class TestComputeDeltas:
    def test_monotonic_growth_single_segment(self):
        """Positive deltas produce a single segment with no compaction events."""
        turns = [
            _make_raw_turn(index=0, input_tokens=1000),
            _make_raw_turn(index=1, input_tokens=2000),
            _make_raw_turn(index=2, input_tokens=3000),
        ]
        delta_turns, events = compute_deltas(turns)

        assert len(delta_turns) == 3
        assert len(events) == 0

        # First turn: delta = context_window
        assert delta_turns[0].context_window == 1000
        assert delta_turns[0].delta == 1000
        assert delta_turns[0].segment_id == 0

        # Subsequent turns: delta = current - previous
        assert delta_turns[1].context_window == 2000
        assert delta_turns[1].delta == 1000
        assert delta_turns[1].segment_id == 0

        assert delta_turns[2].context_window == 3000
        assert delta_turns[2].delta == 1000
        assert delta_turns[2].segment_id == 0

    def test_compaction_creates_new_segment(self):
        """Negative delta triggers a compaction event and new segment."""
        turns = [
            _make_raw_turn(index=0, input_tokens=5000),
            _make_raw_turn(index=1, input_tokens=8000),
            _make_raw_turn(index=2, input_tokens=3000),  # compaction: 8000 -> 3000
            _make_raw_turn(index=3, input_tokens=5000),
        ]
        delta_turns, events = compute_deltas(turns)

        assert len(delta_turns) == 4
        assert len(events) == 1

        # Before compaction: segment 0
        assert delta_turns[0].segment_id == 0
        assert delta_turns[1].segment_id == 0

        # After compaction: segment 1
        assert delta_turns[2].segment_id == 1
        assert delta_turns[2].delta == -5000  # 3000 - 8000
        assert delta_turns[3].segment_id == 1

        # CompactionEvent
        evt = events[0]
        assert evt.segment_id == 1
        assert evt.turn_index == 2
        assert evt.context_before == 8000
        assert evt.context_after == 3000
        assert evt.reduction_tokens == 5000

    def test_multiple_compactions(self):
        """Multiple compactions produce multiple segments."""
        turns = [
            _make_raw_turn(index=0, input_tokens=5000),
            _make_raw_turn(index=1, input_tokens=2000),  # compaction
            _make_raw_turn(index=2, input_tokens=6000),
            _make_raw_turn(index=3, input_tokens=1000),  # compaction
        ]
        delta_turns, events = compute_deltas(turns)

        assert len(events) == 2
        assert delta_turns[0].segment_id == 0
        assert delta_turns[1].segment_id == 1
        assert delta_turns[2].segment_id == 1
        assert delta_turns[3].segment_id == 2

    def test_empty_turns(self):
        """Empty list produces empty results."""
        delta_turns, events = compute_deltas([])
        assert delta_turns == []
        assert events == []

    def test_single_turn(self):
        """Single turn: delta = context_window, segment 0."""
        turns = [_make_raw_turn(index=0, input_tokens=5000)]
        delta_turns, events = compute_deltas(turns)

        assert len(delta_turns) == 1
        assert delta_turns[0].delta == 5000
        assert delta_turns[0].segment_id == 0
        assert events == []

    def test_always_returns_tuple(self):
        """Errata E10: always returns (turns, events) tuple."""
        result = compute_deltas([])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_delta_turn_has_raw_reference(self):
        """DeltaTurn should reference the original RawTurn."""
        raw = _make_raw_turn(index=0, input_tokens=1000)
        delta_turns, _ = compute_deltas([raw])
        assert delta_turns[0].raw is raw

    def test_context_window_includes_cache(self):
        """context_window = input + cache_creation + cache_read."""
        turns = [
            _make_raw_turn(index=0, input_tokens=1000, cache_creation=200, cache_read=300),
        ]
        delta_turns, _ = compute_deltas(turns)
        assert delta_turns[0].context_window == 1500  # 1000 + 200 + 300


# ---------------------------------------------------------------------------
# Stage 4: compute_session_costs
# ---------------------------------------------------------------------------


class TestComputeSessionCosts:
    def test_single_turn_session(self):
        """Single turn: remaining=1, session_cost=delta."""
        turns = [_make_raw_turn(index=0, input_tokens=5000)]
        delta_turns, _ = compute_deltas(turns)
        result = compute_session_costs(delta_turns)

        assert result[0].remaining == 1
        assert result[0].session_cost == 5000  # delta * remaining = 5000 * 1

    def test_inclusive_remaining_last_turn(self):
        """Last turn gets remaining=1, NOT 0. Remaining is inclusive."""
        turns = [
            _make_raw_turn(index=0, input_tokens=1000),
            _make_raw_turn(index=1, input_tokens=2000),
            _make_raw_turn(index=2, input_tokens=3000),
        ]
        delta_turns, _ = compute_deltas(turns)
        result = compute_session_costs(delta_turns)

        # 3 turns in single segment, remaining = [3, 2, 1]
        assert result[0].remaining == 3
        assert result[1].remaining == 2
        assert result[2].remaining == 1

        # session_cost = delta * remaining
        assert result[0].session_cost == 1000 * 3
        assert result[1].session_cost == 1000 * 2
        assert result[2].session_cost == 1000 * 1

    def test_cross_compaction_segments_independent(self):
        """Remaining resets at compaction boundary."""
        turns = [
            _make_raw_turn(index=0, input_tokens=5000),
            _make_raw_turn(index=1, input_tokens=8000),
            # compaction here
            _make_raw_turn(index=2, input_tokens=3000),
            _make_raw_turn(index=3, input_tokens=5000),
            _make_raw_turn(index=4, input_tokens=7000),
        ]
        delta_turns, _ = compute_deltas(turns)
        result = compute_session_costs(delta_turns)

        # Segment 0: turns 0, 1 — remaining [2, 1]
        assert result[0].remaining == 2
        assert result[1].remaining == 1

        # Segment 1: turns 2, 3, 4 — remaining [3, 2, 1]
        assert result[2].remaining == 3
        assert result[3].remaining == 2
        assert result[4].remaining == 1

    def test_session_cost_calculation(self):
        """Session cost = delta * remaining for each turn."""
        turns = [
            _make_raw_turn(index=0, input_tokens=1000),
            _make_raw_turn(index=1, input_tokens=3000),  # delta=2000
            _make_raw_turn(index=2, input_tokens=4000),  # delta=1000
        ]
        delta_turns, _ = compute_deltas(turns)
        result = compute_session_costs(delta_turns)

        assert result[0].session_cost == 1000 * 3  # delta=1000, remaining=3
        assert result[1].session_cost == 2000 * 2  # delta=2000, remaining=2
        assert result[2].session_cost == 1000 * 1  # delta=1000, remaining=1

    def test_empty_turns(self):
        """Empty input returns empty output."""
        assert compute_session_costs([]) == []


# ---------------------------------------------------------------------------
# Stage 3: compute_tool_attributions
# ---------------------------------------------------------------------------


class TestComputeToolAttributions:
    def test_single_tool_gets_nearly_all(self):
        """Single tool with text result gets ~100% minus overhead."""
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="file.py", tool_use_id="toolu_001"),
            ],
            tool_results=[
                ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
            ],
        )
        attrs = compute_tool_attributions(delta=1000, session_cost=3000, raw_turn=raw)

        # Should have 2 entries: the tool and _assistant_overhead
        tool_attrs = [a for a in attrs if a.tool_name != "_assistant_overhead"]
        overhead = [a for a in attrs if a.tool_name == "_assistant_overhead"]

        assert len(tool_attrs) == 1
        assert len(overhead) == 1
        assert tool_attrs[0].tool_name == "Read"
        assert tool_attrs[0].result_size_chars == 400
        assert tool_attrs[0].result_size_tokens_est == 100  # 400 // 4
        # Single tool: fraction should be 1.0 (all of delta allocated to tools)
        assert tool_attrs[0].fraction_of_delta == 1.0
        assert tool_attrs[0].attributed_delta == 1000
        assert tool_attrs[0].attributed_session_cost == 3000

        # Overhead gets remainder = 0
        assert overhead[0].fraction_of_delta == 0.0

    def test_multiple_tools_proportional(self):
        """Multiple tools split proportionally by content size."""
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
                ContentBlock(type="tool_use", size=50, tool_name="Bash", tool_input_summary="ls", tool_use_id="toolu_002"),
            ],
            tool_results=[
                ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=300),
                ToolResult(tool_use_id="toolu_002", content_type="text", content_size_chars=100),
            ],
        )
        attrs = compute_tool_attributions(delta=1000, session_cost=4000, raw_turn=raw)

        tool_attrs = {a.tool_name: a for a in attrs if a.tool_name != "_assistant_overhead"}
        assert len(tool_attrs) == 2

        # 300 / 400 = 0.75, 100 / 400 = 0.25
        assert tool_attrs["Read"].fraction_of_delta == 0.75
        assert tool_attrs["Read"].attributed_delta == 750
        assert tool_attrs["Read"].attributed_session_cost == 3000

        assert tool_attrs["Bash"].fraction_of_delta == 0.25
        assert tool_attrs["Bash"].attributed_delta == 250
        assert tool_attrs["Bash"].attributed_session_cost == 1000

    def test_non_text_results_go_to_overhead(self):
        """tool_references and other non-text results have 0 chars, attributed to overhead."""
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
                ContentBlock(type="tool_use", size=50, tool_name="Agent", tool_input_summary="sub", tool_use_id="toolu_002"),
            ],
            tool_results=[
                ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
                ToolResult(tool_use_id="toolu_002", content_type="tool_references", content_size_chars=0),
            ],
        )
        attrs = compute_tool_attributions(delta=1000, session_cost=2000, raw_turn=raw)

        tool_attrs = {a.tool_name: a for a in attrs if a.tool_name != "_assistant_overhead"}
        overhead = [a for a in attrs if a.tool_name == "_assistant_overhead"][0]

        # Read gets 400/400 = 1.0 of tool fraction
        assert tool_attrs["Read"].fraction_of_delta == 1.0
        # Agent gets 0/400 = 0.0
        assert tool_attrs["Agent"].fraction_of_delta == 0.0
        assert tool_attrs["Agent"].result_size_chars == 0

        # Overhead absorbs remainder
        assert overhead.fraction_of_delta == 0.0  # 1.0 - 1.0 - 0.0 = 0.0

    def test_negative_delta_overhead_absorbs(self):
        """Errata E11: Negative delta after compaction — overhead absorbs negative remainder."""
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
            ],
            tool_results=[
                ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
            ],
        )
        attrs = compute_tool_attributions(delta=-5000, session_cost=-2000, raw_turn=raw)

        tool_attrs = [a for a in attrs if a.tool_name != "_assistant_overhead"]
        overhead = [a for a in attrs if a.tool_name == "_assistant_overhead"][0]

        # Even with negative delta, tool still gets fraction 1.0
        assert tool_attrs[0].fraction_of_delta == 1.0
        assert tool_attrs[0].attributed_delta == -5000
        assert tool_attrs[0].attributed_session_cost == -2000

        # Overhead absorbs remainder (0.0 here)
        assert overhead.fraction_of_delta == 0.0

    def test_matches_by_tool_use_id_not_position(self):
        """Errata E4: Match tool results to content blocks by tool_use_id."""
        # Tool results are in different order from content blocks
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_AAA"),
                ContentBlock(type="tool_use", size=50, tool_name="Bash", tool_input_summary="ls", tool_use_id="toolu_BBB"),
            ],
            tool_results=[
                # Reversed order from content blocks
                ToolResult(tool_use_id="toolu_BBB", content_type="text", content_size_chars=100),
                ToolResult(tool_use_id="toolu_AAA", content_type="text", content_size_chars=300),
            ],
        )
        attrs = compute_tool_attributions(delta=1000, session_cost=2000, raw_turn=raw)

        tool_attrs = {a.tool_name: a for a in attrs if a.tool_name != "_assistant_overhead"}
        # Read has 300 chars, Bash has 100 chars, total 400
        assert tool_attrs["Read"].result_size_chars == 300
        assert tool_attrs["Read"].fraction_of_delta == 0.75
        assert tool_attrs["Bash"].result_size_chars == 100
        assert tool_attrs["Bash"].fraction_of_delta == 0.25

    def test_no_tools_all_overhead(self):
        """Turn with no tools: all delta goes to overhead."""
        raw = _make_raw_turn(index=0, content_blocks=[], tool_results=[])
        attrs = compute_tool_attributions(delta=1000, session_cost=2000, raw_turn=raw)

        assert len(attrs) == 1
        assert attrs[0].tool_name == "_assistant_overhead"
        assert attrs[0].fraction_of_delta == 1.0
        assert attrs[0].attributed_delta == 1000
        assert attrs[0].attributed_session_cost == 2000

    def test_zero_delta(self):
        """Zero delta: all attributions have zero values."""
        raw = _make_raw_turn(
            index=0,
            content_blocks=[
                ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
            ],
            tool_results=[
                ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
            ],
        )
        attrs = compute_tool_attributions(delta=0, session_cost=0, raw_turn=raw)

        for a in attrs:
            assert a.attributed_delta == 0
            assert a.attributed_session_cost == 0


# ---------------------------------------------------------------------------
# Stage 5: apply_phase_labels
# ---------------------------------------------------------------------------


class TestApplyPhaseLabels:
    def test_no_input_all_unknown(self):
        """No milestones, no plugin = all 'unknown'."""
        turns = [_make_raw_turn(index=i) for i in range(3)]
        labels = apply_phase_labels(turns)
        assert labels == {0: "unknown", 1: "unknown", 2: "unknown"}

    def test_milestones_turn_index(self):
        """Turn-index-based milestones assign labels to ranges."""
        turns = [_make_raw_turn(index=i) for i in range(5)]
        milestones = [
            {"start": 0, "end": 1, "label": "init"},
            {"start": 2, "end": 4, "label": "analysis"},
        ]
        labels = apply_phase_labels(turns, milestones=milestones)
        assert labels[0] == "init"
        assert labels[1] == "init"
        assert labels[2] == "analysis"
        assert labels[3] == "analysis"
        assert labels[4] == "analysis"

    def test_milestones_with_gaps(self):
        """Gaps between milestones = 'unknown'."""
        turns = [_make_raw_turn(index=i) for i in range(5)]
        milestones = [
            {"start": 0, "end": 0, "label": "init"},
            {"start": 3, "end": 4, "label": "finish"},
        ]
        labels = apply_phase_labels(turns, milestones=milestones)
        assert labels[0] == "init"
        assert labels[1] == "unknown"
        assert labels[2] == "unknown"
        assert labels[3] == "finish"
        assert labels[4] == "finish"

    def test_plugin_overrides_milestones(self):
        """Plugin label_phases() takes priority over milestones."""

        class FakePlugin:
            name = "fake"

            def label_phases(self, turns):
                return {0: "plugin_phase_a", 1: "plugin_phase_b", 2: "plugin_phase_b"}

        turns = [_make_raw_turn(index=i) for i in range(3)]
        milestones = [{"start": 0, "end": 2, "label": "from_milestones"}]
        labels = apply_phase_labels(turns, milestones=milestones, plugin=FakePlugin())
        assert labels[0] == "plugin_phase_a"
        assert labels[1] == "plugin_phase_b"
        assert labels[2] == "plugin_phase_b"

    def test_plugin_partial_coverage_fills_unknown(self):
        """Plugin that doesn't cover all turns: uncovered turns get 'unknown'."""

        class PartialPlugin:
            name = "partial"

            def label_phases(self, turns):
                return {0: "covered"}

        turns = [_make_raw_turn(index=i) for i in range(3)]
        labels = apply_phase_labels(turns, plugin=PartialPlugin())
        assert labels[0] == "covered"
        assert labels[1] == "unknown"
        assert labels[2] == "unknown"

    def test_milestones_timestamp_based(self):
        """Timestamp-based milestones using ISO 8601 strings."""
        turns = [
            _make_raw_turn(index=0, timestamp="2026-03-24T10:00:00Z"),
            _make_raw_turn(index=1, timestamp="2026-03-24T10:05:00Z"),
            _make_raw_turn(index=2, timestamp="2026-03-24T10:10:00Z"),
        ]
        milestones = [
            {"start_time": "2026-03-24T10:00:00Z", "end_time": "2026-03-24T10:04:00Z", "label": "early"},
            {"start_time": "2026-03-24T10:04:01Z", "end_time": "2026-03-24T10:10:00Z", "label": "late"},
        ]
        labels = apply_phase_labels(turns, milestones=milestones)
        assert labels[0] == "early"
        assert labels[1] == "late"
        assert labels[2] == "late"

    def test_empty_turns(self):
        """Empty turns list returns empty dict."""
        labels = apply_phase_labels([])
        assert labels == {}


# ---------------------------------------------------------------------------
# build_session_profile
# ---------------------------------------------------------------------------


class TestBuildSessionProfile:
    def test_produces_correct_session_profile(self):
        """Full pipeline: deltas -> costs -> attributions -> phases -> profile."""
        turns = [
            _make_raw_turn(
                index=0,
                input_tokens=1000,
                output_tokens=200,
                content_blocks=[
                    ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
                ],
                tool_results=[
                    ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
                ],
            ),
            _make_raw_turn(
                index=1,
                input_tokens=2000,
                output_tokens=300,
                content_blocks=[
                    ContentBlock(type="tool_use", size=50, tool_name="Bash", tool_input_summary="ls", tool_use_id="toolu_002"),
                ],
                tool_results=[
                    ToolResult(tool_use_id="toolu_002", content_type="text", content_size_chars=200),
                ],
            ),
        ]
        milestones = [{"start": 0, "end": 1, "label": "init"}]

        profile = build_session_profile("sess_001", turns, milestones=milestones)

        assert profile.session_id == "sess_001"
        assert profile.session_type == "main"
        assert profile.model == "claude-sonnet-4-20250514"
        assert len(profile.turns) == 2
        assert len(profile.compaction_events) == 0

        # Check summary
        assert profile.summary is not None
        assert profile.summary.total_api_calls == 2
        assert profile.summary.peak_context_window == 2000  # max of [1000, 2000]
        assert profile.summary.total_output_tokens == 500  # 200 + 300

        # Check phases
        assert len(profile.phases) >= 1
        phase = profile.phases[0]
        assert phase.phase == "init"
        assert phase.turn_count == 2

        # Dollar cost should be 0.0 (no pricing function yet)
        assert profile.summary.total_dollars == 0.0

    def test_with_compaction(self):
        """Profile with compaction: multiple segments, compaction events recorded."""
        turns = [
            _make_raw_turn(index=0, input_tokens=5000, output_tokens=100),
            _make_raw_turn(index=1, input_tokens=8000, output_tokens=200),
            _make_raw_turn(index=2, input_tokens=3000, output_tokens=150),  # compaction
            _make_raw_turn(index=3, input_tokens=5000, output_tokens=100),
        ]
        profile = build_session_profile("sess_002", turns)

        assert len(profile.compaction_events) == 1
        assert profile.compaction_events[0].context_before == 8000
        assert profile.compaction_events[0].context_after == 3000

        assert profile.summary is not None
        assert profile.summary.peak_context_window == 8000
        assert profile.summary.total_api_calls == 4

    def test_extracts_model_from_first_turn(self):
        """Model should be extracted from raw_turns[0].model."""
        turns = [
            _make_raw_turn(index=0, input_tokens=1000, model="claude-opus-4-20250514"),
        ]
        profile = build_session_profile("sess_003", turns)
        assert profile.model == "claude-opus-4-20250514"

    def test_empty_turns(self):
        """Empty session produces a valid but empty profile."""
        profile = build_session_profile("sess_empty", [])
        assert profile.session_id == "sess_empty"
        assert len(profile.turns) == 0
        assert profile.summary is not None
        assert profile.summary.total_api_calls == 0

    def test_session_type_parameter(self):
        """session_type parameter is passed through."""
        turns = [_make_raw_turn(index=0)]
        profile = build_session_profile("sess_sub", turns, session_type="subagent")
        assert profile.session_type == "subagent"

    def test_hottest_turns_and_tools(self):
        """Summary should contain hottest turns (by session_cost) and hottest tools."""
        turns = [
            _make_raw_turn(
                index=0,
                input_tokens=1000,
                output_tokens=100,
                content_blocks=[
                    ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="a.py", tool_use_id="toolu_001"),
                ],
                tool_results=[
                    ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=400),
                ],
            ),
            _make_raw_turn(
                index=1,
                input_tokens=5000,
                output_tokens=200,
                content_blocks=[
                    ContentBlock(type="tool_use", size=50, tool_name="Read", tool_input_summary="b.py", tool_use_id="toolu_002"),
                ],
                tool_results=[
                    ToolResult(tool_use_id="toolu_002", content_type="text", content_size_chars=800),
                ],
            ),
        ]
        profile = build_session_profile("sess_hot", turns)

        assert profile.summary is not None
        assert len(profile.summary.hottest_turns) > 0
        assert len(profile.summary.hottest_tools) > 0
        # Hottest tools is list[tuple[str, int]]
        assert isinstance(profile.summary.hottest_tools[0], tuple)


# ---------------------------------------------------------------------------
# build_run_profile
# ---------------------------------------------------------------------------


class TestBuildRunProfile:
    def test_produces_cross_session_summary(self):
        """Run profile with multiple sessions produces correct rollup."""
        turns_a = [
            _make_raw_turn(index=0, input_tokens=1000, output_tokens=200),
            _make_raw_turn(index=1, input_tokens=2000, output_tokens=300),
        ]
        turns_b = [
            _make_raw_turn(index=0, input_tokens=500, output_tokens=100),
        ]

        sess_a = build_session_profile("sess_a", turns_a)
        sess_b = build_session_profile("sess_b", turns_b)

        run = build_run_profile("run_001", [sess_a, sess_b])

        assert run.run_id == "run_001"
        assert len(run.sessions) == 2
        assert run.cross_session_summary is not None

        css = run.cross_session_summary
        # Total billed = sum of all sessions' bucket totals
        assert css.total_billed_tokens > 0
        # Total session cost = sum of all sessions' total_session_cost
        assert css.total_session_cost_tokens > 0
        # Total dollars = 0.0 (no pricing yet)
        assert css.total_dollars == 0.0
        # Session breakdown is a list
        assert isinstance(css.session_breakdown, list)
        assert len(css.session_breakdown) == 2

    def test_empty_sessions(self):
        """Run with no sessions produces valid empty profile."""
        run = build_run_profile("run_empty", [])
        assert run.run_id == "run_empty"
        assert run.cross_session_summary is not None
        assert run.cross_session_summary.total_billed_tokens == 0

    def test_single_session_100_percent(self):
        """Single session gets 100% in breakdown."""
        turns = [_make_raw_turn(index=0, input_tokens=1000, output_tokens=200)]
        sess = build_session_profile("sess_only", turns)
        run = build_run_profile("run_single", [sess])

        css = run.cross_session_summary
        assert len(css.session_breakdown) == 1
        breakdown = css.session_breakdown[0]
        assert "session_id" in breakdown
        assert breakdown["session_id"] == "sess_only"

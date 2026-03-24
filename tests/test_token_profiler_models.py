"""Tests for token_profiler data models and plugin protocol."""

from token_profiler.models import (
    BucketBreakdown,
    CompactionEvent,
    ContentBlock,
    CrossSessionSummary,
    DollarCost,
    PhaseProfile,
    ProfiledTurn,
    RawTurn,
    RunProfile,
    SessionProfile,
    SessionSummary,
    ToolAttribution,
    ToolResult,
    Usage,
)
from token_profiler.plugin_protocol import ProfilerPlugin

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class TestUsage:
    def test_from_dict_all_fields(self):
        data = {
            "input_tokens": 1000,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 300,
            "output_tokens": 400,
        }
        u = Usage.from_dict(data)
        assert u.input_tokens == 1000
        assert u.cache_creation_input_tokens == 200
        assert u.cache_read_input_tokens == 300
        assert u.output_tokens == 400

    def test_from_dict_missing_fields_default_zero(self):
        data = {"input_tokens": 500, "output_tokens": 100}
        u = Usage.from_dict(data)
        assert u.cache_creation_input_tokens == 0
        assert u.cache_read_input_tokens == 0

    def test_from_dict_empty(self):
        u = Usage.from_dict({})
        assert u.input_tokens == 0
        assert u.output_tokens == 0


# ---------------------------------------------------------------------------
# RawTurn
# ---------------------------------------------------------------------------


class TestRawTurn:
    def _make_raw_turn(self, **overrides):
        defaults = {
            "request_id": "req_001",
            "index": 0,
            "timestamp": None,
            "usage": Usage(input_tokens=1000, cache_creation_input_tokens=200, cache_read_input_tokens=300, output_tokens=400),
            "stop_reason": "end_turn",
            "content_blocks": [],
            "tool_results": [],
            "assistant_text": "",
            "model": "claude-sonnet-4-20250514",
        }
        defaults.update(overrides)
        return RawTurn(**defaults)

    def test_context_window_excludes_output(self):
        turn = self._make_raw_turn()
        # context_window = input + cache_creation + cache_read, NOT output
        assert turn.context_window == 1000 + 200 + 300
        assert turn.context_window == 1500

    def test_context_window_zero(self):
        turn = self._make_raw_turn(
            usage=Usage(input_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=500)
        )
        assert turn.context_window == 0

    def test_model_field_exists_errata_e12(self):
        """Errata E12: RawTurn must have a model field."""
        turn = self._make_raw_turn()
        assert turn.model == "claude-sonnet-4-20250514"

    def test_model_default_unknown(self):
        """Errata E12: model should default to 'unknown'."""
        turn = self._make_raw_turn(model="unknown")
        assert turn.model == "unknown"


# ---------------------------------------------------------------------------
# ContentBlock
# ---------------------------------------------------------------------------


class TestContentBlock:
    def test_tool_use_id_field_exists_errata_e13(self):
        """Errata E13: ContentBlock must have a tool_use_id field for matching results to blocks."""
        block = ContentBlock(type="tool_use", size=100, tool_name="Read", tool_use_id="toolu_abc123")
        assert block.tool_use_id == "toolu_abc123"

    def test_text_block(self):
        block = ContentBlock(type="text", size=50, text_content="Hello world")
        assert block.type == "text"
        assert block.text_content == "Hello world"
        assert block.tool_use_id is None

    def test_thinking_block(self):
        block = ContentBlock(type="thinking", size=200, thinking_content="Let me reason...")
        assert block.type == "thinking"
        assert block.thinking_content == "Let me reason..."

    def test_tool_use_block(self):
        block = ContentBlock(
            type="tool_use",
            size=150,
            tool_name="Bash",
            tool_input_summary="ls -la",
            tool_use_id="toolu_xyz",
        )
        assert block.tool_name == "Bash"
        assert block.tool_input_summary == "ls -la"
        assert block.tool_use_id == "toolu_xyz"


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


class TestToolResult:
    def test_text_content_type(self):
        tr = ToolResult(tool_use_id="toolu_001", content_type="text", content_size_chars=500)
        assert tr.content_type == "text"
        assert tr.content_size_chars == 500

    def test_tool_references_content_type(self):
        tr = ToolResult(tool_use_id="toolu_002", content_type="tool_references", content_size_chars=0)
        assert tr.content_type == "tool_references"

    def test_error_content_type(self):
        tr = ToolResult(tool_use_id="toolu_003", content_type="error", content_size_chars=120)
        assert tr.content_type == "error"

    def test_empty_content_type(self):
        tr = ToolResult(tool_use_id="toolu_004", content_type="empty", content_size_chars=0)
        assert tr.content_type == "empty"
        assert tr.content_size_chars == 0


# ---------------------------------------------------------------------------
# ToolAttribution
# ---------------------------------------------------------------------------


class TestToolAttribution:
    def test_token_estimate_chars_div_4(self):
        """Token estimate should be chars // 4."""
        ta = ToolAttribution(
            tool_name="Read",
            description="Read file.py",
            result_size_chars=400,
            result_size_tokens_est=100,
            fraction_of_delta=0.5,
            attributed_delta=500,
            attributed_session_cost=1000,
        )
        # The chars // 4 heuristic: 400 // 4 == 100
        assert ta.result_size_tokens_est == ta.result_size_chars // 4

    def test_attribution_fields(self):
        ta = ToolAttribution(
            tool_name="Bash",
            description="Run tests",
            result_size_chars=800,
            result_size_tokens_est=200,
            fraction_of_delta=0.25,
            attributed_delta=250,
            attributed_session_cost=500,
        )
        assert ta.tool_name == "Bash"
        assert ta.fraction_of_delta == 0.25
        assert ta.attributed_delta == 250


# ---------------------------------------------------------------------------
# CompactionEvent
# ---------------------------------------------------------------------------


class TestCompactionEvent:
    def test_reduction_calculation(self):
        ce = CompactionEvent(
            segment_id=1,
            turn_index=5,
            context_before=100_000,
            context_after=30_000,
            reduction_tokens=70_000,
        )
        assert ce.reduction_tokens == ce.context_before - ce.context_after

    def test_fields(self):
        ce = CompactionEvent(
            segment_id=0,
            turn_index=10,
            context_before=50_000,
            context_after=20_000,
            reduction_tokens=30_000,
        )
        assert ce.segment_id == 0
        assert ce.turn_index == 10


# ---------------------------------------------------------------------------
# BucketBreakdown
# ---------------------------------------------------------------------------


class TestBucketBreakdown:
    def test_total_property(self):
        bb = BucketBreakdown(
            input_tokens=1000,
            cache_creation_tokens=200,
            cache_read_tokens=300,
            output_tokens=400,
        )
        assert bb.total == 1000 + 200 + 300 + 400
        assert bb.total == 1900

    def test_total_zero(self):
        bb = BucketBreakdown(input_tokens=0, cache_creation_tokens=0, cache_read_tokens=0, output_tokens=0)
        assert bb.total == 0


# ---------------------------------------------------------------------------
# DollarCost
# ---------------------------------------------------------------------------


class TestDollarCost:
    def test_total_cost_property(self):
        dc = DollarCost(
            input_cost=0.50,
            cache_creation_cost=0.10,
            cache_read_cost=0.05,
            output_cost=1.00,
        )
        assert dc.total_cost == 0.50 + 0.10 + 0.05 + 1.00
        assert abs(dc.total_cost - 1.65) < 1e-9

    def test_total_cost_zero(self):
        dc = DollarCost(input_cost=0.0, cache_creation_cost=0.0, cache_read_cost=0.0, output_cost=0.0)
        assert dc.total_cost == 0.0


# ---------------------------------------------------------------------------
# SessionSummary — peak_context_window, not sum (Errata E6)
# ---------------------------------------------------------------------------


class TestSessionSummary:
    def test_peak_context_window_field_not_sum(self):
        """Errata E6: SessionSummary uses peak_context_window, NOT sum of all context windows."""
        ss = SessionSummary(
            total_api_calls=10,
            peak_context_window=150_000,
            total_output_tokens=5_000,
            total_session_cost=200_000,
            total_dollars=3.50,
            hottest_turns=[],
            hottest_tools=[],
        )
        assert ss.peak_context_window == 150_000
        # Verify the field name is literally peak_context_window
        assert hasattr(ss, "peak_context_window")

    def test_all_fields(self):
        ss = SessionSummary(
            total_api_calls=5,
            peak_context_window=80_000,
            total_output_tokens=2_000,
            total_session_cost=100_000,
            total_dollars=1.25,
            hottest_turns=[0, 3],
            hottest_tools=[("Read", 50_000)],
        )
        assert ss.total_api_calls == 5
        assert ss.hottest_turns == [0, 3]
        assert ss.hottest_tools == [("Read", 50_000)]


# ---------------------------------------------------------------------------
# SessionProfile — construction with optional fields
# ---------------------------------------------------------------------------


class TestSessionProfile:
    def test_construction_minimal(self):
        sp = SessionProfile(
            session_id="sess_001",
            session_type="main",
            model="claude-sonnet-4-20250514",
            turns=[],
            phases=[],
            compaction_events=[],
        )
        assert sp.session_id == "sess_001"
        assert sp.subagent_name is None
        assert sp.dispatched_from_session is None
        assert sp.dispatched_at_turn is None
        assert sp.returned_at_turn is None
        assert sp.summary is None

    def test_construction_with_optional_fields(self):
        sp = SessionProfile(
            session_id="sess_002",
            session_type="subagent",
            model="claude-sonnet-4-20250514",
            turns=[],
            phases=[],
            compaction_events=[],
            subagent_name="code_review",
            dispatched_from_session="sess_001",
            dispatched_at_turn=5,
            returned_at_turn=5,
            summary=SessionSummary(
                total_api_calls=3,
                peak_context_window=40_000,
                total_output_tokens=1_000,
                total_session_cost=50_000,
                total_dollars=0.75,
                hottest_turns=[],
                hottest_tools=[],
            ),
        )
        assert sp.subagent_name == "code_review"
        assert sp.dispatched_from_session == "sess_001"
        assert sp.dispatched_at_turn == 5
        assert sp.summary is not None
        assert sp.summary.peak_context_window == 40_000


# ---------------------------------------------------------------------------
# RunProfile
# ---------------------------------------------------------------------------


class TestRunProfile:
    def test_construction_minimal(self):
        rp = RunProfile(run_id="run_001", sessions=[])
        assert rp.run_id == "run_001"
        assert rp.sessions == []
        assert rp.cross_session_summary is None

    def test_construction_with_summary(self):
        css = CrossSessionSummary(
            total_billed_tokens=500_000,
            total_session_cost_tokens=300_000,
            total_dollars=5.00,
            session_breakdown=[],
        )
        rp = RunProfile(run_id="run_002", sessions=[], cross_session_summary=css)
        assert rp.cross_session_summary is not None
        assert rp.cross_session_summary.total_billed_tokens == 500_000
        assert rp.cross_session_summary.total_dollars == 5.00


# ---------------------------------------------------------------------------
# ProfiledTurn — basic construction
# ---------------------------------------------------------------------------


class TestProfiledTurn:
    def test_construction(self):
        raw = RawTurn(
            request_id="req_001",
            index=0,
            timestamp=None,
            usage=Usage(input_tokens=1000, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=200),
            stop_reason="end_turn",
            content_blocks=[],
            tool_results=[],
            assistant_text="Hello",
            model="claude-sonnet-4-20250514",
        )
        pt = ProfiledTurn(
            raw=raw,
            context_window=1000,
            delta=1000,
            segment_id=0,
            remaining_calls_in_segment=9,
            session_cost_tokens=1200,
            tool_attributions=[],
            phase="init",
        )
        assert pt.raw.request_id == "req_001"
        assert pt.context_window == 1000
        assert pt.delta == 1000
        assert pt.phase == "init"


# ---------------------------------------------------------------------------
# PhaseProfile — basic construction
# ---------------------------------------------------------------------------


class TestPhaseProfile:
    def test_construction(self):
        pp = PhaseProfile(
            phase="analysis",
            turn_count=5,
            turn_indices=[0, 1, 2, 3, 4],
            delta_sum=10_000,
            session_cost_sum=50_000,
            top_tools=[("Read", 5_000)],
            bucket_breakdown=BucketBreakdown(input_tokens=3000, cache_creation_tokens=1000, cache_read_tokens=4000, output_tokens=2000),
            dollar_cost=DollarCost(input_cost=0.10, cache_creation_cost=0.05, cache_read_cost=0.02, output_cost=0.30),
        )
        assert pp.phase == "analysis"
        assert pp.turn_count == 5
        assert pp.bucket_breakdown.total == 10_000
        assert abs(pp.dollar_cost.total_cost - 0.47) < 1e-9


# ---------------------------------------------------------------------------
# Plugin Protocol — structural subtyping check
# ---------------------------------------------------------------------------


class TestProfilerPlugin:
    def test_protocol_is_runtime_checkable(self):
        """ProfilerPlugin should be a runtime_checkable Protocol."""

        class FakePlugin:
            name: str = "fake"

            def detect(self, turns: list[RawTurn]) -> bool:
                return True

            def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
                return {}

            def name_subagent(self, turns: list[RawTurn]) -> str | None:
                return None

            def enrich_profile(self, profile: SessionProfile) -> None:
                pass

            def optimization_patterns(self) -> list[dict]:
                return []

        assert isinstance(FakePlugin(), ProfilerPlugin)

    def test_non_conforming_class_fails(self):
        """A class missing methods should NOT satisfy the protocol."""

        class NotAPlugin:
            pass

        assert not isinstance(NotAPlugin(), ProfilerPlugin)

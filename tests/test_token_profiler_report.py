"""Tests for token_profiler markdown report generation."""

from token_profiler.models import (
    BucketBreakdown,
    CompactionEvent,
    CrossSessionSummary,
    DollarCost,
    PhaseProfile,
    ProfiledTurn,
    RawTurn,
    RunProfile,
    SessionProfile,
    SessionSummary,
    ToolAttribution,
    Usage,
)
from token_profiler.report import generate_markdown

# ---------------------------------------------------------------------------
# Helpers — build minimal but complete RunProfile objects
# ---------------------------------------------------------------------------


def _make_usage(
    input_tokens=1000,
    cache_creation=0,
    cache_read=0,
    output_tokens=200,
) -> Usage:
    return Usage(
        input_tokens=input_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        output_tokens=output_tokens,
    )


def _make_raw_turn(
    index=0,
    input_tokens=1000,
    cache_creation=0,
    cache_read=0,
    output_tokens=200,
    timestamp=None,
    model="claude-sonnet-4-20250514",
) -> RawTurn:
    return RawTurn(
        request_id=f"req_{index:03d}",
        index=index,
        timestamp=timestamp or "2026-03-24T10:00:00Z",
        usage=_make_usage(input_tokens, cache_creation, cache_read, output_tokens),
        stop_reason="end_turn",
        content_blocks=[],
        tool_results=[],
        assistant_text="",
        model=model,
    )


def _make_tool_attribution(
    tool_name="Read",
    description="file.py",
    result_size_chars=400,
    fraction_of_delta=0.8,
    attributed_delta=800,
    attributed_session_cost=2400,
) -> ToolAttribution:
    return ToolAttribution(
        tool_name=tool_name,
        description=description,
        result_size_chars=result_size_chars,
        result_size_tokens_est=result_size_chars // 4,
        fraction_of_delta=fraction_of_delta,
        attributed_delta=attributed_delta,
        attributed_session_cost=attributed_session_cost,
    )


def _make_profiled_turn(
    index=0,
    context_window=5000,
    delta=1000,
    segment_id=0,
    remaining=3,
    session_cost_tokens=3000,
    phase="init",
    tool_attributions=None,
    timestamp=None,
    input_tokens=1000,
    cache_creation=0,
    cache_read=0,
    output_tokens=200,
) -> ProfiledTurn:
    raw = _make_raw_turn(
        index=index,
        input_tokens=input_tokens,
        cache_creation=cache_creation,
        cache_read=cache_read,
        output_tokens=output_tokens,
        timestamp=timestamp,
    )
    if tool_attributions is None:
        tool_attributions = [
            _make_tool_attribution(
                tool_name="Read",
                attributed_delta=int(delta * 0.8),
                attributed_session_cost=int(session_cost_tokens * 0.8),
                fraction_of_delta=0.8,
            ),
            _make_tool_attribution(
                tool_name="_assistant_overhead",
                description="assistant text, thinking, system prompt growth",
                result_size_chars=0,
                fraction_of_delta=0.2,
                attributed_delta=int(delta * 0.2),
                attributed_session_cost=int(session_cost_tokens * 0.2),
            ),
        ]
    return ProfiledTurn(
        raw=raw,
        context_window=context_window,
        delta=delta,
        segment_id=segment_id,
        remaining_calls_in_segment=remaining,
        session_cost_tokens=session_cost_tokens,
        tool_attributions=tool_attributions,
        phase=phase,
    )


def _make_phase_profile(
    phase="init",
    turn_count=2,
    turn_indices=None,
    delta_sum=2000,
    session_cost_sum=5000,
    top_tools=None,
    input_tokens=2000,
    cache_creation=0,
    cache_read=0,
    output_tokens=400,
    dollar_input=0.006,
    dollar_cache_creation=0.0,
    dollar_cache_read=0.0,
    dollar_output=0.006,
) -> PhaseProfile:
    return PhaseProfile(
        phase=phase,
        turn_count=turn_count,
        turn_indices=turn_indices or [0, 1],
        delta_sum=delta_sum,
        session_cost_sum=session_cost_sum,
        top_tools=top_tools or [("Read", 4000), ("Bash", 1000)],
        bucket_breakdown=BucketBreakdown(
            input_tokens=input_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            output_tokens=output_tokens,
        ),
        dollar_cost=DollarCost(
            input_cost=dollar_input,
            cache_creation_cost=dollar_cache_creation,
            cache_read_cost=dollar_cache_read,
            output_cost=dollar_output,
        ),
    )


def _make_session_profile(
    session_id="sess_001",
    session_type="main",
    model="claude-sonnet-4-20250514",
    turns=None,
    phases=None,
    compaction_events=None,
    summary=None,
) -> SessionProfile:
    if turns is None:
        turns = [
            _make_profiled_turn(index=0, delta=1000, remaining=2, session_cost_tokens=2000, phase="init"),
            _make_profiled_turn(index=1, delta=1000, remaining=1, session_cost_tokens=1000, phase="init"),
        ]
    if phases is None:
        phases = [_make_phase_profile()]
    if summary is None:
        summary = SessionSummary(
            total_api_calls=2,
            peak_context_window=6000,
            total_output_tokens=400,
            total_session_cost=3000,
            total_dollars=0.012,
            hottest_turns=[0, 1],
            hottest_tools=[("Read", 2400), ("Bash", 600)],
        )
    return SessionProfile(
        session_id=session_id,
        session_type=session_type,
        model=model,
        turns=turns,
        phases=phases,
        compaction_events=compaction_events or [],
        summary=summary,
    )


def _make_single_session_run(run_id="run_001") -> RunProfile:
    """Build a single-session RunProfile for basic tests."""
    sess = _make_session_profile()
    return RunProfile(
        run_id=run_id,
        sessions=[sess],
        cross_session_summary=CrossSessionSummary(
            total_billed_tokens=2400,
            total_session_cost_tokens=3000,
            total_dollars=0.012,
            session_breakdown=[
                {
                    "session_id": "sess_001",
                    "session_type": "main",
                    "billed_tokens": 2400,
                    "session_cost": 3000,
                    "dollars": 0.012,
                    "pct_of_billed": 100.0,
                    "pct_of_session_cost": 100.0,
                },
            ],
        ),
    )


def _make_multi_session_run() -> RunProfile:
    """Build a two-session RunProfile for multi-session tests."""
    sess_a = _make_session_profile(session_id="sess_main", session_type="main")
    sess_b = _make_session_profile(
        session_id="sess_sub",
        session_type="subagent",
        summary=SessionSummary(
            total_api_calls=1,
            peak_context_window=3000,
            total_output_tokens=200,
            total_session_cost=1000,
            total_dollars=0.004,
            hottest_turns=[0],
            hottest_tools=[("Bash", 800)],
        ),
    )
    return RunProfile(
        run_id="run_multi",
        sessions=[sess_a, sess_b],
        cross_session_summary=CrossSessionSummary(
            total_billed_tokens=4800,
            total_session_cost_tokens=4000,
            total_dollars=0.016,
            session_breakdown=[
                {
                    "session_id": "sess_main",
                    "session_type": "main",
                    "billed_tokens": 2400,
                    "session_cost": 3000,
                    "dollars": 0.012,
                    "pct_of_billed": 50.0,
                    "pct_of_session_cost": 75.0,
                },
                {
                    "session_id": "sess_sub",
                    "session_type": "subagent",
                    "billed_tokens": 2400,
                    "session_cost": 1000,
                    "dollars": 0.004,
                    "pct_of_billed": 50.0,
                    "pct_of_session_cost": 25.0,
                },
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Tests: all required sections present
# ---------------------------------------------------------------------------


class TestSectionsPresent:
    """Format regression guards: verify each section heading exists and contains
    at least minimal content. Companion value tests in TestSummaryFormatting,
    TestDollarCosts, and TestCostBucketFormatting verify correctness of values
    within these sections."""

    def test_title_contains_run_id(self):
        md = generate_markdown(_make_single_session_run())
        assert "# Token Profile: run_001" in md

    def test_summary_section_has_metrics(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Summary" in md
        assert "Total API calls" in md, "Summary section should contain Total API calls metric"
        # BH-003: Also verify a computed value appears in summary
        assert "| 2 |" in md or "2" in md.split("## Summary")[1].split("## ")[0], \
            "Summary section should contain the actual API call count"

    def test_hottest_turns_section_has_table(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Heat Map -- Top 20 Hottest Turns" in md
        assert "Turn" in md, "Hottest turns section should contain a Turn column"
        # BH-003: Verify a computed turn value appears
        turns_section = md.split("## Heat Map -- Top 20 Hottest Turns")[1].split("## ")[0]
        assert "|" in turns_section, "Hottest turns should contain table rows"

    def test_hottest_tools_section_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Heat Map -- Top 20 Hottest Tools" in md
        # BH-003: Verify tool data appears
        tools_section = md.split("## Heat Map -- Top 20 Hottest Tools")[1].split("## ")[0]
        assert "Read" in tools_section, "Tools section should contain the Read tool from fixture"

    def test_phase_breakdown_section_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Phase Breakdown" in md
        # BH-010: Verify section contains actual phase data, not just heading
        phase_section = md.split("## Phase Breakdown")[1].split("## ")[0]
        assert "|" in phase_section, "Phase breakdown should contain table rows"

    def test_cost_buckets_section_has_table(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Cost Buckets" in md
        assert "Bucket" in md, "Cost buckets section should contain a Bucket column"

    def test_dollar_costs_section_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Dollar Costs" in md
        # BH-010: Verify section contains dollar values (see TestDollarCosts for full checks)
        dollar_section = md.split("## Dollar Costs")[1].split("## ")[0]
        assert "$" in dollar_section, "Dollar costs should contain $ values"

    def test_compaction_events_section_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Compaction Events" in md
        # BH-010: Verify section contains content (see TestCompactionEvents for full checks)
        compaction_section = md.split("## Compaction Events")[1].split("## ")[0]
        assert len(compaction_section.strip()) > 0, "Compaction events should not be empty"

    def test_methodology_section_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Methodology" in md
        # BH-010: Verify section contains methodology text
        methodology_section = md.split("## Methodology")[1]
        assert len(methodology_section.strip()) > 20, "Methodology should contain explanatory text"


# ---------------------------------------------------------------------------
# Tests: Summary numbers formatted correctly
# ---------------------------------------------------------------------------


class TestSummaryFormatting:
    def test_summary_table_sessions(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Sessions | 1 |" in md

    def test_summary_table_api_calls(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Total API calls | 2 |" in md

    def test_summary_table_billed_tokens(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Total billed tokens | 2,400 |" in md

    def test_summary_table_session_cost(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Total session cost (heat) | 3,000 |" in md

    def test_summary_table_dollars(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Total dollars | $0.0120 |" in md


# ---------------------------------------------------------------------------
# Tests: Per-session breakdown when multiple sessions
# ---------------------------------------------------------------------------


class TestMultiSessionBreakdown:
    def test_per_session_table_present(self):
        md = generate_markdown(_make_multi_session_run())
        assert "sess_main" in md
        assert "sess_sub" in md

    def test_per_session_table_has_type_column(self):
        md = generate_markdown(_make_multi_session_run())
        assert "main" in md
        assert "subagent" in md

    def test_single_session_no_breakdown_table(self):
        """Single session should NOT have a per-session breakdown table."""
        md = generate_markdown(_make_single_session_run())
        # The per-session breakdown table header should not appear
        # (we still show the summary, just no per-session table)
        lines = md.split("\n")
        # Count occurrences of session_id in table rows — should be 0 for single session
        breakdown_rows = [ln for ln in lines if "sess_001" in ln and "|" in ln and "Session" not in ln]
        # In a single-session run, we should not have a per-session breakdown table
        # The session_id only appears in the title area, not in a table
        assert len(breakdown_rows) == 0


# ---------------------------------------------------------------------------
# Tests: Hottest turns with tool attributions
# ---------------------------------------------------------------------------


class TestHottestTurns:
    def test_turns_ranked_by_session_cost(self):
        """Hottest turns should appear ranked by session_cost_tokens descending."""
        turns = [
            _make_profiled_turn(index=0, delta=500, remaining=3, session_cost_tokens=1500, phase="init"),
            _make_profiled_turn(index=1, delta=2000, remaining=2, session_cost_tokens=4000, phase="init"),
            _make_profiled_turn(index=2, delta=100, remaining=1, session_cost_tokens=100, phase="init"),
        ]
        sess = _make_session_profile(turns=turns)
        run = RunProfile(
            run_id="run_heat",
            sessions=[sess],
            cross_session_summary=CrossSessionSummary(
                total_billed_tokens=5000,
                total_session_cost_tokens=5600,
                total_dollars=0.01,
                session_breakdown=[],
            ),
        )
        md = generate_markdown(run)
        # Turn 1 (cost 4000) should appear before turn 0 (cost 1500)
        pos_turn1 = md.index("4,000 session cost")
        pos_turn0 = md.index("1,500 session cost")
        assert pos_turn1 < pos_turn0

    def test_turn_entry_format(self):
        """Each turn entry has the expected format."""
        run = _make_single_session_run()
        md = generate_markdown(run)
        # Both turn entries should be present (2-turn fixture)
        assert "x2 remaining" in md
        assert "x1 remaining" in md

    def test_tool_attribution_sub_entries(self):
        """Tool attributions appear as sub-entries under the turn."""
        run = _make_single_session_run()
        md = generate_markdown(run)
        # The Read tool attribution should be listed
        assert "Read" in md


# ---------------------------------------------------------------------------
# Tests: Hottest tools table
# ---------------------------------------------------------------------------


class TestHottestTools:
    def test_tool_table_headers(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Tool |" in md
        assert "Calls" in md
        assert "Session Cost" in md

    def test_tool_aggregation(self):
        """Tools are aggregated across all turns."""
        run = _make_single_session_run()
        md = generate_markdown(run)
        # Read tool should appear in the Hottest Tools section
        tools_section = md.split("## Heat Map -- Top 20 Hottest Tools")[1].split("## ")[0]
        assert "Read" in tools_section


# ---------------------------------------------------------------------------
# Tests: Phase breakdown
# ---------------------------------------------------------------------------


class TestPhaseBreakdown:
    def test_phase_table_headers(self):
        md = generate_markdown(_make_single_session_run())
        assert "| Phase |" in md
        assert "Turns" in md
        assert "Delta Sum" in md

    def test_phase_data_present(self):
        md = generate_markdown(_make_single_session_run())
        assert "init" in md


# ---------------------------------------------------------------------------
# Tests: Cost buckets
# ---------------------------------------------------------------------------


class TestCostBuckets:
    def test_bucket_table_headers(self):
        md = generate_markdown(_make_single_session_run())
        # Find the Cost Buckets section
        assert "| Phase | Input | Cache Create | Cache Read | Output | Total |" in md

    def test_bucket_values(self):
        md = generate_markdown(_make_single_session_run())
        # The init phase has input_tokens=2000, output_tokens=400
        assert "2,000" in md
        assert "400" in md


# ---------------------------------------------------------------------------
# Tests: Dollar costs
# ---------------------------------------------------------------------------


class TestDollarCosts:
    def test_dollar_table_headers(self):
        md = generate_markdown(_make_single_session_run())
        assert "## Dollar Costs" in md
        assert "| Phase |" in md

    def test_dollar_values_formatted(self):
        """Dollar values should be formatted as $X.XXXX."""
        md = generate_markdown(_make_single_session_run())
        assert "$0.0060" in md


# ---------------------------------------------------------------------------
# Tests: Compaction events
# ---------------------------------------------------------------------------


class TestCompactionEvents:
    def test_no_compaction_message(self):
        """When no compaction events, show 'No compaction events detected.'"""
        run = _make_single_session_run()
        md = generate_markdown(run)
        assert "No compaction events detected." in md

    def test_compaction_events_table(self):
        """When compaction events exist, show a table."""
        sess = _make_session_profile(
            compaction_events=[
                CompactionEvent(
                    segment_id=1,
                    turn_index=5,
                    context_before=80000,
                    context_after=30000,
                    reduction_tokens=50000,
                ),
            ],
        )
        run = RunProfile(
            run_id="run_compact",
            sessions=[sess],
            cross_session_summary=CrossSessionSummary(
                total_billed_tokens=5000,
                total_session_cost_tokens=3000,
                total_dollars=0.01,
                session_breakdown=[],
            ),
        )
        md = generate_markdown(run)
        assert "80,000" in md
        assert "30,000" in md
        assert "50,000" in md
        assert "No compaction events detected." not in md


# ---------------------------------------------------------------------------
# Tests: Methodology section
# ---------------------------------------------------------------------------


class TestMethodology:
    def test_methodology_explains_session_cost(self):
        md = generate_markdown(_make_single_session_run())
        # Should contain an explanation of the session cost formula
        assert "session cost" in md.lower() or "session_cost" in md.lower()
        assert "delta" in md.lower()
        assert "remaining" in md.lower()


# ---------------------------------------------------------------------------
# Tests: Overhead filtering in hottest turns
# ---------------------------------------------------------------------------


class TestOverheadFiltering:
    def test_overhead_below_10_percent_skipped(self):
        """Overhead attribution < 10% should be skipped in hot turns."""
        turns = [
            _make_profiled_turn(
                index=0,
                delta=1000,
                remaining=1,
                session_cost_tokens=1000,
                phase="init",
                tool_attributions=[
                    _make_tool_attribution(
                        tool_name="Read",
                        fraction_of_delta=0.95,
                        attributed_delta=950,
                        attributed_session_cost=950,
                    ),
                    _make_tool_attribution(
                        tool_name="_assistant_overhead",
                        description="assistant text, thinking, system prompt growth",
                        result_size_chars=0,
                        fraction_of_delta=0.05,
                        attributed_delta=50,
                        attributed_session_cost=50,
                    ),
                ],
            ),
        ]
        sess = _make_session_profile(turns=turns)
        run = RunProfile(
            run_id="run_overhead",
            sessions=[sess],
            cross_session_summary=CrossSessionSummary(
                total_billed_tokens=1200,
                total_session_cost_tokens=1000,
                total_dollars=0.005,
                session_breakdown=[],
            ),
        )
        md = generate_markdown(run)
        # In the hottest turns section, overhead at 5% should be skipped
        # Find the heat map section
        hot_turns_section = md.split("## Heat Map -- Top 20 Hottest Turns")[1].split("## ")[0]
        assert "_assistant_overhead" not in hot_turns_section

    def test_overhead_above_10_percent_shown(self):
        """Overhead attribution >= 10% should be shown."""
        turns = [
            _make_profiled_turn(
                index=0,
                delta=1000,
                remaining=1,
                session_cost_tokens=1000,
                phase="init",
                tool_attributions=[
                    _make_tool_attribution(
                        tool_name="Read",
                        fraction_of_delta=0.7,
                        attributed_delta=700,
                        attributed_session_cost=700,
                    ),
                    _make_tool_attribution(
                        tool_name="_assistant_overhead",
                        description="assistant text, thinking, system prompt growth",
                        result_size_chars=0,
                        fraction_of_delta=0.3,
                        attributed_delta=300,
                        attributed_session_cost=300,
                    ),
                ],
            ),
        ]
        sess = _make_session_profile(turns=turns)
        run = RunProfile(
            run_id="run_big_overhead",
            sessions=[sess],
            cross_session_summary=CrossSessionSummary(
                total_billed_tokens=1200,
                total_session_cost_tokens=1000,
                total_dollars=0.005,
                session_breakdown=[],
            ),
        )
        md = generate_markdown(run)
        hot_turns_section = md.split("## Heat Map -- Top 20 Hottest Turns")[1].split("## ")[0]
        assert "_assistant_overhead" in hot_turns_section

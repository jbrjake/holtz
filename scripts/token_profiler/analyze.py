"""Analysis pipeline for the token profiler (stages 2-5).

Transforms RawTurn objects into ProfiledTurn objects with session cost metrics.
Pipeline: deltas -> session costs -> tool attributions -> phase labels -> aggregate.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

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

# ---------------------------------------------------------------------------
# Protocols for typed plugin / pricing parameters
# ---------------------------------------------------------------------------


@runtime_checkable
class _PhaseLabelPlugin(Protocol):
    """Minimal protocol for a plugin that labels phases."""

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]: ...


# Pricing function signature: (Usage, model_str) -> DollarCost or similar
PricingFn = Callable[..., Any]


# ---------------------------------------------------------------------------
# Internal intermediate type
# ---------------------------------------------------------------------------


@dataclass
class DeltaTurn:
    """Intermediate representation: RawTurn enriched with context-window delta info."""

    raw: RawTurn
    context_window: int
    delta: int
    segment_id: int
    remaining: int = 1  # filled by compute_session_costs
    session_cost: int = 0  # filled by compute_session_costs


# ---------------------------------------------------------------------------
# Stage 2: compute deltas and detect compaction boundaries
# ---------------------------------------------------------------------------


def compute_deltas(turns: list[RawTurn]) -> tuple[list[DeltaTurn], list[CompactionEvent]]:
    """Walk the turn sequence and compute context_window and delta for each turn.

    Returns (delta_turns, compaction_events).  Errata E10: always returns a tuple.

    A negative delta indicates compaction — a new segment starts and a
    CompactionEvent is recorded.
    """
    if not turns:
        return ([], [])

    delta_turns: list[DeltaTurn] = []
    events: list[CompactionEvent] = []
    segment_id = 0
    prev_cw = 0

    for i, turn in enumerate(turns):
        cw = turn.context_window

        delta = cw if i == 0 else cw - prev_cw

        # Negative delta => compaction boundary
        if delta < 0 and i > 0:
            segment_id += 1
            events.append(
                CompactionEvent(
                    segment_id=segment_id,
                    turn_index=turn.index,
                    context_before=prev_cw,
                    context_after=cw,
                    reduction_tokens=prev_cw - cw,
                )
            )

        delta_turns.append(
            DeltaTurn(
                raw=turn,
                context_window=cw,
                delta=delta,
                segment_id=segment_id,
            )
        )
        prev_cw = cw

    return (delta_turns, events)


# ---------------------------------------------------------------------------
# Stage 4: compute session costs (two-pass within segments)
# ---------------------------------------------------------------------------


def compute_session_costs(delta_turns: list[DeltaTurn]) -> list[DeltaTurn]:
    """Compute remaining-calls and session_cost for each turn within its segment.

    Pass 2: for each turn, remaining = (last_turn_index_in_segment - current_index) + 1
    so remaining is INCLUSIVE (minimum 1).  session_cost = delta * remaining.
    """
    if not delta_turns:
        return []

    # Group turns by segment — find last position-in-list for each segment
    segment_last_pos: dict[int, int] = {}
    for pos, dt in enumerate(delta_turns):
        segment_last_pos[dt.segment_id] = pos

    for pos, dt in enumerate(delta_turns):
        last_pos = segment_last_pos[dt.segment_id]
        dt.remaining = (last_pos - pos) + 1
        dt.session_cost = dt.delta * dt.remaining

    return delta_turns


# ---------------------------------------------------------------------------
# Stage 3: tool attribution
# ---------------------------------------------------------------------------


def compute_tool_attributions(
    delta: int,
    session_cost: int,
    raw_turn: RawTurn,
) -> list[ToolAttribution]:
    """Distribute a turn's delta across tool results proportionally by content size.

    Errata E4: matches by tool_use_id, not position.
    Errata E11: handles negative delta — overhead absorbs negative remainder.
    Errata E15: no dead variables.
    """
    # Build map from tool_use_id to ToolResult
    result_by_id: dict[str, Any] = {}
    for tr in raw_turn.tool_results:
        result_by_id[tr.tool_use_id] = tr

    # Collect tool_use content blocks with their matched results
    tool_entries: list[tuple[str, str, int]] = []  # (tool_name, description, content_size_chars)
    total_chars = 0

    for block in raw_turn.content_blocks:
        if block.type != "tool_use":
            continue

        tool_use_id = block.tool_use_id or ""
        matched_result = result_by_id.get(tool_use_id)

        if matched_result and matched_result.content_type == "text" and matched_result.content_size_chars > 0:
            chars = matched_result.content_size_chars
        else:
            chars = 0

        desc = block.tool_input_summary or block.tool_name or ""
        tool_entries.append((block.tool_name or "unknown", desc, chars))
        total_chars += chars

    attributions: list[ToolAttribution] = []
    sum_fractions = 0.0

    for tool_name, desc, chars in tool_entries:
        fraction = chars / total_chars if total_chars > 0 else 0.0

        sum_fractions += fraction
        attributed_delta = int(delta * fraction)
        attributed_sc = int(session_cost * fraction)

        attributions.append(
            ToolAttribution(
                tool_name=tool_name,
                description=desc,
                result_size_chars=chars,
                result_size_tokens_est=chars // 4,
                fraction_of_delta=fraction,
                attributed_delta=attributed_delta,
                attributed_session_cost=attributed_sc,
            )
        )

    # Overhead entry gets the remainder
    overhead_fraction = 1.0 - sum_fractions
    attributions.append(
        ToolAttribution(
            tool_name="_assistant_overhead",
            description="assistant text, thinking, system prompt growth",
            result_size_chars=0,
            result_size_tokens_est=0,
            fraction_of_delta=overhead_fraction,
            attributed_delta=delta - sum(a.attributed_delta for a in attributions),
            attributed_session_cost=session_cost - sum(a.attributed_session_cost for a in attributions),
        )
    )

    return attributions


# ---------------------------------------------------------------------------
# Stage 5: phase labels
# ---------------------------------------------------------------------------


def apply_phase_labels(
    turns: list[RawTurn],
    milestones: list[dict[str, Any]] | None = None,
    plugin: _PhaseLabelPlugin | None = None,
) -> dict[int, str]:
    """Assign phase labels to turns.

    Priority: plugin.label_phases() > milestones > "unknown".
    Milestones support both turn-index-based (start/end) and timestamp-based
    (start_time/end_time as ISO 8601).  Ranges are inclusive on both ends.
    """
    if not turns:
        return {}

    # Default: everything is "unknown"
    labels: dict[int, str] = {turn.index: "unknown" for turn in turns}

    # Apply milestones if provided
    if milestones:
        for ms in milestones:
            label = ms.get("label", "unknown")

            if "start" in ms and "end" in ms:
                # Turn-index-based
                for turn in turns:
                    if ms["start"] <= turn.index <= ms["end"]:
                        labels[turn.index] = label

            elif "start_time" in ms and "end_time" in ms:
                # Timestamp-based
                try:
                    start_dt = _parse_iso(ms["start_time"])
                    end_dt = _parse_iso(ms["end_time"])
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Malformed timestamp in milestone '{label}': {e}"
                    ) from e
                for turn in turns:
                    if turn.timestamp:
                        try:
                            turn_dt = _parse_iso(turn.timestamp)
                        except (ValueError, TypeError):
                            continue  # skip turns with unparseable timestamps
                        if start_dt <= turn_dt <= end_dt:
                            labels[turn.index] = label

    # Plugin overrides milestone labels where specified (BH-021: preserve
    # milestone labels for turns the plugin doesn't cover)
    if plugin is not None and hasattr(plugin, "label_phases"):
        plugin_labels = plugin.label_phases(turns)
        if plugin_labels:
            for idx, lbl in plugin_labels.items():
                if idx in labels:
                    labels[idx] = lbl

    return labels


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a datetime."""
    # Handle 'Z' suffix for UTC
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# Full pipeline: build_session_profile
# ---------------------------------------------------------------------------


def build_session_profile(
    session_id: str,
    raw_turns: list[RawTurn],
    session_type: str = "main",
    milestones: list[dict[str, Any]] | None = None,
    plugin: _PhaseLabelPlugin | None = None,
    model: str | None = None,
    pricing_fn: PricingFn | None = None,
) -> SessionProfile:
    """Full analysis pipeline: deltas -> session costs -> attributions -> phases -> SessionProfile.

    Errata E5: pricing_fn parameter for dollar costs (default: 0.0).
    Errata E6: peak_context_window = max context_window seen.
    Errata E7: build PhaseProfile list, SessionSummary with hottest_turns/hottest_tools.
    """
    if not raw_turns:
        return SessionProfile(
            session_id=session_id,
            session_type=session_type,
            model=model or "unknown",
            turns=[],
            phases=[],
            compaction_events=[],
            summary=SessionSummary(
                total_api_calls=0,
                peak_context_window=0,
                total_output_tokens=0,
                total_session_cost=0,
                total_dollars=0.0,
                hottest_turns=[],
                hottest_tools=[],
            ),
        )

    # Extract model from first turn if not provided
    resolved_model = model or raw_turns[0].model

    # Stage 2: compute deltas
    delta_turns, compaction_events = compute_deltas(raw_turns)

    # Stage 4: compute session costs
    compute_session_costs(delta_turns)

    # Stage 5: phase labels
    phase_labels = apply_phase_labels(raw_turns, milestones=milestones, plugin=plugin)

    # Stage 3 + assembly: compute attributions and build ProfiledTurns
    profiled_turns: list[ProfiledTurn] = []
    for dt in delta_turns:
        attrs = compute_tool_attributions(
            delta=dt.delta,
            session_cost=dt.session_cost,
            raw_turn=dt.raw,
        )
        profiled_turns.append(
            ProfiledTurn(
                raw=dt.raw,
                context_window=dt.context_window,
                delta=dt.delta,
                segment_id=dt.segment_id,
                remaining_calls_in_segment=dt.remaining,
                session_cost_tokens=dt.session_cost,
                tool_attributions=attrs,
                phase=phase_labels.get(dt.raw.index, "unknown"),
            )
        )

    # Build PhaseProfile list (Errata E7)
    phases = _build_phase_profiles(profiled_turns, resolved_model, pricing_fn)

    # Build SessionSummary (Errata E6, E7)
    summary = _build_session_summary(profiled_turns, phases)

    return SessionProfile(
        session_id=session_id,
        session_type=session_type,
        model=resolved_model,
        turns=profiled_turns,
        phases=phases,
        compaction_events=compaction_events,
        summary=summary,
    )


def _build_phase_profiles(
    turns: list[ProfiledTurn],
    model: str = "unknown",
    pricing_fn: PricingFn | None = None,
) -> list[PhaseProfile]:
    """Aggregate turns into PhaseProfile list, one per unique phase label."""
    # Group turns by phase, preserving order of first appearance
    phase_order: list[str] = []
    phase_turns: dict[str, list[ProfiledTurn]] = {}

    for pt in turns:
        if pt.phase not in phase_turns:
            phase_order.append(pt.phase)
            phase_turns[pt.phase] = []
        phase_turns[pt.phase].append(pt)

    profiles: list[PhaseProfile] = []
    for phase_name in phase_order:
        pts = phase_turns[phase_name]

        # Aggregate bucket breakdown
        input_sum = sum(pt.raw.usage.input_tokens for pt in pts)
        cache_creation_sum = sum(pt.raw.usage.cache_creation_input_tokens for pt in pts)
        cache_read_sum = sum(pt.raw.usage.cache_read_input_tokens for pt in pts)
        output_sum = sum(pt.raw.usage.output_tokens for pt in pts)

        # Top tools by attributed session cost
        tool_costs: Counter[str] = Counter()
        for pt in pts:
            for attr in pt.tool_attributions:
                if attr.tool_name != "_assistant_overhead":
                    tool_costs[attr.tool_name] += attr.attributed_session_cost

        profiles.append(
            PhaseProfile(
                phase=phase_name,
                turn_count=len(pts),
                turn_indices=[pt.raw.index for pt in pts],
                delta_sum=sum(pt.delta for pt in pts),
                session_cost_sum=sum(pt.session_cost_tokens for pt in pts),
                top_tools=tool_costs.most_common(10),
                bucket_breakdown=BucketBreakdown(
                    input_tokens=input_sum,
                    cache_creation_tokens=cache_creation_sum,
                    cache_read_tokens=cache_read_sum,
                    output_tokens=output_sum,
                ),
                dollar_cost=pricing_fn(
                    Usage(
                        input_tokens=input_sum,
                        output_tokens=output_sum,
                        cache_creation_input_tokens=cache_creation_sum,
                        cache_read_input_tokens=cache_read_sum,
                    ),
                    model,
                ) if pricing_fn else DollarCost(
                    input_cost=0.0,
                    cache_creation_cost=0.0,
                    cache_read_cost=0.0,
                    output_cost=0.0,
                ),
            )
        )

    return profiles


def _build_session_summary(
    turns: list[ProfiledTurn],
    phases: list[PhaseProfile],
) -> SessionSummary:
    """Build SessionSummary from profiled turns.

    Errata E6: peak_context_window = max context_window seen.
    Errata E7: hottest_turns (top 5 by session_cost), hottest_tools (top 10).
    """
    # Peak context window
    peak_cw = max((pt.context_window for pt in turns), default=0)

    # Total output tokens
    total_output = sum(pt.raw.usage.output_tokens for pt in turns)

    # Total session cost
    total_sc = sum(pt.session_cost_tokens for pt in turns)

    # Hottest turns: top 5 by absolute session_cost
    sorted_by_cost = sorted(turns, key=lambda pt: abs(pt.session_cost_tokens), reverse=True)
    hottest_turns = [pt.raw.index for pt in sorted_by_cost[:5]]

    # Hottest tools: aggregate across all turns, top 10
    tool_costs: Counter[str] = Counter()
    for pt in turns:
        for attr in pt.tool_attributions:
            if attr.tool_name != "_assistant_overhead":
                tool_costs[attr.tool_name] += attr.attributed_session_cost

    return SessionSummary(
        total_api_calls=len(turns),
        peak_context_window=peak_cw,
        total_output_tokens=total_output,
        total_session_cost=total_sc,
        total_dollars=sum(p.dollar_cost.total_cost for p in phases),
        hottest_turns=hottest_turns,
        hottest_tools=tool_costs.most_common(10),
    )


# ---------------------------------------------------------------------------
# Run-level rollup
# ---------------------------------------------------------------------------


def build_run_profile(
    run_id: str,
    sessions: list[SessionProfile],
) -> RunProfile:
    """Compute CrossSessionSummary rollup across sessions.

    Errata E7: sum billed tokens, session costs, dollars across all sessions.
    Per-session percentage breakdown.
    """
    total_billed = 0
    total_sc = 0
    total_dollars = 0.0
    breakdown: list[dict[str, Any]] = []

    for sess in sessions:
        if sess.summary is None:
            continue

        # Billed tokens = sum of all bucket totals across phases
        sess_billed = sum(p.bucket_breakdown.total for p in sess.phases)
        sess_sc = sess.summary.total_session_cost
        sess_dollars = sess.summary.total_dollars

        total_billed += sess_billed
        total_sc += sess_sc
        total_dollars += sess_dollars

        breakdown.append({
            "session_id": sess.session_id,
            "session_type": sess.session_type,
            "billed_tokens": sess_billed,
            "session_cost": sess_sc,
            "dollars": sess_dollars,
        })

    # Add percentage
    for entry in breakdown:
        entry["pct_of_billed"] = (entry["billed_tokens"] / total_billed * 100) if total_billed > 0 else 0.0
        entry["pct_of_session_cost"] = (entry["session_cost"] / total_sc * 100) if total_sc > 0 else 0.0

    css = CrossSessionSummary(
        total_billed_tokens=total_billed,
        total_session_cost_tokens=total_sc,
        total_dollars=total_dollars,
        session_breakdown=breakdown,
    )

    return RunProfile(
        run_id=run_id,
        sessions=sessions,
        cross_session_summary=css,
    )

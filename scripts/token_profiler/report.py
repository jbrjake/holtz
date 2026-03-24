"""Markdown report generation for the token profiler.

Generates a structured markdown report from a RunProfile, covering
summary statistics, heat maps, phase breakdowns, cost buckets,
dollar costs, compaction events, and methodology.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from token_profiler.models import (
    CompactionEvent,
    ProfiledTurn,
    RunProfile,
)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_int(n: int) -> str:
    """Format an integer with comma separators."""
    return f"{n:,}"


def _fmt_dollars(d: float) -> str:
    """Format a dollar amount as $X.XXXX."""
    return f"${d:.4f}"


def _fmt_pct(f: float) -> str:
    """Format a fraction as a percentage string."""
    return f"{f:.1f}%"


def _fmt_timestamp(ts: str | None) -> str:
    """Format an ISO 8601 timestamp as HH:MM:SS."""
    if not ts:
        return "??:??:??"
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return "??:??:??"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_summary(profile: RunProfile) -> str:
    """Build the Summary section."""
    lines: list[str] = []
    lines.append("## Summary\n")

    css = profile.cross_session_summary
    num_sessions = len(profile.sessions)

    # Compute total API calls across all sessions
    total_api_calls = 0
    for sess in profile.sessions:
        if sess.summary is not None:
            total_api_calls += sess.summary.total_api_calls

    total_billed = css.total_billed_tokens if css else 0
    total_sc = css.total_session_cost_tokens if css else 0
    total_dollars = css.total_dollars if css else 0.0

    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Sessions | {num_sessions} |")
    lines.append(f"| Total API calls | {total_api_calls} |")
    lines.append(f"| Total billed tokens | {_fmt_int(total_billed)} |")
    lines.append(f"| Total session cost (heat) | {_fmt_int(total_sc)} |")
    lines.append(f"| Total dollars | {_fmt_dollars(total_dollars)} |")

    # Per-session breakdown table if multiple sessions
    if num_sessions > 1 and css and css.session_breakdown:
        lines.append("")
        lines.append("### Per-Session Breakdown\n")
        lines.append("| Session | Type | API Calls | Billed Tokens | Session Cost | Dollars | % Billed | % Cost |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for entry in css.session_breakdown:
            # Find matching session for API calls
            api_calls = 0
            for sess in profile.sessions:
                if sess.session_id == entry["session_id"] and sess.summary:
                    api_calls = sess.summary.total_api_calls
                    break
            lines.append(
                f"| {entry['session_id']} "
                f"| {entry['session_type']} "
                f"| {api_calls} "
                f"| {_fmt_int(entry['billed_tokens'])} "
                f"| {_fmt_int(entry['session_cost'])} "
                f"| {_fmt_dollars(entry['dollars'])} "
                f"| {_fmt_pct(entry.get('pct_of_billed', 0.0))} "
                f"| {_fmt_pct(entry.get('pct_of_session_cost', 0.0))} |"
            )

    return "\n".join(lines)


def _section_hottest_turns(profile: RunProfile) -> str:
    """Build the Heat Map -- Top 20 Hottest Turns section."""
    lines: list[str] = []
    lines.append("## Heat Map -- Top 20 Hottest Turns\n")

    # Collect all turns across all sessions
    all_turns: list[tuple[ProfiledTurn, str]] = []
    for sess in profile.sessions:
        for pt in sess.turns:
            all_turns.append((pt, sess.session_id))

    # Sort by session_cost_tokens descending (absolute value for ranking, but show actual)
    all_turns.sort(key=lambda t: abs(t[0].session_cost_tokens), reverse=True)

    # Top 20
    for rank, (pt, _sess_id) in enumerate(all_turns[:20], start=1):
        ts = _fmt_timestamp(pt.raw.timestamp)
        delta_str = f"+{_fmt_int(pt.delta)}" if pt.delta >= 0 else _fmt_int(pt.delta)
        lines.append(
            f"#{rank} [{ts}] {pt.phase} "
            f"| {delta_str} tokens "
            f"| x{pt.remaining_calls_in_segment} remaining "
            f"| {_fmt_int(pt.session_cost_tokens)} session cost"
        )

        # Tool attribution sub-entries
        for attr in pt.tool_attributions:
            # Skip overhead if < 10%
            if attr.tool_name == "_assistant_overhead" and abs(attr.fraction_of_delta) < 0.10:
                continue
            pct = _fmt_pct(attr.fraction_of_delta * 100)
            lines.append(f"  - {attr.tool_name}: {_fmt_int(attr.attributed_session_cost)} session cost ({pct})")

        lines.append("")

    return "\n".join(lines)


def _section_hottest_tools(profile: RunProfile) -> str:
    """Build the Heat Map -- Top 20 Hottest Tools section."""
    lines: list[str] = []
    lines.append("## Heat Map -- Top 20 Hottest Tools\n")

    # Aggregate across all turns by attributed_session_cost
    tool_costs: Counter[str] = Counter()
    tool_calls: Counter[str] = Counter()
    tool_tokens_added: Counter[str] = Counter()

    for sess in profile.sessions:
        for pt in sess.turns:
            for attr in pt.tool_attributions:
                if attr.tool_name == "_assistant_overhead":
                    continue
                tool_costs[attr.tool_name] += attr.attributed_session_cost
                tool_calls[attr.tool_name] += 1
                tool_tokens_added[attr.tool_name] += attr.attributed_delta

    total_cost = sum(tool_costs.values())

    lines.append("| Tool | Calls | Tokens Added | Session Cost | % |")
    lines.append("| --- | --- | --- | --- | --- |")

    for tool_name, cost in tool_costs.most_common(20):
        pct = (cost / total_cost * 100) if total_cost > 0 else 0.0
        lines.append(
            f"| {tool_name} "
            f"| {tool_calls[tool_name]} "
            f"| {_fmt_int(tool_tokens_added[tool_name])} "
            f"| {_fmt_int(cost)} "
            f"| {_fmt_pct(pct)} |"
        )

    return "\n".join(lines)


def _section_phase_breakdown(profile: RunProfile) -> str:
    """Build the Phase Breakdown section."""
    lines: list[str] = []
    lines.append("## Phase Breakdown\n")

    for sess in profile.sessions:
        if len(profile.sessions) > 1:
            lines.append(f"### {sess.session_id}\n")

        lines.append("| Phase | Turns | Delta Sum | Session Cost | Top Tools |")
        lines.append("| --- | --- | --- | --- | --- |")

        for phase in sess.phases:
            top_tools_str = ", ".join(f"{name} ({_fmt_int(cost)})" for name, cost in phase.top_tools[:5])
            lines.append(
                f"| {phase.phase} "
                f"| {phase.turn_count} "
                f"| {_fmt_int(phase.delta_sum)} "
                f"| {_fmt_int(phase.session_cost_sum)} "
                f"| {top_tools_str} |"
            )

        lines.append("")

    return "\n".join(lines)


def _section_cost_buckets(profile: RunProfile) -> str:
    """Build the Cost Buckets section."""
    lines: list[str] = []
    lines.append("## Cost Buckets\n")

    lines.append("| Phase | Input | Cache Create | Cache Read | Output | Total |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for sess in profile.sessions:
        for phase in sess.phases:
            bb = phase.bucket_breakdown
            lines.append(
                f"| {phase.phase} "
                f"| {_fmt_int(bb.input_tokens)} "
                f"| {_fmt_int(bb.cache_creation_tokens)} "
                f"| {_fmt_int(bb.cache_read_tokens)} "
                f"| {_fmt_int(bb.output_tokens)} "
                f"| {_fmt_int(bb.total)} |"
            )

    return "\n".join(lines)


def _section_dollar_costs(profile: RunProfile) -> str:
    """Build the Dollar Costs section."""
    lines: list[str] = []
    lines.append("## Dollar Costs\n")

    lines.append("| Phase | Input | Cache Create | Cache Read | Output | Total |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for sess in profile.sessions:
        for phase in sess.phases:
            dc = phase.dollar_cost
            lines.append(
                f"| {phase.phase} "
                f"| {_fmt_dollars(dc.input_cost)} "
                f"| {_fmt_dollars(dc.cache_creation_cost)} "
                f"| {_fmt_dollars(dc.cache_read_cost)} "
                f"| {_fmt_dollars(dc.output_cost)} "
                f"| {_fmt_dollars(dc.total_cost)} |"
            )

    return "\n".join(lines)


def _section_compaction_events(profile: RunProfile) -> str:
    """Build the Compaction Events section."""
    lines: list[str] = []
    lines.append("## Compaction Events\n")

    all_events: list[CompactionEvent] = []
    for sess in profile.sessions:
        all_events.extend(sess.compaction_events)

    if not all_events:
        lines.append("No compaction events detected.")
        return "\n".join(lines)

    lines.append("| Segment | Turn Index | Context Before | Context After | Reduction |")
    lines.append("| --- | --- | --- | --- | --- |")

    for evt in all_events:
        lines.append(
            f"| {evt.segment_id} "
            f"| {evt.turn_index} "
            f"| {_fmt_int(evt.context_before)} "
            f"| {_fmt_int(evt.context_after)} "
            f"| {_fmt_int(evt.reduction_tokens)} |"
        )

    return "\n".join(lines)


def _section_methodology() -> str:
    """Build the Methodology section."""
    lines: list[str] = []
    lines.append("## Methodology\n")
    lines.append(
        "**Session cost** (heat) measures the cumulative impact of each token added to the "
        "context window. For each turn, the delta (change in context window size) is multiplied "
        "by the number of remaining API calls in the current segment:\n"
    )
    lines.append("```")
    lines.append("session_cost = delta * remaining_calls_in_segment")
    lines.append("```\n")
    lines.append(
        "A token added early in the session is billed on every subsequent turn, so it has a "
        "higher session cost than a token added near the end. Compaction events (context-window "
        "summarisation) reset the segment, since tokens after compaction only persist for the "
        "remainder of the new segment.\n"
    )
    lines.append(
        "Tool attributions distribute each turn's delta proportionally across tool results "
        "by their content size (characters), with the remainder assigned to assistant overhead."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_markdown(profile: RunProfile) -> str:
    """Generate a full markdown report from a RunProfile.

    Returns the complete markdown document as a string.
    """
    sections: list[str] = [
        f"# Token Profile: {profile.run_id}\n",
        _section_summary(profile),
        _section_hottest_turns(profile),
        _section_hottest_tools(profile),
        _section_phase_breakdown(profile),
        _section_cost_buckets(profile),
        _section_dollar_costs(profile),
        _section_compaction_events(profile),
        _section_methodology(),
    ]

    return "\n\n".join(sections) + "\n"

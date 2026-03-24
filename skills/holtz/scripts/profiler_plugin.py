"""Holtz profiler plugin — session-type-specific phase detection and patterns.

Loaded at runtime by the token profiler CLI via::

    python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py

This file is standalone: it does NOT import from token_profiler at runtime.
The ProfilerPlugin protocol is structural (duck typing), so we just
implement the right methods and attribute.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from token_profiler.models import RawTurn

# ---------------------------------------------------------------------------
# Phase detection patterns (order matters: later = higher priority)
# ---------------------------------------------------------------------------

_PHASE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("recon", re.compile(r"Phase[ \t]*0|recon|phase-0-recon", re.IGNORECASE)),
    ("phase-1", re.compile(r"Phase[ \t]*1|Doc.*Audit|doc.*claim", re.IGNORECASE)),
    ("phase-2", re.compile(r"Phase[ \t]*2|Test.*Quality|Test.*Audit", re.IGNORECASE)),
    ("phase-3", re.compile(r"Phase[ \t]*3|Adversarial.*Code|Adversarial.*Audit", re.IGNORECASE)),
    ("merge", re.compile(r"Merge|Justine.*findings|classify.*findings", re.IGNORECASE)),
    ("fix-loop", re.compile(r"Phase[ \t]*4|TDD|fix[ \t]*loop|failing[ \t]*test", re.IGNORECASE)),
    ("convergence", re.compile(r"converg|SUMMARY\.md|final[ \t]*commit", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# Subagent naming patterns
# ---------------------------------------------------------------------------

_SUBAGENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("justine", re.compile(r"Justine", re.IGNORECASE)),
    ("test-audit", re.compile(r"test[ \t]+files.*audit|read[ \t]+all.*test", re.IGNORECASE)),
    ("source-audit", re.compile(r"source[ \t]+modules|subtle[ \t]+bugs|analyze.*modules", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# Detection keywords (checked in first 10 turns)
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"holtz", re.IGNORECASE),
    re.compile(r"phase[ \t]*0", re.IGNORECASE),
    re.compile(r"full[ \t]+audit", re.IGNORECASE),
]


class HoltzProfilerPlugin:
    """Holtz-specific profiler plugin implementing the ProfilerPlugin protocol."""

    name: str = "holtz"

    def detect(self, turns: list[RawTurn]) -> bool:
        """Return True if the session looks like a Holtz audit run.

        Checks the first 10 turns for "holtz", "phase 0", or "full audit".
        """
        for turn in turns[:10]:
            text = turn.assistant_text
            for pattern in _DETECT_PATTERNS:
                if pattern.search(text):
                    return True
        return False

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Map each turn index to a phase label via content heuristics.

        Once a phase is detected, all subsequent turns inherit it until
        a new phase marker is found.  Turns before the first detected
        phase get the label "unknown".
        """
        labels: dict[int, str] = {}
        current_phase = "unknown"

        for turn in turns:
            detected = self._detect_phase(turn.assistant_text)
            if detected is not None:
                current_phase = detected
            labels[turn.index] = current_phase

        return labels

    def name_subagent(self, turns: list[RawTurn]) -> str | None:
        """Identify a subagent session by matching the first turn's text."""
        if not turns:
            return None

        text = turns[0].assistant_text
        for agent_name, pattern in _SUBAGENT_PATTERNS:
            if pattern.search(text):
                return agent_name
        return None

    def enrich_profile(self, profile: object) -> None:
        """No-op for now (future: trace file integration)."""

    def optimization_patterns(self) -> list[dict[str, str]]:
        """Return known Holtz-specific optimization patterns."""
        return [
            {
                "name": "Heavy Early Read",
                "symptom": "Recon phase reads every file, causing large context window before any analysis begins.",
                "fix": "Use targeted reads based on manifest/config files; defer deep reads to audit phases.",
            },
            {
                "name": "Recon Bloat",
                "symptom": "Phase 0 accounts for >30% of total session cost despite producing no findings.",
                "fix": "Cap recon to directory listings and key config files; let audit subagents read source.",
            },
            {
                "name": "Chatty Tool Loop",
                "symptom": "Many small sequential tool calls (Read, Grep) that each add to context window.",
                "fix": "Batch related reads into fewer, larger tool calls; "
                "use glob patterns instead of individual reads.",
            },
            {
                "name": "Subagent Over-delegation",
                "symptom": "Subagent sessions duplicate reads already done by the main session.",
                "fix": "Pass relevant context summaries to subagents; "
                "avoid re-reading files the main session already consumed.",
            },
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_phase(text: str) -> str | None:
        """Return the highest-priority phase label matching *text*, or None."""
        # Iterate in order; later patterns have higher priority, so we
        # keep scanning and return the last match.
        matched: str | None = None
        for phase_label, pattern in _PHASE_PATTERNS:
            if pattern.search(text):
                matched = phase_label
        return matched

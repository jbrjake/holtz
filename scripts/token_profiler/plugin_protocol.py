"""Plugin protocol for session-type-specific profiling logic."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from token_profiler.models import RawTurn, SessionProfile


@runtime_checkable
class ProfilerPlugin(Protocol):
    """Interface that session-type plugins must satisfy.

    Plugins provide domain-specific knowledge about a particular kind
    of Claude Code session (e.g., a Holtz audit run, a coding session,
    a research task) so the profiler can label phases and surface
    optimization patterns.
    """

    name: str

    def detect(self, turns: list[RawTurn]) -> bool:
        """Return True if this plugin recognises the session."""
        ...

    def label_phases(self, turns: list[RawTurn]) -> dict[int, str]:
        """Map turn indices to phase labels."""
        ...

    def name_subagent(self, turns: list[RawTurn]) -> str | None:
        """Return a human-readable name for a subagent session, or None."""
        ...

    def enrich_profile(self, profile: SessionProfile) -> None:
        """Mutate *profile* with plugin-specific enrichments."""
        ...

    def optimization_patterns(self) -> list[dict]:
        """Return a list of known optimization patterns this plugin can detect."""
        ...

"""Schema freshness gate — verifies hook_schema.py matches current Claude Code docs.

This test fetches the official docs page and extracts valid field values.
If Claude Code changes their spec, this test fails BEFORE we ship.

Requires network access. Skipped in offline/CI environments.
"""
from __future__ import annotations

import urllib.request

import pytest

from hook_schema import (
    PRETOOLUSE_VALID_DECISIONS,
    SPEC_URL,
    STOP_VALID_DECISIONS,
)


def _fetch_docs() -> str:
    """Fetch the Claude Code hooks docs page. Raises on failure."""
    req = urllib.request.Request(SPEC_URL, headers={"User-Agent": "holtz-schema-check/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _quoted_in(value: str, html: str) -> bool:
    """Check if a value appears quoted in HTML (handles &quot; entities)."""
    return f'"{value}"' in html or f"&quot;{value}&quot;" in html


@pytest.fixture(scope="module")
def docs_html() -> str:
    try:
        return _fetch_docs()
    except Exception as e:
        pytest.skip(f"Cannot fetch docs (offline?): {e}")


@pytest.mark.network
class TestPreToolUseDecisions:
    """Verify permissionDecision enum matches the live docs."""

    def test_allow_in_docs(self, docs_html: str):
        assert _quoted_in("allow", docs_html)

    def test_deny_in_docs(self, docs_html: str):
        assert _quoted_in("deny", docs_html)

    def test_ask_in_docs(self, docs_html: str):
        assert _quoted_in("ask", docs_html)

    def test_defer_in_docs(self, docs_html: str):
        assert _quoted_in("defer", docs_html)

    def test_block_not_in_pretooluse_decisions(self):
        """'block' was deprecated for PreToolUse — must not be in our schema."""
        assert "block" not in PRETOOLUSE_VALID_DECISIONS

    def test_no_extra_decisions(self, docs_html: str):
        """Every value in our schema must appear in the docs."""
        for decision in PRETOOLUSE_VALID_DECISIONS:
            assert _quoted_in(decision, docs_html), (
                f"'{decision}' is in our schema but not found in docs — stale?"
            )


@pytest.mark.network
class TestStopDecisions:

    def test_block_is_only_stop_decision(self):
        assert STOP_VALID_DECISIONS == {"block"}

    def test_approve_not_valid_for_stop(self):
        """'approve' was never a valid Stop decision."""
        assert "approve" not in STOP_VALID_DECISIONS

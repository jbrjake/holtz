"""Shared utilities for Holtz plugin hooks.

All hooks read JSON from stdin, write reason to stderr, and exit 0/1/2.
Exit 0 = allow, exit 1 = warn (non-blocking), exit 2 = block.
"""
from __future__ import annotations

import json
import sys
from typing import Any


def read_event() -> dict[str, Any]:
    """Read and parse the hook event JSON from stdin.

    Returns an empty dict if stdin is empty or unparseable,
    so hooks degrade gracefully rather than crashing.
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def exit_ok() -> None:
    """Allow the tool call. Exit 0 with no output."""
    sys.exit(0)


def exit_warn(msg: str) -> None:
    """Warn but allow. Exit 1, message to stderr."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def exit_block(msg: str) -> None:
    """Block the tool call. Exit 2, message to stderr."""
    print(msg, file=sys.stderr)
    sys.exit(2)

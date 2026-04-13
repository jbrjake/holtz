#!/usr/bin/env python3
"""Regenerate tests/fixtures/hook_output_schema.json from hook_schema.py.

Run this when Claude Code updates their hook protocol or when
hook_schema.py is updated after a freshness check.

Usage:
    python scripts/refresh_hook_schema.py          # preview to stdout
    python scripts/refresh_hook_schema.py --write   # write to fixture file
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from hook_schema import (  # noqa: E402
    POSTTOOLUSE_HSO_FIELDS,
    POSTTOOLUSE_VALID_DECISIONS,
    PRETOOLUSE_HSO_FIELDS,
    PRETOOLUSE_VALID_DECISIONS,
    STOP_VALID_DECISIONS,
    UNIVERSAL_FIELDS,
    USERPROMPTSUBMIT_HSO_FIELDS,
    USERPROMPTSUBMIT_VALID_DECISIONS,
)

FIXTURE_PATH = os.path.join(REPO_ROOT, "tests", "fixtures", "hook_output_schema.json")


def generate_schema() -> dict:
    """Generate the schema fixture from hook_schema.py constants."""
    return {
        "_comment": (
            "Expected hook output structures per event type. "
            "Regenerate with: python scripts/refresh_hook_schema.py --write"
        ),
        "PreToolUse": {
            "required_wrapper_key": "hookSpecificOutput",
            "required_fields": ["hookEventName", "permissionDecision"],
            "optional_fields": sorted(
                PRETOOLUSE_HSO_FIELDS - {"hookEventName", "permissionDecision"}
            ),
            "valid_decisions": sorted(PRETOOLUSE_VALID_DECISIONS),
            "decision_field": "permissionDecision",
            "hookEventName": "PreToolUse",
            "universal_fields": sorted(UNIVERSAL_FIELDS),
        },
        "PostToolUse": {
            "required_wrapper_key": None,
            "valid_top_level_decisions": sorted(POSTTOOLUSE_VALID_DECISIONS),
            "hookSpecificOutput_fields": sorted(POSTTOOLUSE_HSO_FIELDS),
            "universal_fields": sorted(UNIVERSAL_FIELDS),
        },
        "Stop": {
            "required_wrapper_key": None,
            "valid_decisions": sorted(STOP_VALID_DECISIONS),
            "decision_field": "decision",
            "forbidden_fields": ["hookSpecificOutput"],
            "universal_fields": ["systemMessage", "reason"],
        },
        "SubagentStop": {
            "required_wrapper_key": None,
            "valid_decisions": sorted(STOP_VALID_DECISIONS),
            "decision_field": "decision",
            "forbidden_fields": ["hookSpecificOutput"],
            "universal_fields": ["systemMessage", "reason"],
        },
        "UserPromptSubmit": {
            "required_wrapper_key": None,
            "valid_top_level_decisions": sorted(USERPROMPTSUBMIT_VALID_DECISIONS),
            "hookSpecificOutput_fields": sorted(USERPROMPTSUBMIT_HSO_FIELDS),
            "universal_fields": sorted(UNIVERSAL_FIELDS),
        },
    }


def main() -> int:
    schema = generate_schema()
    output = json.dumps(schema, indent=2) + "\n"

    if "--write" in sys.argv:
        with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {FIXTURE_PATH}")
        return 0

    print(output)
    print("(preview only — pass --write to update the fixture file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

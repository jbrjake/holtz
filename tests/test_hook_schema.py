"""Tests that hook_schema.py is internally consistent and complete."""
import pytest

from hook_schema import (
    PRETOOLUSE_VALID_DECISIONS,
    STOP_VALID_DECISIONS,
    UNIVERSAL_FIELDS,
    validate_hook_output,
)


def test_pretooluse_decisions_are_strings():
    assert all(isinstance(d, str) for d in PRETOOLUSE_VALID_DECISIONS)


def test_pretooluse_has_deny():
    """The value that blocks a tool call must exist."""
    assert "deny" in PRETOOLUSE_VALID_DECISIONS


def test_pretooluse_does_not_have_block():
    """'block' is the OLD deprecated value — must not be listed."""
    assert "block" not in PRETOOLUSE_VALID_DECISIONS


def test_stop_only_has_block():
    """Stop hooks only support 'block' for decision."""
    assert STOP_VALID_DECISIONS == {"block"}


def test_validate_pretooluse_allow():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        },
    })
    assert errs == []


def test_validate_pretooluse_deny():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "blocked",
        },
    })
    assert errs == []


def test_validate_pretooluse_rejects_block():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
        },
    })
    assert len(errs) == 1
    assert "block" in errs[0]


def test_validate_pretooluse_rejects_continue_false_with_deny():
    errs = validate_hook_output("PreToolUse", {
        "continue": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        },
    })
    assert any("continue" in e for e in errs)


def test_validate_stop_allow_empty():
    errs = validate_hook_output("Stop", {})
    assert errs == []


def test_validate_stop_block():
    errs = validate_hook_output("Stop", {"decision": "block", "reason": "not done"})
    assert errs == []


def test_validate_stop_rejects_approve():
    errs = validate_hook_output("Stop", {"decision": "approve", "reason": "done"})
    assert len(errs) == 1


def test_validate_posttooluse_allow():
    errs = validate_hook_output("PostToolUse", {"continue": True, "suppressOutput": True})
    assert errs == []


def test_validate_posttooluse_with_hook_specific():
    errs = validate_hook_output("PostToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "warning",
        },
    })
    assert errs == []

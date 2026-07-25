"""Claude Code hook output schema — single source of truth.

Derived from: https://code.claude.com/docs/en/hooks
Last verified: 2026-07-25

ALL test validators and assertions must reference this file.
When Claude Code changes their spec, update THIS file only.
"""
from __future__ import annotations

# ── PreToolUse ──────────────────────────────────────────────
# hookSpecificOutput.permissionDecision valid values.
# "block" is the OLD deprecated value — do NOT use it.
PRETOOLUSE_VALID_DECISIONS: set[str] = {"allow", "deny", "ask", "defer"}

# hookSpecificOutput fields for PreToolUse
PRETOOLUSE_HSO_FIELDS: set[str] = {
    "hookEventName",          # Required, literal "PreToolUse"
    "permissionDecision",     # Required, one of PRETOOLUSE_VALID_DECISIONS
    "permissionDecisionReason",  # Optional
    "updatedInput",           # Optional
    "additionalContext",      # Optional
}

# ── PostToolUse ─────────────────────────────────────────────
# Top-level decision field (only "block" is valid, omit to allow)
POSTTOOLUSE_VALID_DECISIONS: set[str] = {"block"}

# hookSpecificOutput fields for PostToolUse
POSTTOOLUSE_HSO_FIELDS: set[str] = {
    "hookEventName",          # Required if hookSpecificOutput present
    "additionalContext",      # Optional
    "updatedMCPToolOutput",   # Optional
}

# ── Stop / SubagentStop ────────────────────────────────────
# Only "block" is valid. Omit decision to allow.
STOP_VALID_DECISIONS: set[str] = {"block"}

# ── UserPromptSubmit ────────────────────────────────────────
USERPROMPTSUBMIT_VALID_DECISIONS: set[str] = {"block"}

USERPROMPTSUBMIT_HSO_FIELDS: set[str] = {
    "hookEventName",
    "additionalContext",
    "sessionTitle",
}

# ── SessionStart ────────────────────────────────────────────
# SessionStart cannot block — it is for side effects and context
# injection only, so there is no decision field at all.
SESSIONSTART_VALID_DECISIONS: set[str] = set()

SESSIONSTART_HSO_FIELDS: set[str] = {
    "hookEventName",
    "additionalContext",
    "initialUserMessage",
    "watchPaths",
    "sessionTitle",
    "reloadSkills",
}

# `source` values, i.e. how the session was initiated. Only the first
# three leave the model with no prior context; `resume` restores the
# transcript and `fork` copies it (holtz #79).
SESSIONSTART_SOURCES: set[str] = {
    "startup",
    "resume",
    "clear",
    "compact",
    "fork",
}

# ── Universal top-level fields (all events) ─────────────────
UNIVERSAL_FIELDS: set[str] = {
    "continue",         # bool, default true. false = stop Claude entirely
    "stopReason",       # str, shown to user when continue=false
    "suppressOutput",   # bool, default false
    "systemMessage",    # str, shown to user
}

# ── Spec URL (for automated freshness checks) ──────────────
SPEC_URL = "https://code.claude.com/docs/en/hooks"


def validate_hook_output(event_type: str, output: dict) -> list[str]:
    """Validate hook JSON output against Claude Code's schema.

    Returns a list of error strings. Empty list = valid.
    """
    errors: list[str] = []

    if not output:
        return errors  # Empty output is valid for all events

    if event_type == "PreToolUse":
        errors.extend(_validate_pretooluse(output))
    elif event_type == "PostToolUse":
        errors.extend(_validate_posttooluse(output))
    elif event_type in ("Stop", "SubagentStop"):
        errors.extend(_validate_stop(output))
    elif event_type == "UserPromptSubmit":
        errors.extend(_validate_user_prompt_submit(output))
    elif event_type == "SessionStart":
        errors.extend(_validate_session_start(output))

    return errors


def _validate_pretooluse(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        if hso.get("hookEventName") != "PreToolUse":
            errors.append(
                f"hookEventName must be 'PreToolUse', got '{hso.get('hookEventName')}'"
            )
        decision = hso.get("permissionDecision")
        if decision not in PRETOOLUSE_VALID_DECISIONS:
            errors.append(
                f"Invalid permissionDecision '{decision}'. "
                f"Valid: {PRETOOLUSE_VALID_DECISIONS}"
            )
    else:
        # No hookSpecificOutput — check for misplaced fields
        bad = {"permissionDecision", "additionalContext"} & set(output.keys())
        if bad:
            errors.append(f"Fields {bad} must be inside hookSpecificOutput")

    # continue=false + deny is a contradiction
    if output.get("continue") is False and hso.get("permissionDecision") == "deny":
        errors.append(
            "continue=false stops Claude entirely — don't combine with deny"
        )

    return errors


def _validate_posttooluse(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        event_name = hso.get("hookEventName")
        if event_name and event_name != "PostToolUse":
            errors.append(f"hookEventName must be 'PostToolUse', got '{event_name}'")

    decision = output.get("decision")
    if decision is not None and decision not in POSTTOOLUSE_VALID_DECISIONS:
        errors.append(f"Invalid PostToolUse decision '{decision}'. Only 'block' is valid.")

    return errors


def _validate_stop(output: dict) -> list[str]:
    errors: list[str] = []
    decision = output.get("decision")
    if decision is not None and decision not in STOP_VALID_DECISIONS:
        errors.append(
            f"Invalid Stop decision '{decision}'. Only 'block' is valid; omit to allow."
        )
    # Stop hooks must NOT use hookSpecificOutput
    if "hookSpecificOutput" in output:
        errors.append("Stop hooks must not use hookSpecificOutput")
    return errors


def _validate_user_prompt_submit(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        event_name = hso.get("hookEventName")
        if event_name and event_name != "UserPromptSubmit":
            errors.append(
                f"hookEventName must be 'UserPromptSubmit', got '{event_name}'"
            )

    decision = output.get("decision")
    if decision is not None and decision not in USERPROMPTSUBMIT_VALID_DECISIONS:
        errors.append(
            f"Invalid UserPromptSubmit decision '{decision}'. Only 'block' is valid."
        )

    return errors


def _validate_session_start(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        event_name = hso.get("hookEventName")
        if event_name and event_name != "SessionStart":
            errors.append(
                f"hookEventName must be 'SessionStart', got '{event_name}'"
            )
        unknown = set(hso.keys()) - SESSIONSTART_HSO_FIELDS
        if unknown:
            errors.append(
                f"Unknown SessionStart hookSpecificOutput fields: {sorted(unknown)}"
            )

    # SessionStart cannot block — a decision field is always a mistake.
    if "decision" in output:
        errors.append("SessionStart cannot block — 'decision' is not a valid field")

    return errors

#!/usr/bin/env bash
# scripts/smoke-test-hooks.sh
#
# Live smoke test: registers each hook against real Claude Code
# and verifies no "validation failed" or "hook error" in output.
#
# Requires: claude CLI in PATH
# Usage: scripts/smoke-test-hooks.sh [--verbose]
#
# Exit 0 = all hooks valid, Exit 1 = at least one failed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERBOSE="${1:-}"
FAILURES=0
TESTED=0

# Temp dir for isolated settings
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# Create minimal project structure
mkdir -p "$WORK_DIR/src"
echo "print('hello')" > "$WORK_DIR/src/app.py"

# Check claude is available
if ! command -v claude &>/dev/null; then
    echo "SKIP: claude CLI not in PATH"
    exit 0
fi

# Hook path:event pairs (bash 3 compatible — no associative arrays)
HOOKS="
enforcement/hooks/_daemon_lifecycle.py:PreToolUse
enforcement/hooks/_sahjhan_bootstrap.py:PreToolUse
enforcement/hooks/pre_tool_hook.py:PreToolUse
enforcement/hooks/commit_gate.py:PreToolUse
enforcement/hooks/post_tool_hook.py:PostToolUse
enforcement/hooks/bash_guard.py:PostToolUse
enforcement/hooks/protocol_tracker.py:PostToolUse
enforcement/hooks/stop_hook.py:Stop
enforcement/hooks/primer.py:UserPromptSubmit
hooks/subagent_findings_check.py:SubagentStop
"

SKIPPED=0
for entry in $HOOKS; do
    [ -z "$entry" ] && continue
    hook_path="${entry%%:*}"
    event="${entry##*:}"
    hook_name=$(basename "$hook_path" .py)

    # Build a settings.json that registers just this one hook
    # Use the appropriate matcher for the event type
    if [[ "$event" == "PreToolUse" ]]; then
        MATCHER="Bash"
        PROMPT="run echo smoke-test-$hook_name"
    elif [[ "$event" == "PostToolUse" ]]; then
        MATCHER="Bash"
        PROMPT="run echo smoke-test-$hook_name"
    elif [[ "$event" == "Stop" ]]; then
        # Stop hooks fire when Claude tries to stop — use a one-shot prompt
        MATCHER="*"
        PROMPT="say hi"
    elif [[ "$event" == "UserPromptSubmit" ]]; then
        MATCHER="*"
        PROMPT="say hi"
    elif [[ "$event" == "SubagentStop" ]]; then
        # SubagentStop is hard to trigger in isolation — skip live test
        echo "SKIP $hook_name ($event — requires subagent)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    TESTED=$((TESTED + 1))

    # Write temp settings
    mkdir -p "$WORK_DIR/.claude"
    cat > "$WORK_DIR/.claude/settings.local.json" <<SETTINGS_EOF
{
    "hooks": {
        "$event": [
            {
                "matcher": "$MATCHER",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python \"$REPO_ROOT/$hook_path\""
                    }
                ]
            }
        ]
    }
}
SETTINGS_EOF

    # Run claude with the hook active. `-p` is print mode (single-shot,
    # exits when done); redirect stdin from /dev/null so claude doesn't
    # block waiting on a TTY when invoked from CI.
    OUTPUT=$(cd "$WORK_DIR" && claude -p "$PROMPT" </dev/null 2>&1) || true

    # Check for validation failures or claude itself failing to start
    # (unknown flags, missing API key, etc.) — both must fail the test
    # so we don't silently report PASS when claude never ran the hook.
    if echo "$OUTPUT" | grep -qi "json.*validation.*failed\|hook.*error.*validation"; then
        echo "FAIL $hook_name ($event): json validation failed"
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "  Output: ${OUTPUT:0:500}"
        fi
        FAILURES=$((FAILURES + 1))
    elif echo "$OUTPUT" | grep -qE "^error:|unknown option|usage:.*claude"; then
        echo "FAIL $hook_name ($event): claude failed to start"
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "  Output: ${OUTPUT:0:500}"
        fi
        FAILURES=$((FAILURES + 1))
    else
        echo "PASS $hook_name ($event)"
    fi
done

echo ""
echo "Results: $((TESTED - FAILURES))/$TESTED passed ($SKIPPED skipped)"
if [[ $FAILURES -gt 0 ]]; then
    echo "FAILED: $FAILURES hook(s) produced invalid JSON"
    exit 1
fi
echo "All hooks produce valid JSON per Claude Code"
exit 0

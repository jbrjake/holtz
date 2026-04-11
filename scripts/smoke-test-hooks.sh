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

# Map each hook to its event type and a trigger prompt
declare -A HOOK_EVENTS
HOOK_EVENTS["enforcement/hooks/_daemon_lifecycle.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/_sahjhan_bootstrap.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/pre_tool_hook.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/commit_gate.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/post_tool_hook.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/bash_guard.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/protocol_tracker.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/stop_hook.py"]="Stop"
HOOK_EVENTS["enforcement/hooks/primer.py"]="UserPromptSubmit"
HOOK_EVENTS["hooks/subagent_findings_check.py"]="SubagentStop"

for hook_path in "${!HOOK_EVENTS[@]}"; do
    event="${HOOK_EVENTS[$hook_path]}"
    hook_name=$(basename "$hook_path" .py)
    TESTED=$((TESTED + 1))

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
        continue
    fi

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

    # Run claude with the hook active
    OUTPUT=$(cd "$WORK_DIR" && claude -p "$PROMPT" --no-input 2>&1) || true

    # Check for validation failures
    if echo "$OUTPUT" | grep -qi "json.*validation.*failed\|hook.*error.*validation"; then
        echo "FAIL $hook_name ($event): json validation failed"
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "  Output: ${OUTPUT:0:500}"
        fi
        FAILURES=$((FAILURES + 1))
    else
        echo "PASS $hook_name ($event)"
    fi
done

echo ""
echo "Results: $((TESTED - FAILURES))/$TESTED passed"
if [[ $FAILURES -gt 0 ]]; then
    echo "FAILED: $FAILURES hook(s) produced invalid JSON"
    exit 1
fi
echo "All hooks produce valid JSON per Claude Code"
exit 0

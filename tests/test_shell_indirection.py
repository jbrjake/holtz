"""An indirect sahjhan invocation must be recognized as a sahjhan invocation.

The detectors matched a literal ``sahjhan`` token, so any spelling that put
the binary behind a variable or a shell wrapper was invisible to them. Two
consequences, one in each direction:

* The stall counter treats a re-sync it cannot see as another silent
  command, so the escape from the block increments the block.
* ``_bash_references_blocked_sahjhan`` guards the human-only attestation
  channel — ``event quiz_exhausted_resolved``, the event that clears a lens
  whose re-read quiz the agent failed. Denying the direct spelling while
  allowing ``"$SAH" event quiz_exhausted_resolved`` leaves the channel open
  to the one party it exists to exclude.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.hook_e2e]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, HOOKS_DIR)

from _shell_norm import resolve_indirection  # noqa: E402

# Spellings of one command. Every one of these runs `sahjhan status`.
INDIRECT_FORMS = [
    'SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; "$SAH" status',
    'SAH=$CLAUDE_PLUGIN_ROOT/bin/sahjhan && $SAH status',
    'export SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; ${SAH} status',
    'eval "$CLAUDE_PLUGIN_ROOT/bin/sahjhan status"',
    "eval '$CLAUDE_PLUGIN_ROOT/bin/sahjhan status'",
    'SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; eval "$SAH status"',
    'bash -c "$CLAUDE_PLUGIN_ROOT/bin/sahjhan status"',
    'sh -c "sahjhan status"',
    # Chained assignment: the value of one variable built from another.
    'ROOT=$CLAUDE_PLUGIN_ROOT; SAH=$ROOT/bin/sahjhan; "$SAH" status',
]


class TestResolveIndirection:
    """The normalizer rewrites indirect spellings into direct ones."""

    @pytest.mark.parametrize("command", INDIRECT_FORMS)
    def test_sahjhan_becomes_visible(self, command):
        assert "sahjhan" in resolve_indirection(command).lower(), (
            f"Normalizer left the invocation hidden: {command}"
        )

    def test_direct_command_is_unchanged(self):
        cmd = 'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" status'
        assert resolve_indirection(cmd) == cmd

    def test_unknown_variable_is_left_alone(self):
        """Only variables assigned in the same command are substituted."""
        cmd = '"$MYSTERY" status'
        assert resolve_indirection(cmd) == cmd

    def test_terminates_on_self_referential_assignment(self):
        """A cycle must not spin — bounded passes, not fixpoint iteration."""
        resolve_indirection("A=$B; B=$A; $A status")


class TestIndirectionDetectedByStallCounter:
    """contains_sahjhan_cmd sees through indirection."""

    @pytest.mark.parametrize("command", INDIRECT_FORMS)
    def test_indirect_resync_is_recognized(self, command):
        from _protocol_cache import contains_sahjhan_cmd
        assert contains_sahjhan_cmd(command), (
            f"Indirect re-sync must clear the stall, not increment it: {command}"
        )

    def test_non_sahjhan_indirection_is_not_recognized(self):
        from _protocol_cache import contains_sahjhan_cmd
        assert not contains_sahjhan_cmd('LS=/bin/ls; "$LS" -la')


def _hook_decision(command: str, cwd: str = REPO_ROOT) -> tuple[str, str]:
    event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, "_sahjhan_bootstrap.py")],
        input=json.dumps(event), capture_output=True, text=True,
        cwd=cwd, timeout=20,
    )
    payload = json.loads(result.stdout).get("hookSpecificOutput", {})
    return payload.get("permissionDecision", ""), payload.get("permissionDecisionReason", "")


class TestHumanOnlyChannelNotReachableByIndirection:
    """The blocked-subcommand guard sees through indirection.

    ``event quiz_exhausted_resolved`` is denied to the agent so that the only
    way to record it is a person typing ``! sahjhan …``, which the harness
    runs outside the tool-call path. A spelling the guard cannot parse is a
    second door into that channel.
    """

    def test_direct_form_is_denied(self):
        decision, reason = _hook_decision("sahjhan event quiz_exhausted_resolved")
        assert decision == "deny", "Baseline: the direct spelling must be denied"
        assert "quiz_exhausted_resolved" in reason

    @pytest.mark.parametrize("template", [
        'SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; "$SAH" event quiz_exhausted_resolved',
        'SAH=$CLAUDE_PLUGIN_ROOT/bin/sahjhan && $SAH event quiz_exhausted_resolved',
        'eval "$CLAUDE_PLUGIN_ROOT/bin/sahjhan event quiz_exhausted_resolved"',
        'bash -c "sahjhan event quiz_exhausted_resolved"',
        'ROOT=$CLAUDE_PLUGIN_ROOT; SAH=$ROOT/bin/sahjhan; $SAH event quiz_exhausted_resolved',
    ])
    def test_indirect_forms_are_denied_too(self, template):
        decision, _ = _hook_decision(template)
        assert decision == "deny", (
            f"Indirection must not open the human-only channel: {template}"
        )

    def test_non_sahjhan_command_still_allowed(self):
        """The guard must not start denying ordinary work."""
        decision, _ = _hook_decision('OUT=/tmp/x; grep -rn TODO src/')
        assert decision == "allow"

    def test_taught_command_still_allowed(self):
        """A permitted subcommand reached indirectly stays permitted."""
        decision, _ = _hook_decision(
            'SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; "$SAH" status',
        )
        assert decision == "allow"

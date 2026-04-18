"""End-to-end audit flow tests — run the actual hook chain against a real
daemon and walk transitions the way Claude Code would during a Holtz audit.

These tests are how we know the whole machine actually works — not just that
individual hooks handle JSON correctly, but that a Write/Edit in fix_loop
is actually blocked, that Stop in a non-terminal state is actually blocked,
and that the TDD message the user sees is the *correct* one, not a generic
"enforcement degraded" replacement.

If these pass, the core enforcement claim of Holtz — "you cannot fix without
a failing test first" — holds end-to-end. If they fail, that claim is theater.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")

sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
from hook_runner import run_hook  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.hook_e2e]


def _run_sahjhan(real_daemon, *args, check=True):
    cmd = [
        real_daemon["binary"],
        "--config-dir", real_daemon["config_dir"],
        *args,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=real_daemon["project_root"],
        timeout=10,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"sahjhan failed (exit {result.returncode}):\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def _hook_env(real_daemon):
    env = os.environ.copy()
    env["SAHJHAN_DAEMON_SOCKET"] = real_daemon["sock_path"]
    env["CLAUDE_PLUGIN_ROOT"] = REPO_ROOT
    return env


def _invoke_hook(hook_name, event, real_daemon, *, capture_diag=False):
    script = os.path.join(ENFORCEMENT_HOOKS_DIR, hook_name)
    out = run_hook(
        script, event,
        cwd=real_daemon["project_root"],
        env=_hook_env(real_daemon),
    )
    if capture_diag and "_stderr" not in out:
        # run_hook already strips these on successful JSON parse; re-invoke
        # with subprocess directly when the caller wants stderr for debugging.
        import subprocess as _sp
        res = _sp.run(
            [sys.executable, script],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=10,
            cwd=real_daemon["project_root"],
            env=_hook_env(real_daemon),
        )
        out["_stderr"] = res.stderr
        out["_returncode"] = res.returncode
    return out


def _read_enforcement_cache_via_daemon(real_daemon) -> dict | None:
    """Read the enforcement cache directly from the daemon socket.

    This is the exact call path pre_tool_hook takes — if this returns None
    in tests, pre_tool_hook will skip hook eval as stale.
    """
    sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
    # Force clean import so the test picks up any recent edits to the module.
    for modname in ("_protocol_cache", "_common"):
        sys.modules.pop(modname, None)
    from _protocol_cache import read_cache  # noqa: E402
    return read_cache(real_daemon["project_root"])


def _fast_forward_to_fix_loop(real_daemon) -> None:
    """Fast-forward the real daemon's ledger into fix_loop state.

    Full protocol flow (recon → audit → merge → fix_loop) requires many
    gates. For isolated E2E validation of a single gate, we:
    1. Transition idle → recon via the normal CLI
    2. Record a state_transition event directly so sahjhan's state resolver
       sees the ledger as being in fix_loop

    This bypasses the gate checks intentionally — the gate checks are
    orthogonal to what this test covers (hook wrapper correctly
    propagates sahjhan's decision to Claude Code).
    """
    _run_sahjhan(real_daemon, "ledger", "create", "--from", "run", "1", "--activate")
    _run_sahjhan(real_daemon, "transition", "run_start")
    # Manually record a transition event so the ledger state advances to fix_loop.
    _run_sahjhan(
        real_daemon, "event", "state_transition",
        "--field", "from=recon",
        "--field", "to=fix_loop",
        "--field", "run=1",
        "--field", "auditor=holtz",
        "--field", "project=holtz",
    )
    result = _run_sahjhan(real_daemon, "--json", "status")
    data = json.loads(result.stdout)
    assert data["data"]["state"] == "fix_loop", (
        f"Fast-forward to fix_loop did not land in expected state: {data}"
    )


def _freshen_enforcement_cache(real_daemon) -> None:
    """Run protocol_tracker against a sahjhan command so the enforcement
    cache gets the `last_sahjhan_cmd` timestamp. Without this, pre_tool_hook
    sees stale enforcement and skips hook eval.
    """
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "sahjhan status"},
        "tool_response": {"exit_code": 0, "output": "recon"},
        "cwd": real_daemon["project_root"],
    }
    _invoke_hook("protocol_tracker.py", event, real_daemon)


class TestTddGateBlocksWriteInFixLoop:
    """The flagship enforcement: Write/Edit in fix_loop without a failing test
    must be blocked with a message telling the model to record
    test_failed_before_fix first.

    If this test fails, Holtz's core TDD discipline is theater.
    """

    def test_write_blocked_in_fix_loop_without_failing_test(self, real_daemon):
        """pre_tool_hook must block a source Write in fix_loop with the
        TDD violation message."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        # Sanity probe — confirm sahjhan's own hook eval reports block
        # before we blame the wrapper for the outcome. sahjhan exits 1 on
        # block, so don't treat that as failure here.
        probe = _run_sahjhan(
            real_daemon, "--json", "hook", "eval",
            "--event", "PreToolUse",
            "--tool", "Write",
            "--file", os.path.join(real_daemon["project_root"], "src", "app.py"),
            check=False,
        )
        probe_data = json.loads(probe.stdout)
        assert probe_data["data"]["decision"] == "block", (
            f"Sahjhan hook eval should block, but returned: {probe_data}"
        )

        event = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": os.path.join(real_daemon["project_root"], "src", "app.py"),
                "content": "print('hi')\n",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)

        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny", (
            f"Expected deny, got: {output}"
        )
        reason = hook_out.get("permissionDecisionReason", "")
        assert "TDD" in reason or "failing test" in reason.lower(), (
            f"Block reason should surface the TDD violation instruction "
            f"so the model knows to record test_failed_before_fix. Got: {reason!r}"
        )

    def test_edit_blocked_in_fix_loop_without_failing_test(self, real_daemon):
        """Same enforcement for Edit: in fix_loop, block with TDD message."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": os.path.join(real_daemon["project_root"], "src", "app.py"),
                "old_string": "print('hi')",
                "new_string": "print('hello')",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)

        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny", (
            f"Expected deny, got: {output}"
        )
        reason = hook_out.get("permissionDecisionReason", "")
        assert "TDD" in reason or "failing test" in reason.lower(), (
            f"Block reason should surface the TDD violation instruction. "
            f"Got: {reason!r}"
        )

    def test_write_allowed_after_test_failed_before_fix_event(self, real_daemon):
        """After recording test_failed_before_fix, the same Write should pass."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        # Record the required event to release the gate.
        _run_sahjhan(
            real_daemon, "event", "test_failed_before_fix",
            "--field", "finding_id=BH-001",
            "--field", "test_name=test_something",
            "--field", "run=1",
            "--field", "auditor=holtz",
            "--field", "project=holtz",
        )

        event = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": os.path.join(real_daemon["project_root"], "src", "app.py"),
                "content": "print('hi')\n",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)

        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "allow", (
            f"After test_failed_before_fix event, Write should be allowed. Got: {output}"
        )

    def test_write_blocked_in_recon_state_without_tdd_event(self, real_daemon):
        """TDD gate only applies in fix_loop. Writes in recon must be allowed."""
        _run_sahjhan(real_daemon, "ledger", "create", "--from", "run", "1", "--activate")
        _run_sahjhan(real_daemon, "transition", "run_start")
        _freshen_enforcement_cache(real_daemon)

        event = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": os.path.join(real_daemon["project_root"], "src", "app.py"),
                "content": "x\n",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)
        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "allow", (
            f"Writes outside fix_loop must be allowed. Got: {output}"
        )

    def test_test_file_write_allowed_in_fix_loop(self, real_daemon):
        """Writing test files is allowed in fix_loop (filter exempts tests/**)."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        event = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": os.path.join(
                    real_daemon["project_root"], "tests", "test_new.py",
                ),
                "content": "def test_x(): assert False\n",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)

        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "allow", (
            f"Test file writes should be exempt from TDD gate. Got: {output}"
        )


class TestStopGateBlocksInNonTerminalStates:
    """Stop hook must block the session from exiting while an audit is
    mid-flight — otherwise the user can walk away in fix_loop and ship
    an incomplete audit. Real-daemon tests previously only asserted
    the hook "didn't crash"; this class asserts the actual block.
    """

    def test_stop_blocked_in_recon_state(self, real_daemon):
        """Stop in recon must block with a message naming the state."""
        _run_sahjhan(real_daemon, "ledger", "create", "--from", "run", "1", "--activate")
        _run_sahjhan(real_daemon, "transition", "run_start")
        _freshen_enforcement_cache(real_daemon)

        event = {
            "stop_hook_type": "Stop",
            "stopHookInput": {"description": "test stop"},
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("stop_hook.py", event, real_daemon)

        decision = output.get("decision")
        assert decision == "block", (
            f"Stop in recon must block. Got: {output}"
        )
        reason = output.get("reason", "")
        assert "recon" in reason.lower() or "audit" in reason.lower(), (
            f"Block reason should name the state. Got: {reason!r}"
        )

    def test_stop_blocked_in_fix_loop_state(self, real_daemon):
        """Stop in fix_loop must block — user cannot walk away mid-fix."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        event = {
            "stop_hook_type": "Stop",
            "stopHookInput": {"description": "test stop"},
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("stop_hook.py", event, real_daemon)

        decision = output.get("decision")
        assert decision == "block", (
            f"Stop in fix_loop must block. Got: {output}"
        )
        reason = output.get("reason", "")
        assert "fix_loop" in reason.lower() or "audit" in reason.lower(), (
            f"Block reason should name the state. Got: {reason!r}"
        )


class TestTerminatedAuditRecovery:
    """When the daemon dies mid-audit, the ledger is unrecoverable.
    Primer writes a terminated marker; subsequent tool calls are
    guided toward removing .sahjhan/ to start fresh. This test
    class verifies the recovery path the primer advertises actually
    works — the user can rm the data dir to unstick themselves.
    """

    def _make_terminated_project(self, tmp_path) -> str:
        """Create a terminated-audit fixture (no real daemon needed)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text(
            "reason: daemon_pid_dead\n"
            "detected_by: test\n"
        )
        return str(tmp_path)

    def test_primer_announces_termination_and_recovery(self, tmp_path):
        import subprocess
        project = self._make_terminated_project(tmp_path)
        event = {"cwd": project, "user_prompt": "anything"}
        hook = os.path.join(ENFORCEMENT_HOOKS_DIR, "primer.py")
        result = subprocess.run(
            [sys.executable, hook],
            input=json.dumps(event),
            capture_output=True, text=True, timeout=5,
            cwd=project,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT},
        )
        output = json.loads(result.stdout) if result.stdout.strip() else {}
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "AUDIT TERMINATED" in context, (
            f"Primer must announce termination when marker exists. "
            f"Got: {output}"
        )
        # Recovery path must be discoverable from the message.
        assert ".sahjhan" in context, (
            f"Primer must tell the user where the recovery directory is. "
            f"Got: {context!r}"
        )

    def test_rm_recovery_allowed_when_audit_terminated(self, tmp_path):
        """Once the audit is terminated, ``rm -rf docs/holtz/.sahjhan/``
        is the recovery step. The primer instructs the user to do it
        and the bash_guard/managed-path guards must not block it."""
        import subprocess
        project = self._make_terminated_project(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz/.sahjhan/"},
            "cwd": project,
        }
        hook = os.path.join(ENFORCEMENT_HOOKS_DIR, "_sahjhan_bootstrap.py")
        result = subprocess.run(
            [sys.executable, hook],
            input=json.dumps(event),
            capture_output=True, text=True, timeout=5,
            cwd=project,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT},
        )
        output = json.loads(result.stdout) if result.stdout.strip() else {}
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "allow", (
            f"Recovery rm must be allowed when audit is terminated. "
            f"Got: {output}"
        )


class TestFullAuditLifecycle:
    """Walk the transitions a real user hits: init → recon → fix_loop →
    terminal. Asserts the hook chain doesn't silently allow what should
    be blocked at each state and doesn't block what should pass.
    """

    def test_read_always_allowed_in_fix_loop(self, real_daemon):
        """Read must always pass through — read guards were removed when
        secrets moved to daemon memory. If Reads get blocked, the session
        is bricked (issue #55)."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        event = {
            "tool_name": "Read",
            "tool_input": {
                "file_path": os.path.join(real_daemon["project_root"], "anything.py"),
            },
            "cwd": real_daemon["project_root"],
        }
        # _daemon_lifecycle is the hook that enforces passthrough tools
        output = _invoke_hook("_daemon_lifecycle.py", event, real_daemon)
        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "allow", (
            f"Read must always pass through. Got: {output}"
        )

    def test_managed_path_write_blocked(self, real_daemon):
        """Writes to Sahjhan-managed docs (STATUS.md, PUNCHLIST.md) must
        be blocked by pre_tool_hook even in idle — they are rendered
        from the ledger and must not be edited directly.
        """
        # Idle daemon — no transitions yet
        event = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": os.path.join(
                    real_daemon["project_root"], "docs", "holtz", "STATUS.md",
                ),
                "content": "fake status",
            },
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("pre_tool_hook.py", event, real_daemon)
        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny", (
            f"Write to managed STATUS.md must be denied. Got: {output}"
        )
        reason = hook_out.get("permissionDecisionReason", "")
        assert "managed" in reason.lower() or "sahjhan" in reason.lower(), (
            f"Block reason should explain the path is managed. Got: {reason!r}"
        )

    def test_user_prompt_submit_primer_on_idle(self, real_daemon):
        """Primer hook on UserPromptSubmit should not inject anything when
        no audit is in progress (data_dir is there, but daemon is idle)."""
        event = {
            "cwd": real_daemon["project_root"],
            "user_prompt": "test",
        }
        output = _invoke_hook("primer.py", event, real_daemon)
        # Primer exits_ok silently when idle. No assistant-visible context.
        raw = output.get("_empty") or output.get("hookSpecificOutput", {}).get(
            "additionalContext", ""
        )
        # Either empty output (silent exit_ok) or no additionalContext
        assert output.get("_returncode", 0) == 0
        if isinstance(raw, str) and raw:
            # If primer DID inject, it shouldn't claim an active audit
            assert "AUDIT TERMINATED" not in raw, (
                f"Primer should not claim termination in idle state. Got: {raw!r}"
            )

    def test_commit_gate_blocks_unregistered_git_commit_in_fix_loop(self, real_daemon):
        """In fix_loop, git commit without prior `transition fix_commit`
        must be blocked by commit_gate so the fix isn't atomic-escaped
        (see CHANGELOG for run 19 incidents)."""
        _fast_forward_to_fix_loop(real_daemon)
        _freshen_enforcement_cache(real_daemon)

        # Simulate a prior PostToolUse for a git commit that wasn't registered
        # through a fix_commit transition — this populates the enforcement
        # cache with an unregistered_commits entry the commit_gate checks.
        git_commit_event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: something'"},
            "tool_response": {
                "exit_code": 0,
                "output": "[main abc1234] fix: something\n",
            },
            "cwd": real_daemon["project_root"],
        }
        _invoke_hook("protocol_tracker.py", git_commit_event, real_daemon)

        # Now attempting another git commit without fix_commit should block
        commit_event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: another'"},
            "cwd": real_daemon["project_root"],
        }
        output = _invoke_hook("commit_gate.py", commit_event, real_daemon)
        hook_out = output.get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny", (
            f"commit_gate must block unregistered git commit in fix_loop. "
            f"Got: {output}"
        )
        reason = hook_out.get("permissionDecisionReason", "")
        assert "fix_commit" in reason.lower() or "unregistered" in reason.lower(), (
            f"Block reason should name the missing transition. Got: {reason!r}"
        )

    def test_managed_dir_writes_other_than_setup_still_blocked(self, tmp_path):
        """The daemon-init-pid exemption must be narrow. Attempts to cp
        OTHER files into .sahjhan/ still need to be denied — otherwise
        the exemption becomes a bypass for writing to the ledger."""
        import subprocess
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)

        hostile_commands = [
            # Copying something OTHER than daemon.pid → init pid
            "cp /etc/hostname docs/holtz/.sahjhan/daemon-init-pid",
            # Copying daemon.pid to a DIFFERENT filename
            "cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/ledger.jsonl",
            # Writing to ledger directly
            "cp /tmp/forged docs/holtz/.sahjhan/ledger.jsonl",
            # Chained form that tries to smuggle the exemption
            "cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/daemon-init-pid && cp /tmp/x docs/holtz/.sahjhan/ledger.jsonl",
        ]
        hook = os.path.join(ENFORCEMENT_HOOKS_DIR, "_sahjhan_bootstrap.py")
        for cmd in hostile_commands:
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": cmd},
                "cwd": str(tmp_path),
            }
            result = subprocess.run(
                [sys.executable, hook],
                input=json.dumps(event),
                capture_output=True, text=True, timeout=5,
                cwd=str(tmp_path),
                env={**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT},
            )
            output = json.loads(result.stdout) if result.stdout.strip() else {}
            decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
            assert decision == "deny", (
                f"Hostile command should be denied: {cmd!r}. Got: {output}"
            )

    def test_daemon_init_pid_setup_cp_is_allowed(self, tmp_path):
        """phase-recon.md tells the user to run:

            cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/daemon-init-pid

        This is a protocol-setup step — _daemon_lifecycle.py needs the
        daemon-init-pid file to distinguish the original daemon from a
        restart. The bootstrap hook's MANAGED_DATA guard protects the
        .sahjhan/ directory from arbitrary writes, but this specific cp
        is exactly what the skill prescribes. If the guard blocks it,
        the model follows the skill and gets stuck on the very first
        session before the audit even starts.
        """
        import subprocess
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("12345\n")

        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cp docs/holtz/.sahjhan/daemon.pid "
                    "docs/holtz/.sahjhan/daemon-init-pid"
                ),
            },
            "cwd": str(tmp_path),
        }
        hook = os.path.join(ENFORCEMENT_HOOKS_DIR, "_sahjhan_bootstrap.py")
        result = subprocess.run(
            [sys.executable, hook],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(tmp_path),
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT},
        )
        output = json.loads(result.stdout) if result.stdout.strip() else {}
        hook_out = output.get("hookSpecificOutput", {})
        decision = hook_out.get("permissionDecision")
        assert decision == "allow", (
            f"The SKILL-prescribed daemon-init-pid setup cp must be "
            f"allowed by _sahjhan_bootstrap. Got: {hook_out!r}"
        )

    def test_user_prompt_submit_primer_injects_state_during_audit(self, real_daemon):
        """During an active audit, primer must inject current state so the
        model knows where it is after /clear or compaction."""
        _run_sahjhan(real_daemon, "ledger", "create", "--from", "run", "1", "--activate")
        _run_sahjhan(real_daemon, "transition", "run_start")
        _freshen_enforcement_cache(real_daemon)

        event = {
            "cwd": real_daemon["project_root"],
            "user_prompt": "continue the audit",
        }
        output = _invoke_hook("primer.py", event, real_daemon)
        hook_out = output.get("hookSpecificOutput", {})
        context = hook_out.get("additionalContext", "")
        assert "recon" in context.lower() or "sahjhan resume" in context.lower(), (
            f"Primer must inject resume context during active audit. Got: {output}"
        )

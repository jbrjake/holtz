"""Contract tests: every command the skill tells the agent to run must pass the hook.

Issue #53 root cause: tests verified code paths but not the actual commands from
skill files. Three consecutive broken releases shipped because no test used the
real commands from phase-recon.md and SKILL.md.

This file is the fix. Every sahjhan command extracted from skill/reference docs
gets a test here. If a skill file changes, this file must be updated.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from hook_runner import run_hook

pytestmark = pytest.mark.contract

HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"


def _run_hook(event: dict) -> dict:
    """Run the bootstrap hook with a given event dict, return parsed output."""
    return run_hook(HOOK, event)


def _assert_allowed(command: str, context: str = "") -> None:
    """Assert that a Bash command is allowed through the bootstrap hook."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": "/tmp/fake-cwd",
    }
    output = _run_hook(event)
    decision = output["hookSpecificOutput"]["permissionDecision"]
    reason = output["hookSpecificOutput"].get("permissionDecisionReason", "")
    assert decision == "allow", (
        f"Command BLOCKED but should be ALLOWED.\n"
        f"  Command: {command}\n"
        f"  Context: {context}\n"
        f"  Reason:  {reason}"
    )


def _assert_blocked(command: str, context: str = "") -> None:
    """Assert that a Bash command is blocked by the bootstrap hook."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": "/tmp/fake-cwd",
    }
    output = _run_hook(event)
    decision = output["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny", (
        f"Command ALLOWED but should be BLOCKED.\n"
        f"  Command: {command}\n"
        f"  Context: {context}"
    )


# ---------------------------------------------------------------------------
# Contract commands: extracted from phase-recon.md Step 0 initialization
# ---------------------------------------------------------------------------

class TestPhaseReconInitSequence:
    """Every command from phase-recon.md Step 0 must be allowed."""

    def test_sahjhan_init(self):
        _assert_allowed("sahjhan init", "phase-recon.md: first command in init sequence")

    def test_nohup_daemon_start(self):
        _assert_allowed(
            "nohup sahjhan daemon start > /dev/null 2>&1 &",
            "phase-recon.md: daemon start with nohup + redirect + background",
        )

    def test_ledger_create(self):
        _assert_allowed(
            "sahjhan ledger create --from run 1 --activate",
            "phase-recon.md: ledger create for run 1",
        )

    def test_ledger_create_higher_run(self):
        _assert_allowed(
            "sahjhan ledger create --from run 15 --activate",
            "phase-recon.md: ledger create for arbitrary run number",
        )

    def test_transition_run_start(self):
        _assert_allowed(
            "sahjhan transition run_start",
            "phase-recon.md: transition to run_start",
        )

    def test_event_recon_step(self):
        _assert_allowed(
            "sahjhan event recon_step --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=recon --field step=0 "
            "--field artifact_path=docs/holtz/recon/step0-project-overview.md",
            "phase-recon.md: record recon step event",
        )

    def test_event_recon_finding(self):
        _assert_allowed(
            'sahjhan event recon_finding --field project=holtz --field run=1 '
            '--field auditor=holtz --field phase=recon --field step=0 '
            '--field topic=architecture --field content="Four layers"',
            "phase-recon.md: record recon finding event",
        )


# ---------------------------------------------------------------------------
# Contract commands: extracted from SKILL.md quick reference
# ---------------------------------------------------------------------------

class TestSkillMdQuickReference:
    """Every canonical CLI command from SKILL.md must be allowed."""

    def test_init(self):
        _assert_allowed("sahjhan init", "SKILL.md quick reference")

    def test_ledger_create(self):
        _assert_allowed(
            "sahjhan ledger create --from run 1 --activate",
            "SKILL.md quick reference",
        )

    def test_event_finding(self):
        _assert_allowed(
            "sahjhan event finding --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=audit --field step=7 "
            "--field id=BH-001 --field severity=HIGH --field category=doc/drift "
            '--field location="README.md:108" --field perspective=public-contract '
            '--field description="Pattern count stale" --field predicted_by=1',
            "SKILL.md: event finding",
        )

    def test_event_finding_resolved(self):
        _assert_allowed(
            "sahjhan event finding_resolved --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=fix_loop --field step=10 "
            "--field id=BH-001 --field commit_hash=abc1234",
            "SKILL.md: event finding_resolved",
        )

    def test_event_recon_finding(self):
        _assert_allowed(
            "sahjhan event recon_finding --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=recon --field step=0 "
            '--field topic=architecture --field content="Four layers..."',
            "SKILL.md: event recon_finding",
        )

    def test_event_audit_claim(self):
        _assert_allowed(
            "sahjhan event audit_claim --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=audit --field step=6 "
            '--field source="README.md:15" --field claim="Supports 13 lenses" '
            '--field verdict=VERIFIED --field evidence="..."',
            "SKILL.md: event audit_claim",
        )

    def test_transition_run_start(self):
        _assert_allowed("sahjhan transition run_start", "SKILL.md: transitions")

    def test_transition_recon_complete(self):
        _assert_allowed("sahjhan transition recon_complete", "SKILL.md: transitions")

    def test_transition_audit_complete(self):
        _assert_allowed("sahjhan transition audit_complete", "SKILL.md: transitions")

    def test_transition_merge_complete(self):
        _assert_allowed("sahjhan transition merge_complete", "SKILL.md: transitions")

    def test_transition_fix_commit(self):
        _assert_allowed("sahjhan transition fix_commit", "SKILL.md: transitions")

    def test_set_complete_perspective(self):
        _assert_allowed(
            "sahjhan set complete perspective component",
            "SKILL.md: set complete perspective",
        )

    def test_transition_lens_rotate(self):
        _assert_allowed("sahjhan transition lens_rotate", "SKILL.md: transitions")

    def test_transition_converge(self):
        _assert_allowed("sahjhan transition converge", "SKILL.md: transitions")

    def test_transition_finalize(self):
        _assert_allowed("sahjhan transition finalize", "SKILL.md: transitions")

    def test_status(self):
        _assert_allowed("sahjhan status", "SKILL.md: status check")

    def test_gate_check_converge(self):
        _assert_allowed("sahjhan gate check converge", "SKILL.md: gate check")

    def test_set_status_perspective(self):
        _assert_allowed("sahjhan set status perspective", "SKILL.md: set status")

    def test_ledger_checkpoint(self):
        _assert_allowed(
            "sahjhan ledger checkpoint --snapshot pre-clear",
            "SKILL.md: ledger checkpoint",
        )

    def test_event_fix_start(self):
        _assert_allowed(
            "sahjhan event fix_start --field project=holtz --field run=1 "
            "--field auditor=holtz --field finding_id=BH-001",
            "SKILL.md: event fix_start",
        )

    def test_event_blast_radius(self):
        _assert_allowed(
            "sahjhan event blast_radius --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=fix_loop --field step=10 "
            "--field target_node=module.py --field depth=2 "
            "--field affected_count=5 --field finding_id=BH-001",
            "SKILL.md: event blast_radius",
        )

    def test_event_hardening_complete(self):
        _assert_allowed(
            "sahjhan event hardening_complete --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=fix_loop --field step=10 "
            "--field finding_id=BH-001 --field edge_cases_tested=3 --field tests_added=2",
            "SKILL.md: event hardening_complete",
        )

    def test_event_pattern_analysis_complete(self):
        _assert_allowed(
            "sahjhan event pattern_analysis_complete --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=fix_loop --field step=11 "
            "--field patterns_found=2 --field siblings_found=4",
            "SKILL.md: event pattern_analysis_complete",
        )

    def test_event_iteration_complete(self):
        _assert_allowed(
            "sahjhan event iteration_complete --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=fix_loop --field step=10 "
            "--field perspective=component --field items_resolved=3 --field items_remaining=2 "
            "--field test_count=50 --field tests_passed=true",
            "SKILL.md: event iteration_complete",
        )

    def test_event_snapshot(self):
        _assert_allowed(
            "sahjhan event snapshot --field key=pre_audit_edge_count --field value=28",
            "SKILL.md: event snapshot",
        )

    def test_event_justine_dispatched(self):
        _assert_allowed(
            "sahjhan event justine_dispatched --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=recon --field mode=full",
            "SKILL.md: event justine_dispatched",
        )

    def test_event_merge_agent_dispatched(self):
        _assert_allowed(
            "sahjhan event merge_agent_dispatched --field project=holtz --field run=1 "
            "--field auditor=holtz --field phase=merge --field step=9",
            "SKILL.md: event merge_agent_dispatched",
        )

    def test_render(self):
        _assert_allowed("sahjhan render", "SKILL.md: render subcommand in allowlist")

    def test_manifest_verify(self):
        _assert_allowed(
            "sahjhan manifest verify",
            "SKILL.md: manifest verify (used by bash_guard.py)",
        )


# ---------------------------------------------------------------------------
# Contract commands: convergence flow transitions from phase-convergence.md
# ---------------------------------------------------------------------------

class TestConvergenceFlowTransitions:
    """Every transition in the convergence flow must be allowed."""

    def test_transition_all_perspectives(self):
        _assert_allowed(
            "sahjhan transition all_perspectives",
            "phase-convergence.md: perspective_clean -> all_perspectives_clean",
        )

    def test_transition_final_sweep_start(self):
        _assert_allowed(
            "sahjhan transition final_sweep_start",
            "phase-convergence.md: all_perspectives_clean -> final_sweep",
        )

    def test_transition_sweep_dirty(self):
        _assert_allowed(
            "sahjhan transition sweep_dirty",
            "phase-convergence.md: final_sweep -> fix_loop (dirty sweep)",
        )

    def test_transition_confirm_convergence(self):
        _assert_allowed(
            "sahjhan transition confirm_convergence",
            "phase-convergence.md: final_sweep_clean -> converged",
        )


# ---------------------------------------------------------------------------
# Contract commands: finalize events from phase-finalize.md
# ---------------------------------------------------------------------------

class TestFinalizeEvents:
    """Events required by the finalize gate must be allowed."""

    def test_event_baseline_updated(self):
        _assert_allowed(
            "sahjhan event baseline_updated --field project=holtz --field run=1 "
            '--field auditor=holtz --field sections_changed="Module Dependencies"',
            "phase-finalize.md: baseline_updated event after Step 17",
        )

    def test_event_living_punchlist_updated(self):
        _assert_allowed(
            "sahjhan event living_punchlist_updated --field project=holtz --field run=1 "
            "--field auditor=holtz --field patterns_added=2 --field hotspots_updated=3",
            "phase-finalize.md: living_punchlist_updated event after Step 19",
        )

    def test_event_pattern_contribution_complete(self):
        _assert_allowed(
            "sahjhan event pattern_contribution_complete --field project=holtz --field run=1 "
            "--field auditor=holtz --field patterns_submitted=0 --field outcome=no_new_patterns",
            "phase-finalize.md: pattern_contribution_complete event in Step 18",
        )


# ---------------------------------------------------------------------------
# Contract: commands that must remain BLOCKED
# ---------------------------------------------------------------------------

class TestBlockedContractCommands:
    """Commands the skill says never to run must remain blocked."""

    def test_reset_blocked(self):
        _assert_blocked("sahjhan reset --confirm", "SKILL.md: never run reset")

    def test_daemon_stop_blocked(self):
        _assert_blocked("sahjhan daemon stop", "SKILL.md: daemon stop is blocked")

    def test_bare_sahjhan_blocked(self):
        _assert_blocked("sahjhan", "No subcommand should be blocked")


# ---------------------------------------------------------------------------
# Shell idiom combinatorial tests
# Issue #53: real agent commands use redirects, pipes, backgrounding.
# Every allowed subcommand must work with every common shell idiom.
# ---------------------------------------------------------------------------

# Representative subcommands (covers all categories: simple, multi-token, --field)
_REPRESENTATIVE_SUBCMDS = [
    ("sahjhan init", "init"),
    ("sahjhan status", "status"),
    ("sahjhan daemon start", "daemon start"),
    ("sahjhan transition run_start", "transition"),
    ("sahjhan ledger create --from run 1 --activate", "ledger create"),
    ("sahjhan gate check converge", "gate check"),
    ("sahjhan event finding --field id=BH-001 --field severity=HIGH", "event with fields"),
]

# Common shell idioms that get appended to commands
_SHELL_IDIOMS = [
    # Redirects
    ("2>&1", "stderr to stdout"),
    ("2>/dev/null", "stderr to devnull"),
    (">/dev/null 2>&1", "stdout+stderr to devnull"),
    ("> /tmp/out.log", "stdout to file"),
    ("1>&2", "stdout to stderr"),
    ("&>/dev/null", "combined redirect to devnull"),
    ("2>/tmp/err.log", "stderr to file"),
    # Backgrounding
    ("&", "trailing ampersand"),
    # Pipes
    ("| cat", "pipe to cat"),
    ("| head -20", "pipe to head"),
]

# Shell idioms that wrap the ENTIRE command (prefix + suffix)
_SHELL_WRAPPER_IDIOMS = [
    ("nohup ", " &", "nohup wrapper with background"),
    ("nohup ", " > /dev/null 2>&1 &", "nohup full redirect and background"),
]

# Idioms that chain a second command after the sahjhan command
_SHELL_CHAIN_IDIOMS = [
    ("; echo done", "semicolon chain"),
    ("&& echo ok", "and-chain"),
    ("|| echo fail", "or-chain"),
]


@pytest.mark.parametrize(
    "base_cmd,cmd_label",
    _REPRESENTATIVE_SUBCMDS,
    ids=[label for _, label in _REPRESENTATIVE_SUBCMDS],
)
@pytest.mark.parametrize(
    "idiom,idiom_label",
    _SHELL_IDIOMS,
    ids=[label for _, label in _SHELL_IDIOMS],
)
def test_subcmd_with_shell_idiom(base_cmd, cmd_label, idiom, idiom_label):
    """Every allowed subcommand + shell idiom combination must be allowed."""
    command = f"{base_cmd} {idiom}"
    _assert_allowed(command, f"{cmd_label} + {idiom_label}")


# Help flag must work with all subcommands
@pytest.mark.parametrize(
    "base_cmd,cmd_label",
    _REPRESENTATIVE_SUBCMDS,
    ids=[label for _, label in _REPRESENTATIVE_SUBCMDS],
)
def test_subcmd_with_help_flag(base_cmd, cmd_label):
    """Every allowed subcommand with --help appended must be allowed."""
    _assert_allowed(f"{base_cmd} --help", f"{cmd_label} --help")


# Wrapper idioms (nohup ... &) must work with all subcommands
@pytest.mark.parametrize(
    "base_cmd,cmd_label",
    _REPRESENTATIVE_SUBCMDS,
    ids=[label for _, label in _REPRESENTATIVE_SUBCMDS],
)
@pytest.mark.parametrize(
    "prefix,suffix,idiom_label",
    _SHELL_WRAPPER_IDIOMS,
    ids=[label for _, _, label in _SHELL_WRAPPER_IDIOMS],
)
def test_subcmd_with_wrapper_idiom(base_cmd, cmd_label, prefix, suffix, idiom_label):
    """Every allowed subcommand wrapped with nohup/& must be allowed."""
    command = f"{prefix}{base_cmd}{suffix}"
    _assert_allowed(command, f"{cmd_label} + {idiom_label}")


# Chain idioms (; echo done, && echo ok) must work with all subcommands
@pytest.mark.parametrize(
    "base_cmd,cmd_label",
    _REPRESENTATIVE_SUBCMDS,
    ids=[label for _, label in _REPRESENTATIVE_SUBCMDS],
)
@pytest.mark.parametrize(
    "chain,chain_label",
    _SHELL_CHAIN_IDIOMS,
    ids=[label for _, label in _SHELL_CHAIN_IDIOMS],
)
def test_subcmd_with_chain_idiom(base_cmd, cmd_label, chain, chain_label):
    """Every allowed subcommand + chained second command must be allowed."""
    command = f"{base_cmd} {chain}"
    _assert_allowed(command, f"{cmd_label} + {chain_label}")


# Bare sahjhan with help flags
def test_bare_sahjhan_help():
    _assert_allowed("sahjhan --help", "bare sahjhan --help")


def test_bare_sahjhan_short_help():
    _assert_allowed("sahjhan -h", "bare sahjhan -h")


# Version flag must bypass enforcement like help
def test_bare_sahjhan_version():
    _assert_allowed("sahjhan --version", "bare sahjhan --version")


@pytest.mark.parametrize(
    "base_cmd,cmd_label",
    _REPRESENTATIVE_SUBCMDS,
    ids=[label for _, label in _REPRESENTATIVE_SUBCMDS],
)
def test_subcmd_with_version_flag(base_cmd, cmd_label):
    """Every allowed subcommand with --version appended must be allowed."""
    _assert_allowed(f"{base_cmd} --version", f"{cmd_label} --version")


# ---------------------------------------------------------------------------
# First-run smoke test: full initialization sequence through the hook
# ---------------------------------------------------------------------------

class TestFirstRunInitSequence:
    """Simulate the complete first-run initialization sequence from phase-recon.md.

    Every command in order, as the agent would type them on a project with
    no prior .sahjhan/ directory. This is the sequence that was broken in
    issue #53.
    """

    # The exact commands from phase-recon.md Step 0, in order
    INIT_SEQUENCE = [
        "sahjhan init",
        "nohup sahjhan daemon start > /dev/null 2>&1 &",
        "sahjhan ledger create --from run 1 --activate",
        "sahjhan transition run_start",
    ]

    @pytest.mark.parametrize("command", INIT_SEQUENCE)
    def test_init_sequence_command_allowed(self, command):
        """Each command in the first-run init sequence must be allowed."""
        _assert_allowed(command, "phase-recon.md first-run init sequence")

    def test_init_sequence_complete(self):
        """Run the full sequence and verify all commands pass.

        This catches ordering-dependent issues where individual commands
        pass but the sequence as a whole fails.
        """
        for i, command in enumerate(self.INIT_SEQUENCE):
            _assert_allowed(command, f"init sequence step {i + 1}/{len(self.INIT_SEQUENCE)}")


# ---------------------------------------------------------------------------
# Error message quality: deny messages must not contain parse artifacts
# ---------------------------------------------------------------------------

class TestDenyMessageQuality:
    """Error messages from blocked commands must be coherent and useful."""

    def test_blocked_reset_message_mentions_reset(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "reset" in reason.lower(), "Deny message should mention the blocked subcommand"
        assert "Allowed subcommands:" in reason, "Deny message should list allowed alternatives"

    def test_blocked_unknown_message_mentions_subcmd(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan frobnicate"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "frobnicate" in reason, "Deny message should mention the typed subcommand"

    def test_deny_message_no_redirect_fragments(self):
        """Blocked commands with redirects must not have fragments in the message.

        Regression: 'sahjhan reset 2>&1' was producing 'sahjhan 2' in the
        error message because the redirect fragment leaked into the parser.
        """
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm 2>&1"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        # The message should mention "reset", not "2" or redirect artifacts
        assert "reset" in reason.lower(), (
            f"Deny message contains redirect artifact instead of subcommand: {reason}"
        )
        assert "'sahjhan 2'" not in reason, (
            f"Deny message contains redirect fragment: {reason}"
        )


# ---------------------------------------------------------------------------
# Pre-release contract gate: run scripts/contract_gate.py as a test
# Catches drift between skill instructions and hook enforcement.
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestContractGate:
    """Run the contract gate script and verify it passes."""

    def test_contract_gate_passes(self):
        """The contract gate script must exit 0 (all commands match)."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gate_script = os.path.join(repo_root, "scripts", "contract_gate.py")
        result = subprocess.run(
            [sys.executable, gate_script],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_root,
        )
        assert result.returncode == 0, (
            f"Contract gate FAILED:\n{result.stdout}\n{result.stderr}"
        )

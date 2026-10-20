#!/usr/bin/env python3
"""Pre-release contract gate: verify hook decisions match skill instructions.

Extracts every sahjhan command taught in `skills/**/*.md` — fenced blocks
**and** inline backticks — and asks two questions of each:

  1. Does the hook allow it? An allowed command the hook blocks, or a
     KNOWN_BLOCKED command the hook allows, fails the gate.
  2. Does the *engine* accept its fields? A `sahjhan event` form missing a
     field `events.toml` requires exits 4 on the first use of every run.

Question 2 is new (item 31 / W03). Asking only question 1 is how
`phase-fix-loop.md:52` and `hooks.toml`'s TDD block message came to teach a
`test_failed_before_fix` without `project`, `run` or `auditor`: the hook
allowed the string, and nothing ever ran it. `hooks.toml` is not a skill file,
so its message was outside this gate entirely — it is in scope now, because it
is the string a blocked agent actually copies.

Extraction is shared with `scripts/taught_commands.py` rather than duplicated;
a second copy is exactly how the fenced-only reader drifted from the six inline
commands.

Usage:
    python3 scripts/contract_gate.py          # exit 0 = pass, exit 1 = fail
    python3 scripts/contract_gate.py --verbose  # show every command tested
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_ROOT, "enforcement", "hooks", "_sahjhan_bootstrap.py")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import taught_commands  # noqa: E402

# Commands that appear in skill files but are INTENTIONALLY blocked.
# The contract gate verifies these remain blocked (not accidentally allowed).
KNOWN_BLOCKED = {
    "sahjhan reset",
    "sahjhan reset --confirm",
    "sahjhan daemon stop",
}

# Blocks this gate structurally cannot evaluate, and where each one *is*
# evaluated instead.
#
# `sahjhan daemon stop` is not unconditionally blocked. #57 made it graduated
# on purpose: it is permitted when there is nothing left to protect — no audit
# dir, an audit already marked `terminated`, an unreachable daemon, or a
# daemon-cleanup protocol state. Without that, the stop hook told the agent the
# daemon must be stopped and simultaneously forbade it.
#
# This gate runs hermetically, against a cwd with no audit and no daemon —
# which is precisely the "nothing to protect" case — so the honest answer here
# is `allow`, every time. Asserting `deny` would be asserting a state the gate
# never constructs. The block is verified where the state *can* be built:
# tests/test_worktree_audit_anchor.py::TestV3DaemonStop drives a live daemon in
# `fix_loop` and observes deny from both the main checkout and a worktree, and
# asserts the terminated-audit escape still opens.
#
# It stays in KNOWN_BLOCKED because that set also drives `is_known_blocked`'s
# "the skill file is allowed to mention this" reading; only the *decision*
# assertion is skipped.
STATE_DEPENDENT_BLOCKS = {
    "sahjhan daemon stop": (
        "graduated by #57 — permitted when there is nothing to protect, which "
        "is this gate's own environment. Verified under a live daemon by "
        "tests/test_worktree_audit_anchor.py::TestV3DaemonStop."
    ),
}


def state_dependent_reason(cmd: str) -> str | None:
    """Why this gate cannot assert a decision for ``cmd``, or None."""
    normalized = normalize_command(cmd).lstrip("!").strip()
    for prefix, reason in STATE_DEPENDENT_BLOCKS.items():
        if normalized == prefix or normalized.startswith(prefix + " "):
            return reason
    return None


def extract_sahjhan_commands(md_path: str) -> list[tuple[str, int, str]]:
    """Extract sahjhan commands from a markdown file, fenced and inline.

    Returns list of (command, line_number, file_path) tuples.

    Delegates to `taught_commands.command_spans`, which is the one answer to
    "where are the commands we teach". This function used to read fenced blocks
    only, and to test each physical line separately; a continued command is now
    joined before it is tested, because that is what the shell receives.
    """
    return [
        (span.text, span.line, md_path)
        for span in taught_commands.command_spans(md_path)
    ]


def run_hook(command: str) -> tuple[str, str]:
    """Run the bootstrap hook with a Bash command, return (decision, reason)."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": "/tmp/contract-gate",
    }
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return ("error", result.stderr.strip())
    try:
        output = json.loads(result.stdout)
        decision = output["hookSpecificOutput"]["permissionDecision"]
        reason = output["hookSpecificOutput"].get("permissionDecisionReason", "")
        return (decision, reason)
    except (json.JSONDecodeError, KeyError) as e:
        return ("error", f"Failed to parse hook output: {e}")


def normalize_command(cmd: str) -> str:
    """Normalize a command for matching against KNOWN_BLOCKED."""
    # Strip variable placeholders (N, {lens}, etc.) for fuzzy matching
    # but keep the core structure
    return cmd.strip()


def is_user_command(cmd: str) -> bool:
    """True if the skill file addresses this command to the *user*, not the agent.

    A leading `!` is Claude Code's run-it-yourself prefix, and holtz uses it for
    the two things the agent must not do on its own: stopping the daemon
    mid-audit, and clearing an exhausted lens quiz (#81). For those, "the hook
    denies it" is the contract — so the gate inverts its expectation rather
    than exempting the line. Without this the gate asserted the exact opposite
    of the intended behaviour, and would have gone green only once the
    human-only channel was broken open.
    """
    return normalize_command(cmd).startswith("!")


def is_known_blocked(cmd: str) -> bool:
    """Check if a command matches any known-blocked pattern."""
    normalized = normalize_command(cmd)
    if is_user_command(normalized):
        return True
    return any(
        normalized == blocked or normalized.startswith(blocked + " ")
        for blocked in KNOWN_BLOCKED
    )


def main() -> int:
    verbose = "--verbose" in sys.argv

    # Extract all sahjhan commands
    all_commands: list[tuple[str, int, str]] = []
    for md_path in taught_commands.markdown_files(SKILLS_DIR):
        all_commands.extend(extract_sahjhan_commands(md_path))

    if not all_commands:
        print("ERROR: No sahjhan commands found in skill files!")
        print("  Searched:", SKILLS_DIR)
        return 1

    # Run each through the hook
    failures: list[str] = []
    tested = 0
    allowed_count = 0
    blocked_count = 0

    skipped = 0

    for cmd, line_no, file_path in all_commands:
        rel_path = os.path.relpath(file_path, REPO_ROOT)
        deferred = state_dependent_reason(cmd)
        if deferred:
            skipped += 1
            if verbose:
                print(f"  SKIPPED (state-dependent): {rel_path}:{line_no}: {cmd}\n"
                      f"         {deferred}")
            continue
        decision, reason = run_hook(cmd)
        tested += 1
        expected_blocked = is_known_blocked(cmd)

        if decision == "error":
            failures.append(
                f"  ERROR: {rel_path}:{line_no}: {cmd}\n"
                f"         Hook error: {reason}"
            )
            continue

        if expected_blocked:
            blocked_count += 1
            if decision == "allow":
                why = (
                    "This command is addressed to the user (leading `!`), so the "
                    "hook must deny it on the agent's path — otherwise the agent "
                    "can do it too and the human-only channel is fiction."
                    if is_user_command(cmd)
                    else "This command is in KNOWN_BLOCKED but the hook allowed it."
                )
                failures.append(
                    f"  FAIL (should be BLOCKED): {rel_path}:{line_no}: {cmd}\n"
                    f"         {why}"
                )
            elif verbose:
                print(f"  BLOCKED (expected): {rel_path}:{line_no}: {cmd}")
        else:
            allowed_count += 1
            if decision == "deny":
                failures.append(
                    f"  FAIL (should be ALLOWED): {rel_path}:{line_no}: {cmd}\n"
                    f"         Reason: {reason}"
                )
            elif verbose:
                print(f"  ALLOWED (expected): {rel_path}:{line_no}: {cmd}")

    # Second question: does the engine accept the fields? (item 31 / W03)
    #
    # A command the hook allows can still exit 4 the first time it is run,
    # which is worse than being blocked: the block at least says why. This is
    # the check `contract_gate` never had, and it covers `hooks.toml`'s block
    # messages as well as the skill files.
    field_failures, field_lines = taught_commands.report()
    tested_fields = len(field_lines)
    if verbose:
        for line in field_lines:
            print(line)
    if field_failures:
        failures.extend(
            "  " + line.strip() for line in field_lines
            if line.strip().startswith(("MISSING", "UNKNOWN"))
        )

    # Report
    # Named, never silent: a gate that drops coverage without saying so reads
    # as "everything checked out".
    print(f"\nContract gate: {tested} commands tested "
          f"({allowed_count} should-allow, {blocked_count} should-block, "
          f"{skipped} state-dependent — see STATE_DEPENDENT_BLOCKS); "
          f"{tested_fields} event commands field-checked "
          f"({field_failures} failing)")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):\n")
        for f in failures:
            print(f)
        print()
        return 1

    print("All commands match expected hook decisions and the engine's "
          "required fields. PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

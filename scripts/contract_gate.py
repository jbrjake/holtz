#!/usr/bin/env python3
"""Pre-release contract gate: verify hook decisions match skill instructions.

Extracts all sahjhan commands from fenced code blocks in skills/**/*.md,
runs each through the bootstrap hook, and fails if:
  - An allowed command (from the skill) is blocked by the hook
  - A blocked command (from KNOWN_BLOCKED) is allowed by the hook

This catches drift between skill instructions and hook enforcement even
if someone forgets to update test_contract_commands.py.

Usage:
    python3 scripts/contract_gate.py          # exit 0 = pass, exit 1 = fail
    python3 scripts/contract_gate.py --verbose  # show every command tested
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_ROOT, "enforcement", "hooks", "_sahjhan_bootstrap.py")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Commands that appear in skill files but are INTENTIONALLY blocked.
# The contract gate verifies these remain blocked (not accidentally allowed).
KNOWN_BLOCKED = {
    "sahjhan reset",
    "sahjhan reset --confirm",
    "sahjhan daemon stop",
}


def extract_sahjhan_commands(md_path: str) -> list[tuple[str, int, str]]:
    """Extract sahjhan commands from fenced code blocks in a markdown file.

    Returns list of (command, line_number, file_path) tuples.
    """
    with open(md_path, encoding="utf-8") as f:
        lines = f.readlines()

    commands: list[tuple[str, int, str]] = []
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            # Match lines that contain a sahjhan command
            # Handle line continuations (trailing \)
            cmd = stripped.rstrip("\\").strip()
            if not cmd:
                continue
            # Skip shell comments
            if cmd.startswith("#"):
                continue
            # Only extract lines where sahjhan is actually being invoked
            # (not just mentioned in comments or as part of a path)
            if re.search(r'(?:^|\s|nohup\s+)sahjhan\s', cmd):
                # Clean up: strip leading shell prefixes that aren't part
                # of the command itself (like cp, echo, etc.)
                # We want the actual sahjhan invocation
                commands.append((cmd, i, md_path))

    return commands


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


def is_known_blocked(cmd: str) -> bool:
    """Check if a command matches any known-blocked pattern."""
    normalized = normalize_command(cmd)
    return any(
        normalized == blocked or normalized.startswith(blocked + " ")
        for blocked in KNOWN_BLOCKED
    )


def main() -> int:
    verbose = "--verbose" in sys.argv

    # Find all markdown files under skills/
    md_files: list[str] = []
    for root, _dirs, files in os.walk(SKILLS_DIR):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))

    md_files.sort()

    # Extract all sahjhan commands
    all_commands: list[tuple[str, int, str]] = []
    for md_path in md_files:
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

    for cmd, line_no, file_path in all_commands:
        rel_path = os.path.relpath(file_path, REPO_ROOT)
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
                failures.append(
                    f"  FAIL (should be BLOCKED): {rel_path}:{line_no}: {cmd}\n"
                    f"         This command is in KNOWN_BLOCKED but the hook allowed it."
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

    # Report
    print(f"\nContract gate: {tested} commands tested "
          f"({allowed_count} should-allow, {blocked_count} should-block)")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):\n")
        for f in failures:
            print(f)
        print()
        return 1

    print("All commands match expected hook decisions. PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

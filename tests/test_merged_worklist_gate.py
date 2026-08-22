"""The fix loop must not start with a second worklist still on disk.

P0.4 deleted `PUNCHLIST-MERGED.md` as a concept: the merge writes findings onto
the ledger and `PUNCHLIST.md` is the rendered view of it. The measured failure
is what a leftover copy costs. One run's merged file was written once, at
17:53, re-rendered by nothing, and still marked all 178 findings OPEN including
the 81 already fixed; a later session ran four pattern rounds grepping it
exclusively, blind to 176 findings and 25 committed fixes, and 111 subagent
minutes went to reconciling the bookkeeping against reality afterwards.

The clause gates its deletion at the `merge -> fix_loop` transition. That is
the inverse of the shape that wedged issue #60 — a `file_exists` on this same
path while the PreToolUse guard forbade writing it, so the only satisfying act
was blocked and the run stopped for good. This gate is satisfied by deleting
the file, and the path is deliberately absent from `MANAGED_DOCS`, so the
escape is achievable by construction rather than by permission. Both halves are
proven here: that the delete is allowed, and that the gate reads it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parent.parent
ENFORCEMENT = REPO_ROOT / "enforcement"
MERGED = "docs/holtz/PUNCHLIST-MERGED.md"

sys.path.insert(0, str(ENFORCEMENT / "hooks"))


def _binary() -> str:
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def merged_state(tmp_path):
    """A project sitting in `merge_done`, one transition from the fix loop."""
    binary = _binary()
    root = str(tmp_path)
    (tmp_path / "docs" / "holtz").mkdir(parents=True, exist_ok=True)

    def sah(*args, check=True):
        result = subprocess.run(
            [binary, "--config-dir", str(ENFORCEMENT), *args],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    sah("init")
    # Straight to the state under test rather than walking nine transitions —
    # every one of them has gates of its own and none is what this asserts.
    sah("event", "state_transition", "--field", "from=merge_ready",
        "--field", "to=merge_done", "--field", "command=merge_complete")

    def gate_lines():
        out = sah("gate", "check", "fix_loop_start", check=False).stdout
        return [line.strip() for line in out.splitlines()]

    return tmp_path, gate_lines


def _deletion_gate(lines: list[str]) -> str:
    match = [line for line in lines if "not" in line and "file_exists" in line]
    assert match, f"no not(file_exists) gate in the check output: {lines}"
    return match[0]


class TestTheDeletionGate:

    def test_the_gate_blocks_while_the_merged_worklist_exists(self, merged_state):
        root, gate_lines = merged_state
        (root / MERGED).write_text("| BH-001 | OPEN |\n", encoding="utf-8")

        assert _deletion_gate(gate_lines()).startswith("✗"), (
            "the fix loop may start with a stale second worklist on disk"
        )

    def test_deleting_it_satisfies_the_gate(self, merged_state):
        """The escape's post-state, asserted — not just the block."""
        root, gate_lines = merged_state
        (root / MERGED).write_text("| BH-001 | OPEN |\n", encoding="utf-8")
        assert _deletion_gate(gate_lines()).startswith("✗")

        (root / MERGED).unlink()

        assert _deletion_gate(gate_lines()).startswith("✓"), (
            "deleting the file does not satisfy the gate that demands it be gone"
        )

    def test_a_run_that_never_wrote_one_is_not_blocked(self, merged_state):
        _, gate_lines = merged_state
        assert _deletion_gate(gate_lines()).startswith("✓")


class TestTheEscapeIsReachable:

    def test_the_pretooluse_guard_allows_the_delete(self, tmp_path):
        """#60 in one assertion: a gate whose escape the guard blocks is a wedge.

        `PUNCHLIST-MERGED.md` is absent from MANAGED_DOCS for exactly this
        reason, so the check is against the hook rather than against the list.
        """
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"rm {MERGED}"},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, str(ENFORCEMENT / "hooks" / "_sahjhan_bootstrap.py")],
            input=json.dumps(event), capture_output=True, text=True,
            timeout=30, cwd=str(tmp_path), env=env,
        )
        decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow", (
            f"the only act that satisfies the deletion gate is blocked: {result.stdout}"
        )


def test_the_gate_is_declared_on_the_merge_to_fix_loop_edge():
    """Config-level, so a gate moved to another edge fails here and not in a run."""
    cfg = tomllib.loads((ENFORCEMENT / "transitions.toml").read_text())
    edge = next(
        t for t in cfg["transitions"]
        if t.get("from") == "merge_done" and t.get("command") == "fix_loop_start"
    )
    negated_paths = [
        child.get("path")
        for gate in edge.get("gates", []) if gate.get("type") == "not"
        for child in gate.get("gates", []) if child.get("type") == "file_exists"
    ]
    assert MERGED in negated_paths, (
        f"the merge -> fix_loop edge does not require {MERGED} to be gone: {edge}"
    )

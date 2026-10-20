"""Pattern analysis is owed at the batch boundary, not at every commit.

`git commit` used to be hard-blocked while `pattern_analysis_overdue` was true.
That fires between "the fix is written, verified and green" and "the fix is
recorded" — the one moment where nothing is gained by stopping, because the work
already exists on disk. The agent then ran a 17.9-min median analysis round on
top of an uncommitted fix and came back. One measured commit turned a 4.9-min
fix into 24.0 minutes; across the run, pattern rounds were 1.85x a fix cycle and
43% of in-loop time.

The obligation itself is unchanged and still hard. It is enforced where the fix
batch actually ends — `iteration_boundary` (the /clear) and `set complete
perspective` (the lens) — both gating on the same named query with the opposite
expectation to `pattern_check`'s. Commits get the advisory that always existed
alongside the block.

These tests pin that no ledger state blocks a commit on pattern analysis, that
the advisory survives, and that removing the block did not disturb the
unregistered-commit block sharing the same hook.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

pytestmark = [pytest.mark.hook_e2e, pytest.mark.integration, pytest.mark.slow]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, HOOKS_DIR)


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _init_ledger(project_root: str, resolved_findings: int = 0) -> None:
    """A real ledger with `resolved_findings` findings closed and no analysis."""
    binary = _binary()

    def run(*args):
        result = subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, *args],
            capture_output=True, text=True, cwd=project_root, timeout=30,
        )
        assert result.returncode == 0, (
            f"sahjhan {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
        )

    run("init")
    for n in range(1, resolved_findings + 1):
        run(
            "event", "finding_resolved",
            "--field", f"id=BH-{n:03d}", "--field", "project=t",
            "--field", "run=1", "--field", "auditor=holtz",
            "--field", "phase=fix_loop", "--field", "step=10",
            "--field", "commit_hash=abc1234",
        )


def _cache_says_overdue(project_root: str, unregistered: list[str] | None = None) -> None:
    from _protocol_cache import empty_cache, write_cache
    cache = empty_cache()
    cache["state"] = "fix_loop"
    cache["active"] = True
    cache["unregistered_commits"] = unregistered or []
    cache["pattern_analysis_overdue"] = True
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    write_cache(project_root, cache)


def _commit_gate(project_root: str, command: str = "git commit -m 'fix: next'"):
    """(decision, reason, additionalContext) for one Bash command."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": project_root,
    }
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, "commit_gate.py")],
        input=json.dumps(event), capture_output=True, text=True,
        cwd=project_root, timeout=60,
    )
    if not result.stdout.strip():
        return "allow", "", ""
    payload = json.loads(result.stdout).get("hookSpecificOutput", {})
    return (
        payload.get("permissionDecision", ""),
        payload.get("permissionDecisionReason", ""),
        payload.get("additionalContext", ""),
    )


class TestTheCommitPathIsNotAPatternGate:

    @pytest.mark.parametrize("resolved", [0, 3, 12])
    def test_no_backlog_size_blocks_the_commit(self, tmp_path, mock_daemon, resolved):
        """Not a stale-snapshot carve-out: the ledger agrees at 3 and at 12 and
        the commit goes through anyway. The obligation is owed elsewhere."""
        _init_ledger(str(tmp_path), resolved_findings=resolved)
        _cache_says_overdue(str(tmp_path))

        decision, reason, _ = _commit_gate(str(tmp_path))
        assert decision != "deny", (
            f"Blocked a verified fix from being recorded, {resolved} resolved: {reason}"
        )

    def test_the_commit_still_carries_the_advisory(self, tmp_path, mock_daemon):
        """Dropping the block must not drop the notice — the round is still owed
        before the next /clear."""
        _init_ledger(str(tmp_path), resolved_findings=3)
        _cache_says_overdue(str(tmp_path))

        decision, _, context = _commit_gate(str(tmp_path))
        assert decision == "allow"
        assert "pattern_check" in context, (
            f"The commit says nothing about the owed round: {context!r}"
        )

    def test_unregistered_commits_still_block(self, tmp_path, mock_daemon):
        """The other commit block lives in the same hook and is unrelated."""
        _init_ledger(str(tmp_path), resolved_findings=3)
        _cache_says_overdue(str(tmp_path), unregistered=["abc1234"])

        decision, reason, _ = _commit_gate(str(tmp_path))
        assert decision == "deny", "Unregistered commits must still block"
        assert "fix_commit" in reason

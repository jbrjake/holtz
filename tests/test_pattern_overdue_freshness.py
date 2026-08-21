"""The pattern-analysis block must be decided by the ledger, not by a snapshot.

`pattern_analysis_overdue` is a named query over the ledger, but the commit
gate read it out of the enforcement cache — a value written only when
protocol_tracker happens to observe a sahjhan command. Any command it fails to
observe, or a status refresh that times out, leaves the flag describing a
ledger that has since moved on.

A commit blocked that way is unanswerable: the block prints "run transition
pattern_check" and the analysis has already been done. In the run this came
from, blocked commits were held 12-25 minutes each.

So the gate re-derives the fact at the moment it would block. These tests pin
both directions — a stale flag must not block, and an unanswerable query must
not become an all-clear.

The ledger here is real and the daemon is not involved: `sahjhan query` and
plain `event` writes resolve and append the ledger file directly, which is the
same path the gates evaluate.
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


def _cache_says_overdue(project_root: str) -> None:
    from _protocol_cache import empty_cache, write_cache
    cache = empty_cache()
    cache["state"] = "fix_loop"
    cache["active"] = True
    cache["unregistered_commits"] = []
    cache["pattern_analysis_overdue"] = True
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    write_cache(project_root, cache)


def _commit_gate(project_root: str) -> tuple[str, str]:
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'fix: next'"},
        "cwd": project_root,
    }
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, "commit_gate.py")],
        input=json.dumps(event), capture_output=True, text=True,
        cwd=project_root, timeout=60,
    )
    if not result.stdout.strip():
        return "allow", ""
    payload = json.loads(result.stdout).get("hookSpecificOutput", {})
    return (
        payload.get("permissionDecision", ""),
        payload.get("permissionDecisionReason", ""),
    )


class TestPatternOverdueIsDecidedByTheLedger:

    def test_stale_flag_does_not_block_when_the_ledger_disagrees(
        self, tmp_path, mock_daemon,
    ):
        """The ledger owes no analysis, so a stale cached flag must not block.

        Nothing has been resolved, so the named query is false. Before the fix
        the cached True was the whole decision and the commit was denied with
        an escape the agent had already run.
        """
        _init_ledger(str(tmp_path), resolved_findings=0)
        _cache_says_overdue(str(tmp_path))

        decision, reason = _commit_gate(str(tmp_path))
        assert decision != "deny", (
            f"Blocked a commit on a stale flag the ledger contradicts: {reason}"
        )

    def test_real_backlog_still_blocks(self, tmp_path, mock_daemon):
        """When the ledger confirms the backlog, the block is unchanged.

        Three findings resolved with no pattern analysis after them is exactly
        what the named query counts, so this is the gate doing its job.
        """
        _init_ledger(str(tmp_path), resolved_findings=3)
        _cache_says_overdue(str(tmp_path))

        decision, reason = _commit_gate(str(tmp_path))
        assert decision == "deny", "A real backlog must still block the commit"
        assert "pattern_check" in reason

    def test_analysis_recorded_after_the_fixes_clears_the_block(
        self, tmp_path, mock_daemon,
    ):
        """Recording the analysis is what lifts the block, without a refresh.

        This is the shape that cost the run: the analysis is in the ledger and
        the cache has not caught up. The commit must go through on the ledger's
        word.
        """
        _init_ledger(str(tmp_path), resolved_findings=3)
        subprocess.run(
            [_binary(), "--config-dir", CONFIG_DIR, "event",
             "pattern_analysis_complete",
             "--field", "project=t", "--field", "run=1",
             "--field", "auditor=holtz", "--field", "phase=fix_loop",
             "--field", "step=11", "--field", "patterns_found=2",
             "--field", "siblings_found=0"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30, check=True,
        )
        _cache_says_overdue(str(tmp_path))

        decision, reason = _commit_gate(str(tmp_path))
        assert decision != "deny", (
            f"The analysis is recorded; the block must lift: {reason}"
        )

    def test_unanswerable_query_keeps_the_block(self, tmp_path, monkeypatch):
        """No binary means no answer, and no answer is not an all-clear.

        Re-deriving must fail toward the cached obligation; the opposite would
        turn every environment problem into a silent enforcement bypass.
        """
        import commit_gate
        monkeypatch.setattr(commit_gate, "ensure_sahjhan", lambda: None)
        assert commit_gate._pattern_analysis_still_overdue(
            str(tmp_path), CONFIG_DIR,
        ) is True

"""W32 / item 51 — every checkout of a project reaches *the* project's ledger.

`protocol.toml` puts `data_dir` at `docs/holtz/.sahjhan`, and `.gitignore`
carries it, so no checkout `git worktree add` produces ever contains one. The
engine finds the project by walking up from the caller for the ancestor holding
that directory — and a worktree placed *beside* the main checkout has no such
ancestor. Before the pin moved to 0.25.0 it therefore anchored on itself, and
every enforcement command from there failed with `I/O error (os error 2)`: same
repository, same config, same `--config-dir`, only the directory different.

These tests pin the three cases against the binary holtz actually ships, so a
pin that moved backwards fails here rather than in a user's sibling worktree:

* a **sibling** worktree reads and writes the main checkout's ledger,
* a **nested** worktree — what Claude Code's `isolation: "worktree"` produces,
  and the case that already worked — still does,
* a directory in **no repository** still anchors on itself.

The write half is what makes the first claim mean something. A sibling that
grew a ledger of its own next to the caller would answer a count query just as
happily and still be the bug; only reading the event back *from the main
checkout* distinguishes reaching the ledger from inventing one.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_env import scrubbed_env  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = str(REPO_ROOT / "enforcement")

#: Recorded from the sibling worktree and read back from the main checkout.
#: A value nothing else in the ledger can produce, so the read-back is an
#: assertion about *this* write rather than about the row count.
MARKER = "marker-recorded-from-the-sibling-worktree"


def _git(*args: str, cwd: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env=scrubbed_env(),
    )


@dataclass
class AnchorProject:
    """A main checkout plus the three other directories a caller can be in."""

    main: str
    sibling: str
    nested: str
    outside: str
    binary: str

    def sahjhan(self, *args: str, cwd: str) -> subprocess.CompletedProcess[str]:
        """Run the shipped binary from ``cwd``, as a hook or an agent would."""
        return subprocess.run(
            [self.binary, "--config-dir", CONFIG_DIR, *args],
            cwd=cwd, capture_output=True, text=True, env=scrubbed_env(),
        )

    def query(self, sql: str, *, cwd: str) -> list[dict]:
        result = self.sahjhan("query", sql, "--format", "json", cwd=cwd)
        assert result.returncode == 0, result.stderr or result.stdout
        return json.loads(result.stdout) if result.stdout.strip() else []


@pytest.fixture
def anchor_project(tmp_path):
    """A project whose ignored data dir exists only in the main checkout."""
    sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))
    from _resolve import ensure_sahjhan

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")

    main = str(tmp_path / "project")
    os.makedirs(main)
    _git("init", "-q", "-b", "main", ".", cwd=main)
    _git("config", "user.email", "t@example.com", cwd=main)
    _git("config", "user.name", "T", cwd=main)
    with open(os.path.join(main, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("docs/holtz/.sahjhan/\n")
    _git("add", ".gitignore", cwd=main)
    _git("commit", "-qm", "init", cwd=main)

    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        cwd=main, check=True, capture_output=True, text=True, env=scrubbed_env(),
    )

    sibling = str(tmp_path / "project-fix-a")
    _git("worktree", "add", "-q", "--detach", sibling, "HEAD", cwd=main)
    nested = os.path.join(main, ".claude", "worktrees", "fix-b")
    _git("worktree", "add", "-q", "--detach", nested, "HEAD", cwd=main)

    outside = str(tmp_path / "outside")
    os.makedirs(outside)

    for checkout in (sibling, nested):
        assert not os.path.isdir(os.path.join(checkout, "docs", "holtz", ".sahjhan")), (
            "the fixture is pointless if a worktree carries the data dir"
        )
    return AnchorProject(
        main=main, sibling=sibling, nested=nested, outside=outside, binary=binary,
    )


class TestV1TheSiblingWorktreeReachesTheProjectLedger:
    """V1 — the layout `git worktree add ../myrepo-feature` produces."""

    def test_it_reads_the_same_ledger_as_the_main_checkout(self, anchor_project):
        from_main = anchor_project.query(
            "SELECT type FROM events ORDER BY seq", cwd=anchor_project.main,
        )
        from_sibling = anchor_project.query(
            "SELECT type FROM events ORDER BY seq", cwd=anchor_project.sibling,
        )
        assert from_sibling == from_main
        assert from_main, "an initialized project has a genesis event to read"

    def test_it_writes_to_that_ledger_rather_than_growing_its_own(self, anchor_project):
        recorded = anchor_project.sahjhan(
            "event", "bash_command", "--field", f"command={MARKER}",
            cwd=anchor_project.sibling,
        )
        assert recorded.returncode == 0, recorded.stderr

        seen_from_main = anchor_project.query(
            f"SELECT command FROM events WHERE command='{MARKER}'",
            cwd=anchor_project.main,
        )
        assert [row["command"] for row in seen_from_main] == [MARKER]
        assert not os.path.isdir(
            os.path.join(anchor_project.sibling, "docs", "holtz", ".sahjhan")
        ), "the sibling grew a ledger of its own instead of reaching the project's"


class TestV2TheNestedWorktreeKeepsWorking:
    """V2 — `isolation: "worktree"`'s layout, which resolves by the walk-up alone."""

    def test_it_reads_the_same_ledger_as_the_main_checkout(self, anchor_project):
        from_main = anchor_project.query(
            "SELECT type FROM events ORDER BY seq", cwd=anchor_project.main,
        )
        from_nested = anchor_project.query(
            "SELECT type FROM events ORDER BY seq", cwd=anchor_project.nested,
        )
        assert from_nested == from_main


class TestV3ADirectoryInNoRepositoryStillAnchorsOnItself:
    """V3 — the fallback is unchanged: no repository, no borrowed ledger."""

    def test_it_does_not_reach_the_project_ledger(self, anchor_project):
        anchor_project.sahjhan(
            "event", "bash_command", "--field", f"command={MARKER}",
            cwd=anchor_project.sibling,
        )
        result = anchor_project.sahjhan(
            "query", f"SELECT command FROM events WHERE command='{MARKER}'",
            "--format", "json", cwd=anchor_project.outside,
        )
        assert result.returncode != 0
        assert MARKER not in result.stdout

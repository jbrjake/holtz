"""Tests for enforcement/scripts/verify_suite.py — the suite_green mechanism.

Three layers, because the mechanism has three separable claims:

* **Unit** — the tree hash is stable, sensitive to anything that can change a
  test outcome, and blind to the documents the fix loop rewrites every fix.
* **Subprocess (hook_e2e)** — the CLI honours the contract a gate depends on:
  a red suite records nothing, a missing event blocks, and the block prints a
  command that runs.
* **real_daemon** — the parts only a real daemon can decide: that a restricted
  ``suite_green`` from a hash-pinned caller is accepted, that the agent's own
  ``sahjhan event suite_green`` is refused, and that a green recorded for one
  tree does not satisfy a check on a different one.

The last is the point of the whole design. A gate that trusted "the suite
passed" without binding it to a *tree* would let a fix land on the strength of
a suite run from before the fix — the false-green class of #83, arriving by a
different road.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_SUITE = os.path.join(REPO_ROOT, "enforcement", "scripts", "verify_suite.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "scripts"))
import verify_suite  # noqa: E402, I001


# ── Helpers ──────────────────────────────────────────────────────────────────


def _git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )


def _init_repo(path):
    """A minimal git repo with one commit and a .gitignore."""
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    with open(os.path.join(path, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("ignored/\n")
    with open(os.path.join(path, "app.py"), "w", encoding="utf-8") as fh:
        fh.write("def add(a, b):\n    return a + b\n")
    # Explicit paths, not `add -A`: the real_daemon fixture's project root
    # already holds a live daemon socket under docs/holtz/.sahjhan, and git
    # cannot add a socket.
    _git(path, "add", ".gitignore", "app.py")
    _git(path, "commit", "-qm", "init")
    return path


def _write(path, rel, text):
    full = os.path.join(path, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def _run_verify(repo, *args, env=None):
    """Invoke verify_suite.py the way an agent or a gate does — by path."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, VERIFY_SUITE, *args, "--cwd", repo],
        cwd=repo,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=120,
    )


@pytest.fixture
def repo(tmp_path):
    return _init_repo(str(tmp_path / "proj"))


# ── Unit: the tree hash ──────────────────────────────────────────────────────


class TestTreeHash:
    def test_is_64_hex_and_stable(self, repo):
        first = verify_suite.compute_tree_hash(repo)
        second = verify_suite.compute_tree_hash(repo)
        assert first == second
        assert verify_suite._TREE_HASH_RE.match(first), first

    def test_modifying_a_tracked_file_changes_it(self, repo):
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, "app.py", "def add(a, b):\n    return a - b\n")
        assert verify_suite.compute_tree_hash(repo) != before

    def test_reverting_restores_it(self, repo):
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, "app.py", "def add(a, b):\n    return a - b\n")
        _git(repo, "checkout", "--", "app.py")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_new_untracked_source_changes_it(self, repo):
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, "extra.py", "x = 1\n")
        assert verify_suite.compute_tree_hash(repo) != before

    def test_deleting_a_tracked_file_changes_it(self, repo):
        """Deleting the failing test must not look like the same tree."""
        before = verify_suite.compute_tree_hash(repo)
        os.remove(os.path.join(repo, "app.py"))
        assert verify_suite.compute_tree_hash(repo) != before

    def test_committing_the_same_content_changes_it(self, repo):
        """Committing moves HEAD, and HEAD's oid is part of the hash.

        This is the one place the hash is *stricter* than "same content":
        `fix_commit` records a commit, so the tree it gates and the tree the
        subagent proved are the same content under different HEADs. T4 has to
        record the green after the commit, not before — this test is here so
        that constraint is discovered by a failing test rather than by a fix
        loop that silently re-runs the suite every time.
        """
        _write(repo, "app.py", "def add(a, b):\n    return a + b  # x\n")
        before = verify_suite.compute_tree_hash(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "same content, new HEAD")
        assert verify_suite.compute_tree_hash(repo) != before

    @pytest.mark.parametrize(
        "rel",
        ["docs/holtz/STATUS.md", "docs/holtz/PUNCHLIST.md", "docs/holtz/.sahjhan/x"],
    )
    def test_docs_holtz_is_excluded(self, repo, rel):
        """STATUS/PUNCHLIST are rewritten every fix and cannot affect tests.

        The ledger under docs/holtz/.sahjhan matters most: `--record` appends
        to it, so counting it would invalidate the hash the instant it was
        recorded.
        """
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, rel, "anything at all\n")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_tracked_docs_holtz_change_is_excluded(self, repo):
        _write(repo, "docs/holtz/STATUS.md", "v1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "status")
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, "docs/holtz/STATUS.md", "v2 — rewritten by the fix loop\n")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_gitignored_files_are_excluded(self, repo):
        """A byte-compile or a venv write must not invalidate a green suite."""
        before = verify_suite.compute_tree_hash(repo)
        _write(repo, "ignored/build.log", "noise\n")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_repo_with_no_commits_still_hashes(self, tmp_path):
        path = str(tmp_path / "empty")
        os.makedirs(path)
        _git(path, "init", "-q")
        _write(path, "a.py", "x = 1\n")
        first = verify_suite.compute_tree_hash(path)
        assert verify_suite._TREE_HASH_RE.match(first), first
        _write(path, "a.py", "x = 2\n")
        assert verify_suite.compute_tree_hash(path) != first


class TestScopeOrdering:
    def test_full_only_accepts_full(self):
        assert verify_suite.accepted_scopes("full") == ("full",)

    def test_affected_also_accepts_full(self):
        """Running more tests than asked can never turn a red suite green."""
        assert verify_suite.accepted_scopes("affected") == ("affected", "full")


class TestSuiteCommand:
    def test_default_fails_fast_without_truncating(self):
        """Same contract T1 pinned on the gates, now on the writer.

        `--lf`/`--last-failed` runs *only* the previously failing tests, so a
        green recorded under it can mean a two-test subset passed. `--no-cov`
        belongs to pytest-cov and exits 4 on a target without that plugin.
        """
        default = verify_suite.DEFAULT_PYTEST
        assert "-x" in default.split()
        assert "--ff" in default.split()
        assert "--lf" not in default
        assert "--last-failed" not in default
        assert "--no-cov" not in default

    def test_holtz_pytest_overrides(self, monkeypatch):
        monkeypatch.setenv("HOLTZ_PYTEST", "pytest -q custom")
        assert verify_suite.suite_command() == "pytest -q custom"

    def test_empty_override_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("HOLTZ_PYTEST", "")
        assert verify_suite.suite_command() == verify_suite.DEFAULT_PYTEST


# ── Subprocess: the CLI contract a gate depends on ───────────────────────────


@pytest.mark.hook_e2e
class TestCliContract:
    def test_non_git_directory_fails_closed(self, tmp_path):
        """No tree hash means no honest answer, so it must not allow."""
        plain = str(tmp_path / "plain")
        os.makedirs(plain)
        result = _run_verify(plain, "--check")
        assert result.returncode == 1
        assert "not inside a git repository" in result.stderr

    def test_record_and_check_are_mutually_exclusive(self, repo):
        result = _run_verify(repo, "--record", "--check")
        assert result.returncode == 2

    def test_print_tree_hash_matches_the_library(self, repo):
        result = _run_verify(repo, "--print-tree-hash")
        assert result.returncode == 0
        assert result.stdout.strip() == verify_suite.compute_tree_hash(repo)

    def test_red_suite_records_nothing_and_reports_the_exit_code(self, repo):
        """A failing suite must not reach the daemon at all."""
        result = _run_verify(repo, "--record", env={"HOLTZ_PYTEST": "exit 3"})
        assert result.returncode == 3
        assert "nothing recorded" in result.stderr

    def test_check_without_evidence_blocks_and_prints_a_runnable_escape(self, repo):
        """A block whose printed escape does not run is the #77 deadlock.

        This project has no ledger at all, which the engine reports as an I/O
        error rather than a zero count — the case that first exposed a block
        with no escape on it. Whatever the reason, the check must name a
        command that runs.
        """
        result = _run_verify(repo, "--check")
        assert result.returncode == 1
        assert "FAIL:" in result.stderr
        assert f"tree_hash={verify_suite.compute_tree_hash(repo)}" in result.stderr

        escape = next(
            line.split("Run:", 1)[1].strip()
            for line in result.stderr.splitlines()
            if "Run:" in line
        )
        assert escape.startswith("python3 ")
        assert os.path.isfile(escape.split()[1]), escape
        assert "--record" in escape


# ── real_daemon: what only the engine can decide ─────────────────────────────


@pytest.mark.slow
@pytest.mark.integration
class TestAgainstRealDaemon:
    """The trust story, exercised end to end against a real sahjhan daemon."""

    @staticmethod
    def _prepare(real_daemon):
        """Make the daemon's project root a git repo with an active ledger."""
        root = real_daemon["project_root"]
        _init_repo(root)
        subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"],
             "ledger", "create", "--from", "run", "1", "--activate"],
            cwd=root, capture_output=True, text=True, check=True, timeout=10,
        )
        return root

    @staticmethod
    def _greens(real_daemon):
        result = subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"],
             "--json", "log", "dump"],
            cwd=real_daemon["project_root"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        entries = json.loads(result.stdout)["data"]["entries"]
        return [
            e.get("fields", {}) for e in entries
            if e.get("event_type") == "suite_green"
        ]

    @staticmethod
    def _env(real_daemon):
        return {"SAHJHAN_DAEMON_SOCKET": real_daemon["sock_path"],
                "HOLTZ_PYTEST": "echo '4 passed'"}

    def test_green_suite_records_an_accepted_event(self, real_daemon):
        root = self._prepare(real_daemon)
        expected = verify_suite.compute_tree_hash(root)

        result = _run_verify(root, "--record", env=self._env(real_daemon))
        assert result.returncode == 0, (
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        greens = self._greens(real_daemon)
        assert len(greens) == 1, f"expected one suite_green, got {greens!r}"
        assert greens[0]["tree_hash"] == expected
        assert greens[0]["scope"] == "full"
        assert greens[0]["test_count"] == "4"

    def test_check_passes_only_for_the_tree_that_was_proven(self, real_daemon):
        """Record on one tree, mutate, and the gate must stop trusting it.

        This is the whole reason the event carries a hash. Without it a fix
        could land on the strength of a suite run from before the fix.
        """
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)

        assert _run_verify(root, "--record", env=env).returncode == 0
        assert _run_verify(root, "--check", env=env).returncode == 0

        _write(root, "app.py", "def add(a, b):\n    return a - b\n")
        stale = _run_verify(root, "--check", env=env)
        assert stale.returncode == 1
        assert "no suite_green for this working tree" in stale.stderr

        _git(root, "checkout", "--", "app.py")
        assert _run_verify(root, "--check", env=env).returncode == 0

    def test_docs_holtz_churn_does_not_invalidate_a_green(self, real_daemon):
        """The fix loop rewrites STATUS.md every fix; that must be free."""
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)

        assert _run_verify(root, "--record", env=env).returncode == 0
        _write(root, "docs/holtz/STATUS.md", "rewritten\n")
        assert _run_verify(root, "--check", env=env).returncode == 0

    def test_agent_cannot_record_suite_green_directly(self, real_daemon):
        """`restricted` is layer one: the daemon refuses the bare CLI.

        The agent has `sahjhan event` on its bootstrap allowlist, so this is
        the check that stops it from simply claiming a green. The control
        below is what makes the assertion mean something: an *unrestricted*
        event, recorded the same way against the same ledger, must succeed —
        otherwise a broken fixture would look like enforcement.
        """
        root = self._prepare(real_daemon)
        forged = verify_suite.compute_tree_hash(root)
        result = subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"],
             "event", "suite_green",
             "--field", f"tree_hash={forged}",
             "--field", "scope=full",
             "--field", "command=true",
             "--field", "project=proj",
             "--field", "run=1",
             "--field", "auditor=holtz"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0, (
            "the daemon accepted a bare `sahjhan event suite_green` — "
            "restricted = true is not in force"
        )
        assert "restricted" in result.stderr, (
            "refused, but not for being restricted — the assertion above "
            f"would pass on any incidental failure. stderr: {result.stderr!r}"
        )
        assert not self._greens(real_daemon)

        control = subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"],
             "event", "test_failed_before_fix",
             "--field", "finding_id=BH-001",
             "--field", "test_name=t",
             "--field", "project=proj",
             "--field", "run=1",
             "--field", "auditor=holtz"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        assert control.returncode == 0, (
            "the control event failed too, so the refusal above proves "
            f"nothing about `restricted`. stderr: {control.stderr!r}"
        )

    def test_a_forged_hash_does_not_satisfy_the_gate(self, real_daemon):
        """Even a well-formed hash for another tree must not open the gate."""
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)
        assert _run_verify(root, "--record", env=env).returncode == 0

        # A different tree, proven green, is still a different tree.
        _write(root, "app.py", "def add(a, b):\n    return a * b\n")
        assert _run_verify(root, "--check", env=env).returncode == 1

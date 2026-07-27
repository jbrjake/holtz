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
import re
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


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _node(node_id, file, node_type="function"):
    return {"id": node_id, "type": node_type, "file": file, "line": 1}


def _write_graph(repo, nodes, edges):
    _write(
        repo,
        os.path.join("docs", "holtz", "impact-graph.json"),
        json.dumps({"nodes": nodes, "edges": edges}),
    )


@pytest.fixture
def repo(tmp_path):
    return _init_repo(str(tmp_path / "proj"))


@pytest.fixture
def baselined(repo, monkeypatch):
    """A repo whose last full green was recorded at HEAD.

    Stubs the ledger read so the selection logic can be exercised as a unit.
    What it returns is a *real* commit in the repo, so everything downstream —
    the diff, the file existence checks — runs for real.
    """
    head = _head(repo)
    monkeypatch.setattr(verify_suite, "_baseline_commit", lambda cwd: (head, ""))
    return repo


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

    def test_committing_the_same_content_preserves_it(self, repo):
        """The hash names content, so `git commit` cannot move it.

        This is the property the whole one-run-per-fix collapse rests on.
        `git commit` does not touch a single working-tree byte, so a green
        proven before it is still true after it. While the hash included
        HEAD's oid it was *stricter* than "same content", and the fix loop had
        to record a second green after every commit purely to restore evidence
        the commit had invalidated for no reason.

        Sensitivity is not traded away for this — see the tests either side:
        editing, deleting, and reverting all still move the hash. What is
        given up is stated in the module docstring and pinned by
        `test_amending_only_the_message_preserves_it`: a suite that asserts
        things about git *history* rather than about content can pass a check
        on evidence proven under a different history.
        """
        _write(repo, "app.py", "def add(a, b):\n    return a + b  # x\n")
        _write(repo, "test_new.py", "def test_x(): pass\n")
        before = verify_suite.compute_tree_hash(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "same content, new HEAD")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_amending_only_the_message_preserves_it(self, repo):
        """The accepted bound, pinned so it is a decision and not a surprise.

        Content is all the hash sees, so rewording a commit leaves a green
        valid. For a target whose suite lints commit messages that is a false
        green. It is accepted deliberately: the alternative — the HEAD-oid
        hash — costs a whole extra suite run on every fix to defend against a
        case where the *test suite reads git history*, which is rare, while
        the cost it imposes is universal.
        """
        before = verify_suite.compute_tree_hash(repo)
        _git(repo, "commit", "--amend", "-qm", "a completely different message")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_staging_without_committing_does_not_move_it(self, repo):
        """`git add` is not a content change, so it must not invalidate a green.

        The fix loop stages before it commits. If staging moved the hash, the
        commit step would need its own re-record all over again — the exact
        cost this design removes, reintroduced one step earlier.
        """
        _write(repo, "app.py", "def add(a, b):\n    return a + b  # staged\n")
        before = verify_suite.compute_tree_hash(repo)
        _git(repo, "add", "-A")
        assert verify_suite.compute_tree_hash(repo) == before

    def test_hashing_writes_nothing_into_the_repo(self, repo):
        """`--check` is a predicate; it must not mutate the tree it inspects.

        Computing a content hash means asking git to hash file contents, and
        `git add` writes those blobs into the object store by default. A gate
        that grew the target's `.git/objects` on every check would be leaving
        unreferenced garbage in a repo it was only supposed to read, so the
        object directory is redirected at a temp dir with the real store as an
        alternate: dedup still works, the writes are discarded.
        """
        _write(repo, "brand_new_content.py", "x = 'never seen before'\n")
        objects = os.path.join(repo, ".git", "objects")

        def _snapshot():
            return {
                os.path.join(dirpath, name)
                for dirpath, _, names in os.walk(objects)
                for name in names
            }

        before = _snapshot()
        verify_suite.compute_tree_hash(repo)
        assert _snapshot() == before

        # And the real index is untouched — the hash uses a copy.
        status = _git(repo, "status", "--porcelain").stdout
        assert "?? brand_new_content.py" in status, status

    def test_a_same_second_same_size_edit_is_not_missed(self, repo):
        """The stat cache must never be trusted for a racily-clean entry.

        Hashing content means asking git, and git answers from the index's
        stat cache: same size and same mtime is taken as "unchanged" without
        reading a byte. Since git records whole seconds, a file rewritten in
        the same second it was staged is indistinguishable that way — the
        classic racy-git case. Git's own guard is to distrust any entry whose
        mtime is not older than the *index file's* mtime and re-read it.

        A copy of the index that does not carry the original's mtime silently
        turns that guard off: every entry then looks safely older than the
        copy, so a same-second same-size edit is read off the stale cached oid
        and the hash names a tree that no longer exists — a green for code
        nobody ran. Reproduced 5 times in 12 before the fix, which is why this
        test forces the condition instead of racing for it.

        `core.trustctime = false` is what makes it deterministic rather than
        timing-dependent: with ctime in play the rewrite is caught by the
        changed ctime, which masks the mtime question this test is about.
        """
        _git(repo, "config", "core.trustctime", "false")
        before = verify_suite.compute_tree_hash(repo)

        debug = _git(repo, "ls-files", "--debug", "app.py").stdout
        cached = int(re.search(r"mtime:\s*(\d+)", debug).group(1))
        original = "def add(a, b):\n    return a + b\n"
        edited = "def add(a, b):\n    return b + a\n"
        assert len(edited) == len(original), "the point is a same-size edit"
        _write(repo, "app.py", edited)
        # Entry mtime == what the index cached, and the index no newer than the
        # entry — precisely the state git must refuse to take on trust.
        os.utime(os.path.join(repo, "app.py"), (cached, cached))
        os.utime(os.path.join(repo, ".git", "index"), (cached, cached))

        assert verify_suite.compute_tree_hash(repo) != before

    def test_a_conflicted_tree_hashes_its_conflict_markers(self, repo):
        """A half-merged tree is a real content state, and hashes as one.

        Worth pinning because the intuition points the other way: `git
        write-tree` refuses an index with unmerged entries, so this looks like
        it should fail closed. It does not, because `git add -A` resolves the
        entries against the working tree first — and that is the honest
        answer. The files on disk contain conflict markers, which is content
        the suite will fail on, so it deserves a hash of its own rather than
        an error.
        """
        _git(repo, "checkout", "-qb", "other")
        _write(repo, "app.py", "def add(a, b):\n    return a * b\n")
        _git(repo, "commit", "-qam", "other side")
        _git(repo, "checkout", "-q", "-")
        _write(repo, "app.py", "def add(a, b):\n    return a - b\n")
        _git(repo, "commit", "-qam", "this side")
        merge = subprocess.run(
            ["git", "merge", "other"], cwd=repo, capture_output=True, text=True
        )
        assert merge.returncode != 0, "expected a conflict to set up this test"

        conflicted = verify_suite.compute_tree_hash(repo)
        assert verify_suite._TREE_HASH_RE.match(conflicted)
        _git(repo, "checkout", "--theirs", "--", "app.py")
        assert verify_suite.compute_tree_hash(repo) != conflicted

    def test_an_unusable_index_fails_closed(self, repo):
        """No honest hash exists, so raise rather than invent one.

        A fabricated digest is worse than an error in both directions: it
        either collides with a green that never covered this tree, or it
        blocks with a reason nobody can act on.
        """
        with open(os.path.join(repo, ".git", "index"), "wb") as fh:
            fh.write(b"not an index at all")
        with pytest.raises(verify_suite.TreeHashError):
            verify_suite.compute_tree_hash(repo)

    def test_an_unusable_index_blocks_the_cli_rather_than_crashing(self, repo):
        """And the CLI turns that into a block, not a traceback.

        A gate that dies with a stack trace still exits non-zero, so it fails
        closed either way — but the operator gets no usable statement of what
        broke, and `command_succeeds` surfaces the reason in the block.
        """
        with open(os.path.join(repo, ".git", "index"), "wb") as fh:
            fh.write(b"not an index at all")
        result = _run_verify(repo, "--check")
        assert result.returncode == 1
        assert "cannot hash the working tree" in result.stderr
        assert "Traceback" not in result.stderr

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


# ── Unit: affected-scope selection ───────────────────────────────────────────


class TestChangedSince:
    """What counts as "changed" — the input the whole selection rests on."""

    def test_sees_both_committed_and_uncommitted_work(self, repo):
        """One `git diff <commit>` spans both, and the fix loop needs both.

        The subagent proves its work before committing; the orchestrator
        proves the committed tree after. A baseline diff that only looked at
        commits would miss the first, and one that only looked at the working
        tree would miss the second.
        """
        base = _head(repo)
        _write(repo, "committed.py", "x = 1\n")
        _git(repo, "add", "committed.py")
        _git(repo, "commit", "-qm", "add")
        _write(repo, "app.py", "def add(a, b):\n    return b + a\n")
        _write(repo, "untracked.py", "y = 2\n")

        changed, reason = verify_suite._changed_since(repo, base)
        assert reason == ""
        assert changed == ["app.py", "committed.py", "untracked.py"]

    def test_docs_holtz_is_not_a_change(self, repo):
        """Same exclusion the tree hash makes, for the same reason."""
        base = _head(repo)
        _write(repo, "docs/holtz/STATUS.md", "rewritten\n")
        assert verify_suite._changed_since(repo, base) == ([], "")

    def test_an_unknown_baseline_is_refused_not_ignored(self, repo):
        """A baseline git cannot resolve must widen, never silently diff.

        `git diff` against a bad rev fails, and an empty result read as "no
        files changed" would look identical to a clean tree — which is how a
        selection of nothing gets recorded as a green.
        """
        changed, reason = verify_suite._changed_since(repo, "0" * 40)
        assert changed is None
        assert "not in this repository" in reason


class TestCoveringTests:
    def test_follows_the_edge_from_test_to_covered_entity(self):
        """Pins the direction the skill file teaches.

        `impact-graph-operations.md` says
        `add_edge <test_file_id> <function_id> tests`, so the source is the
        test. Reading it backwards would return an empty set here and a wrong
        set on a graph that happens to be symmetric — a comment cannot hold
        that down, so a test does.
        """
        nodes = {
            "app:add": _node("app:add", "app.py"),
            "t": _node("t", "tests/test_app.py", "test"),
        }
        edges = [{"source": "t", "target": "app:add", "type": "tests"}]
        assert verify_suite._covering_tests("app.py", nodes, edges) == {
            "tests/test_app.py"
        }

    def test_a_backwards_edge_covers_nothing(self):
        nodes = {
            "app:add": _node("app:add", "app.py"),
            "t": _node("t", "tests/test_app.py", "test"),
        }
        edges = [{"source": "app:add", "target": "t", "type": "tests"}]
        assert verify_suite._covering_tests("app.py", nodes, edges) == set()

    def test_other_edge_types_do_not_count_as_coverage(self):
        nodes = {
            "app:add": _node("app:add", "app.py"),
            "t": _node("t", "tests/test_app.py", "test"),
        }
        edges = [{"source": "t", "target": "app:add", "type": "calls"}]
        assert verify_suite._covering_tests("app.py", nodes, edges) == set()


class TestSelectAffected:
    """Every uncertainty must widen. These are the ways it can be uncertain."""

    def test_a_changed_test_file_selects_itself(self, baselined):
        """The TDD loop writes a new test every fix, and the graph built
        during recon has never heard of it. If that alone forced the full
        suite, `affected` would never narrow once."""
        _write(baselined, "tests/test_new.py", "def test_x():\n    assert True\n")
        assert verify_suite.select_affected(baselined, baselined) == (
            ["tests/test_new.py"],
            "",
        )

    def test_a_changed_source_file_selects_its_covering_tests(
        self, repo, monkeypatch
    ):
        """The graph edge is the only thing that can pull this test in.

        The test file is committed *before* the baseline, so it is not itself
        in the diff — if the edge lookup were broken this would widen instead
        of selecting.
        """
        _write(repo, "tests/test_app.py", "def test_add():\n    assert True\n")
        _git(repo, "add", "tests/test_app.py")
        _git(repo, "commit", "-qm", "test")
        head = _head(repo)
        monkeypatch.setattr(verify_suite, "_baseline_commit", lambda cwd: (head, ""))

        _write_graph(
            repo,
            {
                "app:add": _node("app:add", "app.py"),
                "t": _node("t", "tests/test_app.py", "test"),
            },
            [{"source": "t", "target": "app:add", "type": "tests"}],
        )
        _write(repo, "app.py", "def add(a, b):\n    return b + a\n")

        files, reason = verify_suite.select_affected(repo, repo)
        assert reason == ""
        assert files == ["tests/test_app.py"]

    def test_an_uncovered_source_file_widens(self, baselined):
        """#83's lesson stated positively: narrowing is earned per file.

        One changed file the graph cannot account for widens the *whole* run.
        A subset that quietly skips the file you just edited is a green that
        means nothing.
        """
        _write(baselined, "tests/test_app.py", "def test_add():\n    assert True\n")
        _write_graph(baselined, {}, [])
        _write(baselined, "app.py", "def add(a, b):\n    return b + a\n")

        files, reason = verify_suite.select_affected(baselined, baselined)
        assert files is None
        assert "no `tests` edge covers app.py" in reason

    def test_a_changed_conftest_widens(self, baselined):
        """A conftest's reach is every test beneath it, and no edge says so."""
        _write(baselined, "tests/conftest.py", "import pytest\n")
        files, reason = verify_suite.select_affected(baselined, baselined)
        assert files is None
        assert "conftest" in reason

    def test_an_unreadable_graph_widens(self, baselined):
        _write(baselined, "app.py", "def add(a, b):\n    return b + a\n")
        _write(baselined, "docs/holtz/impact-graph.json", "{not json")
        files, reason = verify_suite.select_affected(baselined, baselined)
        assert files is None
        assert "impact graph" in reason

    def test_an_edge_to_a_deleted_test_file_widens(self, baselined):
        """A stale edge names a path pytest would reject; widen instead."""
        _write_graph(
            baselined,
            {
                "app:add": _node("app:add", "app.py"),
                "t": _node("t", "tests/test_gone.py", "test"),
            },
            [{"source": "t", "target": "app:add", "type": "tests"}],
        )
        _write(baselined, "app.py", "def add(a, b):\n    return b + a\n")
        files, reason = verify_suite.select_affected(baselined, baselined)
        assert files is None
        assert "missing from the working tree" in reason

    def test_an_unchanged_tree_widens_rather_than_running_nothing(self, baselined):
        """An empty selection is not "nothing to prove" — it is no evidence.

        Reaching a record with nothing changed means the baseline is not what
        was assumed, and running zero tests to earn a green is exactly the
        false-green this mechanism exists to stop.
        """
        files, reason = verify_suite.select_affected(baselined, baselined)
        assert files is None
        assert "nothing has changed" in reason

    def test_no_baseline_widens(self, repo, monkeypatch):
        """A first run has no proven tree to measure against."""
        monkeypatch.setattr(
            verify_suite, "_baseline_commit", lambda cwd: (None, "no full-scope green")
        )
        files, reason = verify_suite.select_affected(repo, repo)
        assert files is None
        assert reason == "no full-scope green"


class TestSuiteInvocation:
    """What actually gets run, and what scope that run may claim."""

    def test_affected_appends_the_selection_and_keeps_the_scope(self, baselined):
        _write(baselined, "tests/test_new.py", "def test_x():\n    assert True\n")
        command, scope = verify_suite._suite_invocation(
            baselined, baselined, "affected"
        )
        assert scope == "affected"
        assert command == verify_suite.suite_command() + " tests/test_new.py"

    def test_a_request_that_cannot_narrow_becomes_full(self, baselined):
        """The recorded scope is what ran, not what was asked for.

        Recording `affected` for a run that executed everything would
        understate it, and `full` satisfies an `affected` check anyway.
        """
        command, scope = verify_suite._suite_invocation(
            baselined, baselined, "affected"
        )
        assert scope == "full"
        assert command == verify_suite.suite_command()

    def test_full_never_consults_the_graph(self, repo, monkeypatch):
        def _explode(*_args, **_kwargs):
            raise AssertionError("--scope full must not select")

        monkeypatch.setattr(verify_suite, "select_affected", _explode)
        assert verify_suite._suite_invocation(repo, repo, "full") == (
            verify_suite.suite_command(),
            "full",
        )


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

    def test_print_affected_says_why_it_would_not_narrow(self, repo):
        """The diagnostic exists so a graph that never narrows is visible.

        A selective run that silently degrades to the full suite forever is
        indistinguishable from one that works, and the cost it was meant to
        remove comes back unnoticed.
        """
        result = _run_verify(repo, "--print-affected")
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "would run the full suite —" in result.stderr

    def test_record_affected_without_a_baseline_runs_everything(self, repo):
        """No proven tree to diff against means no honest subset.

        This project has no ledger, so there is no full green to measure from.
        The run must widen — and say so — rather than pick some other
        baseline.
        """
        result = _run_verify(
            repo, "--record", "--scope", "affected", env={"HOLTZ_PYTEST": "true"}
        )
        assert "running the full suite —" in result.stderr
        # The unadorned command: no selection was appended to it.
        assert "verify_suite: running true\n" in result.stderr


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

    def _baseline(self, real_daemon, root, env):
        """Commit a covering test, prove everything green, return that HEAD.

        This is the state `--scope affected` is defined against, so building
        it through the real CLI — rather than hand-writing an event — is what
        makes the affected tests below mean anything.
        """
        _write(root, "tests/test_app.py", "def test_add():\n    assert True\n")
        _git(root, "add", "tests/test_app.py")
        _git(root, "commit", "-qm", "tests")
        assert _run_verify(root, "--record", env=env).returncode == 0
        return _head(root)

    def test_a_full_green_records_the_commit_it_proved(self, real_daemon):
        """The baseline every later affected run measures its diff from."""
        root = self._prepare(real_daemon)
        assert _run_verify(root, "--record", env=self._env(real_daemon)).returncode == 0
        assert self._greens(real_daemon)[-1]["commit_hash"] == _head(root)

    def test_affected_narrows_to_the_covering_tests(self, real_daemon):
        """The whole point of T3, proven against a real ledger.

        The baseline commit comes out of the ledger, the diff comes out of
        git, and the covering test comes out of the graph — so this is the
        only test that exercises all three joins at once.
        """
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)
        base = self._baseline(real_daemon, root, env)

        _write_graph(
            root,
            {
                "app:add": _node("app:add", "app.py"),
                "t": _node("t", "tests/test_app.py", "test"),
            },
            [{"source": "t", "target": "app:add", "type": "tests"}],
        )
        _write(root, "app.py", "def add(a, b):\n    return b + a\n")

        result = _run_verify(root, "--record", "--scope", "affected", env=env)
        assert result.returncode == 0, (
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        latest = self._greens(real_daemon)[-1]
        assert latest["scope"] == "affected"
        assert latest["command"].endswith(" tests/test_app.py"), latest["command"]
        assert latest["commit_hash"] == base  # nothing committed since

    def test_an_uncovered_change_records_a_full_green(self, real_daemon):
        """A change the graph cannot account for must not narrow.

        `scope` is recorded as what *ran*, so the ledger says `full` here —
        which is both true and strong enough to satisfy any later check.
        """
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)
        self._baseline(real_daemon, root, env)

        _write_graph(root, {}, [])
        _write(root, "app.py", "def add(a, b):\n    return b + a\n")

        result = _run_verify(root, "--record", "--scope", "affected", env=env)
        assert result.returncode == 0
        assert "no `tests` edge covers app.py" in result.stderr
        assert self._greens(real_daemon)[-1]["scope"] == "full"

    def test_a_subset_that_collects_nothing_widens_before_recording(
        self, real_daemon, tmp_path
    ):
        """A narrowed command that could not run tests proved nothing.

        pytest exits 4 on a usage error and 5 on an empty collection; neither
        is a statement about the code. Recording a green off either would be
        the false green in its purest form — zero tests executed, gate
        satisfied — so the run widens and the ledger says `full`.
        """
        root = self._prepare(real_daemon)
        fake = str(tmp_path / "fake_pytest.py")
        with open(fake, "w", encoding="utf-8") as fh:
            fh.write(
                "import sys\n"
                "if len(sys.argv) > 1:\n"
                "    sys.exit(5)\n"
                "print('9 passed')\n"
            )
        env = {
            "SAHJHAN_DAEMON_SOCKET": real_daemon["sock_path"],
            "HOLTZ_PYTEST": f"{sys.executable} {fake}",
        }
        self._baseline(real_daemon, root, env)

        _write(root, "tests/test_app.py", "def test_add():\n    assert 1 == 1\n")
        result = _run_verify(root, "--record", "--scope", "affected", env=env)
        assert result.returncode == 0, (
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "widening to the full suite" in result.stderr

        latest = self._greens(real_daemon)[-1]
        assert latest["scope"] == "full"
        assert latest["test_count"] == "9"

    def test_an_affected_green_does_not_satisfy_a_full_check(self, real_daemon):
        """`fix_commit` will ask for `affected`, `iteration_boundary` for
        `full`. The ordering that lets one gate be cheap while the other stays
        strict has to hold against a real ledger, not just in the tuple."""
        root = self._prepare(real_daemon)
        env = self._env(real_daemon)
        self._baseline(real_daemon, root, env)

        _write_graph(
            root,
            {
                "app:add": _node("app:add", "app.py"),
                "t": _node("t", "tests/test_app.py", "test"),
            },
            [{"source": "t", "target": "app:add", "type": "tests"}],
        )
        _write(root, "app.py", "def add(a, b):\n    return b + a\n")
        assert _run_verify(
            root, "--record", "--scope", "affected", env=env
        ).returncode == 0

        assert _run_verify(
            root, "--check", "--scope", "affected", env=env
        ).returncode == 0
        strict = _run_verify(root, "--check", "--scope", "full", env=env)
        assert strict.returncode == 1
        assert "no suite_green for this working tree" in strict.stderr

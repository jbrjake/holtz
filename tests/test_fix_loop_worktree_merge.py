"""The fix loop's taught sequence, executed rather than described.

`phase-fix-loop.md` now tells each fix subagent to commit in its own worktree,
rebase onto the orchestrator's branch, and only then record `suite_green`; the
orchestrator fast-forwards. The whole design rests on one identity: **the tree
the subagent proved is byte-for-byte the tree that lands on the branch.** If it
does not hold, `fix_commit`'s suite gate recomputes a hash no green names and
the loop rejects every good fix — which is what shipped in v0.141.2 from a
different cause, with a green gate the whole time.

A line-order test (`test_subagent_contract_consistency.py`) checks that the
steps are *taught* in the right order. This one runs them, with real git and
the real `compute_tree_hash`, because the ordering rule and the identity it
buys are different claims.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")


def _load_verify_suite():
    path = os.path.join(SCRIPTS_DIR, "verify_suite.py")
    spec = importlib.util.spec_from_file_location("_verify_suite_wtm", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_verify_suite = _load_verify_suite()
compute_tree_hash = _verify_suite.compute_tree_hash


def _clean_env() -> dict[str, str]:
    """See test_worktree_boundary._clean_env — pre-commit exports GIT_DIR."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(*args: str, cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd, check=check, capture_output=True, text=True, env=_clean_env(),
    )


def _write(path: str, name: str, body: str) -> None:
    with open(os.path.join(path, name), "w", encoding="utf-8") as fh:
        fh.write(body)


@pytest.fixture
def project(tmp_path):
    """A repo on `main` with two source files, and a worktree factory."""
    root = str(tmp_path / "project")
    os.makedirs(root)
    _git("init", "-q", "-b", "main", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "T", cwd=root)
    _write(root, "alpha.py", "def a():\n    return 1\n")
    _write(root, "beta.py", "def b():\n    return 2\n")
    _git("add", "-A", cwd=root)
    _git("commit", "-qm", "init", cwd=root)

    def worktree(name: str) -> str:
        path = str(tmp_path / "project" / ".claude" / "worktrees" / name)
        _git("worktree", "add", "-q", "-b", f"fix/{name}", path, "main", cwd=root)
        return path

    return {"root": root, "worktree": worktree}


def _subagent_turn(wt: str, filename: str, body: str, branch: str = "main") -> str:
    """Steps 9 and 10 as the skill file teaches them, returning the proved hash."""
    _write(wt, filename, body)
    _git("add", "-A", cwd=wt)
    _git("commit", "-qm", "fix(x): BH-101", cwd=wt)
    _git("rebase", branch, cwd=wt)
    # The record step hashes the tree at this point; the suite run itself is
    # not what this test is about.
    return compute_tree_hash(wt)


def test_the_tree_the_subagent_proved_is_the_tree_that_lands(project):
    """One subagent, the base case for the identity everything else rests on."""
    root, wt = project["root"], project["worktree"]("fix-a")

    proved = _subagent_turn(wt, "alpha.py", "def a():\n    return 11\n")
    _git("merge", "--ff-only", "fix/fix-a", cwd=root)

    assert compute_tree_hash(root) == proved


def test_a_second_subagent_rebasing_onto_the_first_still_lands_its_own_tree(project):
    """Two subagents, merged serially — the case one-at-a-time existed to avoid.

    B's worktree was created from the base commit, so by the time B finishes,
    the branch has moved under it. Rebasing is what makes B's proved tree equal
    the tree the branch will hold after B merges; without it B's green would
    describe a tree that never existed on the branch.
    """
    root = project["root"]
    a, b = project["worktree"]("fix-a"), project["worktree"]("fix-b")

    proved_a = _subagent_turn(a, "alpha.py", "def a():\n    return 11\n")
    _git("merge", "--ff-only", "fix/fix-a", cwd=root)
    assert compute_tree_hash(root) == proved_a

    # B rebases *after* A has landed, which is the serialized part of the loop.
    proved_b = _subagent_turn(b, "beta.py", "def b():\n    return 22\n")
    _git("merge", "--ff-only", "fix/fix-b", cwd=root)

    assert compute_tree_hash(root) == proved_b
    # And A's work survived: the identity is about content, so a tree that
    # dropped alpha.py's fix would also satisfy the equality above.
    with open(os.path.join(root, "alpha.py"), encoding="utf-8") as fh:
        assert "return 11" in fh.read()


def test_an_unrebased_branch_is_refused_rather_than_merged(project):
    """The doc says a refusal means the rebase is stale. It has to actually refuse.

    A plain `git merge` here would succeed by writing a merge commit, whose
    tree is neither subagent's — so the fast-forward restriction is what turns
    a silent wrong answer into a visible one.
    """
    root = project["root"]
    a, b = project["worktree"]("fix-a"), project["worktree"]("fix-b")

    _subagent_turn(a, "alpha.py", "def a():\n    return 11\n")
    _git("merge", "--ff-only", "fix/fix-a", cwd=root)

    # B commits but never rebases, so its branch no longer descends from main.
    _write(b, "beta.py", "def b():\n    return 22\n")
    _git("add", "-A", cwd=b)
    _git("commit", "-qm", "fix(x): BH-102", cwd=b)

    refused = _git("merge", "--ff-only", "fix/fix-b", cwd=root, check=False)

    assert refused.returncode != 0, refused.stdout
    assert compute_tree_hash(root) == compute_tree_hash(a), (
        "a refused merge must leave the branch exactly where it was"
    )


def test_a_conflicting_rebase_aborts_without_a_second_commit(project):
    """The stated way out when two fixes touch the same lines.

    A subagent gets one commit — the pending-commit block is keyed on the
    actor and its escape belongs to the orchestrator — so the conflict path
    has to end in `--abort` and a report, never in committing again.
    """
    root = project["root"]
    a, b = project["worktree"]("fix-a"), project["worktree"]("fix-b")

    _subagent_turn(a, "alpha.py", "def a():\n    return 11\n")
    _git("merge", "--ff-only", "fix/fix-a", cwd=root)

    _write(b, "alpha.py", "def a():\n    return 99\n")
    _git("add", "-A", cwd=b)
    _git("commit", "-qm", "fix(x): BH-102", cwd=b)
    conflicted = _git("rebase", "main", cwd=b, check=False)
    assert conflicted.returncode != 0, "expected a conflict on the same lines"

    _git("rebase", "--abort", cwd=b)

    # One commit on B's branch, and the worktree is usable again.
    log = _git("log", "--oneline", "main..fix/fix-b", cwd=root).stdout
    assert len(log.strip().splitlines()) == 1, log
    assert _git("status", "--porcelain", cwd=b).stdout.strip() == "", (
        "an aborted rebase must leave the worktree clean enough to report from"
    )

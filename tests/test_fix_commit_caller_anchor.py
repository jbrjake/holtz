"""W08 / item 43 — `fix_commit` asks about the tree its caller is standing in.

P0.3 runs the fix loop several subagents wide, each in its own git worktree.
The commit gate charges an actor for its own unregistered commits and prints
`transition fix_commit` as the way out. That escape was unreachable for a
subagent, and every part of the transition was anchored at the project root:

* `git log -1 --format=%B | grep -q '<id>'` read the project's `HEAD`, which
  does not carry the subagent's commit;
* `verify_suite.py --check` recomputed the *project's* tree hash, never the one
  the subagent's `--record` named;
* the `finding_resolved` emit stamped `commit_hash` from the project's `HEAD`.

The first two were sahjhan#46 (shipped in 0.25.0), the third sahjhan#48
(shipped in 0.26.0), and all three now carry `anchor = "caller"`.

**The emit is the half that must not be forgotten, and these tests are ordered
to say so.** Anchoring the gates alone is worse than anchoring neither: the
gate attests that the caller's `HEAD` carries the fix, and the emit then
records the project's unrelated `HEAD` as the commit that resolved the
finding — a false resolution where there used to be a loud block. That hash is
load-bearing twice (`pending_commits_discharged` matches it against what the
tracker charged, and `hardening_batch.py` treats it as a module already
hardened), so `TestTheEmitStampsTheCallersTree` is the test that would catch a
half-applied migration.

**Why two config surfaces, and why neither is a hand-written copy.** The gate
half is driven against holtz's own `enforcement/` directory. The emit half
cannot be: firing an emit needs a real `transition`, a real transition needs
every gate green, and gate 3 wants a `suite_green` — a `restricted` event that
a real daemon refuses to write for a test process (`auth_failed`, reason
`pid_resolution_failed`; the caller is pytest, not a hash-pinned hook). So the
emit half runs against a config *derived from* `enforcement/` with the
preconditional gates stripped and **the emit line kept exactly as written**.
Deleting `anchor` from the real `transitions.toml` therefore still fails these
tests; a hand-maintained copy of the emit would not.
"""
from __future__ import annotations

import json
import os
import re
import shutil
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

#: The finding the worktree's commit message names, and the project's does not.
ITEM = "BH-101"


def _git(*args: str, cwd: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env=scrubbed_env(),
    )
    return result.stdout.strip()


def _binary() -> str:
    sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _only_the_commit_message_gate(config_dir: str) -> None:
    """Strip `fix_commit`'s gates down to the commit-message one, in place.

    The five removed gates are preconditions, not the claim: a finding's
    reachability, a `suite_green` this process may not write, two
    `ledger_has_event_since` rows and the per-iteration circuit breaker. The
    commit-message gate stays — an emit only fires on a transition that passed
    its gates, so removing all of them would test nothing about the tree.

    Rewritten from the real file rather than pasted, so the surviving gate and
    the emit below it are the shipped lines.
    """
    path = os.path.join(config_dir, "transitions.toml")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    start = source.index('command = "fix_commit"')
    gates_open = source.index("gates = [", start)
    gates_close = source.index("\n]\n", gates_open)
    kept = [
        line for line in source[gates_open:gates_close].splitlines()
        if "git log -1 --format=%B" in line
    ]
    assert len(kept) == 1, f"expected exactly one commit-message gate, got {kept}"

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source[:gates_open] + "gates = [\n" + kept[0] + source[gates_close:])


@dataclass
class FixLoopProject:
    """A project in `fix_loop` whose fix lives only in a nested worktree."""

    main: str
    worktree: str
    binary: str
    config_dir: str

    def sahjhan(self, *args: str, cwd: str) -> subprocess.CompletedProcess[str]:
        # `CLAUDE_PLUGIN_ROOT` is not optional here: the suite gate's `cmd`
        # spells it `${CLAUDE_PLUGIN_ROOT:?...}`, so without it the gate exits
        # 127 on the unset variable and reports no `tree_hash` at all — an
        # env failure that looks nothing like a wrong anchor. `scrubbed_env`
        # drops it along with the ambient git state.
        return subprocess.run(
            [self.binary, "--config-dir", self.config_dir, *args],
            cwd=cwd, capture_output=True, text=True,
            env={**scrubbed_env(), "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
        )

    def head(self, cwd: str) -> str:
        return _git("rev-parse", "--short=7", "HEAD", cwd=cwd)

    def gate_report(self, cwd: str) -> str:
        result = self.sahjhan("gate", "check", "fix_commit", f"item_id={ITEM}", cwd=cwd)
        return result.stdout + result.stderr

    def resolutions(self) -> list[dict]:
        result = self.sahjhan(
            "query",
            "SELECT id, commit_hash FROM events WHERE type='finding_resolved'",
            "--format", "json", cwd=self.main,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        return json.loads(result.stdout) if result.stdout.strip() else []


def _build(tmp_path, config_dir: str) -> FixLoopProject:
    binary = _binary()
    main = str(tmp_path / "project")
    os.makedirs(main)
    _git("init", "-q", "-b", "main", ".", cwd=main)
    _git("config", "user.email", "t@example.com", cwd=main)
    _git("config", "user.name", "T", cwd=main)
    # `.claude/*`, not `.claude/`: with the trailing-slash form the directory
    # itself is ignored and `verify_suite`'s `:(exclude).claude` pathspec makes
    # its `git add -A` exit 1, which reports as a hashing failure rather than a
    # tree hash. holtz's own .gitignore:6 uses the glob.
    with open(os.path.join(main, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("docs/holtz/.sahjhan/\n.claude/*\n")
    with open(os.path.join(main, "file.txt"), "w", encoding="utf-8") as fh:
        fh.write("seed\n")
    _git("add", ".gitignore", "file.txt", cwd=main)
    _git("commit", "-qm", "chore: unrelated to any finding", cwd=main)

    init = subprocess.run(
        [binary, "--config-dir", config_dir, "init"],
        cwd=main, capture_output=True, text=True, env=scrubbed_env(),
    )
    assert init.returncode == 0, init.stderr or init.stdout

    # Nested under the project root, which is where Claude Code's
    # `isolation: "worktree"` puts them (`<repo>/.claude/worktrees/<name>/`).
    worktree = os.path.join(main, ".claude", "worktrees", "fix-a")
    _git("worktree", "add", "-q", "--detach", worktree, "HEAD", cwd=main)
    with open(os.path.join(worktree, "file.txt"), "w", encoding="utf-8") as fh:
        fh.write("the fix\n")
    _git("add", "file.txt", cwd=worktree)
    _git("commit", "-qm", f"fix(x): {ITEM} close the finding", cwd=worktree)

    project = FixLoopProject(
        main=main, worktree=worktree, binary=binary, config_dir=config_dir,
    )
    # Reaching `fix_loop` is a precondition, not the claim: seeded as an event
    # rather than driven through run_start / recon_complete / fix_loop_start /
    # resume, whose own gates are a different subject entirely.
    seeded = project.sahjhan(
        "event", "state_transition",
        "--field", "from=awaiting_clear", "--field", "to=fix_loop",
        "--field", "command=resume", "--field", "run=1",
        "--field", "auditor=holtz", "--field", "project=holtz",
        cwd=main,
    )
    assert seeded.returncode == 0, seeded.stderr or seeded.stdout

    assert project.head(main) != project.head(worktree), (
        "the fixture proves nothing if both trees are at the same commit"
    )
    return project


@pytest.fixture
def fix_loop_project(tmp_path):
    """Driven against holtz's own `enforcement/`, gates as shipped."""
    return _build(tmp_path, CONFIG_DIR)


@pytest.fixture
def emit_project(tmp_path):
    """Same, against a derived config whose only `fix_commit` gate is gate 2."""
    derived = str(tmp_path / "config")
    shutil.copytree(CONFIG_DIR, derived)
    _only_the_commit_message_gate(derived)
    return _build(tmp_path, derived)


class TestTheCommitMessageGateReadsTheCallersHead:
    """V6a — sahjhan#46's first gate, against the shipped config."""

    #: The gate's `intent`, which is how a failure names itself in the report.
    INTENT = "commit must reference the punchlist item"

    def test_it_passes_from_the_worktree_holding_the_commit(self, fix_loop_project):
        report = fix_loop_project.gate_report(fix_loop_project.worktree)
        assert self.INTENT not in report, (
            "the worktree's HEAD names the item, so this gate must not be "
            f"among the failures:\n{report}"
        )

    def test_it_still_refuses_from_a_tree_whose_head_does_not_name_the_item(
        self, fix_loop_project,
    ):
        """The other direction, and the one that says this is not a removal.

        A gate that stopped refusing everywhere would pass the test above just
        as happily. The project root's `HEAD` genuinely does not carry the
        item, so from there the block must survive the migration.
        """
        report = fix_loop_project.gate_report(fix_loop_project.main)
        assert self.INTENT in report, (
            f"the project's HEAD does not name {ITEM}; the gate must refuse "
            f"there:\n{report}"
        )


class TestTheSuiteGateHashesTheCallersTree:
    """V6b — sahjhan#46's second gate, the one its reproduction showed by hash.

    Asserted as *which tree the gate hashed*, not as pass/fail: this process
    cannot write the `suite_green` that would make it pass, so the observable
    is the `tree_hash=` the failure reports. Before the anchor it was the
    project's hash from both directories — identical, which is the defect.
    """

    def _reported_hash(self, project, cwd: str) -> str:
        report = project.gate_report(cwd)
        found = re.search(r"tree_hash=([0-9a-f]{64})", report)
        assert found, f"no tree_hash in the gate report:\n{report}"
        return found.group(1)

    def _hash_of(self, project, cwd: str) -> str:
        """What `verify_suite` computes standing in ``cwd`` — the reference."""
        result = subprocess.run(
            [sys.executable,
             str(REPO_ROOT / "enforcement" / "scripts" / "verify_suite.py"),
             "--check", "--scope", "affected"],
            cwd=cwd, capture_output=True, text=True,
            env={**scrubbed_env(), "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
        )
        found = re.search(r"tree_hash=([0-9a-f]{64})", result.stdout + result.stderr)
        assert found, f"no tree_hash from {cwd}:\n{result.stdout}{result.stderr}"
        return found.group(1)

    def test_the_two_trees_hash_differently(self, fix_loop_project):
        """The precondition every other assertion here rests on."""
        assert (self._hash_of(fix_loop_project, fix_loop_project.worktree)
                != self._hash_of(fix_loop_project, fix_loop_project.main))

    def test_from_the_worktree_it_hashes_the_worktree(self, fix_loop_project):
        assert (self._reported_hash(fix_loop_project, fix_loop_project.worktree)
                == self._hash_of(fix_loop_project, fix_loop_project.worktree))

    def test_from_the_project_root_it_still_hashes_the_project(self, fix_loop_project):
        """V7 — the orchestrator calls from here, and nothing moved for it."""
        assert (self._reported_hash(fix_loop_project, fix_loop_project.main)
                == self._hash_of(fix_loop_project, fix_loop_project.main))


class TestTheEmitStampsTheCallersTree:
    """V6c — sahjhan#48. The half that turns a loud block into a false record."""

    def test_a_transition_from_the_worktree_registers_the_worktrees_commit(
        self, emit_project,
    ):
        done = emit_project.sahjhan(
            "transition", "fix_commit", ITEM, cwd=emit_project.worktree,
        )
        assert done.returncode == 0, done.stderr or done.stdout

        resolved = emit_project.resolutions()
        assert [r["id"] for r in resolved] == [ITEM]
        # Asserted against both hashes by name. `!= project_head` alone would
        # survive the emit landing on any third commit, and `== worktree_head`
        # alone would survive the two trees having coincided.
        assert resolved[0]["commit_hash"] == emit_project.head(emit_project.worktree)
        assert resolved[0]["commit_hash"] != emit_project.head(emit_project.main)

    def test_a_transition_from_the_project_root_registers_the_projects_commit(
        self, emit_project,
    ):
        """V7 — the orchestrator's path, unchanged.

        It runs `fix_commit` from the project root after `git merge --ff-only`,
        where the caller *is* the project anchor. Here the project's `HEAD`
        does not name the item, so the same gate that opened for the worktree
        refuses — which is the orchestrator's behaviour before the migration
        and after it.
        """
        refused = emit_project.sahjhan(
            "transition", "fix_commit", ITEM, cwd=emit_project.main,
        )
        assert refused.returncode != 0
        assert emit_project.resolutions() == [], (
            "a refused transition must record no resolution"
        )

"""W26 / item 48 — direct unit tests for the delta's enforcement predicates.

Seven functions decide enforcement outcomes and had no test that imported
them: `is_read_only_cmd`, `_tdd_gate_exempt`, `project_anchor`,
`stall_bumped`/`stall_cleared`, `pending_commits_for`, `exit_boundary_missing`
and `query_named_predicate`. `is_read_only_cmd` is the one with a known escaped
defect — item 38, `sed --in-place` classified read-only — and it was covered
only by parametrized subprocess cases in `test_hook_chains.py`, which is where
that defect slipped through.

The two functions that live in `enforcement/hooks/_common.py` and the one in
`pre_tool_hook.py` are called in a **fresh interpreter**: two `_common.py`
modules exist, and whichever one a test session imported first answers every
later `import _common` — cleanly, and wrongly. `_protocol_cache` has one
module of that name and no `_common` import at load time, so its functions are
imported here directly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / "enforcement" / "hooks"
CONFIG_DIR = REPO_ROOT / "enforcement"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from _protocol_cache import (  # noqa: E402
    _WRITING_FLAGS,
    ORCHESTRATOR,
    is_read_only_cmd,
    pending_commits_for,
    query_named_predicate,
    stall_bumped,
    stall_cleared,
)

SIBLING = "a7f3c2"


def _isolated(module: str, expression: str) -> object:
    """Evaluate ``expression`` after ``from <module> import *`` in a fresh
    interpreter whose first path entry is `enforcement/hooks`, and return its
    JSON-decoded value."""
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(HOOKS)!r})\n"
        f"import {module} as m\n"
        f"print(json.dumps({expression}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


# ── is_read_only_cmd ────────────────────────────────────────────────────────


class TestIsReadOnlyCmd:
    """The stall counter's exemption. A write read as a read escapes the
    counter; a read read as a write costs one nudge — so the tests lean on the
    first direction."""

    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "cat src/a.py",
        "grep -rn needle src/",
        "sed -n '1,5p' a.py",
        "find . -name '*.py'",
        "git log --oneline -5",
        "git diff HEAD~1",
        "git status --short",
        "cat a.py | wc -l",
        "ls && pwd",
        "ls 2>&1",
        "grep x a.py 2>/dev/null",
        "/usr/bin/cat a.py",
    ])
    def test_reads(self, cmd):
        assert is_read_only_cmd(cmd) is True

    @pytest.mark.parametrize("cmd", [
        "",
        "   ",
        "echo hi",
        "touch x",
        "python3 script.py",
        "ls > out.txt",
        "cat a >> b",
        "ls && touch x",
        "ls; rm x",
        "ls & rm x",
        "cat 'unbalanced",
        "git",
        "git commit -m x",
        "git branch topic",
        "git stash",
    ])
    def test_writes_or_unknowns(self, cmd):
        assert is_read_only_cmd(cmd) is False

    @pytest.mark.parametrize(("head", "flag"), [
        (head, flag) for head, flags in sorted(_WRITING_FLAGS.items()) for flag in flags
    ])
    def test_every_writing_flag_disqualifies_in_both_argument_shapes(self, head, flag):
        """Each spelling, as a bare flag and with its argument glued on.

        The prefix match is what reaches `-i.bak` and `--output=x`; this pins
        that it does, for every row, rather than for the rows someone thought
        to write down.
        """
        base = f"{head} status" if head == "git" else head
        assert is_read_only_cmd(f"{base} {flag} x") is False
        assert is_read_only_cmd(f"{base} {flag}=x") is False

    @pytest.mark.parametrize("cmd", [
        "sed --in-place 's/a/b/' src/a.py",
        "sed --in-place=.bak 's/a/b/' src/a.py",
        "sort --output=sorted.txt in.txt",
        "tree --output out.txt",
        "git diff --output=/tmp/x HEAD",
    ])
    def test_the_long_spellings_are_writes(self, cmd):
        """Item 38's class, named rather than derived: `"--in-place"
        .startswith("-i")` is False, so a table carrying only the short
        spelling reads the long one as a read. These are hand-listed so that
        deleting a long spelling from the table fails here."""
        assert is_read_only_cmd(cmd) is False


# ── _tdd_gate_exempt ────────────────────────────────────────────────────────


class TestTddGateExempt:
    """Which Edit/Write targets skip the fix-loop TDD gate: anything outside
    the project, and `docs/` inside it. Everything else needs a failing test."""

    def _exempt(self, cwd: Path, paths: list[str]) -> list[bool]:
        return _isolated(  # type: ignore[return-value]
            "pre_tool_hook",
            f"[m._tdd_gate_exempt(p, {str(cwd)!r}) for p in {paths!r}]",
        )

    def test_the_answers(self, tmp_path):
        project = tmp_path / "project"
        (project / "docs").mkdir(parents=True)
        (project / "src").mkdir()
        cases = {
            "": False,
            str(project / "src" / "a.py"): False,
            "src/a.py": False,
            str(project / "docs" / "notes.md"): True,
            "docs/notes.md": True,
            "docsfoo/a.py": False,
            str(tmp_path / "elsewhere" / "a.py"): True,
            "../elsewhere/a.py": True,
        }
        answers = self._exempt(project, list(cases))
        assert dict(zip(cases, answers, strict=True)) == cases


# ── project_anchor ──────────────────────────────────────────────────────────


class TestProjectAnchor:
    """The main worktree of the repository holding ``cwd``, from anywhere in
    it — and a submodule is its own project."""

    def _anchor(self, cwd: Path) -> str:
        return _isolated("_common", f"m.project_anchor({str(cwd)!r})")  # type: ignore[return-value]

    def test_outside_a_repository_it_is_the_directory_itself(self, tmp_path):
        loose = tmp_path / "loose"
        loose.mkdir()
        assert self._anchor(loose) == os.path.realpath(loose)

    def test_a_subdirectory_anchors_on_the_repository(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "src" / "deep").mkdir(parents=True)
        assert self._anchor(repo / "src" / "deep") == os.path.realpath(repo)

    def test_a_linked_worktree_anchors_on_the_main_one(self, tmp_path):
        repo = tmp_path / "repo"
        gitdir = repo / ".git" / "worktrees" / "wt"
        gitdir.mkdir(parents=True)
        (gitdir / "commondir").write_text("../..\n")
        worktree = tmp_path / "wt"
        (worktree / "src").mkdir(parents=True)
        (worktree / ".git").write_text(f"gitdir: {gitdir}\n")
        assert self._anchor(worktree / "src") == os.path.realpath(repo)

    def test_a_submodule_is_its_own_project(self, tmp_path):
        """Its gitdir has no `commondir`. Following the pointer anyway would
        hand every submodule the superproject's socket."""
        superproject = tmp_path / "super"
        module_gitdir = superproject / ".git" / "modules" / "lib"
        module_gitdir.mkdir(parents=True)
        submodule = superproject / "lib"
        submodule.mkdir()
        (submodule / ".git").write_text(f"gitdir: {module_gitdir}\n")
        assert self._anchor(submodule) == os.path.realpath(submodule)


# ── stall_bumped / stall_cleared ────────────────────────────────────────────


class TestStallCounts:
    """Per-actor charges. Every number below is distinct from every other, so
    a charge landing in the wrong bucket cannot pass for the right one."""

    CACHE = {"stall": {ORCHESTRATOR: 4, SIBLING: 9}}

    def test_a_bump_charges_the_actor_alone(self):
        assert stall_bumped(self.CACHE, SIBLING, 2) == {ORCHESTRATOR: 4, SIBLING: 11}

    def test_a_first_charge_starts_from_zero(self):
        assert stall_bumped(self.CACHE, "fresh", 3) == {ORCHESTRATOR: 4, SIBLING: 9, "fresh": 3}
        assert stall_bumped(None, SIBLING, 1) == {SIBLING: 1}

    def test_a_clear_removes_the_actor_alone(self):
        assert stall_cleared(self.CACHE, SIBLING) == {ORCHESTRATOR: 4}

    def test_clearing_an_actor_with_no_count_changes_nothing(self):
        assert stall_cleared(self.CACHE, "fresh") == {ORCHESTRATOR: 4, SIBLING: 9}

    def test_neither_mutates_the_cache_it_read(self):
        cache = {"stall": {ORCHESTRATOR: 4, SIBLING: 9}}
        stall_bumped(cache, SIBLING, 2)
        stall_cleared(cache, ORCHESTRATOR)
        assert cache == {"stall": {ORCHESTRATOR: 4, SIBLING: 9}}

    def test_the_pre_keying_scalar_is_the_orchestrators(self):
        """RULED D-n (W25): migrate."""
        assert stall_bumped({"stall": 16}, SIBLING, 1) == {ORCHESTRATOR: 16, SIBLING: 1}
        assert stall_cleared({"stall": 16}, SIBLING) == {ORCHESTRATOR: 16}


# ── pending_commits_for ─────────────────────────────────────────────────────


class TestPendingCommitsFor:
    """The commit block asks about the caller's own commits — a sibling's
    pending commit is not evidence about this caller (P0.3, D41)."""

    CACHE = {"unregistered_commits": {ORCHESTRATOR: ["aaa1111"], SIBLING: ["bbb2222", "ccc3333"]}}

    def test_an_actor_sees_its_own(self):
        assert pending_commits_for(self.CACHE, SIBLING) == ["bbb2222", "ccc3333"]
        assert pending_commits_for(self.CACHE, ORCHESTRATOR) == ["aaa1111"]

    def test_an_actor_with_none_sees_none(self):
        assert pending_commits_for(self.CACHE, "fresh") == []
        assert pending_commits_for(None, SIBLING) == []

    def test_the_pre_keying_list_is_the_orchestrators(self):
        legacy = {"unregistered_commits": ["ddd4444"]}
        assert pending_commits_for(legacy, ORCHESTRATOR) == ["ddd4444"]
        assert pending_commits_for(legacy, SIBLING) == []


# ── exit_boundary_missing ───────────────────────────────────────────────────


class TestExitBoundaryMissing:
    """A refusal that blocks in PreToolUse, warns in PostToolUse, and names
    the one thing that fixes it."""

    def _exit(self, reason: str, hook_type: str) -> dict:
        script = (
            "import sys\n"
            f"sys.path.insert(0, {str(HOOKS)!r})\n"
            "from _common import exit_boundary_missing\n"
            f"exit_boundary_missing({reason!r}, {hook_type!r})\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_pre_tool_use_denies_and_names_holtz_start(self):
        out = self._exit("sandbox_not_enabled", "PreToolUse")["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "holtz-start" in out["permissionDecisionReason"]
        assert "sandbox_not_enabled" in out["permissionDecisionReason"]

    def test_post_tool_use_warns_rather_than_denies(self):
        out = self._exit("sandbox_not_enabled", "PostToolUse")["hookSpecificOutput"]
        assert out.get("permissionDecision") != "deny"
        assert "holtz-start" in out["additionalContext"]

    def test_an_unresolved_home_names_home_not_holtz_start(self):
        """W25 row a: `holtz-start` needs the same path, so it is not the fix."""
        reason = self._exit("home_unresolved", "PreToolUse")["hookSpecificOutput"][
            "permissionDecisionReason"
        ]
        assert "HOME" in reason
        assert "ask the user to type `holtz-start`" not in reason


# ── query_named_predicate ───────────────────────────────────────────────────


def _stand_in(tmp_path: Path, stdout: str, code: int = 0) -> str:
    binary = tmp_path / "sahjhan"
    binary.write_text(f"#!/bin/sh\nprintf '%s' '{stdout}'\nexit {code}\n")
    binary.chmod(0o755)
    return str(binary)


class TestQueryNamedPredicate:
    """A named predicate evaluated against the ledger — ``None`` whenever the
    ledger could not answer, never a guessed ``False``."""

    def test_it_reads_the_real_engine_both_ways(self, tmp_path):
        """`deferral_record_complete` is vacuously true, and a deferral naming
        a finding nobody filed makes it false — through the shipped binary."""
        from _resolve import ensure_sahjhan

        binary = ensure_sahjhan()
        if not binary:
            pytest.skip("sahjhan binary not available")
        cfg = str(CONFIG_DIR)
        for args in (["init"], ["ledger", "create", "--from", "run", "1", "--activate"]):
            subprocess.run([binary, "--config-dir", cfg, *args], cwd=tmp_path,
                           check=True, capture_output=True)
        name = "deferral_record_complete"
        assert query_named_predicate(binary, cfg, str(tmp_path), name) is True
        subprocess.run(
            [binary, "--config-dir", cfg, "event", "finding_deferred",
             "--field", "id=BH-999", "--field", "reason=low_priority",
             "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
             "--field", "phase=fix_loop", "--field", "step=10"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        assert query_named_predicate(binary, cfg, str(tmp_path), name) is False

    def test_an_undeclared_name_is_no_answer(self, tmp_path):
        binary = _stand_in(tmp_path, '[{"v": "true"}]')
        assert query_named_predicate(binary, str(CONFIG_DIR), str(tmp_path), "no_such") is None

    @pytest.mark.parametrize(("stdout", "code"), [
        ('[{"v": "true"}]', 1),
        ("[]", 0),
        ("{}", 0),
        ("not json", 0),
    ], ids=["non-zero", "no-rows", "not-a-list", "not-json"])
    def test_an_unreadable_answer_is_none(self, tmp_path, stdout, code):
        binary = _stand_in(tmp_path, stdout, code)
        answer = query_named_predicate(
            binary, str(CONFIG_DIR), str(tmp_path), "deferral_record_complete",
        )
        assert answer is None

    @pytest.mark.parametrize(("stdout", "expected"), [
        ('[{"v": "true"}]', True),
        ('[{"v": "TRUE"}]', True),
        ('[{"v": "false"}]', False),
        ('[{"v": 1}]', False),
    ])
    def test_the_first_value_decides(self, tmp_path, stdout, expected):
        binary = _stand_in(tmp_path, stdout)
        answer = query_named_predicate(
            binary, str(CONFIG_DIR), str(tmp_path), "deferral_record_complete",
        )
        assert answer is expected

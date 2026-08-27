"""F1 — a project whose audit data directory exists only in the main checkout.

`.gitignore` carries `docs/holtz/.sahjhan/`, so a checkout produced by
`git worktree add` does not contain it. Five hooks answer "is an audit active
here" with a probe relative to the *process* cwd, and a fix subagent runs with
its worktree as cwd — so the probe answers "no audit" and the gate behind it is
skipped (item 29 / W02).

This module builds the situation and nothing else: no product code changes, and
the fixture is correct precisely when it **reproduces** the asymmetry rather
than hiding it.

Two things make the reproduction observable without a real daemon:

* a **stub binary** at ``<plugin_root>/bin/sahjhan-<triple>`` — the path
  ``_resolve.sahjhan_binary()`` resolves from ``CLAUDE_PLUGIN_ROOT`` — which
  appends its argv to a log and exits 0. "Did the hook reach
  ``manifest verify``" is then a fact on disk, not an inference from a
  permission decision that reads ``allow`` on both legs for different reasons.
* a **scrubbed environment** on every subprocess (see :mod:`git_env`).

The stub is deliberately not a mock of sahjhan. It records that the binary was
invoked and with what; any test needing the engine's answer wants
``real_daemon``.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from git_env import scrubbed_env
from hook_runner import run_hook

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")

#: The run number written into the main checkout's ``active-ledger`` marker.
#: Chosen so that no plausible wrong answer coincides with it: it is not ``0``
#: (what ``verify_suite._run_number`` returns when the marker is missing — the
#: worktree case), not ``1`` (the first run), and not the count of anything
#: this fixture creates.
ACTIVE_RUN = 7


def _platform_triple() -> str:
    """The suffix ``_resolve.sahjhan_binary()`` looks for on this machine.

    Loaded by path rather than imported by name. ``hooks/_common.py`` and
    ``enforcement/hooks/_common.py`` are different modules with the same name,
    and a by-name import here would seed ``sys.modules`` for the whole pytest
    session with whichever one this file reached first.
    """
    path = os.path.join(ENFORCEMENT_HOOKS_DIR, "_resolve.py")
    spec = importlib.util.spec_from_file_location("_resolve_for_worktree_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.platform_triple())


_STUB_BINARY = """#!/bin/sh
# Stub sahjhan: record the invocation, succeed, do nothing else.
printf '%s\\n' "$*" >> "$SAHJHAN_STUB_LOG"
exit 0
"""


def _git(*args: str, cwd: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=scrubbed_env(),
    )


@dataclass
class WorktreeProject:
    """A main checkout, a linked worktree, and a way to drive hooks in each."""

    main: str
    worktree: str
    sahjhan_dir: str
    plugin_root: str
    stub_log: str
    _extra_env: dict[str, str] = field(default_factory=dict)

    def env(self, **overrides: str) -> dict[str, str]:
        """The environment every subprocess in this fixture must use."""
        base = dict(self._extra_env)
        base.update(overrides)
        return scrubbed_env(
            CLAUDE_PLUGIN_ROOT=self.plugin_root,
            SAHJHAN_STUB_LOG=self.stub_log,
            **base,
        )

    def run_hook(self, hook_name: str, event: dict, *, cwd: str, **env_overrides: str) -> dict:
        """Drive an enforcement hook by subprocess, as Claude Code does.

        ``cwd`` is passed explicitly rather than defaulted, because *which*
        checkout the hook runs in is the whole subject here.
        """
        event = {**event, "cwd": cwd}
        return run_hook(
            os.path.join(ENFORCEMENT_HOOKS_DIR, hook_name),
            event,
            cwd=cwd,
            env=self.env(**env_overrides),
        )

    def binary_calls(self) -> list[str]:
        """Every argv line the stub binary recorded, oldest first."""
        try:
            with open(self.stub_log, encoding="utf-8") as fh:
                return [line.strip() for line in fh if line.strip()]
        except OSError:
            return []

    def reset_binary_calls(self) -> None:
        with open(self.stub_log, "w", encoding="utf-8"):
            pass

    def reached_manifest_verify(self) -> bool:
        return any("manifest verify" in line for line in self.binary_calls())


def make_worktree_project(root: str) -> WorktreeProject:
    """Build the main checkout, its ignored audit dir, and a linked worktree."""
    main = os.path.join(root, "project")
    os.makedirs(main, exist_ok=True)

    _git("init", "-q", "-b", "main", cwd=main)
    _git("config", "user.email", "t@example.com", cwd=main)
    _git("config", "user.name", "T", cwd=main)

    # The line that creates the whole situation: the audit dir is ignored, so
    # `git worktree add` has nothing to check out there.
    with open(os.path.join(main, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("docs/holtz/.sahjhan/\n")
    with open(os.path.join(main, "src.py"), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    _git("add", ".gitignore", "src.py", cwd=main)
    _git("commit", "-qm", "init", cwd=main)

    sahjhan_dir = os.path.join(main, "docs", "holtz", ".sahjhan")
    os.makedirs(sahjhan_dir, exist_ok=True)
    with open(os.path.join(sahjhan_dir, "active-ledger"), "w", encoding="utf-8") as fh:
        fh.write(f"run-{ACTIVE_RUN}\n")
    with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w", encoding="utf-8") as fh:
        fh.write(f"{os.getpid()}\n")

    worktree = os.path.join(main, ".claude", "worktrees", "fix-a")
    _git("worktree", "add", "-q", "--detach", worktree, "HEAD", cwd=main)
    assert not os.path.isdir(
        os.path.join(worktree, "docs", "holtz", ".sahjhan")
    ), "the fixture is pointless if the worktree carries the audit dir"

    plugin_root = os.path.join(root, "plugin")
    bin_dir = os.path.join(plugin_root, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    stub = os.path.join(bin_dir, f"sahjhan-{_platform_triple()}")
    with open(stub, "w", encoding="utf-8") as fh:
        fh.write(_STUB_BINARY)
    os.chmod(stub, 0o755)  # noqa: S103 - a test stub the fixture owns
    stub_log = os.path.join(root, "sahjhan-calls.log")
    with open(stub_log, "w", encoding="utf-8"):
        pass

    return WorktreeProject(
        main=main,
        worktree=worktree,
        sahjhan_dir=sahjhan_dir,
        plugin_root=plugin_root,
        stub_log=stub_log,
    )


def fresh_enforcement_state() -> dict:
    """Cache state that makes ``is_enforcement_fresh`` true right now.

    Serve this from ``mock_daemon`` so the main-checkout leg gets past the
    freshness check and on to the binary. Without it both legs exit early and
    the asymmetry the fixture exists to show is invisible.
    """
    return {
        "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "unregistered_commits": {},
    }


__all__ = [
    "ACTIVE_RUN",
    "ENFORCEMENT_HOOKS_DIR",
    "REPO_ROOT",
    "WorktreeProject",
    "fresh_enforcement_state",
    "make_worktree_project",
]

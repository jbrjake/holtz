"""Tests for the boundary directory a linked git worktree resolves.

`boundary_dir()` names where the daemon socket lives. It is keyed by a digest
of a path, and *which* path is the whole question: key it on the process cwd
and a fix subagent working in a linked worktree resolves a socket nothing is
bound to, so its couriers fail closed and the per-actor TDD gate can never open
for it (P0.3 / D40). Key it on the main worktree and linked worktrees of one
project share one daemon, while two separate checkouts — the case the digest
was introduced for — still do not collide.

Both halves are asserted here. A test that only proved worktrees now agree
would pass just as well against `return "constant"`, which is the shape that
disarms the socket separation entirely.

The module is loaded by path rather than imported by name: `hooks/_common.py`
and `enforcement/hooks/_common.py` are different modules with the same name,
and in a shared pytest process whichever one an earlier test reached first
wins.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")


def _load_common():
    """Load `enforcement/hooks/_common.py` by path, never by module name."""
    path = os.path.join(HOOKS_DIR, "_common.py")
    spec = importlib.util.spec_from_file_location("_enforcement_common_wt", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_common = _load_common()


def _clean_env(**overrides: str) -> dict[str, str]:
    """The ambient environment with git's per-invocation variables removed.

    `git-hooks/pre-commit` runs this suite, and a git hook inherits `GIT_DIR`,
    `GIT_INDEX_FILE` and friends pointing at *this* repository. Left in place
    they follow every subprocess into the throwaway repositories below, where
    `git worktree add` exits 128 — so the tests would pass when run by hand and
    fail only inside the commit that ships them.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(overrides)
    return env


def _git(*args: str, cwd: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=_clean_env(),
    )


def _make_repo(path: str) -> str:
    """A git repo with one commit, so `git worktree add` has something to check out."""
    os.makedirs(path, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "t@example.com", cwd=path)
    _git("config", "user.name", "T", cwd=path)
    with open(os.path.join(path, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("x\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-qm", "init", cwd=path)
    return path


def _expected_key(path: str) -> str:
    """The digest `boundary_dir` is documented to produce for a given anchor."""
    return hashlib.sha256(os.path.realpath(path).encode()).hexdigest()[:12]


def test_a_linked_worktree_resolves_the_main_worktrees_boundary(tmp_path):
    """The blocker D40 rules on: a worktree subagent must reach the main daemon."""
    main = _make_repo(str(tmp_path / "project"))
    wt = str(tmp_path / "project" / ".claude" / "worktrees" / "fix-a")
    _git("worktree", "add", "-q", "--detach", wt, "HEAD", cwd=main)

    assert _common.boundary_dir(wt) == _common.boundary_dir(main)


def test_a_worktree_outside_the_project_also_resolves_it(tmp_path):
    """Placement is the harness's choice, so the rule cannot depend on nesting.

    Claude Code 2.1.246 nests isolated worktrees at
    `<project>/.claude/worktrees/<name>/`, but `git worktree add` accepts any
    path and a consumer may have moved one. The link is what makes a worktree
    part of this project, not where it sits.
    """
    main = _make_repo(str(tmp_path / "project"))
    wt = str(tmp_path / "elsewhere" / "fix-b")
    _git("worktree", "add", "-q", "--detach", wt, "HEAD", cwd=main)

    assert _common.boundary_dir(wt) == _common.boundary_dir(main)


def test_two_separate_checkouts_still_get_different_sockets(tmp_path):
    """The property the digest was introduced for, which D40 must not spend."""
    one = _make_repo(str(tmp_path / "checkout-one"))
    two = _make_repo(str(tmp_path / "checkout-two"))

    assert _common.boundary_dir(one) != _common.boundary_dir(two)


def test_a_subdirectory_resolves_the_repo_root(tmp_path):
    """A system-owned path anchors at the project root, not at the process cwd."""
    main = _make_repo(str(tmp_path / "project"))
    sub = os.path.join(main, "src", "deep")
    os.makedirs(sub)

    assert _common.boundary_dir(sub) == _common.boundary_dir(main)


def test_the_main_worktrees_key_does_not_move(tmp_path):
    """A plain checkout keeps the exact socket it had before D40.

    Asserted against the digest rather than against another call, so a change
    that altered every key consistently would still fail here. An audit running
    when this ships must not have its socket renamed underneath it.
    """
    main = _make_repo(str(tmp_path / "project"))
    expected = os.path.join(
        os.path.expanduser("~"), ".holtz", "run", _expected_key(main)
    )

    assert _common.boundary_dir(main) == expected


def test_a_directory_that_is_not_a_repo_keys_on_itself(tmp_path):
    """No repo, no anchor — the fallback stays the path it was given."""
    plain = str(tmp_path / "not-a-repo")
    os.makedirs(plain)
    expected = os.path.join(
        os.path.expanduser("~"), ".holtz", "run", _expected_key(plain)
    )

    assert _common.boundary_dir(plain) == expected


def test_a_submodule_is_its_own_project(tmp_path):
    """A submodule's `.git` is a file too, and it is not a worktree of the super.

    Both carry a `gitdir:` pointer, so a rule that followed the pointer without
    checking what it points at would hand a submodule the superproject's
    daemon. `commondir` is what distinguishes them: linked worktrees have one,
    submodule gitdirs do not.
    """
    super_repo = _make_repo(str(tmp_path / "super"))
    sub_origin = _make_repo(str(tmp_path / "sub-origin"))
    _git(
        "-c", "protocol.file.allow=always",
        "submodule", "add", "-q", sub_origin, "vendor/sub",
        cwd=super_repo,
    )
    submodule = os.path.join(super_repo, "vendor", "sub")

    assert os.path.isfile(os.path.join(submodule, ".git"))
    # Asserted positively. "different from the superproject" also holds when
    # the pointer is followed to some third path that is nobody's project, so
    # inequality alone would pass against a rule that is simply wrong.
    expected = os.path.join(
        os.path.expanduser("~"), ".holtz", "run", _expected_key(submodule)
    )
    assert _common.boundary_dir(submodule) == expected


@pytest.mark.parametrize("missing", ["gitdir", "commondir"])
def test_an_unreadable_link_falls_back_rather_than_guessing(tmp_path, missing):
    """A malformed link keys on the directory itself instead of raising.

    `boundary_dir` is called from every hook, including the ones whose job is
    to report that something is wrong. Raising here would turn a broken
    checkout into a stack trace on an unrelated tool call.
    """
    main = _make_repo(str(tmp_path / "project"))
    wt = str(tmp_path / "project" / ".claude" / "worktrees" / "fix-c")
    _git("worktree", "add", "-q", "--detach", wt, "HEAD", cwd=main)

    if missing == "gitdir":
        with open(os.path.join(wt, ".git"), "w", encoding="utf-8") as fh:
            fh.write("this is not a gitdir pointer\n")
    else:
        with open(os.path.join(wt, ".git"), encoding="utf-8") as fh:
            gitdir = fh.read().split("gitdir:", 1)[1].strip()
        os.remove(os.path.join(gitdir, "commondir"))

    expected = os.path.join(
        os.path.expanduser("~"), ".holtz", "run", _expected_key(wt)
    )
    assert _common.boundary_dir(wt) == expected


# ── The end-to-end half: a worktree subagent writing through the real daemon ──
#
# The unit tests above prove two paths hash to one key. They cannot prove the
# daemon at that key accepts the write, because `record_authed_event` is
# authenticated by peer identity against `trusted-callers.toml` and a stale
# manifest fails open in a way that looks like success everywhere else. Only a
# real daemon distinguishes them, which is why this fixture starts one — and
# deliberately does **not** set `SAHJHAN_DAEMON_SOCKET`, the override every
# other e2e test uses. That override is exactly the line D40 changes; a test
# that set it would exercise the harness rather than the fix.


def _daemon_at_the_resolved_socket(project_root: str, home: str, binary: str):
    """Start a daemon where `boundary_dir` says it should be, as holtz-start does."""
    config_dir = os.path.join(REPO_ROOT, "enforcement")
    env = _clean_env(HOME=home)
    sock_path = os.path.join(_common.boundary_dir(project_root), "daemon.sock")
    os.makedirs(os.path.dirname(sock_path), mode=0o700, exist_ok=True)

    subprocess.run(
        [binary, "--config-dir", config_dir, "init"],
        cwd=project_root, check=True, capture_output=True, text=True, env=env,
    )
    proc = subprocess.Popen(
        [binary, "--config-dir", config_dir, "daemon", "start",
         "--idle-timeout", "30"],
        cwd=project_root,
        env={**env, "SAHJHAN_DAEMON_SOCKET": sock_path},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("sahjhan daemon did not create socket within 5s")
    return proc, sock_path, config_dir


@pytest.fixture
def worktree_daemon(monkeypatch):
    """A git project with a live daemon at its *resolved* boundary socket.

    `HOME` is redirected to a short `/tmp` path for two reasons: the real one
    must not collect test sockets, and `boundary_dir` hangs off `~`, so a long
    pytest tmp path would breach the 104-byte macOS `AF_UNIX` limit.
    """
    sys.path.insert(0, HOOKS_DIR)
    from _resolve import ensure_sahjhan

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")

    home = tempfile.mkdtemp(prefix="hm-", dir="/tmp")
    monkeypatch.setenv("HOME", home)
    project_root = tempfile.mkdtemp(prefix="wt-", dir="/tmp")
    _make_repo(project_root)

    spec = importlib.util.spec_from_file_location(
        "_sandbox_control_wt", os.path.join(HOOKS_DIR, "sandbox_control.py")
    )
    assert spec and spec.loader
    sandbox_control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox_control)
    settings_path = os.path.join(project_root, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump({"sandbox": sandbox_control.sandbox_settings(project_root)}, fh)

    proc, sock_path, config_dir = _daemon_at_the_resolved_socket(
        project_root, home, binary
    )

    yield {
        "binary": binary,
        "config_dir": config_dir,
        "project_root": project_root,
        "sock_path": sock_path,
        "home": home,
    }

    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            cwd=project_root, timeout=5, capture_output=True,
            env=_clean_env(HOME=home, SAHJHAN_DAEMON_SOCKET=sock_path),
        )
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=3)
        if proc.poll() is None:
            proc.kill()
    shutil.rmtree(project_root, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)


def _sahjhan(env_home: str, daemon: dict, *args: str, cwd: str | None = None):
    return subprocess.run(
        [daemon["binary"], "--config-dir", daemon["config_dir"], *args],
        cwd=cwd or daemon["project_root"],
        capture_output=True, text=True,
        env=_clean_env(HOME=env_home),
    )


def _tdd_evidence_rows(daemon: dict) -> list[dict]:
    result = _sahjhan(
        daemon["home"], daemon, "--json", "query",
        "SELECT agent_id, finding_id FROM events WHERE type='tdd_evidence'",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _run_courier(cwd: str, home: str, agent_id: str) -> subprocess.CompletedProcess:
    """Fire `tdd_courier.py` the way Claude Code does — subprocess, JSON on stdin.

    No `SAHJHAN_DAEMON_SOCKET`: the courier must resolve the socket itself.
    """
    event = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" '
                "event test_failed_before_fix --field finding_id=BH-101 "
                "--field test_name=test_thing"
            )
        },
        "tool_response": {"exit_code": 0, "stdout": "", "stderr": ""},
        "cwd": cwd,
        "agent_id": agent_id,
    }
    env = _clean_env(HOME=home, CLAUDE_PLUGIN_ROOT=REPO_ROOT)
    env.pop("SAHJHAN_DAEMON_SOCKET", None)
    return subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, "tdd_courier.py")],
        input=json.dumps(event), cwd=cwd, capture_output=True, text=True, env=env,
    )


def _record_failing_test(daemon: dict, cwd: str) -> None:
    """The agent-written half of the pair, recorded from ``cwd``.

    Written from the worktree in the positive test on purpose: it also proves
    the ledger sahjhan resolves by walking up is the main one, so the courier's
    `_UNPAIRED` query and its write are talking about the same chain.
    """
    result = _sahjhan(
        daemon["home"], daemon, "event", "test_failed_before_fix",
        "--field", "finding_id=BH-101", "--field", "test_name=test_thing",
        "--field", f"project={os.path.basename(daemon['project_root'])}",
        "--field", "run=1", "--field", "auditor=holtz",
        cwd=cwd,
    )
    assert result.returncode == 0, result.stderr


class TestTheCourierReachesTheMainDaemonFromAWorktree:
    """P0.3's whole point: a fix subagent in its own tree is still enforced."""

    def test_a_worktree_courier_writes_tdd_evidence_to_the_main_ledger(
        self, worktree_daemon
    ):
        """The positive claim, asserted on a row that must exist.

        Not "no error was printed" — a courier that silently declined would
        satisfy that. The evidence row, carrying the actor the host reported,
        is the thing the TDD gate then filters on.
        """
        main = worktree_daemon["project_root"]
        wt = os.path.join(main, ".claude", "worktrees", "fix-a")
        _git("worktree", "add", "-q", "--detach", wt, "HEAD", cwd=main)
        _record_failing_test(worktree_daemon, cwd=wt)

        result = _run_courier(wt, worktree_daemon["home"], agent_id="agent-7")

        assert result.returncode == 0, result.stderr
        rows = _tdd_evidence_rows(worktree_daemon)
        assert [r["agent_id"] for r in rows] == ["agent-7"], result.stderr

    def test_a_separate_checkout_cannot_reach_this_projects_daemon(
        self, worktree_daemon, tmp_path
    ):
        """The property the per-checkout digest existed for, still held.

        A second repository is not a worktree of this one, so its courier must
        find nothing at its own key. Asserted against the *main* ledger staying
        empty of evidence rather than against the courier's exit status, so a
        courier that wrote to some third ledger would still fail this.
        """
        other = _make_repo(str(tmp_path / "unrelated"))
        _record_failing_test(worktree_daemon, cwd=worktree_daemon["project_root"])

        result = _run_courier(other, worktree_daemon["home"], agent_id="agent-9")

        assert _tdd_evidence_rows(worktree_daemon) == [], result.stdout

"""Tests for suite_courier.py — the channel that records `suite_green`.

The agent's shell is sandboxed and cannot reach the daemon, so a suite run
cannot write its own result. This hook does, from outside the sandbox. That
makes it the one place where something the agent produced turns into a ledger
entry a gate believes, so the tests are organised around the question that
matters: *which fields can the agent influence?*

Everything a gate reads (`tree_hash`, `commit_hash`, `scope`) must come from
the hook's own git calls or from the command text the host reports. Everything
that crosses from the run's output (`command`, `test_count`) must be a field no
gate consults.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import verify_suite  # noqa: E402

import suite_courier  # noqa: E402
from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

PLUGIN_COMMAND = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/verify_suite.py" '
    "--record --scope affected"
)


def _marker(**payload) -> str:
    return f"{verify_suite.RECORD_MARKER} {json.dumps(payload, sort_keys=True)}"


def _git_repo(root) -> str:
    """A real git repo with one commit — the courier shells out to git for real."""
    root = str(root)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
    # The courier re-derives the affected selection, which reads
    # `git ls-files --others --exclude-standard` — so without neutering the
    # developer's global excludes these tests answer a different question on
    # every machine.
    subprocess.run(["git", "config", "core.excludesFile", os.devnull],
                   cwd=root, check=True, capture_output=True)
    with open(os.path.join(root, "a.py"), "w", encoding="utf-8") as f:
        f.write("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True,
                   capture_output=True, env=env)
    return root


def _event(root, command=PLUGIN_COMMAND, output=None, exit_code=None):
    response: dict = {"output": output if output is not None else _marker(
        command="python3 -m pytest -q", scope_ran="affected", test_count="42",
    )}
    if exit_code is not None:
        response["exit_code"] = exit_code
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": response,
        "cwd": str(root),
    }


def _recorded(mock_daemon) -> dict | None:
    for req in mock_daemon.recorded_events:
        if req.get("event_type") == "suite_green":
            return req.get("fields", {})
    return None


# ── which commands are this channel at all ───────────────────────────────────


class TestCommandRecognition:
    """The recognizer lives beside the command it recognizes, and is shared.

    If `phase-fix-loop.md` taught one invocation and the courier accepted a
    different one, the failure would be silent: green suite, nothing recorded,
    `fix_commit` blocked forever with no error pointing here.
    """

    @pytest.mark.parametrize("command", [
        PLUGIN_COMMAND,
        'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/verify_suite.py" --record --scope full',
        "python3 /abs/path/enforcement/scripts/verify_suite.py --record --scope full",
        "python3 $CLAUDE_PLUGIN_ROOT/enforcement/scripts/verify_suite.py --record --scope affected",
    ])
    def test_accepts_the_prescribed_invocations(self, command):
        assert verify_suite.record_scope_of(command) in ("full", "affected")

    def test_the_skill_file_command_is_one_of_them(self):
        """Read the taught command out of the doc rather than trusting a copy.

        A test that hardcodes the invocation passes happily while the skill
        file drifts to a different one.
        """
        doc = os.path.join(REPO_ROOT, "skills", "holtz", "references", "phase-fix-loop.md")
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        taught = [
            line.strip(" `") for line in text.replace("`", "\n").splitlines()
            if "verify_suite.py" in line and "--record" in line
        ]
        assert taught, "phase-fix-loop.md no longer teaches a --record command"
        for command in taught:
            assert verify_suite.record_scope_of(command) is not None, \
                f"the courier would not recognize a command the skill file teaches: {command!r}"

    @pytest.mark.parametrize("command", [
        "python3 verify_suite.py --check --scope affected",   # the read side
        "python3 /elsewhere/verify_suite.py --record --scope full",  # wrong tree
        "python3 /x/enforcement/scripts/verify_suite.py --record --scope everything",
        "echo hi",
        "",
    ])
    def test_rejects_everything_else(self, command):
        assert verify_suite.record_scope_of(command) is None

    def test_a_bare_record_takes_the_parsers_default_scope(self):
        """`--record` alone runs the full suite, so it records `full`.

        Not recognizing it would be worse than either alternative: the command
        succeeds, nothing is written, and the deadlock arrives later with
        nothing pointing back at the omitted flag.
        """
        assert verify_suite.record_scope_of(
            "python3 /x/enforcement/scripts/verify_suite.py --record"
        ) == verify_suite.build_parser().parse_args(["--record"]).scope

    def test_rejects_a_redirected_cwd(self, tmp_path):
        """`--cwd` would run another repo's suite under this repo's tree hash.

        The courier hashes the tree at the event's cwd, so honouring a
        redirect would attach a true result to the wrong tree — the one thing
        the hash exists to prevent.
        """
        assert verify_suite.record_scope_of(
            f"python3 /x/enforcement/scripts/verify_suite.py --record --scope full --cwd {tmp_path}"
        ) is None


@pytest.mark.hook_e2e
class TestChainedCommandsAreNotTheChannel:

    @pytest.mark.parametrize("command", [
        f"{PLUGIN_COMMAND} && git commit -m x",
        f"echo '{'SUITE-GREEN:'} {{}}' ; {PLUGIN_COMMAND}",
        f"rm -rf /tmp/x && {PLUGIN_COMMAND}",
    ])
    def test_multi_segment_lines_record_nothing(self, tmp_path, mock_daemon, command):
        """One Bash line whose success becomes evidence must not carry cargo."""
        _git_repo(tmp_path)
        code, _, _ = run_enforcement_hook(
            "suite_courier.py", _event(tmp_path, command=command), cwd=str(tmp_path),
        )
        assert code == 0
        assert _recorded(mock_daemon) is None


# ── the provenance split ─────────────────────────────────────────────────────


@pytest.mark.hook_e2e
class TestProvenance:

    def test_hashes_come_from_the_hook_not_the_output(self, tmp_path, mock_daemon):
        """A lying marker cannot move any field a gate consults.

        The marker forges a tree hash and a commit. Both must be ignored: the
        hook shells out to git itself, from outside the sandbox, on the same
        unchanged tree.
        """
        root = _git_repo(tmp_path)
        lying = _marker(
            command="pytest", scope_ran="full", test_count="1",
            tree_hash="0" * 64, commit_hash="deadbeef",
        )
        code, _, _ = run_enforcement_hook(
            "suite_courier.py", _event(root, output=lying), cwd=root,
        )
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields is not None, "a green run must record"

        assert fields["tree_hash"] == verify_suite.compute_tree_hash(root)
        assert fields["tree_hash"] != "0" * 64
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True).stdout.strip()
        assert fields["commit_hash"] == head

    def test_the_marker_cannot_weaken_an_explicit_full(self, tmp_path, mock_daemon):
        """`--scope full` records `full` however the run describes itself.

        Scope is read from the command text the host reported, so the only
        thing that can set it is what the human-visible command said.
        """
        root = _git_repo(tmp_path)
        command = PLUGIN_COMMAND.replace("--scope affected", "--scope full")
        weakening = _marker(command="pytest", scope_ran="affected", test_count="1")
        run_enforcement_hook(
            "suite_courier.py", _event(root, command=command, output=weakening), cwd=root,
        )
        assert _recorded(mock_daemon)["scope"] == "full"

    def test_informational_fields_come_from_the_marker(self, tmp_path, mock_daemon):
        """`command` and `test_count` are the run's own report, and no gate reads them."""
        root = _git_repo(tmp_path)
        code, _, _ = run_enforcement_hook("suite_courier.py", _event(root), cwd=root)
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields["command"] == "python3 -m pytest -q"
        assert fields["test_count"] == "42"

    def test_an_unprovable_subset_records_full_because_the_hook_says_so(
        self, tmp_path, mock_daemon,
    ):
        """`--scope affected` in a repo with no impact graph really ran everything.

        Recording it as `affected` would throw away a full green and force the
        whole suite to run again before the three transitions that need one.
        The upgrade is safe because the hook re-derives it: this repo has no
        graph and no baseline, so `select_affected` cannot narrow, here or in
        the run.
        """
        root = _git_repo(tmp_path)
        code, _, _ = run_enforcement_hook("suite_courier.py", _event(root), cwd=root)
        assert code == 0
        assert _recorded(mock_daemon)["scope"] == "full"


class TestScopeUpgradeIsDerived:
    """The upgrade is a function of the tree, not of anything the run said."""

    def test_upgrades_only_when_the_subset_cannot_narrow(self, monkeypatch):
        monkeypatch.setattr(suite_courier, "select_affected", lambda root, cwd: (None, "why"))
        assert suite_courier._effective_scope("affected", "/r", "/r") == "full"

    def test_a_narrowed_run_stays_affected(self, monkeypatch):
        """The run tested a subset, so the evidence is subset-strength."""
        monkeypatch.setattr(
            suite_courier, "select_affected", lambda root, cwd: (["tests/test_a.py"], ""),
        )
        assert suite_courier._effective_scope("affected", "/r", "/r") == "affected"

    def test_full_is_never_downgraded(self, monkeypatch):
        """An explicit full request is the strongest claim; nothing weakens it."""
        monkeypatch.setattr(
            suite_courier, "select_affected", lambda root, cwd: (["tests/test_a.py"], ""),
        )
        assert suite_courier._effective_scope("full", "/r", "/r") == "full"


# ── the two signals ──────────────────────────────────────────────────────────


@pytest.mark.hook_e2e
class TestBothSignalsRequired:

    def test_a_nonzero_exit_records_nothing(self, tmp_path, mock_daemon):
        """Belt for the brace: 2.x does not fire PostToolUse on failure, but a
        version that did must not turn a red suite into a green ledger entry."""
        root = _git_repo(tmp_path)
        code, _, _ = run_enforcement_hook(
            "suite_courier.py", _event(root, exit_code=1), cwd=root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_a_missing_marker_records_nothing_and_says_so(self, tmp_path, mock_daemon):
        """On 2.x the marker is the only second opinion there is.

        Silence here would be the worst outcome: the suite passed, nothing was
        written, and `fix_commit` blocks much later with nothing pointing back.
        """
        root = _git_repo(tmp_path)
        code, output, _ = run_enforcement_hook(
            "suite_courier.py", _event(root, output="all good, 42 passed"), cwd=root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "NOT recorded" in context

    def test_a_malformed_marker_records_nothing(self, tmp_path, mock_daemon):
        root = _git_repo(tmp_path)
        code, _, _ = run_enforcement_hook(
            "suite_courier.py",
            _event(root, output=f"{verify_suite.RECORD_MARKER} not json at all"),
            cwd=root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_the_marker_is_read_from_the_end(self, tmp_path, mock_daemon):
        """It is printed last so truncation of a noisy run cannot eat it."""
        root = _git_repo(tmp_path)
        noisy = "\n".join(["....." * 40] * 50 + [_marker(
            command="pytest", scope_ran="affected", test_count="7")])
        code, _, _ = run_enforcement_hook(
            "suite_courier.py", _event(root, output=noisy), cwd=root,
        )
        assert _recorded(mock_daemon)["test_count"] == "7"


@pytest.mark.hook_e2e
class TestOtherToolsAreUntouched:

    def test_non_bash_events_pass_through(self, tmp_path, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "suite_courier.py",
            {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}, "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_an_ordinary_bash_command_records_nothing(self, tmp_path, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "suite_courier.py", _event(tmp_path, command="pytest -q"), cwd=str(tmp_path),
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

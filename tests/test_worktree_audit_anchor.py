"""W02 / item 29 — "is an audit active here" is answered at the project anchor.

`.gitignore` carries `docs/holtz/.sahjhan/`, so a linked worktree does not
contain it, and five sites probed for it relative to the process cwd. A fix
subagent runs with its worktree as cwd, so for the three actors the fix loop
dispatches: manifest verification was skipped, the fail-closed degrade path
failed open, daemon-death detection was off, the terminated marker went to the
wrong place, and `sahjhan daemon stop` was permitted mid-run.

The socket already resolved through `project_anchor` (D40). These tests assert
the probe beside it now does too, and — for each one — that the worktree and
the main checkout reach the **same** decision. "The two agree" is the claim,
because "the worktree denies" alone would also hold for a hook that denies
everything.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worktree_project import ACTIVE_RUN, REPO_ROOT, fresh_enforcement_state  # noqa: E402

pytestmark = pytest.mark.hook_e2e


def _bash_event(command: str = "echo hello") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": 0, "stdout": "", "stderr": ""},
    }


def _edit_event(project_dir: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": os.path.join(project_dir, "src.py"),
            "old_string": "x = 1",
            "new_string": "x = 2",
        },
    }


def _decision(out: dict) -> str | None:
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


class TestV1ManifestVerification:
    """V1 — `bash_guard.py` verifies at a worktree cwd instead of exiting ok."""

    def test_the_worktree_reaches_manifest_verify(self, worktree_cwd, mock_daemon):
        mock_daemon.state = fresh_enforcement_state()
        worktree_cwd.reset_binary_calls()
        worktree_cwd.run_hook("bash_guard.py", _bash_event(), cwd=worktree_cwd.worktree)
        calls = worktree_cwd.binary_calls()
        assert any("manifest verify" in line for line in calls), calls

    def test_both_checkouts_verify(self, worktree_cwd, mock_daemon):
        """The claim is agreement, not merely that the worktree does something."""
        mock_daemon.state = fresh_enforcement_state()
        seen = {}
        for name, cwd in (("main", worktree_cwd.main), ("worktree", worktree_cwd.worktree)):
            worktree_cwd.reset_binary_calls()
            worktree_cwd.run_hook("bash_guard.py", _bash_event(), cwd=cwd)
            seen[name] = worktree_cwd.reached_manifest_verify()
        assert seen == {"main": True, "worktree": True}, seen

    def test_a_project_with_no_audit_still_pays_nothing(self, worktree_cwd, mock_daemon):
        """The ordering `bash_guard` documents must survive the anchoring.

        The probe exists so a project without an audit never triggers the
        ~100 MB bootstrap. Anchoring must not turn "no audit anywhere" into
        "verify anyway".
        """
        mock_daemon.state = fresh_enforcement_state()
        import shutil

        shutil.rmtree(worktree_cwd.sahjhan_dir)
        worktree_cwd.reset_binary_calls()
        worktree_cwd.run_hook("bash_guard.py", _bash_event(), cwd=worktree_cwd.worktree)
        assert worktree_cwd.binary_calls() == []

    def test_the_theoretical_courier_pays_nothing_either(
        self, worktree_cwd, mock_daemon
    ):
        """W18 / item 36. The same ordering, at the hook that lacked it.

        `pending()` reached `ensure_sahjhan()` with no audit probe in front of
        it, so any Bash line naming `merge_punchlists.py` in **any**
        plugin-installed project bought a ~100 MB download and an injected
        protocol warning about a sweep that project never asked for.

        This is invisible to a test run inside this repo, which always has an
        audit dir — which is why it is here, on the fixture that can take one
        away, rather than beside the courier's own tests.
        """
        mock_daemon.state = fresh_enforcement_state()
        import shutil

        shutil.rmtree(worktree_cwd.sahjhan_dir)
        worktree_cwd.reset_binary_calls()
        out = worktree_cwd.run_hook(
            "theoretical_courier.py",
            _bash_event(
                'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/'
                'merge_punchlists.py" --justine docs/holtz/justine/PUNCHLIST.md'
            ),
            cwd=worktree_cwd.worktree,
        )
        assert worktree_cwd.binary_calls() == []
        # And no warning: a project with no audit has no findings to sweep, so
        # there is nothing that should have happened and did not. The warning
        # channel exists for a board left dirty, and spending it here would
        # teach every consumer to ignore it.
        context = json.dumps(out)
        assert "NOT auto-deferred" not in context, context


class TestV2AndV5TheDegradePathFailsClosed:
    """V2/V5 — `exit_enforcement_error` denies at a worktree cwd.

    The punchlist's observation was `nodir -> allow, withdir -> deny`. It has
    to become `deny -> deny`, which is what makes `pre_tool_hook.py:9`'s
    "Fails closed (blocks) during active audits if the daemon is unreachable"
    true for the actors it was written about.
    """

    def test_the_worktree_denies_when_enforcement_cannot_run(
        self, worktree_cwd, mock_daemon
    ):
        mock_daemon.state = fresh_enforcement_state()
        worktree_cwd.disable_binary()
        out = worktree_cwd.run_hook(
            "pre_tool_hook.py", _edit_event(worktree_cwd.worktree),
            cwd=worktree_cwd.worktree,
        )
        assert _decision(out) == "deny", out
        reason = out["hookSpecificOutput"].get("permissionDecisionReason", "")
        assert "ENFORCEMENT DEGRADED" in reason, reason

    def test_both_checkouts_deny(self, worktree_cwd, mock_daemon):
        mock_daemon.state = fresh_enforcement_state()
        worktree_cwd.disable_binary()
        decisions = {}
        for name, cwd in (("main", worktree_cwd.main), ("worktree", worktree_cwd.worktree)):
            out = worktree_cwd.run_hook(
                "pre_tool_hook.py", _edit_event(cwd), cwd=cwd,
            )
            decisions[name] = _decision(out)
        assert decisions == {"main": "deny", "worktree": "deny"}, decisions

    def test_outside_an_audit_it_still_allows(self, worktree_cwd, mock_daemon):
        """Fail-open outside audits is the documented behaviour and must hold.

        Without this, "deny" above could be a hook that blocks unconditionally.
        """
        mock_daemon.state = fresh_enforcement_state()
        worktree_cwd.disable_binary()
        import shutil

        shutil.rmtree(worktree_cwd.sahjhan_dir)
        out = worktree_cwd.run_hook(
            "pre_tool_hook.py", _edit_event(worktree_cwd.worktree),
            cwd=worktree_cwd.worktree,
        )
        assert _decision(out) in (None, "allow"), out


class TestV3DaemonStop:
    """V3 — a subagent cannot stop the daemon from its worktree."""

    def test_daemon_stop_is_blocked_from_the_worktree(self, worktree_cwd, mock_daemon):
        mock_daemon.state = {**fresh_enforcement_state(), "state": "fix_loop"}
        out = worktree_cwd.run_hook(
            "_sahjhan_bootstrap.py", _bash_event("sahjhan daemon stop"),
            cwd=worktree_cwd.worktree,
        )
        assert _decision(out) == "deny", out
        assert "fix_loop" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_both_checkouts_block_it(self, worktree_cwd, mock_daemon):
        mock_daemon.state = {**fresh_enforcement_state(), "state": "fix_loop"}
        decisions = {
            name: _decision(worktree_cwd.run_hook(
                "_sahjhan_bootstrap.py", _bash_event("sahjhan daemon stop"), cwd=cwd,
            ))
            for name, cwd in (
                ("main", worktree_cwd.main), ("worktree", worktree_cwd.worktree),
            )
        }
        assert decisions == {"main": "deny", "worktree": "deny"}, decisions

    def test_the_escape_still_exists_when_the_audit_is_terminated(
        self, worktree_cwd, mock_daemon
    ):
        """The stop hook's own escape hatch must stay reachable.

        #57 turned a blanket block into a graduated one precisely so the agent
        is not told to stop the daemon and forbidden from doing it. Anchoring
        the probe must not re-close that door.
        """
        mock_daemon.state = {**fresh_enforcement_state(), "state": "fix_loop"}
        with open(os.path.join(worktree_cwd.sahjhan_dir, "terminated"), "w",
                  encoding="utf-8") as fh:
            fh.write("reason: daemon_pid_dead\n")
        out = worktree_cwd.run_hook(
            "_sahjhan_bootstrap.py", _bash_event("sahjhan daemon stop"),
            cwd=worktree_cwd.worktree,
        )
        assert _decision(out) in (None, "allow"), out


class TestV4TheCourierRecordsTheProjectsRunNumber:
    """V4 — `suite_courier` writes the real run and the anchored project."""

    # The plugin's own script: the courier records only for the pinned copy
    # (D-v), and the fixture's CLAUDE_PLUGIN_ROOT is a stub directory.
    _COMMAND = (
        f"python3 {os.path.join(REPO_ROOT, 'enforcement', 'scripts', 'verify_suite.py')} "
        "--record --scope full"
    )

    def _drive(self, worktree_cwd, mock_daemon, cwd: str) -> dict:
        marker = "SUITE-GREEN: " + json.dumps(
            {"command": "pytest", "scope": "full", "test_count": "5", "python": "python3"},
            sort_keys=True,
        )
        mock_daemon.recorded_events.clear()
        worktree_cwd.run_hook(
            "suite_courier.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": self._COMMAND},
                "tool_response": {"exit_code": 0, "stdout": marker, "stderr": ""},
            },
            cwd=cwd,
        )
        assert mock_daemon.recorded_events, "the courier recorded nothing"
        return mock_daemon.recorded_events[-1]["fields"]

    def test_the_worktree_records_the_projects_run_number(
        self, worktree_cwd, mock_daemon
    ):
        mock_daemon.state = fresh_enforcement_state()
        fields = self._drive(worktree_cwd, mock_daemon, worktree_cwd.worktree)
        # Positive claims about the values. `run != "0"` would also pass on a
        # third wrong answer, and `"0"` is what `events.toml` accepts against
        # `^\d+$` — which is how a worktree's missing marker poisoned run
        # attribution for every emit after it.
        assert fields["run"] == str(ACTIVE_RUN), fields
        assert fields["project"] == os.path.basename(worktree_cwd.main), fields

    def test_it_equals_what_the_main_checkout_records(self, worktree_cwd, mock_daemon):
        mock_daemon.state = fresh_enforcement_state()
        main = self._drive(worktree_cwd, mock_daemon, worktree_cwd.main)
        wt = self._drive(worktree_cwd, mock_daemon, worktree_cwd.worktree)
        assert (wt["run"], wt["project"]) == (main["run"], main["project"])

    def test_the_tree_hash_still_describes_the_tree_that_was_tested(
        self, worktree_cwd, mock_daemon
    ):
        """Only `project` and `run` move to the anchor.

        `tree_hash` is the claim "these tests ran against this content", and a
        worktree's content is its own. Anchoring it would attach the main
        checkout's hash to a subagent's result.
        """
        mock_daemon.state = fresh_enforcement_state()
        main = self._drive(worktree_cwd, mock_daemon, worktree_cwd.main)
        wt = self._drive(worktree_cwd, mock_daemon, worktree_cwd.worktree)
        assert main["tree_hash"] and wt["tree_hash"]
        assert "tree_hash" in main and "tree_hash" in wt


class TestTheAnchorIsOneNamedFact:
    """The helper exists and every converted site refers to it.

    Item 29 was five careful copies of one path expression, one of which was
    corrected (the socket, D40) while the others were not. The check that
    stops it recurring is that the copies are gone.
    """

    #: Sites that name `docs/holtz/…` from `cwd` and are **not** the audit
    #: data dir, each with the reason it is not. Anything else is a new inline
    #: copy and fails this test.
    _ALLOWED_INLINE = {
        # `resolve_config_dir` asks *where is the config*, not *is an audit
        # active*, and it lives in the same file as the builder.
        ("_common.py", 'persisted = os.path.join(cwd, "docs", "holtz", ".sahjhan", "config-dir")'),
        # `docs/holtz/audit/` is an artifact directory, not the audit state dir.
        ("lens_quiz.py", 'artifact_path = os.path.join(cwd, "docs", "holtz", "audit", f"lens-{lens}.md")'),
    }

    def test_only_common_builds_the_audit_dir_path(self):
        """The check that fails the build on the next inline copy.

        Item 29 was one path expression written out at fourteen sites, one of
        which had been corrected (the socket, D40) while the rest had not. A
        test that only asserted the five the review happened to find would let
        the fifteenth in.
        """
        import re

        hooks_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "enforcement", "hooks",
        )
        pattern = re.compile(r'os\.path\.join\(\s*cwd\s*,\s*"docs"\s*,\s*"holtz"')
        offenders = []
        for name in sorted(os.listdir(hooks_dir)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(hooks_dir, name), encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    if not pattern.search(line):
                        continue
                    if (name, line.strip()) in self._ALLOWED_INLINE:
                        continue
                    offenders.append(f"{name}:{lineno}: {line.strip()}")
        assert offenders == [], (
            "these build the audit data dir inline instead of calling "
            "`_common.audit_data_dir`:\n  " + "\n  ".join(offenders)
        )

    def test_the_allowlist_is_not_a_way_out(self):
        """Every allowlisted line must still exist, spelled exactly.

        An allowlist nobody checks becomes the place inline copies go to hide:
        edit the line and the entry silently stops matching anything, so the
        exemption widens to nothing while the test keeps passing.
        """
        hooks_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "enforcement", "hooks",
        )
        for name, text in self._ALLOWED_INLINE:
            with open(os.path.join(hooks_dir, name), encoding="utf-8") as fh:
                body = fh.read()
            assert text in body, f"{name} no longer contains the exempted line: {text}"

    def test_audit_data_dir_is_defined_from_the_same_anchor_as_the_socket(self):
        import importlib.util

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "enforcement", "hooks", "_common.py",
        )
        spec = importlib.util.spec_from_file_location("_common_anchor_check", path)
        assert spec and spec.loader
        common = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(common)
        anchor = "/tmp/anchor-probe"
        assert common.audit_data_dir(anchor) == os.path.join(
            common.project_anchor(anchor), "docs", "holtz", ".sahjhan"
        )

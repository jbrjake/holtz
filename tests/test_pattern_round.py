"""Tests for the pattern-round yield: `pattern_round.py` + `pattern_courier.py`.

`patterns_found` was a number the agent typed, and the one run it has been
measured against recorded ``5`` and ``2`` for rounds 14 and 15 while
``patterns-brief.md`` says in its own words that both added none. So the tests
here are organised around the question the fix has to answer: *can the recorded
number be anything other than what the brief says?*

Everything a future gate could read (`patterns_found`, `pattern_ids`, `run`) is
re-derived by the hook from the brief and the ledger. `siblings_found` crosses
from the run's own output and no gate consults it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import pattern_round  # noqa: E402

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

PLUGIN_COMMAND = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/pattern_round.py" '
    "--record --siblings-found 4"
)

BRIEF = os.path.join("docs", "holtz", "patterns-brief.md")
ARCHIVE = os.path.join("docs", "holtz", "patterns-brief-archive.md")


def _entry(pat_id: str, run: int, date: str = "2026-08-21") -> str:
    return (
        f"## {pat_id}: A name ({'Run'} {run}, {date})\n"
        "**What to look for:** something\n"
        "**Detection heuristic:** `grep x`\n"
        "**Example:** somewhere\n\n"
    )


def _write(root, rel: str, body: str) -> None:
    path = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


# ── reading the brief ────────────────────────────────────────────────────────


class TestBriefEntries:

    def test_reads_id_and_run_tag(self, tmp_path):
        _write(tmp_path, BRIEF, "# Brief\n\n" + _entry("PAT-001", 3))
        assert pattern_round.brief_entries(str(tmp_path)) == {"PAT-001": "3"}

    def test_the_archive_counts(self, tmp_path):
        """The rolling policy moves the five oldest entries out of the brief.

        An entry this run added can therefore leave the live file while still
        being this run's yield. Reading only the brief would make a long run's
        early rounds silently un-count themselves — the same defect the
        open-only punchlist had against recon's cold-file scan.
        """
        _write(tmp_path, BRIEF, "# Brief\n\n" + _entry("PAT-020", 1))
        _write(tmp_path, ARCHIVE, "# Archive\n\n" + _entry("PAT-001", 1))
        assert set(pattern_round.brief_entries(str(tmp_path))) == {"PAT-001", "PAT-020"}

    def test_a_heading_inside_a_fence_is_an_example_not_an_entry(self, tmp_path):
        """The brief quotes its own format, and quoted headings are not entries.

        Recorded in the brief itself as BH-005 of run 14 — the same defect
        `pattern_brief_compact.py` masks fences for.
        """
        _write(
            tmp_path,
            BRIEF,
            "# Brief\n\n"
            + _entry("PAT-001", 1)
            + "```markdown\n"
            + _entry("PAT-999", 1)
            + "```\n",
        )
        assert set(pattern_round.brief_entries(str(tmp_path))) == {"PAT-001"}

    def test_a_tilde_fence_does_not_close_a_backtick_fence(self, tmp_path):
        _write(
            tmp_path,
            BRIEF,
            "# Brief\n\n```\n~~~\n" + _entry("PAT-999", 1) + "```\n" + _entry("PAT-002", 1),
        )
        assert set(pattern_round.brief_entries(str(tmp_path))) == {"PAT-002"}

    def test_a_missing_brief_is_zero_entries_not_an_error(self, tmp_path):
        assert pattern_round.brief_entries(str(tmp_path)) == {}

    def test_a_heading_without_a_run_tag_is_not_an_entry(self, tmp_path):
        """The tag is what separates this run's work from an inherited brief."""
        _write(tmp_path, BRIEF, "# Brief\n\n## PAT-001: A name\n**What to look for:** x\n")
        assert pattern_round.brief_entries(str(tmp_path)) == {}


# ── deriving the yield ───────────────────────────────────────────────────────


class _FakeLedger:
    """Answer `pattern_round`'s two queries without a ledger on disk.

    Restricted events cannot be written by the test process, so seeding prior
    rounds through the real binary is not available. The derivation is the
    thing under test here; the channel is covered end-to-end below.
    """

    def __init__(self, run: str | None, reported: list[str]):
        self.run = run
        self.reported = reported

    def __call__(self, binary, config_dir, cwd, sql):
        if "SELECT run" in sql:
            return ([] if self.run is None else [{"run": self.run}]), ""
        return [{"pattern_ids": ids} for ids in self.reported], ""


@pytest.fixture
def fake_ledger(monkeypatch):
    def install(run="1", reported=()):
        monkeypatch.setattr(
            pattern_round, "sahjhan_target", lambda cwd: ("sah", CONFIG_DIR, "")
        )
        monkeypatch.setattr(
            pattern_round, "query_ledger", _FakeLedger(run, list(reported))
        )
    return install


class TestRoundYield:

    def test_counts_only_this_run(self, tmp_path, fake_ledger):
        """A brief inherited from prior audits is not round one's yield.

        Without the run tag the first round of every run on a mature project
        would report the whole twenty-entry brief as its own discovery.
        """
        fake_ledger(run="2")
        _write(tmp_path, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1) + _entry("PAT-002", 2))
        result, problem = pattern_round.round_yield(str(tmp_path))
        assert problem == ""
        assert result.new_ids == ["PAT-002"]
        assert result.run == "2"

    def test_subtracts_what_an_earlier_round_reported(self, tmp_path, fake_ledger):
        """The baseline is the ledger, so a standing entry counts once."""
        fake_ledger(run="1", reported=["PAT-001,PAT-002"])
        _write(
            tmp_path, BRIEF,
            "# Brief\n\n" + _entry("PAT-001", 1) + _entry("PAT-002", 1) + _entry("PAT-003", 1),
        )
        result, _ = pattern_round.round_yield(str(tmp_path))
        assert result.new_ids == ["PAT-003"]

    def test_a_round_that_wrote_nothing_yields_zero(self, tmp_path, fake_ledger):
        """The rounds this exists for: the brief says none were added."""
        fake_ledger(run="1", reported=["PAT-001"])
        _write(tmp_path, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1))
        result, _ = pattern_round.round_yield(str(tmp_path))
        assert result.new_ids == []

    def test_ids_are_sorted(self, tmp_path, fake_ledger):
        fake_ledger(run="1")
        _write(
            tmp_path, BRIEF,
            "# Brief\n\n" + _entry("PAT-012", 1) + _entry("PAT-003", 1),
        )
        result, _ = pattern_round.round_yield(str(tmp_path))
        assert result.new_ids == ["PAT-003", "PAT-012"]

    def test_a_ledger_naming_no_run_is_a_problem_not_a_zero(self, tmp_path, fake_ledger):
        """Fail closed: a silent zero would look like a dry round."""
        fake_ledger(run=None)
        _write(tmp_path, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1))
        result, problem = pattern_round.round_yield(str(tmp_path))
        assert result is None
        assert "run" in problem


# ── which commands are this channel at all ───────────────────────────────────


class TestCommandRecognition:
    """The recognizer lives beside the command it recognizes, and is shared.

    If `phase-fix-loop.md` taught one invocation and the courier accepted a
    different one, the failure would be silent: the round runs, nothing is
    recorded, and `iteration_boundary` blocks later with nothing pointing here.
    """

    @pytest.mark.parametrize("command", [
        PLUGIN_COMMAND,
        "python3 /abs/path/enforcement/scripts/pattern_round.py --record --siblings-found 0",
        "python3 $CLAUDE_PLUGIN_ROOT/enforcement/scripts/pattern_round.py --siblings-found 7 --record",
    ])
    def test_accepts_the_prescribed_invocations(self, command):
        assert pattern_round.siblings_of(command) is not None

    def test_the_skill_file_command_is_one_of_them(self):
        """Read the taught command out of the doc rather than trusting a copy."""
        doc = os.path.join(REPO_ROOT, "skills", "holtz", "references", "phase-fix-loop.md")
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        taught = [
            line.strip()
            for line in text.splitlines()
            if "pattern_round.py" in line and "--record" in line
        ]
        assert taught, "phase-fix-loop.md no longer teaches a --record command"
        for command in taught:
            # `M` is the doc's placeholder for the count the agent supplies.
            assert pattern_round.siblings_of(command.replace(" M", " 3")) is not None, \
                f"the courier would not recognize a taught command: {command!r}"

    @pytest.mark.parametrize("command", [
        "python3 /x/enforcement/scripts/pattern_round.py --show",       # the read side
        "python3 /elsewhere/pattern_round.py --record --siblings-found 1",  # wrong tree
        "python3 /x/enforcement/scripts/pattern_round.py --record --siblings-found many",
        "python3 /x/enforcement/scripts/pattern_round.py --record --patterns-found 5",
        "echo hi",
        "",
    ])
    def test_rejects_everything_else(self, command):
        assert pattern_round.siblings_of(command) is None

    def test_rejects_a_redirected_cwd(self, tmp_path):
        """`--cwd` would attach another project's brief to this ledger."""
        assert pattern_round.siblings_of(
            f"python3 /x/enforcement/scripts/pattern_round.py --record "
            f"--siblings-found 1 --cwd {tmp_path}"
        ) is None


# ── the channel, end to end ──────────────────────────────────────────────────


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def project(tmp_path):
    """A git repo with a real ledger carrying one run-bearing event."""
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        cwd=root, capture_output=True, text=True, timeout=60, check=True,
    )
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding",
         "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
         "--field", "phase=fix_loop", "--field", "step=10", "--field", "id=BH-001",
         "--field", "severity=HIGH", "--field", "category=bug",
         "--field", "location=a.py:1", "--field", "description=x",
         "--field", "perspective=component", "--field", "predicted_by=none"],
        cwd=root, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return root


def _marker(**payload) -> str:
    return f"{pattern_round.RECORD_MARKER} {json.dumps(payload, sort_keys=True)}"


def _event(root, command=PLUGIN_COMMAND, output=None, exit_code=None):
    response: dict = {
        "output": output if output is not None else _marker(siblings_found="4")
    }
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
        if req.get("event_type") == "pattern_analysis_complete":
            return req.get("fields", {})
    return None


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestProvenance:

    def test_the_count_comes_from_the_brief(self, project, mock_daemon):
        _write(project, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1) + _entry("PAT-002", 1))
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project), cwd=project,
        )
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields is not None, "a closed round must record"
        assert fields["patterns_found"] == "2"
        assert fields["pattern_ids"] == "PAT-001,PAT-002"
        assert fields["run"] == "1"

    def test_a_lying_marker_cannot_move_the_count(self, project, mock_daemon):
        """The marker forges the very fields the derivation exists to own."""
        _write(project, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1))
        lying = _marker(siblings_found="4", patterns_found="99", pattern_ids="PAT-042")
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project, output=lying), cwd=project,
        )
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields["patterns_found"] == "1"
        assert fields["pattern_ids"] == "PAT-001"

    def test_a_dry_round_records_zero_and_no_ids(self, project, mock_daemon):
        """The case the whole item is for: nothing written, nothing claimed."""
        _write(project, BRIEF, "# Brief\n\nNo entries yet.\n")
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project), cwd=project,
        )
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields["patterns_found"] == "0"
        assert "pattern_ids" not in fields

    def test_siblings_come_from_the_marker(self, project, mock_daemon):
        """How many siblings a round filed is a fact only the round has."""
        _write(project, BRIEF, "# Brief\n\n" + _entry("PAT-001", 1))
        run_enforcement_hook("pattern_courier.py", _event(project), cwd=project)
        assert _recorded(mock_daemon)["siblings_found"] == "4"


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestBothSignalsRequired:

    def test_a_nonzero_exit_records_nothing(self, project, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project, exit_code=1), cwd=project,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_a_missing_marker_records_nothing_and_says_so(self, project, mock_daemon):
        code, output, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project, output="done"), cwd=project,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "NOT recorded" in context

    @pytest.mark.parametrize("command", [
        f"{PLUGIN_COMMAND} && git commit -m x",
        f"echo 'PATTERN-ROUND: {{}}' ; {PLUGIN_COMMAND}",
    ])
    def test_multi_segment_lines_record_nothing(self, project, mock_daemon, command):
        """One Bash line whose success becomes evidence must not carry cargo."""
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(project, command=command), cwd=project,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestOtherToolsAreUntouched:

    def test_non_bash_events_pass_through(self, tmp_path, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py",
            {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}, "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_an_ordinary_bash_command_records_nothing(self, tmp_path, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "pattern_courier.py", _event(tmp_path, command="pytest -q"), cwd=str(tmp_path),
        )
        assert code == 0
        assert _recorded(mock_daemon) is None


# ── the yield stop, against a real daemon ────────────────────────────────────


@pytest.mark.slow
@pytest.mark.integration
class TestTheYieldStop:
    """Two consecutive rounds that added no pattern withdraw the obligation.

    Driven through the real writer end to end, because that is the only way to
    get a restricted `pattern_analysis_complete` onto a ledger — and because a
    test that hand-wrote the events would be asserting against its own idea of
    what a round records rather than against what one does.

    The predicate comes out of `protocol.toml`, not restated here, so editing
    the config re-tests the config.
    """

    @staticmethod
    def _overdue_sql() -> str:
        import tomllib
        with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
            return tomllib.load(fh)["queries"]["pattern_analysis_overdue"]["sql"]

    @staticmethod
    def _prepare(real_daemon) -> str:
        root = real_daemon["project_root"]
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"],
             "ledger", "create", "--from", "run", "1", "--activate"],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        )
        return root

    @staticmethod
    def _sah(real_daemon, root, *args):
        result = subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"], *args],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    _COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
               "--field", "phase=fix_loop", "--field", "step=10"]

    def _resolve(self, real_daemon, root, *ids):
        for finding_id in ids:
            self._sah(real_daemon, root, "event", "finding",
                      "--field", f"id={finding_id}", "--field", "severity=HIGH",
                      "--field", "category=bug", "--field", "location=a.py:1",
                      "--field", "perspective=component", "--field", "predicted_by=none",
                      "--field", "description=x", *self._COMMON)
            self._sah(real_daemon, root, "event", "finding_resolved",
                      "--field", f"id={finding_id}", "--field", "commit_hash=abc1234",
                      *self._COMMON)

    def _round(self, real_daemon, root, pat_ids: list[str]) -> None:
        """Run a pattern round the way the skill file teaches it.

        Brief first, then `--record`, then the courier the harness fires. Only
        driving the courier would test the writer while leaving the sequence
        that produces its input unexercised.
        """
        body = "# Brief\n\n" + "".join(_entry(pat_id, 1) for pat_id in pat_ids)
        _write(root, BRIEF, body)

        script = os.path.join(SCRIPTS_DIR, "pattern_round.py")
        env = {**os.environ, "SAHJHAN_DAEMON_SOCKET": real_daemon["sock_path"]}
        command = f"python3 {script} --record --siblings-found 0"
        run = subprocess.run(
            [sys.executable, script, "--record", "--siblings-found", "0"],
            cwd=root, capture_output=True, text=True, env=env, timeout=60,
        )
        assert run.returncode == 0, f"{run.stdout}\n{run.stderr}"
        courier = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "pattern_courier.py")],
            input=json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_response": {"output": run.stdout, "exit_code": 0},
                "cwd": root,
            }),
            capture_output=True, text=True, env=env, timeout=60,
        )
        assert courier.returncode == 0, courier.stderr
        assert "NOT recorded" not in courier.stdout, courier.stdout

    def _overdue(self, real_daemon, root) -> str:
        result = self._sah(real_daemon, root, "query", self._overdue_sql(), "--format", "json")
        rows = json.loads(result.stdout)
        return str(list(rows[0].values())[0])

    def test_three_resolutions_still_owe_a_round(self, real_daemon):
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001", "BH-002", "BH-003")
        assert self._overdue(real_daemon, root) == "true"

    def test_one_dry_round_is_not_enough_to_stop(self, real_daemon):
        """The rule is two *consecutive* rounds; one is a bad day."""
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001")
        self._round(real_daemon, root, [])
        self._resolve(real_daemon, root, "BH-002", "BH-003", "BH-004")
        assert self._overdue(real_daemon, root) == "true"

    def test_two_dry_rounds_withdraw_the_obligation(self, real_daemon):
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001")
        self._round(real_daemon, root, [])
        self._round(real_daemon, root, [])
        self._resolve(real_daemon, root, "BH-002", "BH-003", "BH-004")
        assert self._overdue(real_daemon, root) == "false"

    def test_a_productive_round_re_arms_it(self, real_daemon):
        """The window is the last two rounds, so a yield puts the demand back."""
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001")
        self._round(real_daemon, root, [])
        self._round(real_daemon, root, [])
        self._round(real_daemon, root, ["PAT-001"])
        self._resolve(real_daemon, root, "BH-002", "BH-003", "BH-004")
        assert self._overdue(real_daemon, root) == "true"

    def test_two_dry_rounds_that_are_not_consecutive_do_not_stop_it(self, real_daemon):
        """The rule is a window, not a tally, and this is where they differ.

        `ORDER BY seq DESC LIMIT 2` in a derived table expresses the window
        naturally and is wrong here: the engine applies the outer WHERE before
        the LIMIT, so it counts every dry round the run ever had. That form
        passes the consecutive cases and fails only this one.
        """
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001")
        self._round(real_daemon, root, [])
        self._round(real_daemon, root, ["PAT-001"])
        self._round(real_daemon, root, ["PAT-001"])  # no new id — a dry round
        self._resolve(real_daemon, root, "BH-002", "BH-003", "BH-004")
        assert self._overdue(real_daemon, root) == "true"

    def test_a_round_resets_the_resolution_count_either_way(self, real_daemon):
        """The first conjunct is untouched: a fresh round is never overdue."""
        root = self._prepare(real_daemon)
        self._resolve(real_daemon, root, "BH-001", "BH-002", "BH-003")
        self._round(real_daemon, root, ["PAT-001"])
        assert self._overdue(real_daemon, root) == "false"


# ── the taught sequence ──────────────────────────────────────────────────────


class TestTheDocTeachesTheOrderTheDerivationNeeds:
    """The gate cannot see this, so the document's own line order is the test.

    Recording before the brief is written derives the previous round's yield
    and reports it as this one's. The old step order did exactly that: record
    at step 4, update the brief at step 5.
    """

    def test_the_brief_is_written_before_the_round_is_recorded(self):
        doc = os.path.join(REPO_ROOT, "skills", "holtz", "references", "phase-fix-loop.md")
        with open(doc, encoding="utf-8") as f:
            lines = f.read().splitlines()

        brief_step = next(
            (i for i, line in enumerate(lines)
             if "**Update `docs/holtz/patterns-brief.md`" in line), None
        )
        record_step = next(
            (i for i, line in enumerate(lines) if "pattern_round.py --record" in line), None
        )
        assert brief_step is not None, "phase-fix-loop.md no longer has a brief-update step"
        assert record_step is not None, "phase-fix-loop.md no longer records the round"
        assert brief_step < record_step, (
            "phase-fix-loop.md records the round before the brief is updated, so "
            "the derived patterns_found would describe the previous round"
        )

    def test_the_doc_names_the_state_the_pattern_check_block_sends_you_to(self):
        """`pattern_check` can now be refused because the obligation lapsed.

        Its block says to run Step 11 in `fix_loop` instead, which is only an
        escape if the doc actually offers that path.
        """
        doc = os.path.join(REPO_ROOT, "skills", "holtz", "references", "phase-fix-loop.md")
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        assert "**Stay in `fix_loop`**" in text, (
            "phase-fix-loop.md no longer offers a pattern round without "
            "pattern_check, but the transition's block message sends you there"
        )

    def test_no_skill_file_teaches_the_retired_agent_write(self):
        """`sahjhan event pattern_analysis_complete` is refused by the engine now.

        A skill file still teaching it would hand the agent a command that
        fails, at the one point in the round where failing means the round is
        never recorded.
        """
        offenders = []
        for base, _dirs, files in os.walk(os.path.join(REPO_ROOT, "skills")):
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as fh:
                    for number, line in enumerate(fh, 1):
                        if "event pattern_analysis_complete" in line:
                            offenders.append(f"{path}:{number}")
        assert not offenders, offenders

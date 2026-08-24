"""P0.1's amplification measurement.

The audited run filed **2.43 findings per fix**. Its open count rose
monotonically 124 -> 273 and fell exactly once, and `converge` requires every
finding closed — so the run was non-terminating from pattern round 1 and
nothing in the protocol measured that. This is the thing that notices:

    A = findings filed since fix_loop_start / findings resolved since it

evaluated at each pattern round, tripping when `A > 1.0` for three
*consecutive* rounds.

**The gate that consumes it is not here yet.** The clause puts the block on
`pattern_done` with `sahjhan defer batch --severity low,medium` as its escape,
and `pattern_analysis` has exactly one exit — `pattern_done` — while
`defer_low`/`defer_medium` exist only from `fix_loop`. A run blocked there
cannot reach its own escape. That is a design question for the author of the
clause, not one to settle here; the measurement lands first because it is
correct independently of where the block ends up.

Driven through the real writer end to end, because a restricted
`pattern_analysis_complete` only reaches a ledger that way, and because a test
that hand-wrote the rounds would assert against its own idea of what a round
records. Every predicate comes out of `protocol.toml` rather than being
restated, so editing the config re-tests the config.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_pattern_round import BRIEF, _entry, _write  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=fix_loop", "--field", "step=10"]


def _named_query(name: str) -> str:
    with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
        queries = tomllib.load(fh)["queries"]
    assert name in queries, f"protocol.toml has no [queries.{name}]"
    return queries[name]["sql"]


class _Run:
    """A ledger in the fix loop, driven the way the skill files drive one."""

    def __init__(self, real_daemon):
        self.d = real_daemon
        self.root = real_daemon["project_root"]
        subprocess.run(["git", "init", "-q", self.root], check=True, capture_output=True)
        self.sah("ledger", "create", "--from", "run", "1", "--activate")
        self.sah("event", "state_transition", "--field", "from=merge_done",
                 "--field", "to=fix_loop", "--field", "command=fix_loop_start")
        self._pat = 0

    def sah(self, *args, check=True):
        result = subprocess.run(
            [self.d["binary"], "--config-dir", self.d["config_dir"], *args],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def file(self, finding_id, severity="HIGH"):
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", "category=bug",
                 "--field", "location=a.py:1", "--field", "perspective=component",
                 "--field", "predicted_by=none", "--field", "description=x", *_COMMON)

    def resolve(self, finding_id):
        self.sah("event", "finding_resolved", "--field", f"id={finding_id}",
                 "--field", "commit_hash=abc1234", *_COMMON)

    def round(self):
        """One pattern round, through `pattern_round.py --record` + the courier.

        Each round writes a fresh PAT entry so the yield stop never withdraws
        the obligation mid-test — that is a different clause, and a dry round
        here would confound the two.
        """
        self._pat += 1
        _write(self.root, BRIEF, "# Brief\n\n" + "".join(
            _entry(f"PAT-{n:03d}", 1) for n in range(1, self._pat + 1)))

        script = os.path.join(SCRIPTS_DIR, "pattern_round.py")
        command = f"python3 {script} --record --siblings-found 0"
        env = {**os.environ, "SAHJHAN_DAEMON_SOCKET": self.d["sock_path"]}
        record = subprocess.run(
            [sys.executable, script, "--record", "--siblings-found", "0"],
            cwd=self.root, capture_output=True, text=True, env=env, timeout=60,
        )
        assert record.returncode == 0, f"{record.stdout}\n{record.stderr}"
        courier = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "pattern_courier.py")],
            input=json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_response": {"output": record.stdout, "exit_code": 0},
                "cwd": self.root,
            }),
            capture_output=True, text=True, env=env, timeout=60,
        )
        assert courier.returncode == 0, courier.stderr
        assert "NOT recorded" not in courier.stdout, courier.stdout

    def answer(self, query_name):
        out = self.sah("query", _named_query(query_name), "--format", "json").stdout
        return str(list(json.loads(out)[0].values())[0])

    def diverging(self):
        return self.answer("amplification_diverging") == "true"

    def defer_batch(self):
        return self.sah("defer", "batch", "--severity", "low,medium", check=False)


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


class TestTheMeasurement:
    """`A > 1.0` for three consecutive rounds, and nothing weaker."""

    def test_a_diverging_run_trips_after_the_third_round(self, run):
        """Two findings filed per round, one resolved — A = 2.0 throughout."""
        for n in (1, 2):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        assert not run.diverging(), "two rounds is not three"

        run.file("BH-301")
        run.file("BH-302")
        run.resolve("BH-301")
        run.round()
        assert run.diverging(), "three diverging rounds must trip the breaker"

    def test_a_converging_run_never_trips(self, run):
        """More resolved than filed, for four rounds."""
        run.file("BH-001")
        run.file("BH-002")
        run.file("BH-003")
        for n in range(1, 4):
            run.resolve(f"BH-{n:03d}")
            run.round()
        run.round()
        assert not run.diverging()

    def test_three_rounds_are_consecutive_ones(self, run):
        """A run that diverged, recovered, and relapsed is not diverging.

        Rounds 1 and 2 amplify, round 3 clears the backlog, round 4 amplifies
        again: three diverging rounds exist, but not three in a row. Drop the
        seq floor and this reads `true` — the same shape as counting "any two
        dry rounds ever" instead of two consecutive ones.
        """
        for n in (1, 2):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        run.resolve("BH-102")
        run.resolve("BH-202")
        run.round()
        assert not run.diverging(), "the recovery round is in the window"

        run.file("BH-401")
        run.file("BH-402")
        run.round()
        assert not run.diverging(), (
            "three diverging rounds exist but the middle of the last three "
            "converged — the window is not being applied"
        )

    def test_quiet_rounds_do_not_accumulate_divergence(self, run):
        """0 filed and 0 resolved in the window leaves A undefined, not infinite.

        One balanced fix, then three rounds that touch nothing. Written as a
        division, `filed / resolved` on the quiet rounds is 1.0 at best and
        0/0 at worst; written as `filed > resolved` it is plainly false, which
        is the answer a run that is not amplifying should get.

        The balanced fix is not decoration: `pattern_round.py` derives the run
        from the ledger and refuses when no event names one.
        """
        run.file("BH-001")
        run.resolve("BH-001")
        for _ in range(4):
            run.round()
        assert not run.diverging()

    def test_amplification_is_measured_from_the_first_entry_to_the_fix_loop(self, run):
        """`fix_loop_start` is MIN(seq), not the latest re-entry.

        A lens rotation returns to `fix_loop`; taking the most recent entry
        would restart the measurement there and read a diverging run as clean.
        """
        for n in (1, 2):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        run.sah("event", "state_transition", "--field", "from=perspective_clean",
                "--field", "to=fix_loop", "--field", "command=lens_rotate")
        run.file("BH-301")
        run.file("BH-302")
        run.resolve("BH-301")
        run.round()

        assert run.diverging(), (
            "a re-entry to fix_loop reset the measurement window"
        )


class TestWhyTheGateIsNotOnPatternDoneYet:
    """The escape is unreachable from the state a `pattern_done` block holds.

    P0.1 says: gate `pattern_done`, and clear it with one
    `sahjhan defer batch --severity low,medium`. Both halves are fine on their
    own; together they wedge. `pattern_analysis` has exactly one outgoing edge,
    and `defer_low`/`defer_medium` are declared `fix_loop -> fix_loop`, so a
    run stopped at `pattern_done` cannot run the command the block names —
    #77's deadlock reached from a new direction.

    These pin the two facts a fix has to change, so the naive gate cannot be
    added back without one of them failing first.
    """

    def test_pattern_analysis_has_exactly_one_exit(self):
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        exits = [t["command"] for t in transitions if t.get("from") == "pattern_analysis"]
        assert exits == ["pattern_done"], (
            f"pattern_analysis now has other exits ({exits}) — a block on "
            f"pattern_done may no longer be a dead end, and the deadlock this "
            f"file documents may be resolvable"
        )

    def test_the_batch_cannot_run_from_pattern_analysis(self, run):
        """And it fails fatally, not per item — nothing is deferred at all."""
        run.file("BH-001", "LOW")
        run.sah("event", "state_transition", "--field", "from=fix_loop",
                "--field", "to=pattern_analysis", "--field", "command=pattern_check")

        result = run.defer_batch()
        assert result.returncode != 0, (
            f"the batch now runs from pattern_analysis:\n{result.stdout}"
        )
        assert "no transition 'defer_low' available from state 'pattern_analysis'" \
            in result.stderr, result.stderr


class TestTheTwoLowQueriesAgree:
    """`open_low_count` must count exactly the rows `open_low_findings` returns.

    The engine cannot compose named queries, so the escape's gate and the
    batch's population spell the same predicate twice. This is what stops them
    drifting: one ledger, both queries, same answer.
    """

    def test_the_count_equals_the_number_of_ids(self, run):
        run.file("BH-001", "LOW")
        run.file("BH-002", "LOW")
        run.file("BH-003", "MEDIUM")
        run.file("BH-004", "HIGH")
        run.file("BH-002", "HIGH")          # a correction out of the population
        run.file("BH-005", "LOW")
        run.resolve("BH-005")               # closed, out of the population

        ids = json.loads(
            run.sah("query", _named_query("open_low_findings"), "--format", "json").stdout
        )
        count = int(run.answer("open_low_count"))
        assert count == len(ids), (
            f"open_low_count says {count}, open_low_findings returns {ids} — "
            f"the two spellings of the LOW population have drifted"
        )
        assert count == 1, ids

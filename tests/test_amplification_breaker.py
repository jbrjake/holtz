"""P0.1's amplification measurement.

The audited run filed **2.43 findings per fix**. Its open count rose
monotonically 124 -> 273 and fell exactly once, and `converge` requires every
finding closed — so the run was non-terminating from pattern round 1 and
nothing in the protocol measured that. This is the thing that notices:

    A = findings filed since fix_loop_start / findings resolved since it

evaluated at each pattern round, tripping when `A > 1.0` for three
*consecutive* rounds.

The block lands on `pattern_done` — the edge that returns to `fix_loop` — so a
tripped breaker stops the next fix being dispatched rather than firing between
a verified fix and its own commit. Its escape is one
`sahjhan defer batch --severity low,medium`, and the escape only works because
`defer_low`/`defer_medium` are also declared from `pattern_analysis`: that
state has no other exit, so without those edges the block would be a dead end
that names a command the run cannot reach.

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


def _query_names(gates: list[dict]) -> set[str]:
    """Every named query a gate tree references, at any nesting depth.

    The breaker is an `any_of` wrapping an `all_of`, so a flat scan of the
    top-level gates finds one of its three queries and misses two — which
    would make "both seats read the same queries" pass while they disagreed
    about the escape.
    """
    names: set[str] = set()
    for gate in gates:
        if gate.get("query"):
            names.add(gate["query"])
        names |= _query_names(gate.get("gates", []))
    return names


def _named_query(name: str) -> str:
    with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
        queries = tomllib.load(fh)["queries"]
    assert name in queries, f"protocol.toml has no [queries.{name}]"
    return queries[name]["sql"]


class _Run:
    """A ledger in the fix loop, driven the way the skill files drive one."""

    def __init__(self, real_daemon, run_number: int = 1):
        """``run_number`` picks the ledger, so one daemon can hold two runs.

        V5 needs a diverging run and a converging run compared *in one test* —
        two tests each asserting one value can both pass while the predicate is
        a constant, which is the failure P0.1 actually shipped. The fixture
        yields one daemon, so the second arm gets its own ledger here rather
        than its own daemon.
        """
        self.d = real_daemon
        self.root = real_daemon["project_root"]
        subprocess.run(["git", "init", "-q", self.root], check=True, capture_output=True)
        # A real run always has a HEAD: `fix_commit` and `merge_finding` both
        # stamp `commit_hash` from `git rev-parse --short=7 HEAD`, which exits
        # non-zero on a repo with no commits and blocks the whole transition.
        for args in (["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"],
                     ["commit", "-q", "--allow-empty", "-m", "root"]):
            subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True)
        self.sah("ledger", "create", "--from", "run", str(run_number), "--activate")
        self.sah("event", "state_transition", "--field", "from=merge_done",
                 "--field", "to=fix_loop", "--field", "command=fix_loop_start")
        self._pat = 0
        # The pattern brief is a file in a shared project root, so two runs
        # writing PAT-001 over each other would have the second arm's rounds
        # read as a brief that shrank. Prefixing by ledger keeps them apart.
        self._pat_prefix = f"PAT-{run_number}"

    def sah(self, *args, check=True):
        result = subprocess.run(
            [self.d["binary"], "--config-dir", self.d["config_dir"], *args],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def file(self, finding_id, severity="HIGH", pattern_id=None,
             reachability="user_reachable", perspective="component"):
        attribution = ["--field", f"pattern_id={pattern_id}"] if pattern_id else []
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", "category=bug",
                 "--field", "location=a.py:1", "--field", f"perspective={perspective}",
                 "--field", "predicted_by=none", "--field", f"reachability={reachability}",
                 "--field", "description=x",
                 *attribution, *_COMMON)

    def defer(self, finding_id, reason="low_priority"):
        self.sah("event", "finding_deferred", "--field", f"id={finding_id}",
                 "--field", f"reason={reason}", *_COMMON)

    def resolve(self, finding_id):
        self.sah("event", "finding_resolved", "--field", f"id={finding_id}",
                 "--field", "commit_hash=abc1234", *_COMMON)

    def round(self, pat_ids=None):
        """One pattern round, through `pattern_round.py --record` + the courier.

        By default each round writes a fresh PAT entry so the yield stop never
        withdraws the obligation mid-test — that is a different clause, and a
        dry round here would confound the two. `pat_ids` overrides the brief's
        whole contents when a test needs specific ids.
        """
        if pat_ids is None:
            self._pat += 1
            pat_ids = [f"{self._pat_prefix}{n:02d}" for n in range(1, self._pat + 1)]
        _write(self.root, BRIEF, "# Brief\n\n" + "".join(
            _entry(pat_id, 1) for pat_id in pat_ids))

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

    def sweep(self, present=(), retired=()):
        """One stale sweep, through `stale_sweep.py --record` + its courier.

        Same two-process shape as `round()`, and for the same reason: the
        script runs where the daemon is unreachable and the courier writes the
        restricted event. Defaults to sweeping whatever is open, which is what
        `--show` would tell the agent.
        """
        script = os.path.join(SCRIPTS_DIR, "stale_sweep.py")
        if not present and not retired:
            present = json.loads(self.sah(
                "query",
                "SELECT DISTINCT f.id FROM events f WHERE f.type='finding' "
                "AND f.id NOT IN (SELECT r.id FROM events r WHERE r.type='finding_resolved') "
                "AND f.id NOT IN (SELECT d.id FROM events d WHERE d.type='finding_deferred')",
                "--format", "json").stdout)
            present = sorted(row["id"] for row in present)

        args = ["--record", "--present", ",".join(present)]
        if retired:
            args += ["--retired", ",".join(retired)]
        command = f"python3 {script} " + " ".join(
            a if a.startswith("--") else (a or "''") for a in args)

        env = {**os.environ, "SAHJHAN_DAEMON_SOCKET": self.d["sock_path"]}
        record = subprocess.run(
            [sys.executable, script, *args],
            cwd=self.root, capture_output=True, text=True, env=env, timeout=60,
        )
        assert record.returncode == 0, f"{record.stdout}\n{record.stderr}"
        courier = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "stale_sweep_courier.py")],
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

    def enter_pattern_analysis(self):
        self.sah("event", "state_transition", "--field", "from=fix_loop",
                 "--field", "to=pattern_analysis", "--field", "command=pattern_check")

    def merge(self, finding_id, into, check=True):
        return self.sah("transition", "merge_finding", finding_id, into, check=check)

    def gate_check(self, command="pattern_done", *args):
        """`args` are `key=value` bindings, the way the CLI takes them.

        A parameterised gate reports `unevaluable` without its argument, so a
        transition with `args` has to be checked with them bound or the read
        says nothing about the gate.
        """
        return self.sah("gate", "check", command, *args, check=False).stdout

    def blocked_on_amplification(self):
        out = self.gate_check()
        assert out.strip(), "gate check produced nothing — is the run in pattern_analysis?"
        return "✗" in out and "amplification" in out

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


class TestTheBlock:
    """A tripped breaker closes `pattern_done`, so no next fix is dispatched."""

    def _trip(self, run, lows=2, mediums=2):
        for n in (1, 2, 3):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        for n in range(1, lows + 1):
            run.file(f"BH-4{n:02d}", "LOW")
        for n in range(1, mediums + 1):
            run.file(f"BH-5{n:02d}", "MEDIUM")
        assert run.diverging()
        run.enter_pattern_analysis()

    def test_pattern_done_is_blocked_while_the_breaker_is_tripped(self, run):
        self._trip(run)
        assert run.blocked_on_amplification(), run.gate_check()

    def test_the_block_names_the_command_that_clears_it(self, run):
        """An escape the agent cannot read is a deadlock with extra steps."""
        self._trip(run)
        assert "defer batch --severity low,medium" in run.gate_check()

    def test_an_untripped_run_is_not_blocked_by_the_breaker(self, run):
        """Non-vacuity: the gate is not simply always shut."""
        run.file("BH-001")
        run.resolve("BH-001")
        run.round()
        run.enter_pattern_analysis()
        assert not run.blocked_on_amplification(), run.gate_check()


class TestTheEscapeIsReachableFromTheBlockedState:
    """`pattern_analysis` has no exit but `pattern_done`.

    So the deferral transitions have to exist from there too, or the block is a
    dead end that names a command the run cannot reach — #77 from a new
    direction. `sahjhan defer batch` does not merely refuse each item in that
    case; it exits non-zero on the first and defers nothing at all.
    """

    def test_the_deferral_transitions_exist_from_pattern_analysis(self):
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        from_pattern = {t["command"] for t in transitions
                        if t.get("from") == "pattern_analysis"}
        assert {"defer_low", "defer_medium"} <= from_pattern, (
            f"pattern_analysis can only reach {sorted(from_pattern)} — the "
            f"pattern_done block names an escape the run cannot run"
        )

    def test_the_batch_runs_from_pattern_analysis(self, run):
        run.file("BH-001", "LOW")
        run.enter_pattern_analysis()

        result = run.defer_batch()
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        assert "defer_low: 1 applied" in result.stdout, result.stdout

    def test_the_medium_cap_is_not_weaker_inside_a_round(self, run):
        """The escape must not become a way around D5's 50% rule."""
        for n in range(1, 5):
            run.file(f"BH-5{n:02d}", "MEDIUM")
        run.enter_pattern_analysis()

        result = run.defer_batch()
        assert "defer_medium: 2 applied, 2 refused" in result.stdout, result.stdout


class TestTheEscapeClearsTheBlock:
    """The named command always reaches the post-state the predicate asserts.

    This is the property the whole design turns on. Asserting the SQL alone
    proves the block; only driving the escape proves the way out.
    """

    def _trip(self, run, lows, mediums):
        for n in (1, 2, 3):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        for n in range(1, lows + 1):
            run.file(f"BH-4{n:02d}", "LOW")
        for n in range(1, mediums + 1):
            run.file(f"BH-5{n:02d}", "MEDIUM")
        run.enter_pattern_analysis()

    def test_one_batch_clears_the_amplification_block(self, run):
        self._trip(run, lows=3, mediums=4)
        assert run.blocked_on_amplification(), run.gate_check()

        result = run.defer_batch()
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

        assert not run.blocked_on_amplification(), (
            f"the named escape ran and the block did not clear:\n"
            f"{result.stdout}\n{run.gate_check()}"
        )
        assert run.diverging(), (
            "the escape must clear the block without erasing the measurement — "
            "the amplification happened and is still true"
        )

    def test_it_clears_even_though_mediums_remain_open(self, run):
        """Why the predicate says "budget spent" and not "no open MEDIUM".

        Eight MEDIUMs, four deferrable. Phrased as an empty set this would
        still be blocked with no command left to run.
        """
        self._trip(run, lows=0, mediums=8)
        assert run.blocked_on_amplification()

        run.defer_batch()
        assert not run.blocked_on_amplification(), run.gate_check()

        still_open = json.loads(run.sah(
            "query", _named_query("open_medium_findings"), "--format", "json").stdout)
        assert len(still_open) == 4, (
            f"the cap did not hold — expected half the MEDIUMs still open, "
            f"got {still_open}"
        )

    def test_a_low_filed_after_the_escape_blocks_again(self, run):
        """The gate reads the ledger at check time, not a latched flag."""
        self._trip(run, lows=1, mediums=0)
        run.defer_batch()
        assert not run.blocked_on_amplification()

        run.file("BH-402", "LOW")
        assert run.blocked_on_amplification(), (
            "a LOW filed after the batch left the block open"
        )


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


# ── W14 / items 5 + 10 ──────────────────────────────────────────────────────


class TestTheBreakerSitsOnTheTaughtPath:
    """Item 5 — `pattern_done` is the rare path; `iteration_boundary` is not.

    P0.1's block lands on `pattern_done`, reachable only from
    `pattern_analysis`. But `phase-fix-loop.md:101` teaches staying in
    `fix_loop` as the *usual* course and entering `pattern_analysis` only when
    `iteration_boundary` blocks. On the usual path `pattern_done` never runs,
    so the breaker never evaluates and the batch deferral it prescribes is
    never triggered — and `pattern_done`'s escape is the only place deferral is
    taught. The round cap was given a second seat for exactly this reason; the
    breaker was not. RULED (Jon, 2026-08-26): it gets one too.
    """

    def _diverge_without_entering_pattern_analysis(self, run):
        """Three diverging rounds on the taught path — `fix_loop` throughout.

        `round()` records through `pattern_round.py`, which is Step 11's
        in-loop form; nothing here calls `enter_pattern_analysis`. A test that
        entered it would reproduce the old passing state.
        """
        for n in (1, 2, 3):
            run.file(f"BH-{n}01")
            run.file(f"BH-{n}02")
            run.resolve(f"BH-{n}01")
            run.round()
        run.file("BH-401", "LOW")
        run.file("BH-501", "MEDIUM")
        run.file("BH-502", "MEDIUM")
        assert run.diverging(), "the fixture must actually diverge"

    def test_the_boundary_blocks_on_the_taught_path(self, run):
        self._diverge_without_entering_pattern_analysis(run)
        out = run.gate_check("iteration_boundary")
        assert "amplification" in out and "✗" in out, (
            f"a diverging run reached the boundary unblocked:\n{out}"
        )

    def test_the_boundary_names_the_command_that_clears_it(self, run):
        self._diverge_without_entering_pattern_analysis(run)
        assert "defer batch --severity low,medium" in run.gate_check("iteration_boundary")

    def test_a_converging_run_is_not_blocked_at_the_boundary(self, run):
        """Non-vacuity: the new seat is not simply always shut."""
        run.file("BH-001")
        run.resolve("BH-001")
        run.round()
        out = run.gate_check("iteration_boundary")
        assert not ("amplification" in out and "✗" in out), out

    def test_both_seats_read_the_same_named_queries(self):
        """One predicate, two consumers — the arrangement the round cap has.

        Asserted on the config rather than on behaviour, because drift is what
        this guards: two seats spelling the same rule differently is how #77
        deadlocked, and behaviour tests only catch it once they disagree.
        """
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]

        def breaker_queries(command):
            for t in transitions:
                if t.get("command") != command:
                    continue
                for gate in t.get("gates", []):
                    if gate.get("type") != "any_of":
                        continue
                    if "amplification" not in gate.get("intent", ""):
                        continue
                    return _query_names(gate["gates"])
            return set()

        assert breaker_queries("pattern_done") == breaker_queries("iteration_boundary")
        assert breaker_queries("pattern_done") == {
            "amplification_diverging", "open_low_count", "medium_deferral_budget",
        }


class TestADeferralRetiresAFinding:
    """Item 10 — the two converge conjuncts pulled against each other.

    `converge` requires `amplification_diverging` false and names no escape.
    The breaker's prescribed escape is `defer batch`, and deferrals were not
    counted on the resolved side — so the one command the protocol teaches for
    a diverging run moved the `pattern_done` block and left the `converge`
    conjunct reading the same predicate exactly as it was.
    """

    def test_a_round_whose_findings_were_all_deferred_is_not_divergence(self, run):
        """V3 — filed, deferred, board empty.

        **Four findings across three rounds**, deliberately: with one per round
        the finding count and the round count coincide, and a predicate reading
        the wrong dimension would give the right answer by accident. The second
        round files two.
        """
        filings = [("BH-101",), ("BH-201", "BH-202"), ("BH-301",)]
        for ids in filings:
            for finding_id in ids:
                run.file(finding_id, "LOW")
                run.defer(finding_id)
            run.round()
        assert sum(len(ids) for ids in filings) == 4
        assert len(filings) == 3
        assert not run.diverging(), (
            "every finding filed in these rounds was retired by a deferral, "
            "and the board is empty — that is not amplification"
        )

    def test_a_round_with_neither_resolution_nor_deferral_still_diverges(self, run):
        """The direction the change must not break: unretired filing is still
        divergence. Green before this unit, and under its mutation."""
        for n in (1, 2, 3):
            run.file(f"BH-{n}01", "LOW")
            run.round()
        assert run.diverging()

    def test_the_converge_seat_names_a_command(self):
        """Item 11 — a block with no escape printed is a dead end."""
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        gate = next(
            g for t in transitions if t.get("command") == "converge"
            for g in t.get("gates", [])
            if g.get("query") == "amplification_diverging"
        )
        assert "`" in gate.get("intent", ""), (
            f"converge's amplification gate names no command: {gate.get('intent')!r}"
        )


class TestOneEscapeTwoSitesOneOutcome:
    """V4 — `defer batch` has to move the `converge` conjunct too.

    It does, but **not by acting on the rounds already recorded**, and that
    distinction is the whole of item 10's second half. The join is
    `f.seq <= r.seq`, so each round counts only what had happened by then: a
    deferral made after the last round moves no round's window and cannot
    retroactively un-diverge it. What the escape buys is the *next* round —
    whose window does include the deferrals — and the outer filter is a
    sliding window over the last three rounds, so one clean round drops the
    count below 3 and `converge` opens.

    Asserted in both halves, because "the escape works" and "the escape works
    immediately" are different claims and only the second one is false.
    """

    def _trip(self, run):
        for n in (1, 2, 3):
            run.file(f"BH-{n}01", "LOW")
            run.file(f"BH-{n}02", "LOW")
            run.round()
        assert run.diverging()

    def test_the_batch_alone_does_not_move_the_converge_conjunct(self, run):
        """The honest half. Recorded so nobody reads V4 as more than it is."""
        self._trip(run)
        result = run.defer_batch()
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        assert run.diverging(), (
            "a deferral after the last round cannot change what that round "
            "counted — if this ever passes, the window has been changed and "
            "the measurement no longer means what its comment says"
        )

    def test_the_batch_plus_the_round_it_buys_clears_converge(self, run):
        """And the half that makes the escape real."""
        self._trip(run)
        run.defer_batch()
        run.round()
        assert not run.diverging(), (
            "the round after the batch counts the deferrals as retirements, "
            "and a sliding window of three rounds needs all three diverging"
        )

    def test_the_same_escape_clears_both_blocks(self, run):
        """One command, two block sites, one outcome."""
        self._trip(run)
        run.defer_batch()
        run.round()
        for command in ("iteration_boundary", "pattern_done"):
            out = run.gate_check(command) if command == "iteration_boundary" else None
            if out is None:
                run.enter_pattern_analysis()
                out = run.gate_check("pattern_done")
            assert not ("amplification" in out and "✗" in out), (
                f"{command} still blocks on amplification after the escape:\n{out}"
            )


class TestTheBreakerMeasuresWhatItsTitleSays:
    """V5 — the guard against P0.1's own history.

    P0.1 shipped once as a detector whose condition was true at fix-loop entry
    on *every* run: a converging run and a diverging run read identically, so
    it carried zero information about the thing it was named for. This asserts
    the two runs read **differently**, which is the one claim that failure
    would have falsified.
    """

    @staticmethod
    def _diverging(run, prefix):
        """Files two per round, retires none. A = infinite."""
        for n in (1, 2, 3):
            run.file(f"{prefix}-{n}01", "LOW")
            run.file(f"{prefix}-{n}02", "LOW")
            run.round()

    @staticmethod
    def _converging(run, prefix):
        """Files two per round and retires both — one fixed, one deferred.

        Deliberately not "files nothing": a run that files nothing is trivially
        not diverging, and a detector that only distinguished activity from
        silence would pass a weaker version of this test. Both retirement
        spellings appear so the arm exercises the denominator item 10 widened.
        """
        for n in (1, 2, 3):
            run.file(f"{prefix}-{n}01", "LOW")
            run.file(f"{prefix}-{n}02", "LOW")
            run.resolve(f"{prefix}-{n}01")
            run.defer(f"{prefix}-{n}02")
            run.round()

    def test_a_converging_run_and_a_diverging_run_read_differently(self, real_daemon):
        """Both drives in one test, so the comparison is the assertion.

        Two separate tests each asserting one value can both pass while the
        predicate is a constant — the failure mode P0.1 actually shipped. Only
        requiring the answers to *differ* rules that out.
        """
        # `BH` and `BJ` rather than two free-form prefixes: `events.toml`
        # constrains a finding id to `^B[HJ]-\d{3}$`, so those are the only two
        # available. They land in separate ledgers, so reuse would be safe —
        # distinct ids just make a failure readable.
        diverging_run = _Run(real_daemon, run_number=1)
        self._diverging(diverging_run, "BH")
        diverged = diverging_run.diverging()

        converging_run = _Run(real_daemon, run_number=2)
        self._converging(converging_run, "BJ")
        converged = converging_run.diverging()

        assert diverged != converged, (
            "the breaker gives the same answer for a run that files twice what "
            "it retires and a run that retires everything it files — it "
            "carries no information about amplification"
        )
        assert diverged is True
        assert converged is False

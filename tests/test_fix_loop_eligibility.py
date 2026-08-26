"""P0.5's first route (D29/D34): only `user_reachable` findings are fix-loop
eligible.

The audited run spent ~22 of its 62 commits on defects reachable only by making
some other call raise, and gave BH-258 a full fix cycle after its own text
conceded reachability "is uncertain… needs a reachability probe before any fix"
— while 51 of its 75 open HIGHs sat untouched from before the first commit.
`fix_commit` is the only place the engine can see fix-loop eligibility:
`fix_start` is an event, and D30 established that the engine does not gate
events.

**A gate is only as good as its escape, and this one needed two built first.**
Every CRITICAL must carry a `finding_resolved` before `converge`
(`all_critical_resolved`, no reachability filter), so refusing `fix_commit`
must leave every reachability grade a live route to convergence:

| grade | route |
|---|---|
| `user_reachable` | the ordinary fix cycle — the gate lets it through |
| `fault_injected` | Step 15's hardening batch writes `finding_resolved` |
| `theoretical` | the auto-deferral converges (Jon, 2026-08-25) |

The third row is a change to D4's first conjunct and was ruled after this was
measured, not assumed: driven against a real daemon, a `theoretical` CRITICAL
is auto-deferred at filing, `all_critical_resolved` refused that deferral,
`merge_finding` refused an already-closed finding, and the hardening batch's
population is `fault_injected` **and open** — so re-grading was the only exit
left, which D34 itself calls a forgery. `theoretical` is not an agent's
discretionary priority call; it is a statement that no path was found, and a
courier writes it.

`TestEveryCriticalHasARoute` is the file's centre of gravity. It enumerates the
grades rather than testing the gate in isolation, because a gate whose escape
is missing for one grade is #77 at the end of the run.
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
SCRIPTS_DIR = os.path.join(REPO_ROOT, "skills", "holtz", "scripts")
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_hardening_batch import _Board  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]

ELIGIBILITY_QUERY = "item_is_user_reachable"


def _named_query(name, item_id=None):
    from _protocol_cache import named_query_sql  # noqa: PLC0415

    sql = named_query_sql(CONFIG_DIR, name)
    assert sql, f"protocol.toml has no [queries.{name}]"
    return sql.replace("{{item_id}}", item_id) if item_id else sql


def _transitions():
    try:
        import tomllib  # noqa: PLC0415
    except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
        import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
    with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
        return tomllib.load(fh)["transitions"]


def _gates(command):
    return next(t for t in _transitions() if t["command"] == command)["gates"]


@pytest.fixture
def board(tmp_path):
    return _Board(str(tmp_path))


@pytest.fixture
def live(real_daemon):
    return _Board(
        real_daemon["project_root"],
        config_dir=real_daemon["config_dir"],
        env={**os.environ, "SAHJHAN_DAEMON_SOCKET": real_daemon["sock_path"]},
    )


# ── The gate itself ──────────────────────────────────────────────────────────


class TestTheEligibilityPredicate:
    """`item_is_low`'s shape, one field over — and the max-seq clause carries
    the same weight: a probe that establishes a path must make the finding
    workable, and a re-grade the other way must stop it."""

    def _answer(self, board, finding_id):
        sql = _named_query(ELIGIBILITY_QUERY, finding_id)
        out = board.sah("query", sql, "--format", "json").stdout
        return str(list(json.loads(out)[0].values())[0])

    def test_a_user_reachable_finding_is_eligible(self, board):
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        assert self._answer(board, "BH-001") == "true"

    def test_a_fault_injected_finding_is_not(self, board):
        board.file("BH-001", "a.py:1", reachability="fault_injected")
        assert self._answer(board, "BH-001") == "false"

    def test_a_theoretical_finding_is_not(self, board):
        board.file("BH-001", "a.py:1", reachability="theoretical")
        assert self._answer(board, "BH-001") == "false"

    def test_a_finding_that_does_not_exist_is_not(self, board):
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        assert self._answer(board, "BH-002") == "false"

    def test_a_probe_that_establishes_a_path_makes_it_eligible(self, board):
        """The legitimate way off `theoretical`: reachability is the latest
        filing (D25), so a probe that finds a path re-files and the finding
        becomes workable."""
        board.file("BH-001", "a.py:1", reachability="theoretical")
        assert self._answer(board, "BH-001") == "false"
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        assert self._answer(board, "BH-001") == "true"

    def test_a_regrade_off_user_reachable_removes_eligibility(self, board):
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        board.file("BH-001", "a.py:1", reachability="fault_injected")
        assert self._answer(board, "BH-001") == "false"

    def test_fix_commit_carries_the_gate(self):
        assert any(gate.get("query") == ELIGIBILITY_QUERY
                   for gate in _gates("fix_commit"))

    def test_fix_commit_does_not_gate_on_openness(self):
        """Kept from the theoretical-deferral work, and still load-bearing:
        `fix_commit` is the route a re-graded finding takes back onto the
        board, and an openness gate would refuse one that had already been
        auto-deferred."""
        for gate in _gates("fix_commit"):
            assert gate.get("query") != "item_open"


# ── Every CRITICAL must still have a route to convergence ────────────────────


class TestEveryCriticalHasARoute:
    """The escape, enumerated rather than argued.

    `all_critical_resolved` has no reachability filter and gates `converge`, so
    if any grade of CRITICAL loses its route the run can neither converge nor
    make itself converge — #77's shape at the end of the run.
    """

    def _critical(self, board, name):
        sql = _named_query("all_critical_resolved")
        out = board.sah("query", sql, "--format", "json").stdout
        return str(list(json.loads(out)[0].values())[0]) if name else out

    def _all_critical_resolved(self, board):
        sql = _named_query("all_critical_resolved")
        out = board.sah("query", sql, "--format", "json").stdout
        return str(list(json.loads(out)[0].values())[0])

    def test_a_user_reachable_critical_is_fixable(self, board):
        """Route 1: the gate lets it through, so the ordinary cycle applies."""
        board.file("BH-001", "a.py:1", severity="CRITICAL",
                   reachability="user_reachable")
        sql = _named_query(ELIGIBILITY_QUERY, "BH-001")
        out = board.sah("query", sql, "--format", "json").stdout
        assert str(list(json.loads(out)[0].values())[0]) == "true"
        assert self._all_critical_resolved(board) == "false"
        board.resolve("BH-001")
        assert self._all_critical_resolved(board) == "true"

    def test_a_fault_injected_critical_is_closed_by_the_batch(self, live):
        """Route 2, driven end to end against the real transitions. This is
        the escape D34 named, and it had to be built before the gate."""
        live.file("BH-001", "tqdm/std.py:736", severity="CRITICAL")
        assert self._all_critical_resolved(live) == "false"
        live.batch("tqdm", ["tqdm/std.py"])
        assert self._all_critical_resolved(live) == "true"

    def test_a_theoretical_critical_converges_on_its_deferral(self, board):
        """Route 3, and the one D34's ruling did not cover. A `theoretical`
        deferral is machine-written and says no path was found; it is not the
        discretionary act `all_critical_resolved` refuses."""
        board.file("BH-001", "a.py:1", severity="CRITICAL",
                   reachability="theoretical")
        assert self._all_critical_resolved(board) == "false"
        board.defer("BH-001", reason="theoretical")
        assert self._all_critical_resolved(board) == "true"

    def test_an_ordinary_deferral_still_does_not_converge(self, board):
        """The counterweight, and it must not be an empty set: the exclusion
        is scoped to one reason word. `low_priority`, `medium_budget` and
        `cant_reproduce` still refuse to close a CRITICAL, which is what D4's
        conjunct is for."""
        for index, reason in enumerate(
                ("low_priority", "medium_budget", "cant_reproduce"), start=1):
            finding = f"BH-{index:03d}"
            board.file(finding, "a.py:1", severity="CRITICAL",
                       reachability="user_reachable")
            board.defer(finding, reason=reason)
            assert self._all_critical_resolved(board) == "false", (
                f"a CRITICAL deferred {reason} satisfied the conjunct that "
                "says resolved"
            )
            board.resolve(finding)
        assert self._all_critical_resolved(board) == "true"

    def test_a_theoretical_deferral_does_not_excuse_a_user_reachable_high(self, board):
        """The exclusion is on one conjunct only. `all_user_reachable_high_closed`
        already accepts any deferral, so nothing there moves — but a HIGH
        re-graded onto `user_reachable` after a theoretical deferral must still
        be visible as closed, not resurrected."""
        board.file("BH-001", "a.py:1", reachability="theoretical")
        board.defer("BH-001", reason="theoretical")
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        sql = _named_query("all_user_reachable_high_closed")
        out = board.sah("query", sql, "--format", "json").stdout
        assert str(list(json.loads(out)[0].values())[0]) == "true"


# ── The worklist has to show what is workable ────────────────────────────────


class TestTheWorklistRoutes:
    """A gate the agent only meets at `fix_commit` costs it a whole cycle. The
    worklist read is where the routing has to be visible."""

    def _list(self, board, *args):
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "findings.py"), "list", *args],
            capture_output=True, text=True, timeout=60, cwd=board.root,
            env=board.env,
        )
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        return result.stdout

    def test_it_filters_to_the_eligible_population(self, board):
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        board.file("BH-002", "a.py:2", reachability="fault_injected")
        board.file("BH-003", "a.py:3", reachability="theoretical")
        out = self._list(board, "--reachability", "user_reachable")
        assert "BH-001" in out
        assert "BH-002" not in out
        assert "BH-003" not in out

    def test_the_unfiltered_list_still_shows_everything(self, board):
        """Non-vacuity: the filter is a filter, not a broken query."""
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        board.file("BH-002", "a.py:2", reachability="fault_injected")
        out = self._list(board)
        assert "BH-001" in out and "BH-002" in out

    def test_the_latest_filing_decides(self, board):
        board.file("BH-001", "a.py:1", reachability="fault_injected")
        board.file("BH-001", "a.py:1", reachability="user_reachable")
        assert "BH-001" in self._list(board, "--reachability", "user_reachable")

    def test_the_fix_loop_teaches_the_filtered_read(self):
        path = os.path.join(REPO_ROOT, "skills", "holtz", "references",
                            "phase-fix-loop.md")
        with open(path, encoding="utf-8") as fh:
            assert "--reachability user_reachable" in fh.read()

"""P0.5's third route (D29): a `theoretical` finding comes off the board itself.

`theoretical` is its own confession — no path found, reachability itself
unestablished. BH-258 conceded in its own text that reachability "is
uncertain… needs a reachability probe before any fix" and got a full fix cycle
anyway, while 51 of the run's 75 open HIGHs were never worked at all.

D29 chose a **courier** over teaching the openness predicates to skip
`theoretical`, so there stays exactly one definition of closed and `DEFERRED.md`
needs no second rule — the same reasoning that chose the courier in D8. The
courier writes a real `finding_deferred`, so every counter, render and gate that
already reads deferral sees it without being told anything new.

The tests are organised around what would make an auto-deferral wrong:

* **The latest filing decides** (D25). A finding re-graded `theoretical` →
  `user_reachable` must stop being swept; one re-graded the other way must
  start. Matching any row ever filed under the id is the defect `fe2ef56` fixed
  one field over.
* **The courier re-derives.** The population comes from the ledger, not from
  the command text — so a finding filed by `merge_punchlists.py`, whose inner
  `sahjhan event finding` no hook ever sees, is swept too.
* **It is idempotent.** A second filing must not spend a second deferral: the
  MEDIUM budget counts deferral rows, and a doubled row would spend a cap that
  exists to stop exactly that.
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
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import theoretical_courier as tc  # noqa: E402

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=audit", "--field", "step=8"]

_FILE_CMD = (
    'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event finding '
    "--field id=BH-001 --field severity=HIGH --field category=bug/logic "
    "--field location=a.py:1 --field perspective=component "
    "--field predicted_by=none --field reachability=theoretical --field description=x"
)


def _binary():
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


# ── What wakes the courier ───────────────────────────────────────────────────


class TestTrigger:
    """A loose trigger is safe here — the ledger is what decides the
    population — but a trigger that misses a filing path leaves the board
    carrying findings the clause says are off it."""

    def test_a_finding_filing_wakes_it(self):
        assert tc.files_a_finding(_FILE_CMD)

    def test_the_merge_script_wakes_it(self):
        """Its inner `sahjhan event finding` runs in a subprocess no hook sees,
        so the outer command is the only signal there is."""
        assert tc.files_a_finding(
            'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/merge_punchlists.py" '
            "--justine docs/holtz/justine/PUNCHLIST.md"
        )

    def test_a_filing_in_a_chain_wakes_it(self):
        assert tc.files_a_finding(f"cd /tmp && {_FILE_CMD}")

    def test_another_event_does_not(self):
        assert not tc.files_a_finding(
            'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event fix_start '
            "--field id=BH-001"
        )

    def test_a_status_read_does_not(self):
        assert not tc.files_a_finding("sahjhan status 2>&1")

    def test_a_query_naming_findings_does_not(self):
        """The #77 shape: a read-only diagnostic carrying the same tokens as
        the mutating command."""
        assert not tc.files_a_finding(
            "sahjhan query \"SELECT id FROM events WHERE type='finding'\" --format json"
        )


# ── The population ───────────────────────────────────────────────────────────


class _Board:
    def __init__(self, root):
        self.binary = _binary()
        self.root = root
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        subprocess.run(
            [self.binary, "--config-dir", CONFIG_DIR, "init"],
            cwd=root, capture_output=True, text=True, timeout=60, check=True,
        )

    def sah(self, *args, check=True):
        result = subprocess.run(
            [self.binary, "--config-dir", CONFIG_DIR, *args],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def file(self, finding_id, reachability="theoretical", severity="HIGH"):
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", "category=bug/logic",
                 "--field", "location=a.py:1", "--field", "perspective=component",
                 "--field", "predicted_by=none", "--field", f"reachability={reachability}",
                 "--field", "description=x", *_COMMON)

    def resolve(self, finding_id):
        self.sah("event", "finding_resolved", "--field", f"id={finding_id}",
                 "--field", "commit_hash=abc1234", *_COMMON)

    def defer(self, finding_id, reason="low_priority"):
        self.sah("event", "finding_deferred", "--field", f"id={finding_id}",
                 "--field", f"reason={reason}", *_COMMON)

    def deferrals(self):
        result = self.sah("query", "--type", "finding_deferred", "--format", "jsonl")
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


@pytest.fixture
def board(tmp_path):
    return _Board(str(tmp_path))


def _ids(rows):
    return sorted(row["id"] for row in rows)


class TestPopulation:
    """Driven through `--show` as a subprocess, not by importing `pending`.

    Two different `_common.py` modules ship in this tree — `hooks/_common.py`
    and `enforcement/hooks/_common.py` — with the same exit helpers and a
    different `resolve_config_dir`. Whichever one some earlier test imports
    first wins for the whole pytest process, and the import still *succeeds*,
    so the courier silently resolves its config to the repo root and every
    query comes back empty. The three negatives below then pass vacuously,
    which is how the breakage hides. A subprocess gets its own `sys.path[0]`
    and cannot be poisoned by test ordering — CLAUDE.md's rule 2, earning it.
    """

    def _show(self, board):
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "theoretical_courier.py"),
             "--show", "--cwd", board.root],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        return json.loads(result.stdout)

    def test_an_open_theoretical_finding_is_pending(self, board):
        board.file("BH-001")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_a_user_reachable_finding_is_not(self, board):
        board.file("BH-001")
        board.file("BH-002", reachability="user_reachable")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_a_fault_injected_finding_is_not(self, board):
        """Its route is finalize batching, not auto-deferral."""
        board.file("BH-001")
        board.file("BH-003", reachability="fault_injected")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_a_resolved_theoretical_finding_is_not(self, board):
        board.file("BH-001")
        board.file("BH-002")
        board.resolve("BH-002")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_an_already_deferred_finding_is_not(self, board):
        """Idempotence: the budget gate counts deferral rows."""
        board.file("BH-001")
        board.file("BH-002")
        board.defer("BH-002")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_a_regrade_to_user_reachable_leaves_the_population(self, board):
        """Severity is the latest filing (D25) and so is reachability — a
        finding upgraded off `theoretical` must stop being swept."""
        board.file("BH-001", reachability="theoretical")
        board.file("BH-001", reachability="user_reachable")
        assert _ids(self._show(board)) == []

    def test_a_regrade_to_theoretical_joins_the_population(self, board):
        board.file("BH-001", reachability="user_reachable")
        board.file("BH-001", reachability="theoretical")
        assert _ids(self._show(board)) == ["BH-001"]

    def test_the_run_context_rides_the_finding(self, board):
        """Nothing the courier writes is invented: a deferral is stamped with
        the phase and step of the filing it defers, not a constant."""
        board.file("BH-001")
        row = self._show(board)[0]
        assert row["project"] == "t"
        assert row["run"] == "1"
        assert row["auditor"] == "holtz"
        assert row["phase"] == "audit"
        assert row["step"] == "8"


# ── The auto-deferral must not be a one-way door ─────────────────────────────


class TestAnAutoDeferredCriticalIsStillFixable:
    """The property that keeps auto-deferral safe, and it is not obvious.

    `all_critical_resolved` requires every CRITICAL to carry a
    `finding_resolved`, so auto-deferring a `theoretical` CRITICAL would
    deadlock convergence outright unless the deferral either converges or
    leaves the fix route open. **Both hold, and each is load-bearing on its
    own.**

    *It converges.* Per Jon's 2026-08-25 ruling the conjunct excludes a
    deferral whose reason is `theoretical` — the one reason word a courier
    writes rather than an agent choosing it, and the one that says no path was
    found rather than that the work is not worth doing. Before that exclusion,
    P0.5's fix-loop eligibility gate (D34) would have left a theoretical
    CRITICAL with no route at all: measured against a real daemon, the
    conjunct refused the deferral, `merge_finding` refused an already-closed
    finding, and the hardening batch covers `fault_injected` findings that are
    still open.

    *And the fix route stays open.* `fix_commit` has no openness gate, so a
    finding whose probe later establishes a path comes back onto the board by
    re-filing. Add `item_open` there and that return trip closes.
    """

    def _fix_commit_gates(self):
        try:
            import tomllib  # noqa: PLC0415
        except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
            import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        return next(t for t in transitions if t["command"] == "fix_commit")["gates"]

    def test_fix_commit_does_not_gate_on_openness(self):
        for gate in self._fix_commit_gates():
            assert gate.get("query") != "item_open", (
                "fix_commit gained an openness gate — an auto-deferred finding "
                "whose probe later establishes a path could no longer be fixed "
                "after re-filing, so the only route back onto the board closes"
            )

    def test_an_agent_typed_deferral_does_not_converge_a_critical(self, board):
        """The escape belongs to the courier, and to nothing else.

        Typing the deferral through the CLI is the forged path, not the route:
        the CLI write is stamped `agent:cli` and the exclusion counts only
        `hook:hooks/theoretical_courier.py`. The earned half is in
        `TestTheCourierWritesForReal`, which is where a daemon exists to
        produce that row.
        """
        from _protocol_cache import named_query_sql  # noqa: PLC0415

        board.file("BH-001", severity="CRITICAL")
        sql = named_query_sql(CONFIG_DIR, "all_critical_resolved")
        assert "false" in board.sah("query", sql, "--format", "json").stdout.lower()
        board.defer("BH-001", reason="theoretical")
        assert "false" in board.sah("query", sql, "--format", "json").stdout.lower(), (
            "an agent-typed finding_deferred closed a CRITICAL — the exclusion "
            "is not reading recorded_by"
        )

    def test_a_discretionary_deferral_does_not(self, board):
        """The exclusion is one word wide. A CRITICAL deferred `low_priority`
        still blocks — that is what the conjunct is for, and it must not be an
        empty set that a broken query could satisfy."""
        from _protocol_cache import named_query_sql  # noqa: PLC0415

        board.file("BH-001", severity="CRITICAL")
        board.defer("BH-001", reason="low_priority")
        sql = named_query_sql(CONFIG_DIR, "all_critical_resolved")
        assert "false" in board.sah("query", sql, "--format", "json").stdout.lower()


# ── The predicate lives in the config, not in Python ─────────────────────────


class TestTheQueryIsNamed:
    """H7 exists because a hook holding its own copy of a gate's SQL is how
    #77 shipped. The courier resolves the name out of `protocol.toml`."""

    def test_the_courier_carries_no_sql(self):
        with open(os.path.join(HOOKS_DIR, "theoretical_courier.py"), encoding="utf-8") as fh:
            source = fh.read()
        assert "FROM events" not in source

    def test_the_named_query_exists(self):
        from _protocol_cache import named_query_sql  # noqa: PLC0415

        sql = named_query_sql(CONFIG_DIR, tc.POPULATION_QUERY)
        assert sql and "reachability" in sql


# ── The write ────────────────────────────────────────────────────────────────


@pytest.mark.hook_e2e
class TestTheCourierRecords:

    def _event(self, root, command=_FILE_CMD, exit_code=0):
        return {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"output": "", "exit_code": exit_code},
            "cwd": str(root),
        }

    def _run(self, event):
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "theoretical_courier.py")],
            input=json.dumps(event), capture_output=True, text=True, timeout=60,
        )

    def test_a_failed_command_records_nothing(self, board):
        board.file("BH-001")
        assert self._run(self._event(board.root, exit_code=1)).returncode == 0
        assert board.deferrals() == []

    def test_an_unrelated_command_records_nothing(self, board):
        board.file("BH-001")
        assert self._run(self._event(board.root, command="ls -la")).returncode == 0
        assert board.deferrals() == []


@pytest.mark.slow
@pytest.mark.integration
class TestTheCourierWritesForReal:
    """The write half, against a daemon that actually authenticates the caller.

    `mock_daemon` reimplements the ops without hash auth, so a mock-only suite
    stays green while a stale `trusted-callers.toml` has silently disabled the
    write. Only this shape catches that.
    """

    def _sah(self, real_daemon, *args):
        return subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"], *args],
            cwd=real_daemon["project_root"], capture_output=True, text=True, timeout=60,
        )

    def _file(self, real_daemon, finding_id, reachability, severity="HIGH"):
        result = self._sah(
            real_daemon, "event", "finding", "--field", f"id={finding_id}",
            "--field", f"severity={severity}", "--field", "category=bug/logic",
            "--field", "location=a.py:1", "--field", "perspective=component",
            "--field", "predicted_by=none", "--field", f"reachability={reachability}",
            "--field", "description=x", *_COMMON)
        assert result.returncode == 0, result.stderr

    def _deferred(self, real_daemon):
        result = self._sah(real_daemon, "query", "--type", "finding_deferred",
                           "--format", "jsonl")
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        return sorted(r.get("id") or r.get("fields", {}).get("id") for r in rows)

    def _fire(self, real_daemon):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": _FILE_CMD},
            "tool_response": {"output": "", "exit_code": 0},
            "cwd": real_daemon["project_root"],
        }
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "theoretical_courier.py")],
            input=json.dumps(event), capture_output=True, text=True, timeout=60,
            cwd=real_daemon["project_root"],
        )

    def test_the_theoretical_finding_is_deferred(self, real_daemon):
        self._file(real_daemon, "BH-001", "theoretical")
        self._file(real_daemon, "BH-002", "user_reachable")
        result = self._fire(real_daemon)
        assert result.returncode == 0, result.stderr
        assert self._deferred(real_daemon) == ["BH-001"], (
            f"stdout={result.stdout} stderr={result.stderr}")

    def test_a_second_firing_spends_no_second_deferral(self, real_daemon):
        """Idempotence. `medium_deferral_budget` counts deferral rows, so a
        doubled row spends a cap that exists to stop exactly that."""
        self._file(real_daemon, "BH-001", "theoretical")
        self._fire(real_daemon)
        self._fire(real_daemon)
        assert self._deferred(real_daemon) == ["BH-001"]

    def test_the_row_it_writes_names_it_as_the_writer(self, real_daemon):
        """The mechanism the exclusion rests on, read at the row.

        `all_critical_resolved` and `lens_critical_resolved` both require this
        exact literal. It is the manifest key the daemon verified the peer
        against — the identity it checks and the identity it stamps are one
        fact — so a rename of this file, or its removal from
        `trusted-callers.toml`, silently empties both exclusions.
        """
        self._file(real_daemon, "BH-001", "theoretical")
        assert self._fire(real_daemon).returncode == 0
        rows = self._sah(
            real_daemon, "query",
            "SELECT recorded_by FROM events WHERE type='finding_deferred'",
            "--format", "json").stdout
        assert [r["recorded_by"] for r in json.loads(rows)] == [
            "hook:hooks/theoretical_courier.py"
        ]

    def test_the_deferral_it_writes_converges_a_critical(self, real_daemon):
        """The escape D34's eligibility gate rests on, driven end to end.

        A `theoretical` CRITICAL has no other route: `fix_commit` refuses the
        grade, `merge_finding` refuses an already-closed finding, and the
        hardening batch's population is `fault_injected` and open. If the
        courier's own row stops satisfying the conjunct, a run that files one
        cannot converge at all.
        """
        from _protocol_cache import named_query_sql  # noqa: PLC0415

        self._file(real_daemon, "BH-001", "theoretical", severity="CRITICAL")
        sql = named_query_sql(CONFIG_DIR, "all_critical_resolved")
        before = self._sah(real_daemon, "query", sql, "--format", "json").stdout
        assert "false" in before.lower(), before

        assert self._fire(real_daemon).returncode == 0
        after = self._sah(real_daemon, "query", sql, "--format", "json").stdout
        assert "true" in after.lower(), after


# ── Registration ─────────────────────────────────────────────────────────────


class TestRegistration:
    """A hook the harness never fires is a producer that never produces."""

    def test_it_is_in_hooks_json(self):
        with open(os.path.join(REPO_ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            assert "theoretical_courier.py" in fh.read()

    def test_it_is_in_the_trusted_caller_list(self):
        """`TRUSTED_SCRIPTS` is hand-kept — the generator will not discover a
        new courier, and the first regeneration after adding one looks
        entirely successful while its writes are silently refused."""
        with open(os.path.join(REPO_ROOT, "scripts", "hash-trusted-callers.sh"),
                  encoding="utf-8") as fh:
            assert "enforcement/hooks/theoretical_courier.py" in fh.read()

    def test_it_is_in_the_manifest(self):
        with open(os.path.join(CONFIG_DIR, "trusted-callers.toml"), encoding="utf-8") as fh:
            assert "theoretical_courier.py" in fh.read()


# ── The taught contract ──────────────────────────────────────────────────────


class TestTheDocSaysSo:

    def test_punchlist_format_states_the_routing(self):
        """A grading with a consequence the agent cannot see is a grading the
        board will not carry honestly."""
        with open(os.path.join(REPO_ROOT, "skills", "holtz", "references",
                               "punchlist-format.md"), encoding="utf-8") as fh:
            body = fh.read()
        reachability = body.split("## Reachability")[1].split("## ")[0]
        assert "defer" in reachability.lower()

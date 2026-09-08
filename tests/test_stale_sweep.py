"""P0.2's swap: `stale_sweep.py` + `stale_sweep_courier.py` (D8).

Past ~round 8 the owed round is satisfied by a stale sweep instead of pattern
analysis. Nothing recorded a sweep before this — Step 11b writes `fix_start`
and a `cant_reproduce` deferral only for the findings it *retires*, so a sweep
where everything still reproduces left no trace, and an obligation cannot be
discharged by a fact the ledger does not hold.

The question these tests are organised around is the one that decides whether
the swap is worth anything: *can a sweep be claimed without triaging the
board?* Coverage is the cost. D21 settled the population as every open finding
at every severity, so the script derives it from the ledger and the courier
derives it again — the script lives in a tree the agent can edit; the ledger
does not.

The gate half is the other risk. A conjunct that merely withdrew the obligation
past round 8 would withdraw it permanently, because the only thing that resets
the counter is a round and no round would be owed. It is spelled as one floor
over two event types so the obligation keeps cycling.
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

import stale_sweep  # noqa: E402

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

PLUGIN_COMMAND = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/stale_sweep.py" '
    "--record --present BH-001"
)

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=fix_loop", "--field", "step=10"]


# ── Command recognition ──────────────────────────────────────────────────────


class TestCommandRecognition:
    """The courier records only for a command it can identify."""

    def test_the_taught_command_is_recognised(self):
        assert stale_sweep.verdicts_of(
            'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/stale_sweep.py" '
            "--record --present BH-001,BH-002 --retired BH-004"
        ) == (["BH-001", "BH-002"], ["BH-004"])

    def test_retired_alone_is_a_sweep(self):
        """A sweep that could reproduce nothing is still a sweep."""
        assert stale_sweep.verdicts_of(
            "python3 enforcement/scripts/stale_sweep.py --record "
            "--present '' --retired BH-004"
        ) == ([], ["BH-004"])

    def test_show_is_not_a_record(self):
        assert stale_sweep.verdicts_of(
            "python3 enforcement/scripts/stale_sweep.py --show"
        ) is None

    def test_another_script_is_not_a_sweep(self):
        assert stale_sweep.verdicts_of(
            "python3 enforcement/scripts/pattern_round.py --record --siblings-found 4"
        ) is None

    def test_cwd_is_refused(self):
        """The courier derives against the event's cwd; a sweep pointed
        elsewhere would attach another project's board to this ledger."""
        assert stale_sweep.verdicts_of(
            "python3 enforcement/scripts/stale_sweep.py --record "
            "--present BH-001 --cwd /tmp/other"
        ) is None


# ── The channel, end to end ──────────────────────────────────────────────────


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


class _Board:
    """A git repo with a real ledger, and findings on it."""

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

    def file(self, finding_id, severity="HIGH"):
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", "category=bug",
                 "--field", "location=a.py:1", "--field", "perspective=component",
                 "--field", "predicted_by=none", "--field", "reachability=user_reachable",
                 "--field", "description=x", *_COMMON)

    def resolve(self, finding_id):
        self.sah("event", "finding_resolved", "--field", f"id={finding_id}",
                 "--field", "commit_hash=abc1234", *_COMMON)

    def defer_cant_reproduce(self, finding_id):
        self.sah("event", "finding_deferred", "--field", f"id={finding_id}",
                 "--field", "reason=cant_reproduce", *_COMMON)

    def enter_fix_loop(self):
        """The state a sweep runs in, so real transitions are accepted."""
        self.sah("event", "state_transition", "--field", "from=merge_done",
                 "--field", "to=fix_loop", "--field", "command=start_fix_loop",
                 "--field", "run=1", "--field", "auditor=holtz", "--field", "project=t")

    def retire(self, finding_id):
        """Retire a finding the way Step 11b does — through the transition.

        `defer_cant_reproduce` is a *transition*, so the engine writes a
        `state_transition` of its own alongside the `finding_deferred` it
        emits. `defer_cant_reproduce` above writes only the event, which is
        the shape every earlier test used and the reason a run-global
        watermark looked survivable.
        """
        investigations = os.path.join(self.root, "docs", "holtz", "investigations")
        os.makedirs(investigations, exist_ok=True)
        with open(os.path.join(investigations, f"{finding_id}.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("reproduction attempts\n")
        self.sah("event", "fix_start", "--field", f"finding_id={finding_id}",
                 "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz")
        self.sah("transition", "defer_cant_reproduce", finding_id)

    def sibling_fix_commit(self, finding_id):
        """Another actor's fix landing while this sweep is in progress.

        Both halves, as F2's `two_actors.sibling_fix_commit` records them: the
        run-global `state_transition` — the thing that used to move this
        sweep's window — and the `finding_resolved` the transition auto-emits,
        which is what legitimately takes its own finding off the board.
        """
        self.sah("event", "state_transition", "--field", "from=fix_loop",
                 "--field", "to=fix_loop", "--field", "command=fix_commit",
                 "--field", "run=1", "--field", "auditor=holtz", "--field", "project=t")
        self.resolve(finding_id)


@pytest.fixture
def board(tmp_path):
    b = _Board(str(tmp_path))
    b.file("BH-001")
    return b


def _marker(**payload) -> str:
    return f"{stale_sweep.RECORD_MARKER} {json.dumps(payload, sort_keys=True)}"


def _event(root, command=PLUGIN_COMMAND, output=None, exit_code=None):
    response: dict = {"output": output if output is not None else _marker(retired="0")}
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
        if req.get("event_type") == "stale_sweep_complete":
            return req.get("fields", {})
    return None


def _command(present, retired=None):
    tail = f" --retired {','.join(retired)}" if retired else ""
    joined = ",".join(present) or "''"
    return (
        'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/stale_sweep.py" '
        f"--record --present {joined}{tail}"
    )


class TestCoverageIsTheCost:
    """A sweep is only a sweep if it accounted for the whole board."""

    def test_the_population_is_every_open_finding(self, board):
        board.file("BH-002")
        board.file("BH-003", "LOW")
        result, problem = stale_sweep.sweep_coverage(board.root)
        assert problem == ""
        assert result.population == ["BH-001", "BH-002", "BH-003"]

    def test_a_resolved_finding_is_off_the_board(self, board):
        board.file("BH-002")
        board.resolve("BH-002")
        result, _ = stale_sweep.sweep_coverage(board.root)
        assert result.population == ["BH-001"]

    def test_this_sweep_s_own_retirements_are_still_its_work(self, board):
        """A `cant_reproduce` deferral recorded during the sweep leaves the
        open set — counting only what is open now would fail the sweep for the
        findings it successfully retired."""
        board.file("BH-002")
        board.defer_cant_reproduce("BH-002")
        result, _ = stale_sweep.sweep_coverage(board.root)
        assert result.population == ["BH-001", "BH-002"]

    def test_a_missing_verdict_is_refused(self, board):
        board.file("BH-002")
        result, problem = stale_sweep.check(board.root, ["BH-001"], [])
        assert result is None
        assert "BH-002" in problem and "no verdict" in problem

    def test_an_invented_verdict_is_refused(self, board):
        result, problem = stale_sweep.check(board.root, ["BH-001", "BH-777"], [])
        assert result is None
        assert "BH-777" in problem

    def test_a_finding_cannot_be_both(self, board):
        result, problem = stale_sweep.check(board.root, ["BH-001"], ["BH-001"])
        assert result is None
        assert "both present and retired" in problem

    def test_exact_coverage_passes(self, board):
        board.file("BH-002")
        result, problem = stale_sweep.check(board.root, ["BH-001"], ["BH-002"])
        assert problem == ""
        assert result.population == ["BH-001", "BH-002"]


#: The floor `_POPULATION_SQL` carried before item 35 — a watermark over the
#: whole run. Restated here and nowhere else so V4's mutation is exactly the
#: one line the fix changed.
_RUN_GLOBAL_WATERMARK = (
    "COALESCE((SELECT MAX(t.seq) FROM events t "
    "WHERE t.type='state_transition'), 0)"
)


class TestTheWindowIsTheSweepNotTheRun:
    """Item 35: "this sweep" was scoped to the run, and anyone could move it.

    The window was `seq > MAX(seq of any state_transition)`. Every one of these
    drives a `state_transition` that the sweep does not own — or, worse, one
    that the sweep *does* — and asks whether the findings it retired are still
    its work.
    """

    def test_two_retirements_by_one_actor_are_both_still_the_sweep_s_work(self, board):
        """No concurrency at all, and the window still loses a retirement.

        `defer cant-reproduce` is itself a transition, and the engine writes
        that `state_transition` *below* the `finding_deferred` it emits. So the
        second retirement's own transition stepped a run-global watermark past
        the first retirement's row. A sweep that retires two findings is the
        ordinary case, not the concurrent one.
        """
        board.file("BH-002")
        board.file("BH-003")
        board.enter_fix_loop()
        board.retire("BH-002")
        board.retire("BH-003")

        result, problem = stale_sweep.check(
            board.root, ["BH-001"], ["BH-002", "BH-003"])
        assert problem == ""
        assert result.population == ["BH-001", "BH-002", "BH-003"]

    def test_a_sibling_fix_commit_does_not_take_the_retirements_with_it(self, board):
        """V1 — a three-wide loop lands a fix while the sweep is running."""
        for finding_id in ("BH-002", "BH-003", "BH-004"):
            board.file(finding_id)
        board.defer_cant_reproduce("BH-002")
        board.defer_cant_reproduce("BH-003")
        board.sibling_fix_commit("BH-004")

        result, problem = stale_sweep.check(
            board.root, ["BH-001"], ["BH-002", "BH-003"])
        assert problem == ""
        assert result.population == ["BH-001", "BH-002", "BH-003"], (
            "BH-004 is off the board because the sibling resolved it; "
            "BH-002 and BH-003 are this sweep's own retirements"
        )

    def test_the_sibling_between_two_retirements_is_the_case_adjacency_hides(self, board):
        """V2 — the interleaving that needs three events to construct.

        A window bug that only shows up when the sibling lands *after* both
        retirements is the "a SQL LIMIT is not a window" trap: the natural test
        set is consecutive, and the two spellings agree on every consecutive
        case. Here the sibling sits between the two retirements, so only the
        earlier one falls below a run-global watermark.
        """
        for finding_id in ("BH-002", "BH-003", "BH-004"):
            board.file(finding_id)
        board.defer_cant_reproduce("BH-002")
        board.sibling_fix_commit("BH-004")
        board.defer_cant_reproduce("BH-003")

        result, problem = stale_sweep.check(
            board.root, ["BH-001"], ["BH-002", "BH-003"])
        assert problem == ""
        assert result.population == ["BH-001", "BH-002", "BH-003"]

    def test_the_run_global_watermark_is_what_lost_the_retirements(
        self, board, monkeypatch
    ):
        """V4, as a permanent test rather than a transcript.

        Put the old floor back and the retirement below the sibling goes
        missing again; restore it and it comes back. That is what says the fix
        is the window and not something else that moved alongside it.

        The mutated population is asserted as the value it must be, not as
        "not the right one": BH-001 is still open and BH-003 still sits above
        the sibling, so a mutation that merely broke the query would give a
        different answer than the one the defect gives.
        """
        for finding_id in ("BH-002", "BH-003", "BH-004"):
            board.file(finding_id)
        board.defer_cant_reproduce("BH-002")
        board.sibling_fix_commit("BH-004")
        board.defer_cant_reproduce("BH-003")

        monkeypatch.setattr(
            stale_sweep, "_POPULATION_SQL",
            stale_sweep._population_sql(_RUN_GLOBAL_WATERMARK))
        mutated, _ = stale_sweep.sweep_coverage(board.root)
        assert mutated.population == ["BH-001", "BH-003"], (
            "the old floor should lose exactly the retirement recorded below "
            "the sibling's transition"
        )
        result, problem = stale_sweep.check(
            board.root, ["BH-001"], ["BH-002", "BH-003"])
        assert result is None and "BH-002" in problem

        monkeypatch.undo()
        result, problem = stale_sweep.check(
            board.root, ["BH-001"], ["BH-002", "BH-003"])
        assert problem == ""
        assert result.population == ["BH-001", "BH-002", "BH-003"]

    def test_the_courier_states_no_window_of_its_own(self, board):
        """V3, the half that holds by construction.

        The courier re-derives rather than trusting the script, and the only
        thing that keeps the two derivations equal is that there is one of
        them. A second copy of the window here would agree on the day it was
        written and silently stop agreeing later.
        """
        with open(os.path.join(HOOKS_DIR, "stale_sweep_courier.py"), encoding="utf-8") as fh:
            source = fh.read()
        assert "SELECT" not in source and "state_transition" not in source
        assert "from stale_sweep import" in source


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestProvenance:
    """Everything a gate reads is re-derived by the hook."""

    def test_a_covered_sweep_records(self, board, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "stale_sweep_courier.py", _event(board.root), cwd=board.root,
        )
        assert code == 0
        fields = _recorded(mock_daemon)
        assert fields is not None, "a covered sweep must record"
        assert fields["triaged"] == "1"
        assert fields["retired"] == "0"
        assert fields["run"] == "1"

    def test_an_uncovered_sweep_records_nothing(self, board, mock_daemon):
        """The script is in a tree the agent can edit; the ledger is not, so
        the courier checks coverage again rather than trusting the exit code."""
        board.file("BH-002")
        code, _, _ = run_enforcement_hook(
            "stale_sweep_courier.py", _event(board.root), cwd=board.root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_the_counts_come_from_the_ledger_not_the_marker(self, board, mock_daemon):
        """The marker forges the very fields the derivation exists to own."""
        board.file("BH-002")
        lying = _marker(retired="99", triaged="99")
        run_enforcement_hook(
            "stale_sweep_courier.py",
            _event(board.root, command=_command(["BH-001", "BH-002"]), output=lying),
            cwd=board.root,
        )
        fields = _recorded(mock_daemon)
        assert fields["triaged"] == "2"
        assert fields["retired"] == "0"

    def test_the_sweep_is_stamped_with_where_it_ran(self, board, mock_daemon):
        run_enforcement_hook(
            "stale_sweep_courier.py", _event(board.root), cwd=board.root,
        )
        fields = _recorded(mock_daemon)
        assert fields["phase"] == stale_sweep.SWEEP_PHASE == "fix_loop"
        assert fields["step"] == stale_sweep.SWEEP_STEP == "11"


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestBothSignalsRequired:

    def test_a_nonzero_exit_records_nothing(self, board, mock_daemon):
        code, _, _ = run_enforcement_hook(
            "stale_sweep_courier.py", _event(board.root, exit_code=1), cwd=board.root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_a_missing_marker_records_nothing_and_warns(self, board, mock_daemon):
        code, out, _ = run_enforcement_hook(
            "stale_sweep_courier.py",
            _event(board.root, output="done\n"), cwd=board.root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None
        assert "NOT recorded" in json.dumps(out)

    def test_a_chained_command_records_nothing(self, board, mock_daemon):
        """Otherwise arbitrary work rides the one Bash line whose success this
        hook converts into a ledger entry."""
        chained = PLUGIN_COMMAND + " && echo done"
        code, _, _ = run_enforcement_hook(
            "stale_sweep_courier.py", _event(board.root, command=chained),
            cwd=board.root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None

    def test_another_tool_is_untouched(self, board, mock_daemon):
        event = {"tool_name": "Read", "tool_input": {"file_path": "x"},
                 "tool_response": {}, "cwd": board.root}
        code, _, _ = run_enforcement_hook(
            "stale_sweep_courier.py", event, cwd=board.root,
        )
        assert code == 0
        assert _recorded(mock_daemon) is None


class TestTheCourierIsTrusted:
    """A restricted writer the daemon cannot authenticate is enforcement that
    silently fails open — the manifest is generated from a hand-kept list, so
    a new courier is exactly what goes missing."""

    def test_the_courier_is_in_the_manifest(self):
        import tomllib
        with open(os.path.join(CONFIG_DIR, "trusted-callers.toml"), "rb") as fh:
            callers = tomllib.load(fh)["callers"]
        assert "hooks/stale_sweep_courier.py" in callers

    def _daemon_reaching_helpers(self):
        """Every helper in the shared modules that ends at `_daemon_request`.

        Derived, not listed. A hand-kept set here would be a second copy of the
        fact `_common.py` and `_protocol_cache.py` already state, and it would
        go stale exactly the way `TRUSTED_SCRIPTS` does — which is the defect
        this test exists to catch, reproduced inside the test that catches it.

        A fixpoint rather than one hop: `read_cache` reaches the daemon through
        `read_cache_with_boundary`, so a one-hop scan would call a hook that
        only reads the cache untrusted-but-fine, and item 47 is precisely such
        a hook.
        """
        import ast

        defs = {}
        for module in ("_common.py", "_protocol_cache.py"):
            with open(os.path.join(HOOKS_DIR, module), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs[node.name] = ast.dump(node)

        reaching = {"_daemon_request"}
        changed = True
        while changed:
            changed = False
            for name, dumped in defs.items():
                if name in reaching:
                    continue
                if any(f"id='{r}'" in dumped or f"attr='{r}'" in dumped
                       for r in reaching):
                    reaching.add(name)
                    changed = True
        return reaching

    def test_every_registered_daemon_caller_is_in_the_manifest(self):
        """Generalised, because this is how the gap arrives: the generator's
        `TRUSTED_SCRIPTS` is hand-kept, so regenerating after adding a hook
        changes nothing and everything still looks fine.

        Scoped to hooks.json entrypoints, because since sahjhan 0.21.0 the
        daemon authenticates the process *directly* holding the socket. A
        module like `quiz_vault.py` calls `record_authed_event` but is only
        ever imported — `lens_quiz.py` and `quiz_capture.py` are the processes,
        and they are the ones that must be pinned.

        **Every peer-gated op, not only `record_authed_event`.** Item 47:
        `_sahjhan_bootstrap.py` is a registered PreToolUse entrypoint that
        calls `_daemon_request({"op": "enforcement_read"})` and never writes an
        event, so a check keyed on the *write* helper skipped it for the three
        months it sat unpinned. A read that is refused is worse than a write
        that is refused, because one of its two uses fails **open**:
        `is_enforcement_fresh(None)` returns falsey and the TDD gate for
        Bash-based source writes is simply not applied.
        """
        import tomllib
        with open(os.path.join(CONFIG_DIR, "trusted-callers.toml"), "rb") as fh:
            callers = tomllib.load(fh)["callers"]
        with open(os.path.join(REPO_ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            registered = fh.read()
        helpers = self._daemon_reaching_helpers()

        for name in sorted(os.listdir(HOOKS_DIR)):
            if not name.endswith(".py") or f"/{name}" not in registered:
                continue
            with open(os.path.join(HOOKS_DIR, name), encoding="utf-8") as fh:
                source = fh.read()
            reached = sorted(h for h in helpers if f"{h}(" in source)
            if not reached:
                continue
            assert f"hooks/{name}" in callers, (
                f"{name} is a registered hook that reaches the daemon via "
                f"{reached} but is not in trusted-callers.toml — the daemon "
                f"refuses it, and the op it needed silently does nothing"
            )

    def test_the_derivation_finds_the_read_path_and_not_only_the_write(self):
        """Non-vacuity for the helper set itself.

        If the fixpoint ever collapses to `record_authed_event`, the test above
        goes back to passing on item 47's exact shape while looking unchanged.
        """
        helpers = self._daemon_reaching_helpers()
        assert {"read_cache", "record_authed_event"} <= helpers, sorted(helpers)

    def test_the_courier_is_registered_as_a_posttooluse_hook(self):
        with open(os.path.join(REPO_ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            registered = fh.read()
        assert "stale_sweep_courier.py" in registered


# ── The swap itself ──────────────────────────────────────────────────────────


from test_amplification_breaker import _Run  # noqa: E402


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _sweeps_recorded(run) -> int:
    rows = json.loads(run.sah(
        "query", "SELECT count(*) AS n FROM events WHERE type='stale_sweep_complete'",
        "--format", "json").stdout)
    return int(rows[0]["n"])


@pytest.mark.slow
@pytest.mark.integration
class TestTheWindowEndToEnd:
    """The same two claims, driven through the script and its courier.

    `check` running in-process is the script's own reading. These go through
    the real daemon, because the window has to hold at the end that actually
    writes the event — and because `stale_sweep_complete`, the thing the window
    is now anchored on, is restricted and only the courier can put one there.
    """

    def test_a_sibling_fix_commit_mid_sweep_still_lets_the_sweep_record(self, run):
        """V1 and V3's other half at once: the courier re-derives, so this is
        the window holding where the ledger entry is actually made."""
        for finding_id in ("BH-001", "BH-002", "BH-003"):
            run.file(finding_id)
        run.defer("BH-002", reason="cant_reproduce")
        run.sah("event", "state_transition", "--field", "from=fix_loop",
                "--field", "to=fix_loop", "--field", "command=fix_commit")
        run.resolve("BH-003")

        run.sweep(present=["BH-001"], retired=["BH-002"])
        assert _sweeps_recorded(run) == 1

    def test_an_earlier_sweep_s_retirements_stay_off_the_board(self, run):
        """The property the run-global watermark bought, and the one a window
        anchored on the sweep has to keep.

        A finding retired by the *previous* sweep is not this sweep's work.
        Asking for its verdict again would fail every sweep after the first —
        the failure mode the fix could have traded the old one for.
        """
        run.file("BH-001")
        run.file("BH-002")
        run.defer("BH-002", reason="cant_reproduce")
        run.sweep(present=["BH-001"], retired=["BH-002"])
        assert _sweeps_recorded(run) == 1

        run.sweep(present=["BH-001"])
        assert _sweeps_recorded(run) == 2, (
            "the second sweep recorded nothing — BH-002 is being counted as "
            "this sweep's work a second time"
        )


def _owe_a_round(run, findings):
    """Three resolutions since the last round is what makes one owed."""
    for finding_id in findings:
        run.file(finding_id)
        run.resolve(finding_id)


@pytest.mark.slow
@pytest.mark.integration
class TestTheSweepDischargesTheRoundPastEight:
    """Past ~round 8 the owed round is satisfied by a sweep instead."""

    def _rounds(self, run, n):
        run.file("BH-001")
        for _ in range(n):
            run.round()

    def test_a_sweep_before_round_eight_discharges_nothing(self, run):
        """Non-vacuity, and the half that keeps the swap a *swap*: a sweep is
        worth running early and still costs nothing here, but a run seven
        rounds in still owes a real pattern round."""
        self._rounds(run, 7)
        _owe_a_round(run, ["BH-101", "BH-102", "BH-103"])
        assert run.answer("pattern_analysis_overdue") == "true"

        run.sweep()
        assert run.answer("pattern_analysis_overdue") == "true", (
            "a sweep discharged the round before round 8 — the swap is "
            "supposed to start there"
        )

    def test_a_sweep_at_round_eight_discharges_the_round(self, run):
        self._rounds(run, 8)
        _owe_a_round(run, ["BH-101", "BH-102", "BH-103"])
        assert run.answer("pattern_analysis_overdue") == "true"

        run.sweep()
        assert run.answer("pattern_analysis_overdue") == "false", (
            "past round 8 the owed round is satisfied by a stale sweep, and "
            "this one was not"
        )

    def test_the_obligation_comes_back(self, run):
        """The property a bare relief conjunct would destroy.

        "Past round 8 no round is owed" would withdraw the obligation
        *permanently* — nothing raises it again, because the only thing that
        resets the counter is a round and none would ever be owed. Widening the
        floor to both event types keeps it cycling on the same 3-resolved rule.
        """
        self._rounds(run, 8)
        _owe_a_round(run, ["BH-101", "BH-102", "BH-103"])
        run.sweep()
        assert run.answer("pattern_analysis_overdue") == "false"

        _owe_a_round(run, ["BH-201", "BH-202", "BH-203"])
        assert run.answer("pattern_analysis_overdue") == "true", (
            "three more fixes after a sweep and nothing is owed — the "
            "obligation stopped cycling"
        )

    def test_the_boundary_opens_on_the_sweep(self, run):
        """The swap where it is felt: `iteration_boundary` blocks on the owed
        round, and past round 8 a sweep is what opens it."""
        self._rounds(run, 8)
        _owe_a_round(run, ["BH-101", "BH-102", "BH-103"])
        out = run.gate_check("iteration_boundary")
        assert "✗" in out and "pattern_analysis_overdue" in out

        run.sweep()
        after = [ln for ln in run.gate_check("iteration_boundary").splitlines()
                 if "pattern_analysis_overdue" in ln]
        assert len(after) == 1 and after[0].strip().startswith("✓"), after

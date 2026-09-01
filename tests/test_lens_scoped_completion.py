"""W07 / item 3: lens completion is graded on the lens, not on the board.

P0.1 removed `all_findings_closed == 0` from `converge` because it was
unreachable — the audited run's open count rose 124 -> 273 and fell exactly
once — and replaced it with four conjuncts that say which findings actually
have to be closed. The identical named query stayed on
`set complete perspective`, which a run must pass **thirteen times**, once per
lens. The unreachable requirement was not removed; it was moved one door
upstream and multiplied by thirteen.

RULED (Jon, 2026-08-26), option (a): `set complete perspective` requires every
CRITICAL and every `user_reachable` HIGH **carrying this lens** to be
resolved-or-deferred. **A clean lens is not an empty board.** Lens 3 blocks on
its own open CRITICALs and ignores lens 1's open MEDIUMs — and lens 1's open
CRITICALs, which `converge` still catches run-wide.

The accepted cost is asserted here rather than left as prose: a finding filed
under an already-completed lens is caught only at `converge`
(`test_a_finding_under_a_finished_lens_is_caught_only_at_converge`). That is
the trade that stops lens 7 being answerable for lens 2's board.

Driven against a real daemon and read out of `protocol.toml` rather than
restated, so editing the config re-tests the config. `TestNonVacuity` is the
half that says these assertions discriminate: it restores the run-wide gate in
a derived config and requires the same two scenarios to block.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_amplification_breaker import _named_query, _Run  # noqa: E402
from test_round_item_cap import _blocked_on  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]

#: The lens whose completion is under test, and one it must ignore. Both are
#: real members of `[sets.perspective]` — the gate binds `{{current_perspective}}`
#: from the transition's argument, and an invented lens would test a filter
#: against a value no run can hold.
LENS = "security"
OTHER = "component"

COMPLETION = "set complete perspective"

#: The two queries this unit adds, referenced by name because the name is what
#: `gate check` prints and what the block message shares with its escape.
LENS_CRITICAL = "lens_critical_resolved"
LENS_HIGH = "lens_user_reachable_high_closed"

#: The run-wide conjuncts that must keep catching what the lens gate lets past.
RUN_WIDE_CRITICAL = "all_critical_resolved"
RUN_WIDE_FAULT_INJECTED = "no_open_fault_injected"

#: `theoretical_courier.py` fires on a `sahjhan event finding` call; the text
#: only has to be recognisable as one.
_FILE_CMD = "sahjhan event finding --field id=BH-001"


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _answer(run, name, perspective=None):
    """One named query's answer, with the lens bound the way a gate binds it."""
    sql = _named_query(name)
    if perspective is not None:
        sql = sql.replace("{{current_perspective}}", perspective)
    assert "{{" not in sql, f"{name} left a binding unresolved: {sql}"
    out = run.sah("query", sql, "--format", "json").stdout
    return str(list(json.loads(out)[0].values())[0])


def _gate_check(run, command, *args, config_dir=None):
    """`gate check` against an arbitrary config dir, on this run's ledger.

    `_Run.gate_check` is pinned to the shipped `enforcement/`; `TestNonVacuity`
    needs the same ledger read by a mutated copy of it, which is the only way
    to prove the assertions below discriminate.
    """
    result = subprocess.run(
        [run.d["binary"], "--config-dir", config_dir or run.d["config_dir"],
         "gate", "check", command, *args],
        cwd=run.root, capture_output=True, text=True, timeout=60,
    )
    return result.stdout


def _lens_gate(run, perspective=LENS, config_dir=None):
    return _gate_check(run, COMPLETION, f"current_perspective={perspective}",
                       config_dir=config_dir)


def _enter(run, state):
    """Seed a state the run would otherwise have to earn.

    A precondition, not the claim — the `final_sweep` gates are a different
    subject, and `test_fix_commit_caller_anchor` reaches `fix_loop` the same
    way for the same reason.
    """
    run.sah("event", "state_transition", "--field", "from=fix_loop",
            "--field", f"to={state}", "--field", "command=seeded")


# ── The gate is scoped to the lens ───────────────────────────────────────────


class TestTheLensGateAsksAboutItsOwnLens:
    """V2 and V3, the two halves of the ruling.

    A filter can be wrong in two directions and only one of them is visible
    from a blocked run: stop blocking on everything (V3 alone passes for a gate
    that was simply deleted) and keep blocking on this lens (V2). Both are
    asserted, on the query and through `gate check`.
    """

    def test_a_lens_blocks_on_its_own_open_critical(self, run):
        """V2."""
        run.file("BH-001", severity="CRITICAL", perspective=LENS)

        assert _answer(run, LENS_CRITICAL, LENS) == "false"
        assert _blocked_on(_lens_gate(run), LENS_CRITICAL), (
            "an open CRITICAL filed under this lens did not block its "
            "completion"
        )

    def test_a_lens_blocks_on_its_own_open_user_reachable_high(self, run):
        """V2, the second conjunct."""
        run.file("BH-001", severity="HIGH", reachability="user_reachable",
                 perspective=LENS)

        assert _answer(run, LENS_HIGH, LENS) == "false"
        assert _blocked_on(_lens_gate(run), LENS_HIGH)

    def test_another_lenss_open_medium_does_not_block(self, run):
        """V3 — the ruling, in its mildest form."""
        run.file("BH-001", severity="MEDIUM", perspective=OTHER)

        assert _answer(run, LENS_CRITICAL, LENS) == "true"
        assert _answer(run, LENS_HIGH, LENS) == "true"
        out = _lens_gate(run)
        assert not _blocked_on(out, LENS_CRITICAL), out
        assert not _blocked_on(out, LENS_HIGH), out

    def test_another_lenss_open_critical_does_not_block_this_one(self, run):
        """V3 at its sharpest, and the half the ruling spells out.

        Lens 3 is not answerable for lens 1's board *even for a CRITICAL* —
        that one is `converge`'s to catch, run-wide, and
        `test_a_finding_under_a_finished_lens_is_caught_only_at_converge`
        asserts it still is.
        """
        run.file("BH-001", severity="CRITICAL", perspective=OTHER)

        assert _answer(run, LENS_CRITICAL, LENS) == "true"
        assert not _blocked_on(_lens_gate(run), LENS_CRITICAL)

    def test_the_gate_moves_with_the_lens_it_is_asked_about(self, run):
        """The binding is real: one board, two lenses, two different answers.

        Both directions in one test, because a query that ignored its argument
        would satisfy either half alone.
        """
        run.file("BH-001", severity="CRITICAL", perspective=LENS)
        run.file("BH-002", severity="CRITICAL", perspective=OTHER)

        assert _answer(run, LENS_CRITICAL, LENS) == "false"
        assert _answer(run, LENS_CRITICAL, OTHER) == "false"

        run.resolve("BH-001")
        assert _answer(run, LENS_CRITICAL, LENS) == "true"
        assert _answer(run, LENS_CRITICAL, OTHER) == "false", (
            "resolving this lens's CRITICAL answered for the other lens too — "
            "the filter is not reading its argument"
        )

    def test_the_lens_is_the_latest_filing(self, run):
        """D25, one field over from severity and reachability.

        A finding re-filed under another lens moves to that lens's board. It is
        the same shape the severity and reachability predicates already carry,
        and it is bounded the same way: re-filing to dodge a lens gate leaves
        the CRITICAL sitting in front of `converge`.
        """
        run.file("BH-001", severity="CRITICAL", perspective=LENS)
        assert _answer(run, LENS_CRITICAL, LENS) == "false"

        run.file("BH-001", severity="CRITICAL", perspective=OTHER)
        assert _answer(run, LENS_CRITICAL, LENS) == "true"
        assert _answer(run, LENS_CRITICAL, OTHER) == "false"
        assert _answer(run, RUN_WIDE_CRITICAL) == "false", (
            "a CRITICAL re-filed onto another lens escaped the run-wide "
            "conjunct as well — the lens scope must not be a way out"
        )


# ── What the lens gate lets past, `converge` must still catch ────────────────


class TestTheAcceptedCost:
    """V4 and V5. The trade is stated in the ruling; here it is measured."""

    def test_a_finding_under_a_finished_lens_is_caught_only_at_converge(self, run):
        """V4 — the accepted cost, both halves.

        A CRITICAL filed under a lens the run has already completed is asked
        about by no lens gate again: the only gate that would is
        `set complete perspective` for *that* lens, and the run has rotated
        past it. So the assertion is that the gate the run is actually standing
        at passes, and that `converge` does not.
        """
        run.file("BH-001", severity="CRITICAL", perspective=OTHER)

        out = _lens_gate(run, LENS)
        assert not _blocked_on(out, LENS_CRITICAL), (
            f"the lens under way answered for a finished lens's board:\n{out}"
        )

        _enter(run, "final_sweep")
        converge = _gate_check(run, "converge")
        assert _blocked_on(converge, RUN_WIDE_CRITICAL), (
            "a CRITICAL no lens gate will ever ask about again also walked "
            f"through `converge` — nothing catches it:\n{converge}"
        )

    def test_a_fault_injected_high_no_longer_blocks_a_lens(self, run):
        """V5, first half — the defect item 3 names.

        `item_is_user_reachable` refuses a `fault_injected` finding at
        `fix_commit`, and Step 15's hardening batch is taught after all
        thirteen lenses. Under the run-wide gate one such HIGH read `1` and
        blocked every lens with no escape reachable from where the block was
        printed.
        """
        run.file("BH-001", severity="HIGH", reachability="fault_injected",
                 perspective=LENS)

        assert _answer(run, LENS_HIGH, LENS) == "true"
        out = _lens_gate(run)
        assert not _blocked_on(out, LENS_HIGH), out
        assert not _blocked_on(out, LENS_CRITICAL), out

    def test_that_fault_injected_high_is_still_caught_at_converge(self, run):
        """V5, second half. Letting it past the lens gate is only safe because
        `no_open_fault_injected` refuses to converge on it."""
        run.file("BH-001", severity="HIGH", reachability="fault_injected",
                 perspective=LENS)

        assert _answer(run, RUN_WIDE_FAULT_INJECTED) == "false"
        _enter(run, "final_sweep")
        converge = _gate_check(run, "converge")
        assert _blocked_on(converge, RUN_WIDE_FAULT_INJECTED), converge


# ── The block has to name something the run can do from here ─────────────────


class TestTheBlockPrintsAnEscape:
    """V6. `intent` prose is not the claim — the escape has to be reachable
    from the state the block is printed in, and one of them is run."""

    def _intents(self):
        try:
            import tomllib  # noqa: PLC0415
        except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
            import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        completion = next(t for t in transitions if t["command"] == COMPLETION)
        intents = {
            gate["query"]: gate.get("intent", "")
            for gate in completion["gates"]
            if gate.get("query") in (LENS_CRITICAL, LENS_HIGH)
        }
        # Without this the per-intent loops below iterate an empty dict and
        # pass while the gates do not exist at all.
        assert set(intents) == {LENS_CRITICAL, LENS_HIGH}, (
            f"{COMPLETION} does not carry both lens gates: {sorted(intents)}"
        )
        return transitions, intents

    def test_both_gates_carry_an_intent(self):
        """The old gate carried none at all, so the block printed no escape."""
        _, intents = self._intents()
        assert set(intents) == {LENS_CRITICAL, LENS_HIGH}
        for query, intent in intents.items():
            assert intent.strip(), f"{query} blocks with no escape"

    def test_each_intent_names_a_command_declared_from_this_state(self):
        """A block must name something reachable from its own side.

        `set complete perspective` leaves `fix_loop`, so an escape declared
        only from `pattern_analysis` or `final_sweep` would be a block naming
        an act the run cannot perform — #77's shape.
        """
        transitions, intents = self._intents()
        from_fix_loop = {
            t["command"] for t in transitions
            if t.get("from") == "fix_loop" and t.get("command")
        }
        for query, intent in intents.items():
            named = [c for c in from_fix_loop if c in intent]
            assert named, (
                f"{query}'s intent names no command declared from fix_loop: "
                f"{intent!r}"
            )

    def test_the_fix_loop_teaches_the_lens_scoped_condition(self):
        """The gate and the sequence that leads to it, in one commit.

        "When a perspective passes clean" was compatible with either gate, so
        an agent reading it would still clear the whole board — the work this
        ruling exists to stop, with a green gate saying nothing.
        """
        path = os.path.join(REPO_ROOT, "skills", "holtz", "references",
                            "phase-fix-loop.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        taught = text[text.index("A lens passes clean"):][:400]
        for phrase in ("filed under that lens", "other lenses", "fault_injected"):
            assert phrase in taught, f"the taught condition omits {phrase!r}"

    def test_the_escape_runs_for_a_theoretical_critical(self, run):
        """An escape that is *run*, end to end, against the real daemon.

        `theoretical` is written by a courier rather than chosen, and says no
        path to the defect was found. Without the `reason='theoretical'`
        exclusion this conjunct inherits from `all_critical_resolved`, such a
        CRITICAL has no route at all: `fix_commit` refuses it, the hardening
        batch's population is `fault_injected`, and re-grading to clear a gate
        is a forgery.
        """
        run.file("BH-001", severity="CRITICAL", reachability="theoretical",
                 perspective=LENS)
        assert _blocked_on(_lens_gate(run), LENS_CRITICAL)

        courier = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "theoretical_courier.py")],
            input=json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": _FILE_CMD},
                "tool_response": {"output": "", "exit_code": 0},
                "cwd": run.root,
            }),
            capture_output=True, text=True, timeout=60, cwd=run.root,
            env={**os.environ, "SAHJHAN_DAEMON_SOCKET": run.d["sock_path"]},
        )
        assert courier.returncode == 0, courier.stderr
        assert "NOT recorded" not in courier.stdout, courier.stdout

        assert _answer(run, LENS_CRITICAL, LENS) == "true", (
            "the auto-deferral ran and the lens gate still refuses — the "
            "block names an act that does not clear it"
        )
        assert not _blocked_on(_lens_gate(run), LENS_CRITICAL)

    def test_an_ordinary_deferral_does_not_clear_a_lens_critical(self, run):
        """The counterweight, so the exclusion above is not a hole.

        `low_priority`, `medium_budget` and `cant_reproduce` are discretionary
        acts. Refusing them is what the conjunct is for — the same scope
        `all_critical_resolved` carries, and the same test that guards it.
        """
        for index, reason in enumerate(
                ("low_priority", "medium_budget", "cant_reproduce"), start=1):
            finding = f"BH-{index:03d}"
            run.file(finding, severity="CRITICAL", perspective=LENS)
            run.defer(finding, reason=reason)
            assert _answer(run, LENS_CRITICAL, LENS) == "false", (
                f"a CRITICAL deferred {reason} satisfied the lens conjunct "
                "that says resolved"
            )
            run.resolve(finding)
        assert _answer(run, LENS_CRITICAL, LENS) == "true"


# ── Non-vacuity ──────────────────────────────────────────────────────────────


class TestNonVacuity:
    """V7. Restore the run-wide gate in a derived config; the two scenarios
    this unit exists to unblock must block again.

    A derived copy of `enforcement/` rather than a hand-written config: a
    pasted one cannot drift-fail, and the point is to re-run the *shipped*
    gates with one line put back.
    """

    @staticmethod
    def _config_with_the_run_wide_gate(tmp_path):
        derived = str(tmp_path / "run-wide-config")
        shutil.copytree(CONFIG_DIR, derived)
        path = os.path.join(derived, "transitions.toml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        anchor = f'command = "{COMPLETION}"\nargs = ["current_perspective"]\ngates = [\n'
        assert anchor in text, "the transition's declaration changed shape"
        text = text.replace(
            anchor,
            anchor + '    { type = "query", query = "all_findings_closed", expect = "0" },\n',
            1,
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return derived

    def test_the_run_wide_gate_blocks_on_another_lenss_medium(self, run, tmp_path):
        """V3's scenario, under the gate this unit removes."""
        run.file("BH-001", severity="MEDIUM", perspective=OTHER)

        derived = self._config_with_the_run_wide_gate(tmp_path)
        out = _lens_gate(run, config_dir=derived)
        assert _blocked_on(out, "all_findings_closed"), (
            "restoring the run-wide gate did not block on another lens's open "
            f"MEDIUM — V3 is not discriminating:\n{out}"
        )
        assert not _blocked_on(_lens_gate(run), LENS_CRITICAL), (
            "the shipped config blocks too, so the derived one proves nothing"
        )

    def test_the_run_wide_gate_blocks_on_a_fault_injected_high(self, run, tmp_path):
        """V5's scenario, under the gate this unit removes."""
        run.file("BH-001", severity="HIGH", reachability="fault_injected",
                 perspective=LENS)

        derived = self._config_with_the_run_wide_gate(tmp_path)
        out = _lens_gate(run, config_dir=derived)
        assert _blocked_on(out, "all_findings_closed"), out
        assert not _blocked_on(_lens_gate(run), LENS_HIGH), (
            "the shipped config blocks too, so the derived one proves nothing"
        )


# ── The run-wide query is gone from this transition ──────────────────────────


def test_all_findings_closed_no_longer_gates_lens_completion():
    """The mirror of `test_all_findings_closed_no_longer_gates_converge`.

    P0.1 removed this query from `converge` and left it here, where a run meets
    it thirteen times. A test on each door is what stops it moving again.
    """
    try:
        import tomllib  # noqa: PLC0415
    except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
        import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
    with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
        transitions = tomllib.load(fh)["transitions"]
    completion = next(t for t in transitions if t["command"] == COMPLETION)
    assert "all_findings_closed" not in {
        gate.get("query") for gate in completion["gates"]
    }

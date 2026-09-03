"""W12 / items 34 + 28 — a recorded command's CLI refuses what its courier does.

Four scripts print an evidence line a PostToolUse courier turns into a ledger
entry. Each carries a recognizer that decides whether a Bash line *is* that
command, and each returned `None` for two different situations while exiting 0
on both:

* the line was some other command entirely — nothing to say;
* the line named this very script and asked it to record, in a shape the
  recognizer refuses — the agent believed it recorded something, nothing was
  written, and the gate that wanted the evidence blocked later with no
  connection back to this moment.

**Silence is the defect.** So a test here that only asserted "nothing was
recorded" would reproduce the bug rather than catch it: every one of these
reads the warning.

Two ends, tested separately because they fail differently. The CLI end
(`TestTheParserRefusesWhatTheCourierRefuses`) is where a shape the script
itself can see must stop — `--cwd` with `--record`, and `--record` without
`--present`. The courier end (`TestTheCourierSaysSoInsteadOfExitingQuiet`) is
where the shapes only the *host* can see must be reported — a wrapper before
the interpreter, and a chained segment. Neither script can see those: it ran,
it was fine, it exited 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

#: script module, its courier, and the flags that make a *complete* recorded
#: command for it. Every row is driven through both ends.
_RECORDED = [
    ("verify_suite", "suite_courier.py", ["--scope", "full"], "suite_green"),
    ("pattern_round", "pattern_courier.py", ["--siblings-found", "0"], "pattern_analysis_complete"),
    ("stale_sweep", "stale_sweep_courier.py", ["--present", "BH-001"], "stale_sweep_complete"),
    ("hardening_batch", "hardening_batch_courier.py", ["--module", "x"], "hardening batch"),
]
_IDS = [row[0] for row in _RECORDED]


def _script(name: str) -> str:
    return os.path.join(SCRIPTS_DIR, f"{name}.py")


def _run(name: str, *args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _script(name), *args],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )


def _post_tool(command: str, cwd: str, exit_code: int = 0, output: str = "") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"output": output, "exit_code": exit_code},
        "cwd": str(cwd),
    }


def _warning(courier: str, command: str, cwd: str, exit_code: int = 0) -> str:
    """What the courier said, as the transcript would carry it."""
    code, out, _ = run_enforcement_hook(
        courier, _post_tool(command, cwd, exit_code), cwd=cwd)
    assert code == 0, f"{courier} exited {code}"
    return json.dumps(out)


# ── V1 · the CLI end ─────────────────────────────────────────────────────────


class TestTheParserRefusesWhatTheCourierRefuses:
    """A shape the script can see itself must fail at the script."""

    @pytest.mark.parametrize("name,_courier,flags,_event", _RECORDED, ids=_IDS)
    def test_cwd_with_record_is_refused_at_the_cli(self, name, _courier, flags, _event, tmp_path):
        """`--cwd` is what every recognizer refuses, and what every parser took.

        The courier derives against the *event's* directory, so a recorded
        command pointed elsewhere would attach another project's board to this
        ledger — which is why the recognizers refuse it. Taking it here made
        that refusal silent: the script checked the board, printed its marker
        and exited 0, and the courier wrote nothing.
        """
        result = _run(name, "--record", *flags, "--cwd", str(tmp_path), cwd=str(tmp_path))
        # Exit 2 is argparse's, and the distinction is the whole point:
        # measured against the unmodified tree these commands *already* exited
        # non-zero — they ran, reached the ledger, and failed because a bare
        # tmp dir has none. So `returncode != 0` alone passes on the defect,
        # and only "refused before it did anything" discriminates.
        assert result.returncode == 2, (
            f"{name} did not refuse --cwd with --record at the parser; it ran, "
            f"and a run that reaches the board exits 0 on a real one and "
            f"records nothing\n{result.stdout}\n{result.stderr}"
        )
        assert "--cwd" in result.stderr and "--record" in result.stderr
        assert "ledger" not in result.stderr, (
            "the refusal must come before anything reads the board"
        )

    @pytest.mark.parametrize("name,_courier,_flags,_event", _RECORDED, ids=_IDS)
    def test_cwd_still_points_the_diagnostic_paths(self, name, _courier, _flags, _event, tmp_path):
        """The flag is not withdrawn — only the pair is refused.

        `--show`/`--check` are how an agent inspects a board it is not standing
        in, and nothing records off them. Without this, "refuse `--cwd`" could
        be implemented by deleting the flag and every test above would still
        pass.
        """
        diagnostic = "--check" if name == "verify_suite" else "--show"
        result = _run(name, diagnostic, "--cwd", str(tmp_path), cwd=REPO_ROOT)
        assert "--cwd cannot be combined" not in result.stderr
        assert "unrecognized arguments" not in result.stderr

    def test_record_without_present_is_refused_at_the_cli(self, tmp_path):
        """Item 28, the whole of it.

        `verdicts_of` returns None without `--present`, but `main` accepted
        `--record --retired BH-004`: it passed the coverage check, printed
        `STALE-SWEEP:`, exited 0 — and the courier recorded nothing and said
        nothing, while every other failure on that path warns.
        """
        result = _run("stale_sweep", "--record", "--retired", "BH-004", cwd=str(tmp_path))
        assert result.returncode == 2, (
            "the sweep ran instead of being refused; on a real board it exits "
            f"0 and the courier records nothing\n{result.stdout}\n{result.stderr}"
        )
        assert "--present" in result.stderr

    def test_an_empty_sweep_is_still_spelled(self, tmp_path):
        """A sweep that retired everything says `--present ''`, and the
        recognizer has always accepted that — so requiring the flag takes
        nothing away. Without this the fix could have been "require a
        non-empty --present", which would refuse a legitimate sweep."""
        from stale_sweep import verdicts_of
        assert verdicts_of(
            "python3 enforcement/scripts/stale_sweep.py --record "
            "--present '' --retired BH-004"
        ) == ([], ["BH-004"])


# ── V2 + V3 · the courier end ────────────────────────────────────────────────


@pytest.mark.hook_e2e
@pytest.mark.slow
class TestTheCourierSaysSoInsteadOfExitingQuiet:
    """A shape only the host can see must be reported, not passed over."""

    @pytest.mark.parametrize("name,courier,flags,event_label", _RECORDED, ids=_IDS)
    def test_a_wrapper_before_the_interpreter_warns(
        self, name, courier, flags, event_label, tmp_path
    ):
        """V3, and the ruling it asks to be stated.

        `_INTERPRETERS` is `python|python3|py`, so a wrapper lands in
        `tokens[0]` and shifts the script into `tokens[2]`: the recognizer
        cannot parse it at all. The space of wrappers — `poetry run`, `uv run`,
        `conda run`, a venv shim — is not enumerable, so **the taught spelling
        stays the only supported one and the failure is made loud** rather than
        the set being widened. Both were acceptable to the unit; silence was
        not.
        """
        command = (
            f"poetry run python ${{CLAUDE_PLUGIN_ROOT}}/enforcement/scripts/"
            f"{name}.py --record " + " ".join(flags)
        )
        said = _warning(courier, command, str(tmp_path))
        assert "NOT recorded" in said, (
            f"{courier} passed over a wrapped record command in silence"
        )
        assert "python3" in said, "the warning must name the form that works"

    @pytest.mark.parametrize("name,courier,flags,event_label", _RECORDED, ids=_IDS)
    def test_a_chained_record_warns(self, name, courier, flags, event_label, tmp_path):
        """Chaining is refused so arbitrary work cannot ride the one Bash line
        whose success becomes a ledger entry. The refusal stays; the silence
        goes."""
        command = (
            f"python3 ${{CLAUDE_PLUGIN_ROOT}}/enforcement/scripts/{name}.py "
            f"--record " + " ".join(flags) + " && echo done"
        )
        assert "NOT recorded" in _warning(courier, command, str(tmp_path))

    @pytest.mark.parametrize("name,courier,flags,event_label", _RECORDED, ids=_IDS)
    def test_a_failed_command_is_not_warned_about_twice(
        self, name, courier, flags, event_label, tmp_path
    ):
        """The parser's refusal is the message. Repeating it here would turn
        one clear error into two, and would fire on every red suite run."""
        command = (
            f"python3 ${{CLAUDE_PLUGIN_ROOT}}/enforcement/scripts/{name}.py "
            f"--record " + " ".join(flags) + f" --cwd {tmp_path}"
        )
        assert "NOT recorded" not in _warning(courier, command, str(tmp_path), exit_code=2)

    @pytest.mark.parametrize("name,courier,flags,event_label", _RECORDED, ids=_IDS)
    def test_reading_the_script_is_not_running_it(
        self, name, courier, flags, event_label, tmp_path
    ):
        """The discriminator names the script *and* `--record`.

        This repo edits these four scripts constantly. A courier that warned on
        every line mentioning its own path would fire on `git add`, `cat` and
        `ruff check`, and a warning that fires on everything is read as noise —
        which is the same failure as silence, arrived at from the other side.
        """
        for command in (f"git add enforcement/scripts/{name}.py",
                        f"cat enforcement/scripts/{name}.py"):
            assert "NOT recorded" not in _warning(courier, command, str(tmp_path))

    def test_the_tdd_record_chained_with_a_test_run_warns(self, tmp_path):
        """The shape `phase-fix-loop.md` invited by teaching this step without
        the "run it alone" line its three siblings carry.

        A subagent running `pytest …; sahjhan event test_failed_before_fix …`
        records the event and no evidence row, then meets the TDD gate refusing
        its source edit with nothing to point at.
        """
        command = (
            "pytest -q tests/test_x.py; sahjhan --config-dir "
            '"$CLAUDE_PLUGIN_ROOT/enforcement" event test_failed_before_fix '
            "--field project=holtz --field run=1 --field auditor=holtz "
            "--field finding_id=BH-001 --field test_name=test_x"
        )
        said = _warning("tdd_courier.py", command, str(tmp_path))
        assert "NOT recorded" in said and "alone on its own Bash line" in said

    def test_an_unrelated_command_stays_silent_in_the_tdd_courier(self, tmp_path):
        assert "NOT recorded" not in _warning(
            "tdd_courier.py", "pytest -q; ruff check .", str(tmp_path))


# ── The warning quotes a form the document actually teaches ──────────────────


class TestTheWarningQuotesTheTaughtForm:
    """`TAUGHT_PREFIX` is a copy of a string that lives in a skill file.

    A courier telling the agent to run something the document does not teach is
    worse than saying nothing, so the copy is pinned rather than trusted.
    """

    @pytest.mark.parametrize("name,_courier,_flags,_event", _RECORDED, ids=_IDS)
    def test_the_prefix_appears_in_a_skill_file(self, name, _courier, _flags, _event):
        import importlib

        prefix = importlib.import_module(name).TAUGHT_PREFIX
        references = os.path.join(REPO_ROOT, "skills", "holtz", "references")
        taught = ""
        for entry in sorted(os.listdir(references)):
            if entry.endswith(".md"):
                with open(os.path.join(references, entry), encoding="utf-8") as fh:
                    taught += fh.read()
        assert prefix in taught, (
            f"{name}.TAUGHT_PREFIX is not a form any reference file teaches, so "
            f"the courier's warning points at a command the agent has never "
            f"been shown: {prefix!r}"
        )


# ── V5 · non-vacuity ─────────────────────────────────────────────────────────


class TestTheRefusalsAreWhatDoIt:
    """Put each half back the way it was and require the symptom to return."""

    @pytest.mark.parametrize("name,_courier,flags,_event", _RECORDED, ids=_IDS)
    def test_without_the_cli_refusal_the_command_exits_zero_again(
        self, name, _courier, flags, _event, tmp_path, monkeypatch
    ):
        """The old behaviour, exactly: `--record --cwd` exits 0 and records
        nothing. Driven in-process so the monkeypatch reaches the parser."""
        import importlib

        module = importlib.import_module(name)
        monkeypatch.setattr(module, "refuse_cwd_with_record", lambda *a, **k: None)
        # Only the parser's answer is under test, so the run is allowed to fail
        # for any *later* reason — what must not happen is a SystemExit(2) from
        # `parser.error`, which is what the refusal raises.
        try:
            module.main(["--record", *flags, "--cwd", str(tmp_path)])
        except SystemExit as exc:
            assert exc.code != 2, "the CLI still refused --cwd with the guard removed"
        except Exception:  # noqa: BLE001 — a later failure is not this claim
            pass

    @pytest.mark.hook_e2e
    @pytest.mark.slow
    def test_without_the_discriminator_the_courier_goes_quiet_again(self, tmp_path):
        """`looks_like_a_record` is what turns the silent path into a warning.

        Asserted through the module the couriers import rather than through a
        copy: a courier that grew its own version of the check would pass this
        while the four drifted apart.
        """
        import _recorded_command  # noqa: PLC0415 — see the module docstring

        wrapped = (
            "poetry run python ${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/"
            "stale_sweep.py --record --present BH-001"
        )
        tail = os.path.join("enforcement", "scripts", "stale_sweep.py")
        assert _recorded_command.looks_like_a_record(wrapped, tail)

        without_record = wrapped.replace(" --record", "")
        assert not _recorded_command.looks_like_a_record(without_record, tail)
        assert "NOT recorded" not in _warning(
            "stale_sweep_courier.py", without_record, str(tmp_path))

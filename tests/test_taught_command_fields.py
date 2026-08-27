"""F3-V — the taught-command field check runs, and reports per command.

Two layers, because one of them can run in CI and the other is the only thing
that proves the first is asking the engine's question rather than a plausible
imitation of it:

* **static** — read `events.toml`, read every taught `sahjhan event … --field`
  form, and report per command. No daemon, so it runs everywhere.
* **`real_daemon`** — take the string a skill file actually teaches and run it
  against the binary. If the static layer says a field is missing, the engine
  must refuse the command for that field.

W01 ships no product change, so the static check exits non-zero against this
tree. That is the point: it reproduces item 31. W03 fixes the taught forms and
wires the check into `contract_gate.py`, and only then does exit 0 mean
anything.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import taught_commands as tc  # noqa: E402

pytestmark = pytest.mark.contract

#: The full-field form `phase-fix-loop.md` step 3 and `hooks.toml`'s TDD block
#: message both teach. Spelled once here so a test cannot drift from the file.
_TDD_RECORD = (
    "sahjhan event test_failed_before_fix "
    "--field project=holtz --field run=1 --field auditor=holtz "
    "--field finding_id=BH-001 --field test_name=test_thing"
)


def _span(text: str, *, source: str = "x.md", line: int = 1, origin: str = "inline"):
    return tc.CommandSpan(source=source, line=line, origin=origin, text=text)


class TestItReadsTheSchemaRatherThanRestatingIt:
    def test_required_fields_come_from_events_toml(self):
        required = tc.load_required_fields()
        assert required["test_failed_before_fix"] == {
            "finding_id", "test_name", "project", "run", "auditor",
        }

    def test_an_optional_field_is_not_required(self):
        """`pattern_id` is `optional = true` on `finding` — the flag must count."""
        required = tc.load_required_fields()
        assert "pattern_id" not in required["finding"]
        assert "id" in required["finding"]


class TestItSeesBothSources:
    def test_it_reads_inline_backticks_not_only_fenced_blocks(self):
        """`contract_gate.extract_sahjhan_commands` reads fences only.

        Six of item 31's commands are inline, which is how they were missed.
        """
        commands = tc.all_taught_commands()
        origins = {c.origin for c in commands}
        assert "inline" in origins
        assert "fenced" in origins

    def test_it_reads_hooks_toml_block_messages(self):
        """The escape a blocked agent copies is not in any skill file."""
        commands = tc.commands_in_hook_messages()
        assert commands, "hooks.toml teaches at least one sahjhan event command"
        assert all(c.origin == "hooks.toml message" for c in commands)

    def test_a_bare_mention_is_not_a_taught_command(self):
        """Prose naming the tool is not a form anyone is told to type."""
        assert tc._commands_in(_span("sahjhan event finding")) == []


class TestItReportsPerCommand:
    def test_every_command_gets_a_verdict(self):
        commands = tc.all_taught_commands()
        failures, lines = tc.report(commands)
        assert len(lines) == len(commands)
        assert failures == sum(1 for line in lines if line.strip().startswith(("MISSING", "UNKNOWN")))

    def test_it_names_the_field_and_the_place(self):
        """A report that says only "something is wrong" cannot drive a fix."""
        short = tc._commands_in(_span(
            "sahjhan event test_failed_before_fix --field finding_id=BH-001",
            source="phase-fix-loop.md", line=52,
        ))
        _failures, lines = tc.report(short)
        assert len(lines) == 1, lines
        assert "phase-fix-loop.md:52" in lines[0]
        assert "test_failed_before_fix" in lines[0]
        for field in ("project", "run", "auditor"):
            assert field in lines[0], lines[0]


class TestEveryTaughtFormIsRunnable:
    """W03: the whole tree passes, and the two named sites carry the same set."""

    def test_nothing_taught_is_missing_a_required_field(self):
        failures, lines = tc.report()
        assert failures == 0, "\n".join(
            line for line in lines if not line.strip().startswith("ok")
        )

    def test_the_taught_tdd_record_is_complete(self):
        command = next(
            c for c in tc.all_taught_commands()
            if c.source.endswith("phase-fix-loop.md")
            and c.event_type == "test_failed_before_fix"
        )
        assert tc.missing_fields(command) == set()

    def test_the_block_message_and_the_skill_file_teach_the_same_fields(self):
        """V5 — the two cannot drift apart again.

        `hooks.toml`'s message is the string a blocked agent copies; the skill
        file's step 3 is the string it was following when it got blocked. They
        described different commands, and only one of them was in any gate's
        scope. Compared as **field sets**, not as text: the two lines differ in
        wording (`--config-dir`, ordering) and always will.
        """
        skill = next(
            c for c in tc.all_taught_commands()
            if c.source.endswith("phase-fix-loop.md")
            and c.event_type == "test_failed_before_fix"
        )
        message = next(
            c for c in tc.commands_in_hook_messages()
            if c.event_type == "test_failed_before_fix"
        )
        assert skill.fields == message.fields, (
            f"skill file: {sorted(skill.fields)}\n"
            f"hooks.toml: {sorted(message.fields)}"
        )
        # Positive: both equal the schema, so "they agree" cannot be satisfied
        # by two identically-wrong commands.
        assert skill.fields >= tc.load_required_fields()["test_failed_before_fix"]

    def test_a_form_missing_one_field_is_reported(self):
        """V4 non-vacuity: drop `--field project=` and the check goes red.

        Without this, every assertion above would hold just as well against a
        `missing_fields` that always returned the empty set.
        """
        without_project = _TDD_RECORD.replace("--field project=holtz ", "")
        command = tc._commands_in(_span(without_project))[0]
        assert tc.missing_fields(command) == {"project"}

    def test_a_complete_form_reports_nothing_missing(self):
        command = tc._commands_in(_span(_TDD_RECORD))[0]
        assert tc.missing_fields(command) == set()


@pytest.mark.slow
@pytest.mark.integration
class TestTheEngineAgreesWithTheStaticCheck:
    """The second layer: what the binary does with the string we teach."""

    def _run(self, real_daemon, command_text: str) -> subprocess.CompletedProcess:
        args = command_text.split()
        assert args[0] == "sahjhan"
        return subprocess.run(
            [real_daemon["binary"], "--config-dir", real_daemon["config_dir"], *args[1:]],
            capture_output=True, text=True, timeout=15,
            cwd=real_daemon["project_root"],
        )

    def test_a_form_missing_a_field_is_refused_for_that_field(self, real_daemon):
        """The shape item 31 shipped: the taught form minus `project`.

        Not read from the skill file — the file is fixed now. This is the
        engine's half of the static check: when `missing_fields` says a field
        is absent, `sahjhan` refuses the command and names it.
        """
        result = self._run(
            real_daemon,
            "sahjhan event test_failed_before_fix "
            "--field finding_id=BH-001 --field test_name=test_thing",
        )
        combined = result.stdout + result.stderr
        # Positive claims about the observed values, not `!= 0` / "not empty":
        # a wrong-but-nonzero exit and a different error would both survive an
        # inequality, and this is the layer that proves the static check is
        # asking the engine's question.
        assert result.returncode == 4, combined
        assert "missing field 'project' for event 'test_failed_before_fix'" in combined, (
            combined
        )

    def test_the_full_form_is_accepted(self, real_daemon):
        """Non-vacuity: the difference is the fields, not the command."""
        from two_actors import TwoActors

        actors = TwoActors(real_daemon)
        actors.bootstrap()
        result = self._run(real_daemon, _TDD_RECORD)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_the_string_the_skill_file_teaches_runs(self, real_daemon):
        """V3 — the exact line from `phase-fix-loop.md`, not a paraphrase.

        Taken from the file at test time and run against the binary. A test
        carrying its own copy of the command would go green while the file it
        is supposed to be about drifted — which is the shape of item 31 itself.

        Only the placeholders a reader substitutes are substituted: `N`,
        `BH-NNN`, `...`, and `$CLAUDE_PLUGIN_ROOT`.
        """
        from two_actors import TwoActors

        actors = TwoActors(real_daemon)
        actors.bootstrap()

        taught = next(
            c for c in tc.all_taught_commands()
            if c.source.endswith("phase-fix-loop.md")
            and c.event_type == "test_failed_before_fix"
        )
        command = (
            taught.text
            .replace('--config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" ', "")
            .replace("--field run=N", "--field run=1")
            .replace("--field finding_id=BH-NNN", "--field finding_id=BH-001")
            .replace("--field test_name=...", "--field test_name=test_thing")
        )
        assert "BH-NNN" not in command and "run=N" not in command, command

        result = self._run(real_daemon, command)
        assert result.returncode == 0, (
            f"the taught command still does not run:\n{command}\n"
            + result.stdout + result.stderr
        )

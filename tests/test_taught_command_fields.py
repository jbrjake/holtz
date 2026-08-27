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
        found = tc._commands_in(
            "record findings via `sahjhan event finding` immediately",
            source="x.md", line=1, origin="inline",
        )
        assert found == []


class TestItReportsPerCommand:
    def test_every_command_gets_a_verdict(self):
        commands = tc.all_taught_commands()
        failures, lines = tc.report(commands)
        assert len(lines) == len(commands)
        assert failures == sum(1 for line in lines if line.strip().startswith(("MISSING", "UNKNOWN")))

    def test_it_names_the_field_and_the_place(self):
        """A report that says only "something is wrong" cannot drive a fix."""
        _failures, lines = tc.report()
        hit = [line for line in lines if "phase-fix-loop.md:52" in line]
        assert len(hit) == 1, lines
        assert "test_failed_before_fix" in hit[0]
        for field in ("project", "run", "auditor"):
            assert field in hit[0], hit[0]


class TestItReproducesItem31:
    """Positive claims about the omissions as they stand at this commit."""

    def test_the_taught_tdd_record_omits_three_required_fields(self):
        command = next(
            c for c in tc.all_taught_commands()
            if c.source.endswith("phase-fix-loop.md")
            and c.event_type == "test_failed_before_fix"
        )
        assert tc.missing_fields(command) == {"project", "run", "auditor"}

    def test_the_gates_own_escape_omits_the_same_three(self):
        command = next(
            c for c in tc.commands_in_hook_messages()
            if c.event_type == "test_failed_before_fix"
        )
        assert tc.missing_fields(command) == {"project", "run", "auditor"}

    def test_a_complete_form_reports_nothing_missing(self):
        """Non-vacuity: the check is capable of passing.

        Without this, every assertion above would hold just as well against a
        function that reported every field of every event as missing.
        """
        complete = tc._commands_in(
            "sahjhan event test_failed_before_fix --field finding_id=BH-001 "
            "--field test_name=t --field project=holtz --field run=1 "
            "--field auditor=holtz",
            source="x.md", line=1, origin="inline",
        )[0]
        assert tc.missing_fields(complete) == set()


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

    def test_the_taught_tdd_record_is_refused_for_a_named_field(self, real_daemon):
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
        result = self._run(
            real_daemon,
            "sahjhan event test_failed_before_fix "
            "--field finding_id=BH-001 --field test_name=test_thing "
            "--field project=holtz --field run=1 --field auditor=holtz",
        )
        assert result.returncode == 0, result.stdout + result.stderr

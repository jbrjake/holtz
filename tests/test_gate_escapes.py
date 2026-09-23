"""W25 / item 11, V2 — a blocking gate prints an escape, and the escape runs.

Of item 11's four gates, two no longer gate anything: `all_findings_closed`
left `converge` and lens completion under W07, and `medium_deferral_budget`'s
self-contradictory `converge` seat was deleted by W05 (pinned by
`test_convergence_redefinition.py` and `test_medium_budget_seats.py`). The
amplification seat on `converge` names `defer batch`, and W14 drives it end to
end (`test_the_batch_plus_the_round_it_buys_clears_converge`).

That leaves `quiz_exhaustions_resolved`, the gate `48c72fd` left printing
*"no unresolved quiz exhaustions"* and nothing else. Its escape is the one
event in the protocol a person writes, so the test does what the person does:
it reads the command out of `phase-convergence.md`'s fenced block and runs it.

`quiz_exhausted` is `restricted`, and a test process cannot author a
restricted event. So the run uses a config **derived from `enforcement/` at
test time** with that single flag cleared — never a pasted copy that could
drift from the one it stands in for.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "enforcement"
DOC = REPO_ROOT / "skills" / "holtz" / "references" / "phase-convergence.md"
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))

LENS = "security"

pytestmark = pytest.mark.integration


def _derived_plugin_root(tmp_path: Path) -> Path:
    """A plugin root whose `enforcement/` is the real one, `quiz_exhausted`
    unrestricted — the one change the test needs, and asserted to be one."""
    root = tmp_path / "plugin"
    shutil.copytree(CONFIG_DIR, root / "enforcement")
    events = root / "enforcement" / "events.toml"
    text = events.read_text(encoding="utf-8")
    start = text.index("[events.quiz_exhausted]\n")
    end = text.index("\n[", start + 1)
    block = text[start:end]
    assert block.count("restricted = true\n") == 1, block
    events.write_text(
        text[:start] + block.replace("restricted = true\n", "") + text[end:],
        encoding="utf-8",
    )
    return root


class _Project:
    def __init__(self, tmp_path: Path) -> None:
        from _resolve import ensure_sahjhan

        binary = ensure_sahjhan()
        if not binary:
            pytest.skip("sahjhan binary not available")
        self.binary = binary
        self.plugin = _derived_plugin_root(tmp_path)
        self.config = str(self.plugin / "enforcement")
        self.root = tmp_path / "project"
        self.root.mkdir()
        # `converge` also runs the lint and the suite gate; neither is under
        # test here, and both are cheap to answer without running anything.
        self.env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(self.plugin), "HOLTZ_LINT": "true"}
        self.sah("init")
        self.sah("ledger", "create", "--from", "run", "1", "--activate")

    def sah(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [self.binary, "--config-dir", self.config, *args],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def quiz_line(self) -> str:
        out = subprocess.run(
            [self.binary, "--config-dir", self.config, "gate", "check", "converge"],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=300,
        ).stdout
        lines = [ln for ln in out.splitlines() if "quiz_exhaustions_resolved" in ln]
        assert len(lines) == 1, out
        return lines[0]


def _taught_escape() -> str:
    """The `! sahjhan … event quiz_exhausted_resolved …` line the doc teaches."""
    fenced = re.findall(r"```bash\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)
    lines = [
        ln.strip() for block in fenced for ln in block.splitlines()
        if "event quiz_exhausted_resolved" in ln
    ]
    assert len(lines) == 1, lines
    return lines[0]


class TestTheQuizGateNamesTheHumanEscape:

    def test_the_block_names_it_and_the_taught_command_clears_it(self, tmp_path):
        project = _Project(tmp_path)
        project.sah("event", "state_transition", "--field", "from=all_perspectives_clean",
                    "--field", "to=final_sweep", "--field", "command=final_sweep_start")
        project.sah("event", "quiz_exhausted", "--field", "project=t", "--field", "run=1",
                    "--field", "auditor=holtz", "--field", f"perspective={LENS}")

        blocked = project.quiz_line()
        assert "✗" in blocked, blocked
        assert "`! sahjhan event quiz_exhausted_resolved`" in blocked, (
            f"the refusal must name the human's command:\n{blocked}"
        )

        taught = _taught_escape()
        assert taught.startswith("! "), taught
        command = (
            taught[2:]
            .replace("<project>", "t").replace("<run>", "1").replace("<lens>", LENS)
        )
        assert "<" not in command, f"an unfilled placeholder in the taught command: {command}"
        ran = subprocess.run(
            command.replace("sahjhan ", f"{project.binary} ", 1),
            shell=True, cwd=project.root, env=project.env,
            capture_output=True, text=True, timeout=60,
        )
        assert ran.returncode == 0, f"{command}\n{ran.stdout}\n{ran.stderr}"

        cleared = project.quiz_line()
        assert "✓" in cleared and "✗" not in cleared, cleared

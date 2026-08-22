"""Holtz's own procedure reads the worklist with `findings.py`, never the file.

`docs/holtz/PUNCHLIST.md` is rendered as a six-column table.
`validate_punchlist.py` parses `### BH-NNN:` prose blocks and exits
``ERROR: No punchlist items found`` on the render — verified against a real
rendered punchlist, not inferred. So any Holtz step that reads the worklist
through that parser is a mandated command that always fails, which is why
`findings.py` was written.

P0.4 removed those calls from the fix loop and missed the convergence loop,
where the invocation used a `<path>` placeholder rather than a managed
filename and so matched no path-based check. The invariant with teeth is not
about paths: it is that Holtz's procedure has exactly one worklist lookup.

Justine is exempt. `docs/holtz/justine/` is her own tree, nothing renders it,
and her punchlist really is the prose format this parser wants.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = REPO_ROOT / "skills" / "holtz" / "references"

# Flags that mean "read the worklist through this parser", as opposed to
# validating a prose punchlist's structure.
READ_MODES = ("--filter-status", "--render", "--resolved-before")

JUSTINE_OWNED = {"justine-skill.md", "status-file-format.md"}


def _holtz_procedure() -> list[Path]:
    """The documents that drive a Holtz run's own steps."""
    files = sorted(REFERENCES.glob("phase-*.md"))
    files += [REFERENCES / "step-10-fix-loop.md"]
    files = [f for f in files if f.name not in JUSTINE_OWNED]
    assert files, "no phase documents found — the glob is wrong"
    return files


def test_no_holtz_step_reads_the_worklist_through_the_prose_parser():
    offenders = []
    for path in _holtz_procedure():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "validate_punchlist.py" not in line:
                continue
            if any(flag in line for flag in READ_MODES):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno} {line.strip()}")

    assert not offenders, (
        "Holtz steps read the worklist through `validate_punchlist.py`, which "
        "cannot parse the rendered punchlist:\n  " + "\n  ".join(offenders) + "\n\n"
        "Use `findings.py list` — it reads the ledger the punchlist is a view of."
    )


@pytest.mark.parametrize("name", ["phase-fix-loop.md", "phase-convergence.md"])
def test_the_loops_that_re_read_the_worklist_name_the_query(name):
    text = (REFERENCES / name).read_text(encoding="utf-8")
    assert "findings.py list" in text, (
        f"{name} re-reads the worklist each iteration but names no lookup"
    )


class TestTheResweepIsScoped:
    """Step 16 was *"Full re-run of Steps 6-8"* — the phase that produced 124
    findings in 143.7 min — run again at the end of a converging run. Its own
    stated job is catching what the fixes introduced, which is a file set the
    run can name."""

    def _step_16(self) -> list[str]:
        text = (REFERENCES / "phase-convergence.md").read_text(encoding="utf-8")
        assert "### Step 16" in text, "phase-convergence.md has no Step 16"
        return text.split("### Step 16", 1)[1].splitlines()

    def test_the_changed_files_are_derived_before_the_sweep_is_dispatched(self):
        """The document's own order: a sweep dispatched before the scope is
        derived is the full sweep with extra steps."""
        lines = self._step_16()
        diff = next((i for i, ln in enumerate(lines) if "git diff" in ln), None)
        dispatch = next((i for i, ln in enumerate(lines)
                         if "ispatch" in ln), None)

        assert diff is not None, "Step 16 never derives the files the run changed"
        assert dispatch is not None, "Step 16 never dispatches the sweep"
        assert diff < dispatch, (
            f"Step 16 dispatches the sweep at line {dispatch} before deriving "
            f"its scope at line {diff}"
        )

    def test_the_scope_widens_to_dependents(self):
        """A fix in one file can break its callers, so the changed set alone is
        not the affected set."""
        body = "\n".join(self._step_16())
        assert "blast_radius" in body, (
            "Step 16 sweeps only the changed files — nothing widens the scope "
            "to what depends on them"
        )

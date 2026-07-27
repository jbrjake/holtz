"""Guardrail: the fix-loop subagent contract must stay internally coherent.

Commit 800624f shipped "subagent-dispatched fixes" as a docs-only change whose
subagent contract contradicted itself: it said both "delegated to subagents"
*and* "returns artifacts only / must NOT modify the enforced working tree", and
the enforcement hooks were never wired to match. A downstream consumer's
subagent got hard-blocked (TDD gate + stall) because the doc told it to author
artifacts and avoid Sahjhan — the exact opposite of what the gate requires.

These tests fail if the docs drift back to that incoherent, artifact-only
state. The live invariant is enforced separately by
tests/test_sahjhan_integration.py::TestPreToolHookSubagentTddParity (the hook
treats a subagent identically to the main agent). This file guards the *prose*
that tells the orchestrator how to drive the subagent, so the two can't
silently diverge again.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "holtz"

# Files that describe the fix-loop subagent's division of labour.
_CONTRACT_FILES = [
    SKILL_DIR / "SKILL.md",
    SKILL_DIR / "references" / "phase-fix-loop.md",
    SKILL_DIR / "references" / "step-10-fix-loop.md",
]

# Phrases from the retired artifact-only contract. Their return means the docs
# once again tell the subagent NOT to run the very protocol its edits are gated
# on — which is what made the feature unshippable the first time.
_FORBIDDEN = (
    "returns artifacts only",
    "must not modify the enforced working tree",
    "must not record any sahjhan event",
    "does not commit, does not record",
    "returns compact artifacts",
)


@pytest.mark.parametrize("path", _CONTRACT_FILES, ids=lambda p: p.name)
def test_no_artifact_only_contract(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for phrase in _FORBIDDEN:
        assert phrase not in text, (
            f"{path.name} contains retired artifact-only contract language "
            f"({phrase!r}). The fix-loop subagent works IN the enforced tree and "
            f"runs the TDD protocol itself (fix_start -> failing test -> "
            f"test_failed_before_fix -> fix -> suite -> hardening); it does not "
            f"return artifacts for the orchestrator to apply. See "
            f"references/phase-fix-loop.md Step A."
        )


def test_phase_fix_loop_affirms_in_tree_tdd() -> None:
    """phase-fix-loop.md must positively state that the subagent works in the
    enforced tree and records test_failed_before_fix, gated by the pre-edit
    hook. This is the counterpart to the forbidden-phrase check: the doc cannot
    silently revert to artifact-only without also dropping these affirmations."""
    text = (SKILL_DIR / "references" / "phase-fix-loop.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "enforced working tree" in lowered, (
        "phase-fix-loop.md must say the subagent works in the enforced working tree"
    )
    assert "test_failed_before_fix" in text, (
        "phase-fix-loop.md must have the subagent record test_failed_before_fix"
    )
    assert "pre-edit hook" in lowered, (
        "phase-fix-loop.md must name the pre-edit hook as the mechanism that "
        "enforces TDD on the subagent"
    )


def test_orchestrator_keeps_commit_and_transition() -> None:
    """The orchestrator, not the subagent, owns git commits and protocol-state
    transitions. Both must be stated so the linear-git/ledger invariant holds."""
    text = (SKILL_DIR / "references" / "phase-fix-loop.md").read_text(encoding="utf-8")
    assert "fix_commit" in text
    assert "git commit" in text.lower()


def test_per_item_procedure_couples_fix_commit_to_resolution() -> None:
    """The Per-Item Fix Procedure must tie `fix_commit` to `finding_resolved`.

    The bug this guards: the procedure recorded the fix_commit *transition* but
    never a finding_resolved *event*. STATUS/PUNCHLIST "Resolved" and the
    perspective/pattern/convergence gates all read finding_resolved, so an audit
    following the procedure verbatim resolved zero findings and could not
    converge. The fix makes `fix_commit` auto-emit `finding_resolved`; the doc
    must say so, so it can't drift back to a commit+transition that resolves
    nothing.
    """
    text = (SKILL_DIR / "references" / "phase-fix-loop.md").read_text(encoding="utf-8")
    assert "finding_resolved" in text, (
        "phase-fix-loop.md must explain that fix_commit records finding_resolved."
    )
    lowered = text.lower()
    assert "auto-record" in lowered or "auto-emit" in lowered or "auto record" in lowered, (
        "phase-fix-loop.md must state that fix_commit auto-records the "
        "finding_resolved resolution (so agents don't record it by hand)."
    )


def _fix_loop_lines() -> list[str]:
    return (
        (SKILL_DIR / "references" / "phase-fix-loop.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )


def test_subagent_proves_the_suite_instead_of_asserting_it() -> None:
    """The subagent's suite step must produce evidence, not a claim.

    It used to read "Run full suite. Confirm all pass." — a report the
    orchestrator could only take on faith, which is why the orchestrator ran
    the suite again and the gate ran it a third time. `--record` binds the
    result to a hash of the working tree, so the next two steps can read it.
    """
    text = "\n".join(_fix_loop_lines())
    assert "verify_suite.py --record --scope affected" in text, (
        "the fix subagent must record a suite_green, not report a pass-count"
    )
    assert "Run full suite. Confirm all pass." not in text, (
        "retired: an unevidenced suite claim forces the orchestrator to re-run"
    )


def test_orchestrator_reads_the_evidence_instead_of_re_running() -> None:
    """B.10 validates by ledger read. Re-running is the cost T4 removed."""
    text = "\n".join(_fix_loop_lines())
    assert "verify_suite.py --check --scope affected" in text, (
        "the orchestrator must validate the subagent's green by checking the "
        "ledger for this tree"
    )
    assert "re-run the full suite" not in text.lower(), (
        "retired: the orchestrator's re-run and the gate's run execute on a "
        "byte-identical tree, so one of them is pure waste"
    )


def test_the_commit_needs_no_second_green() -> None:
    """The tree hash names content, so `git commit` cannot invalidate a green.

    While the hash included HEAD's oid the loop had to record twice per fix —
    once for the orchestrator to read, once more after the commit purely to
    restore evidence the commit had invalidated without changing a byte. That
    second record is the last of the three original suite runs, and its
    absence here is what makes the collapse a real 3 -> 1. Pinned by
    TestTreeHash::test_committing_the_same_content_preserves_it on the other
    side of the seam.
    """
    lines = _fix_loop_lines()
    commit = [i for i, line in enumerate(lines) if "`git commit` with finding ID" in line]
    assert len(commit) == 1, f"expected one commit step, found {len(commit)}"
    late = [
        line
        for i, line in enumerate(lines)
        if i > commit[0] and "verify_suite.py --record --scope affected" in line
    ]
    assert not late, (
        "a per-fix green must not be re-recorded after the commit — the hash is "
        f"content-addressed, so step 10's evidence still holds. Found: {late}"
    )


def test_the_subagent_records_the_green_last() -> None:
    """Nothing may change the tree between the record and the orchestrator's read.

    The subagent writes a hardening test (`hardening_complete`) as its final
    piece of work. Record the green before that write and the hardening test
    lands *after* the tree it was proven on, so the orchestrator's `--check`
    recomputes a hash no green names, and the fix loop rejects a fix that is
    perfectly good. That is not hypothetical: it shipped in v0.141.2, where
    the record sat at subagent step 5 and the hardening write at step 8.

    So the ordering rule is stronger than "before the commit": the record must
    be the subagent's *last* step.
    """
    lines = _fix_loop_lines()
    record = [i for i, line in enumerate(lines) if "verify_suite.py --record --scope affected" in line]
    assert len(record) == 1, f"expected one per-fix record, found {len(record)}"
    # `event hardening_complete`, not the bare event name: the orchestrator's
    # step 10 also names `hardening_complete` when listing what it reads out of
    # the ledger, and that mention is not a step that writes to the tree.
    hardening = [i for i, line in enumerate(lines) if "event hardening_complete" in line]
    assert len(hardening) == 1, (
        f"expected one hardening_complete recording step, found {len(hardening)}"
    )
    assert record[0] > hardening[0], (
        "the suite green must be recorded after the hardening test is written "
        "and its event recorded — otherwise the hardening write invalidates "
        "the very green the orchestrator is about to read"
    )
    validate = [i for i, line in enumerate(lines) if "verify_suite.py --check --scope affected" in line]
    assert validate and record[0] < min(validate), (
        "and still before the orchestrator reads it"
    )


def test_the_full_scope_transitions_are_taught() -> None:
    """`affected` is only sound because something periodically runs everything.

    The three transitions whose gates demand `--scope full` must be named
    together with the command that satisfies them. A skill file that teaches
    the narrowing but not the re-basing leaves the agent blocked at the first
    /clear with no instruction that clears it.
    """
    text = "\n".join(_fix_loop_lines())
    assert "verify_suite.py --record --scope full" in text
    for command in ("iteration_boundary", "set complete perspective", "converge"):
        assert command in text, f"{command} needs a full green; say so"


def test_step_10_cross_references_resolution_event() -> None:
    """step-10-fix-loop.md's triage paths end at 'Commit'; it must point at the
    resolution event so a reader of that file alone doesn't think commit is the
    last enforcement action."""
    text = (SKILL_DIR / "references" / "step-10-fix-loop.md").read_text(encoding="utf-8")
    assert "finding_resolved" in text, (
        "step-10-fix-loop.md must reference the finding_resolved ledger event so "
        "its triage paths don't imply commit alone resolves a finding."
    )

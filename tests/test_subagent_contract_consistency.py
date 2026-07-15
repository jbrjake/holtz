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

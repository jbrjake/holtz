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

import re
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


def test_step_10_does_not_mandate_a_second_suite_run() -> None:
    """Two docs described the same tail suite run, and one of them recorded nothing.

    `phase-fix-loop.md` Step A.9 runs the suite once, last, and records
    `suite_green` for the tree. `step-10-fix-loop.md`'s hardening section told
    the subagent to "run full suite again after any hardening tests are added"
    — a bare run that records nothing, in a place where the recorded run has
    not happened yet. Measured across one run: 45 back-to-back full-suite runs
    with an identical pass count within 5 minutes.

    Worse than duplicated, it was ordered wrong. It sat before the blast-radius
    section, while Step A puts blast radius first, so the two files disagreed
    about the sequence a subagent performs — the class of defect that shipped
    v0.141.2.
    """
    text = (SKILL_DIR / "references" / "step-10-fix-loop.md").read_text(encoding="utf-8")
    assert "Run full suite again" not in text, (
        "step-10-fix-loop.md mandates a second tail suite run; Step A.9's "
        "recorded run is the one that counts, and it must come after the "
        "hardening tests this section writes"
    )


def test_the_fix_loop_routes_by_the_measured_criteria_not_by_triage_path() -> None:
    """`phase-audit.md` routes its subagents by task; the fix loop routed none.

    97 of 107 subagents in the measured run were Opus, including every fix
    agent, so the line has to exist. It also has to be the line that was asked
    for: P1.2 names two criteria — a test that can't fail, and a fix confined
    to one file, together about 30 of 59 fix agents. Routing by triage path
    instead is a different rule over a different population; a deterministic
    bug spanning four files is Fast Path and is not a single-file fix.
    """
    routing = next(
        (line for line in _fix_loop_lines() if line.startswith("**Model routing:**")),
        None,
    )
    assert routing is not None, "phase-fix-loop.md has no model routing line"
    assert 'model: "sonnet"' in routing, "the routing line names no cheaper model"
    assert "can't fail" in routing, (
        "the routing line must name the vacuous-test criterion — it is half "
        "the qualifying population"
    )
    assert "one file" in routing, (
        "the routing line must name the single-file criterion — it is the "
        "other half"
    )
    assert "Fast Path" not in routing, (
        "routing by triage path is the proxy P1.2 was rebuilt away from: it "
        "sends multi-file deterministic bug fixes to the cheaper model and "
        "keeps single-file investigations on the expensive one"
    )


@pytest.mark.parametrize("doc", ["phase-audit.md", "justine-skill.md"])
def test_every_subagent_brief_numbers_the_compact_read(doc: str) -> None:
    """P2.2: the compactor was invoked once in a 24-round run.

    Where it appeared at all, it was clause (a) of a seven-clause sentence —
    the shape a reader skims past. Every subagent brief that mentions the
    brief must give the compact read its own numbered step, the same as the
    fix loop's pattern round does, and the count has to match the number of
    briefs so adding a third brief cannot quietly re-bury it.
    """
    text = (SKILL_DIR / "references" / doc).read_text(encoding="utf-8")
    lines = text.splitlines()

    briefs = sum(1 for line in lines if "**Subagent brief" in line)
    assert briefs, f"{doc} no longer briefs a subagent — update this test"

    numbered_reads = sum(
        1 for line in lines
        if re.match(r"^\s*\d+\.\s", line) and "pattern brief compact" in line.lower()
    )
    assert numbered_reads == briefs, (
        f"{doc} has {briefs} subagent brief(s) but {numbered_reads} numbered "
        f"compact-read step(s) — a brief that buries it in prose is the one "
        f"whose subagents read the whole 181 KB file"
    )

    assert "read the compact pattern brief by running" not in text, (
        f"{doc} still carries the compact read as a lettered clause inside a "
        f"run-on sentence"
    )


def test_the_pattern_round_reads_the_brief_compact() -> None:
    """The brief reached 181 KB against a ~400 B/entry spec, and the compactor
    that renders it 26x smaller was invoked once in the whole run — because the
    doc governing every pattern round never named it."""
    text = "\n".join(_fix_loop_lines())
    assert "pattern_brief_compact.py" in text, (
        "phase-fix-loop.md Step 11 must name the compactor; it is the doc every "
        "pattern round reads and the only place a whole-file read is prescribed"
    )


def test_step_10_cross_references_resolution_event() -> None:
    """step-10-fix-loop.md's triage paths end at 'Commit'; it must point at the
    resolution event so a reader of that file alone doesn't think commit is the
    last enforcement action."""
    text = (SKILL_DIR / "references" / "step-10-fix-loop.md").read_text(encoding="utf-8")
    assert "finding_resolved" in text, (
        "step-10-fix-loop.md must reference the finding_resolved ledger event so "
        "its triage paths don't imply commit alone resolves a finding."
    )


def test_the_stale_sweep_records_fix_start_before_deferring() -> None:
    """`defer cant-reproduce` gates on `fix_start` since the last transition.

    In the per-item fix path the subagent records `fix_start` at step 1, long
    before any deferral, so the gate is satisfied incidentally. The stale sweep
    has no fix subagent and no fix_start of its own — teach the deferral without
    it and every retirement the sweep finds is rejected by the gate. The step
    order is the whole contract here, so it is asserted on the document's own
    lines rather than by driving the gate.
    """
    lines = _fix_loop_lines()
    starts = [i for i, line in enumerate(lines) if "### Step 11b" in line]
    assert len(starts) == 1, f"expected one Step 11b heading, found {len(starts)}"
    ends = [i for i, line in enumerate(lines) if line.startswith("### ") and i > starts[0]]
    sweep = lines[starts[0]: ends[0] if ends else len(lines)]

    fix_start = [i for i, line in enumerate(sweep) if "event fix_start" in line]
    defer = [i for i, line in enumerate(sweep) if "defer cant-reproduce" in line]
    assert fix_start, (
        "Step 11b defers findings without recording `fix_start` — "
        "`defer_cant_reproduce` gates on it, so every retirement is rejected"
    )
    assert defer, "Step 11b no longer records the retirements it finds"
    assert min(fix_start) < min(defer), (
        "Step 11b must record `fix_start` before the deferral, not after"
    )

    investigation = [i for i, line in enumerate(sweep)
                     if "docs/holtz/investigations/" in line]
    assert investigation and min(investigation) < min(defer), (
        "`defer_cant_reproduce` also gates on a non-empty "
        "docs/holtz/investigations/<id>.md — Step 11b must write it first"
    )

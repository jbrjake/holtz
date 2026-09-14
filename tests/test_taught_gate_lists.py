"""Prose that restates a gate list drifts away from the gate (item 7).

`phase-convergence.md` step 4 told the agent that `converge` checks *"all
perspectives complete, suite passes, linters pass, zero open items, no protocol
violations"*. `zero open items` is `all_findings_closed`, which P0.1 removed
from the transition precisely because the audited run's open count rose 124 to
273 and fell once — it was unreachable, and a run driving toward it cannot
terminate. The gate had moved; the sentence had not, and nothing could tell.

The fix is not a better sentence. It is a test that reads the conjuncts out of
`transitions.toml` and requires the doc to name each one, so the next person to
change the gate finds this red instead of leaving a reader aimed at a gate that
no longer exists.

Named queries only. The other conjuncts (`set_covered`, `command_succeeds`,
`file_exists`, `no_violations`) carry an intent rather than a name, and a check
on prose-vs-prose is the thing this file exists to avoid.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSITIONS = REPO_ROOT / "enforcement" / "transitions.toml"
EVENTS = REPO_ROOT / "enforcement" / "events.toml"
CONVERGENCE_DOC = REPO_ROOT / "skills" / "holtz" / "references" / "phase-convergence.md"
SKILL = REPO_ROOT / "skills" / "holtz" / "SKILL.md"

#: The line SKILL.md's reachability routing hangs off. Extraction is anchored
#: on it rather than on prose so the test reads a list, not a sentence.
_ROUTING_ANCHOR = "the `reachability` grade routes it:"


def _converge_query_names() -> list[str]:
    with open(TRANSITIONS, "rb") as fh:
        transitions = tomllib.load(fh)["transitions"]
    converge = [t for t in transitions if t.get("command") == "converge"]
    assert len(converge) == 1, f"expected one converge transition, found {len(converge)}"
    names = [g["query"] for g in converge[0].get("gates", []) if g.get("query")]
    assert names, "converge has no named-query conjuncts — has the gate moved?"
    return names


def test_the_doc_names_every_converge_query() -> None:
    text = CONVERGENCE_DOC.read_text(encoding="utf-8")
    missing = [name for name in _converge_query_names() if name not in text]
    assert not missing, (
        f"phase-convergence.md does not name {missing} — the agent reads this "
        f"file to know what `converge` will check, and a conjunct it cannot "
        f"see is one it cannot work toward. Run `sahjhan gate check converge` "
        f"and put every named query in step 4."
    )


def test_the_doc_does_not_name_a_retired_convergence_gate() -> None:
    """`all_findings_closed` is declared but attached to nothing.

    It is kept in `protocol.toml` as the one *named* spelling of "a finding is
    open", and `test_all_findings_closed_no_longer_gates_converge` guards the
    door. A doc that restates it as a convergence requirement re-attaches it in
    the only place that matters — the reader — where no gate test can see it.
    """
    text = CONVERGENCE_DOC.read_text(encoding="utf-8").lower()
    for phrase in ("zero open items", "all_findings_closed", "all findings closed"):
        assert phrase not in text, (
            f"phase-convergence.md tells the agent converge requires {phrase!r}. "
            f"P0.1 replaced that with the four conjuncts above; MEDIUM and LOW "
            f"may legitimately remain open at convergence."
        )


def _engine_reachability_grades() -> set[str]:
    """The `reachability` field's domain, read from the pattern the engine enforces."""
    with open(EVENTS, "rb") as fh:
        events = tomllib.load(fh)["events"]
    patterns = {
        field["pattern"]
        for event in events.values()
        for field in event.get("fields", [])
        if field.get("name") == "reachability" and field.get("pattern")
    }
    assert len(patterns) == 1, f"reachability is declared with {patterns} — which one binds?"
    pattern = patterns.pop()
    match = re.fullmatch(r"\^\(([^)]+)\)\$", pattern)
    assert match, f"cannot read the alternatives out of {pattern!r}"
    return set(match.group(1).split("|"))


def _skill_reachability_grades() -> set[str]:
    """The grades SKILL.md routes, taken from its list rather than its prose."""
    lines = SKILL.read_text(encoding="utf-8").splitlines()
    anchors = [i for i, line in enumerate(lines) if _ROUTING_ANCHOR in line]
    assert len(anchors) == 1, (
        f"expected one reachability routing anchor ({_ROUTING_ANCHOR!r}) in "
        f"SKILL.md, found {len(anchors)}"
    )
    grades = set()
    for line in lines[anchors[0] + 1:]:
        match = re.match(r"\s*[-*]\s+`([a-z_]+)`", line)
        if match:
            grades.add(match.group(1))
            continue
        # Markdown puts a blank line between a paragraph and the list under
        # it. Stopping on the first non-item would read an empty list and
        # report "the doc names no grades" for a doc that names all three.
        if line.strip():
            break
    return grades


def test_skill_md_routes_exactly_the_grades_the_engine_accepts() -> None:
    """Item 8 — the deferral rules named no reachability grade at all.

    `reachability` appeared once in the whole of SKILL.md, as a field in an
    example, while the rules said only *"CRITICAL/HIGH must be fixed; LOW,
    budget-capped MEDIUM, and can't-reproduce may be deferred."* Severity is
    half the routing: only `user_reachable` is fix-loop eligible,
    `fault_injected` batches at Step 15, and `theoretical` is deferred by the
    courier. An agent reading the old rules drives a `theoretical` CRITICAL
    into the fix loop and a `fault_injected` one into `converge`, where
    `no_open_fault_injected` refuses it two doors from the end.

    Set equality both ways: a grade the engine accepts and the doc omits
    strands the agent, and a grade the doc invents is a command that fails.
    """
    assert _skill_reachability_grades() == _engine_reachability_grades()

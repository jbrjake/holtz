"""P4.1: `merge_punchlists.py` — the merge is a script, not a subagent's prose.

`merge-protocol.md:11` calls the merge *"mechanical — it follows the
classification rules below without judgment calls, except for contradictions"*,
and `:165` calls it deterministic. It ran 36.7 minutes as a Sonnet subagent
hand-writing throwaway `python3 -c` scripts over 354 Holtz findings and 33 of
Justine's. The clause's remedy is a script plus one residual agent job:
adjudicating contradiction candidates.

The tests are organised around the parts an LLM merge gets wrong and a green
suite would not notice:

* **One-to-one matching.** "Scan all unmatched Justine items" is a claim about
  a shrinking pool. A per-item independent decision matches one Justine finding
  to two Holtz findings and inflates the agreement count.
* **A severity disagreement is an Agreement.** The protocol says so twice and
  says explicitly it is *not* double-counted. Two counts that must agree.
* **The 5-line threshold is inclusive, and 6 is not a match** — the boundary
  `merge-examples.md` spends a whole example on.
* **Contradictions are candidates, never verdicts.** The script may not resolve
  one; if it ever does, the clause's residual agent job has been deleted.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
SKILL_SCRIPTS = os.path.join(REPO_ROOT, "skills", "holtz", "scripts")
sys.path.insert(0, SKILL_SCRIPTS)
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, HOOKS_DIR)

import merge_punchlists as mp  # noqa: E402
import validate_merge_report  # noqa: E402

import validate_punchlist as vp  # noqa: E402

# One well-formed item, parameterised by the lens it states.
_ITEM_TEMPLATE = """\
### BJ-{num:03d}: Item {num}
**Severity:** LOW
**Category:** bug/logic
**Location:** `mod{num}.py:1`
**Status:** OPEN
**Lens:** {lens}

**Problem:** Something is wrong in a way that takes a full sentence to say.

**Evidence:** The evidence, also long enough to satisfy the length check.

**Discovery Chain:** read it -> saw it -> concluded it

**Acceptance Criteria:**
- [ ] fixed

**Validation Command:**
```bash
pytest
```
"""

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=audit", "--field", "step=8"]


def _binary():
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _named_query(name):
    """A predicate read from `protocol.toml`, never restated here.

    Asserting a consequence through the query the production code actually
    runs is what makes the assertion follow a config edit instead of drifting
    from one.
    """
    try:
        import tomllib  # noqa: PLC0415
    except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
        import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
    with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
        queries = tomllib.load(fh)["queries"]
    assert name in queries, f"protocol.toml has no [queries.{name}]"
    return queries[name]["sql"]


def _flat(row):
    """One ledger row as a single mapping.

    `sahjhan query --format jsonl` puts declared fields under `fields` and the
    envelope at the top level, and which keys land where has moved between
    versions. Flattening once here is what lets a test compare two filings
    field by field instead of naming the fields it happens to remember.
    """
    return {**row.get("fields", {}), **{k: v for k, v in row.items() if k != "fields"}}


#: The envelope keys `_declared` must never let into a field comparison. `prev`
#: is the hash-chain link, so it differs between *any* two events by
#: construction — including two that carry identical fields.
_ENVELOPE = ("seq", "ts", "timestamp", "hash", "prev", "prev_hash", "type")


def _declared(row):
    """Just the event's own fields — the envelope dropped, by name.

    Used where a test compares two filings of one finding. `prev` alone would
    make every such comparison fail for a reason that says nothing about the
    merge, and adding it to a test-local ignore list would hide the next
    envelope key that shows up. The guard below is what stops this returning
    an empty mapping and passing vacuously.
    """
    fields = {k: v for k, v in _flat(row).items() if k not in _ENVELOPE}
    assert {"id", "severity", "reachability"} <= set(fields), (
        f"the row shape changed — this comparison would be vacuous: {fields}"
    )
    return fields


def holtz(finding_id, severity="HIGH", category="bug/logic", location="a.py:10",
          description="x", reachability="user_reachable"):
    return mp.Finding(id=finding_id, severity=severity, category=category,
                      location=location, description=description,
                      reachability=reachability)


def justine(finding_id, severity="HIGH", category="bug/logic", location="a.py:10",
            description="x", reachability="user_reachable"):
    return mp.Finding(id=finding_id, severity=severity, category=category,
                      location=location, description=description,
                      reachability=reachability)


# ── Location ─────────────────────────────────────────────────────────────────


class TestLocation:
    """`location` is free text; matching needs a path, a line and a symbol."""

    def test_a_backticked_file_and_line(self):
        assert mp.parse_location("`app/routes/auth.py:47`") == mp.Location(
            "app/routes/auth.py", 47, None)

    def test_a_bare_file_and_line(self):
        assert mp.parse_location("README.md:34") == mp.Location("README.md", 34, None)

    def test_a_file_with_no_line(self):
        assert mp.parse_location("app/db/queries.py") == mp.Location(
            "app/db/queries.py", None, None)

    def test_a_parenthesised_function(self):
        """`merge-examples.md:119`'s own spelling."""
        assert mp.parse_location("`app/models/order.py:88` (function `save_order`)") == \
            mp.Location("app/models/order.py", 88, "save_order")

    def test_a_symbol_with_no_line(self):
        assert mp.parse_location("app/models/order.py (class OrderStore)") == \
            mp.Location("app/models/order.py", None, "OrderStore")

    def test_a_line_range_keeps_its_start(self):
        assert mp.parse_location("std.py:736-740") == mp.Location("std.py", 736, None)


# ── "Same bug" ───────────────────────────────────────────────────────────────


class TestSameBug:
    """All three of file, category and proximity, per `merge-protocol.md:62`."""

    def test_a_different_file_is_not_the_same_bug(self):
        assert not mp.same_bug(holtz("BH-001", location="a.py:10"),
                               justine("BJ-001", location="b.py:10"))

    def test_a_different_category_is_not_the_same_bug(self):
        assert not mp.same_bug(holtz("BH-001", category="bug/logic"),
                               justine("BJ-001", category="test/missing"))

    def test_five_lines_apart_is_a_match(self):
        """Inclusive: `merge-protocol.md:67` says "within 5 … (inclusive)"."""
        assert mp.same_bug(holtz("BH-001", location="a.py:47"),
                           justine("BJ-001", location="a.py:52"))

    def test_six_lines_apart_is_not_a_match(self):
        """`merge-examples.md:219` Scenario B, the whole point of the example."""
        assert not mp.same_bug(holtz("BH-001", location="a.py:47"),
                               justine("BJ-001", location="a.py:53"))

    def test_an_exact_symbol_match_needs_no_lines(self):
        assert mp.same_bug(holtz("BH-001", location="a.py (function save_order)"),
                           justine("BJ-001", location="a.py (function save_order)"))

    def test_a_different_symbol_is_not_a_match(self):
        assert not mp.same_bug(holtz("BH-001", location="a.py (function save_order)"),
                              justine("BJ-001", location="a.py (function load_order)"))

    def test_neither_side_locates_so_file_and_category_suffice(self):
        """The location-free fallback, `merge-protocol.md:77`."""
        assert mp.same_bug(holtz("BH-001", location="a.py"),
                           justine("BJ-001", location="a.py"))

    def test_a_line_inside_the_named_function_body_matches(self, tmp_path):
        """The third proximity option: one side names a line, the other a
        symbol, and the line falls inside that symbol's body."""
        source = tmp_path / "a.py"
        source.write_text(
            "import os\n"
            "\n"
            "def save_order(x):\n"
            "    a = 1\n"
            "    b = 2\n"
            "    return a + b\n"
            "\n"
            "def other():\n"
            "    pass\n",
            encoding="utf-8",
        )
        assert mp.same_bug(holtz("BH-001", location="a.py:5"),
                           justine("BJ-001", location="a.py (function save_order)"),
                           cwd=str(tmp_path))

    def test_a_line_outside_the_named_function_body_does_not_match(self, tmp_path):
        source = tmp_path / "a.py"
        source.write_text(
            "import os\n"
            "\n"
            "def save_order(x):\n"
            "    return 1\n"
            "\n"
            "def other():\n"
            "    pass\n",
            encoding="utf-8",
        )
        assert not mp.same_bug(holtz("BH-001", location="a.py:7"),
                               justine("BJ-001", location="a.py (function save_order)"),
                               cwd=str(tmp_path))


# ── Classification ───────────────────────────────────────────────────────────


class TestClassification:

    def test_a_matched_pair_is_an_agreement(self):
        result = mp.classify([holtz("BH-001")], [justine("BJ-001")])
        assert [(h.id, j.id) for h, j in result.agreements] == [("BH-001", "BJ-001")]
        assert result.holtz_only == [] and result.justine_only == []

    def test_an_unmatched_holtz_item_is_holtz_only(self):
        result = mp.classify([holtz("BH-001", location="a.py:10")],
                             [justine("BJ-001", location="b.py:10")])
        assert [f.id for f in result.holtz_only] == ["BH-001"]
        assert [f.id for f in result.justine_only] == ["BJ-001"]

    def test_a_severity_disagreement_is_also_an_agreement(self):
        """`merge-protocol.md:56`: counted in the Agreement total, listed
        separately, never double-counted. Two numbers that must agree."""
        result = mp.classify([holtz("BH-001", severity="CRITICAL")],
                             [justine("BJ-001", severity="HIGH")])
        assert len(result.agreements) == 1
        assert [(h.id, j.id) for h, j in result.severity_disagreements] == \
            [("BH-001", "BJ-001")]
        assert result.holtz_only == [] and result.justine_only == []

    def test_matching_is_one_to_one(self):
        """Two Holtz findings four lines apart both match one Justine item
        under a per-item decision. The pool shrinks: exactly one wins."""
        result = mp.classify(
            [holtz("BH-001", location="a.py:10"), holtz("BH-002", location="a.py:12")],
            [justine("BJ-001", location="a.py:11")],
        )
        assert len(result.agreements) == 1
        assert len(result.holtz_only) == 1
        assert result.justine_only == []

    def test_the_closest_by_line_wins(self):
        result = mp.classify(
            [holtz("BH-001", location="a.py:10")],
            [justine("BJ-009", location="a.py:14"), justine("BJ-002", location="a.py:11")],
        )
        assert [j.id for _, j in result.agreements] == ["BJ-002"]

    def test_an_equal_distance_breaks_to_the_lower_item_number(self):
        """`merge-protocol.md:76`, and the reason ordering is not incidental."""
        result = mp.classify(
            [holtz("BH-001", location="a.py:10")],
            [justine("BJ-009", location="a.py:12"), justine("BJ-002", location="a.py:8")],
        )
        assert [j.id for _, j in result.agreements] == ["BJ-002"]


# ── Contradictions stay the agent's job ──────────────────────────────────────


class TestContradictionCandidates:
    """The one classification the clause keeps for the agent."""

    def test_a_verification_phrase_over_a_shared_file_is_a_candidate(self):
        result = mp.classify(
            [holtz("BH-009", location="app/client/http.py:23")],
            [justine("BJ-015", location="app/client/http.py:23",
                     description="Verified: timeout=0 is intentional. This is "
                                 "correct behavior for httpx.")],
        )
        assert [f.id for f, _ in result.contradiction_candidates] == ["BJ-015"]

    def test_an_ordinary_finding_is_not_a_candidate(self):
        result = mp.classify(
            [holtz("BH-009", location="app/client/http.py:23")],
            [justine("BJ-015", location="app/client/http.py:23",
                     description="timeout=0 hangs forever.")],
        )
        assert result.contradiction_candidates == []

    def test_a_verification_phrase_about_an_unshared_file_is_not_a_candidate(self):
        """A candidate is a *disagreement*; nobody disagreed about b.py."""
        result = mp.classify(
            [holtz("BH-009", location="a.py:23")],
            [justine("BJ-015", location="b.py:23",
                     description="Confirmed this is intentional and correct behavior.")],
        )
        assert result.contradiction_candidates == []

    def test_the_script_never_resolves_a_candidate(self):
        """A contradiction candidate is still recorded per its own class —
        `merge-protocol.md:40`. Nothing is dropped or deferred by the script."""
        result = mp.classify(
            [holtz("BH-009", location="a.py:23", category="bug/logic")],
            [justine("BJ-015", location="b.py:99", category="doc/drift",
                     description="Verified this is correct behavior in a.py.")],
        )
        assert [f.id for f in result.justine_only] == ["BJ-015"]


# ── The report ───────────────────────────────────────────────────────────────


class TestReport:

    def _report(self, tmp_path, result):
        path = tmp_path / "MERGE-REPORT.md"
        path.write_text(mp.render_report(result, date="2026-08-25"), encoding="utf-8")
        return path

    def test_the_gate_passes_on_a_rendered_report(self, tmp_path):
        """The report the script writes must satisfy `merge_complete`'s own
        gate — the four sections, each non-empty."""
        result = mp.classify(
            [holtz("BH-001"), holtz("BH-002", location="z.py:1")],
            [justine("BJ-001"), justine("BJ-002", location="q.py:1")],
        )
        assert validate_merge_report.validate(str(self._report(tmp_path, result))) == []

    def test_the_gate_passes_when_nothing_matched(self, tmp_path):
        """An empty section is a gate failure, so the degenerate merge — no
        agreements at all — is the case that has to render a real body."""
        result = mp.classify([holtz("BH-001", location="a.py:1")],
                             [justine("BJ-001", location="b.py:1")])
        assert validate_merge_report.validate(str(self._report(tmp_path, result))) == []

    def test_the_agreement_total_includes_severity_disagreements(self, tmp_path):
        result = mp.classify([holtz("BH-001", severity="CRITICAL")],
                             [justine("BJ-001", severity="HIGH")])
        body = mp.render_report(result, date="2026-08-25")
        assert "## Agreement\n1 item" in body

    def test_blind_spots_name_the_categories_each_auditor_missed(self, tmp_path):
        result = mp.classify(
            [holtz("BH-001", location="a.py:1", category="bug/state")],
            [justine("BJ-001", location="README.md:3", category="doc/drift")],
        )
        body = mp.render_report(result, date="2026-08-25")
        holtz_line = next(x for x in body.splitlines() if "Holtz's blind spots" in x)
        justine_line = next(x for x in body.splitlines() if "Justine's blind spots" in x)
        assert "doc/drift" in holtz_line
        assert "bug/state" in justine_line

    def test_candidates_are_listed_for_review_not_decided(self, tmp_path):
        result = mp.classify(
            [holtz("BH-009", location="a.py:23")],
            [justine("BJ-015", location="a.py:23",
                     description="Confirmed intentional — correct behavior.")],
        )
        body = mp.render_report(result, date="2026-08-25")
        assert "BJ-015" in body.split("## Contradictions")[1]


# ── The impact graph ─────────────────────────────────────────────────────────


class TestGraphMerge:
    """`merge-protocol.md:146`'s five conflict rules, one test each."""

    def test_a_node_only_one_graph_has_is_added(self):
        merged = mp.merge_graphs({"nodes": {}, "edges": []},
                                 {"nodes": {"a": {"id": "a"}}, "edges": []})
        assert merged["nodes"]["a"] == {"id": "a"}

    def test_the_higher_risk_score_wins(self):
        merged = mp.merge_graphs(
            {"nodes": {"a": {"id": "a", "risk_score": 0.2}}, "edges": []},
            {"nodes": {"a": {"id": "a", "risk_score": 0.7}}, "edges": []},
        )
        assert merged["nodes"]["a"]["risk_score"] == 0.7

    def test_the_higher_risk_score_wins_from_either_side(self):
        merged = mp.merge_graphs(
            {"nodes": {"a": {"id": "a", "risk_score": 0.9}}, "edges": []},
            {"nodes": {"a": {"id": "a", "risk_score": 0.1}}, "edges": []},
        )
        assert merged["nodes"]["a"]["risk_score"] == 0.9

    def test_audit_counts_sum(self):
        merged = mp.merge_graphs(
            {"nodes": {"a": {"id": "a", "audit_count": 3}}, "edges": []},
            {"nodes": {"a": {"id": "a", "audit_count": 2}}, "edges": []},
        )
        assert merged["nodes"]["a"]["audit_count"] == 5

    def test_the_most_recent_audit_timestamp_wins(self):
        merged = mp.merge_graphs(
            {"nodes": {"a": {"id": "a", "last_audited": "2026-03-01"}}, "edges": []},
            {"nodes": {"a": {"id": "a", "last_audited": "2026-08-01"}}, "edges": []},
        )
        assert merged["nodes"]["a"]["last_audited"] == "2026-08-01"

    def test_different_edge_types_between_the_same_nodes_both_survive(self):
        merged = mp.merge_graphs(
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "imports"}]},
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "calls"}]},
        )
        assert {e["type"] for e in merged["edges"]} == {"imports", "calls"}

    def test_the_same_edge_keeps_the_more_recent_metadata(self):
        merged = mp.merge_graphs(
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "imports",
                                     "metadata": {"discovered": "2026-01-01",
                                                  "confidence": "low"}}]},
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "imports",
                                     "metadata": {"discovered": "2026-08-01",
                                                  "confidence": "high"}}]},
        )
        assert len(merged["edges"]) == 1
        assert merged["edges"][0]["metadata"]["confidence"] == "high"

    def test_the_other_auditors_note_is_appended(self):
        merged = mp.merge_graphs(
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "imports",
                                     "metadata": {"discovered": "2026-08-01",
                                                  "note": "canonical"}}]},
            {"nodes": {}, "edges": [{"source": "a", "target": "b", "type": "imports",
                                     "metadata": {"discovered": "2026-01-01",
                                                  "note": "justine saw it too"}}]},
        )
        assert "canonical" in merged["edges"][0]["metadata"]["note"]
        assert "justine saw it too" in merged["edges"][0]["metadata"]["note"]


# ── Reading Justine's punchlist ──────────────────────────────────────────────


_JUSTINE = """# Holtz Punchlist

## Items

### BJ-001: Missing validation
**Severity:** HIGH
**Reachability:** user_reachable
**Category:** bug/security
**Location:** `app/auth.py:47`
**Lens:** security

**Problem:** No email validation.

**Evidence:** grep shows no call.

**Discovery Chain:** a -> b

**Acceptance Criteria:**
- [ ] validated

**Validation Command:**
```bash
pytest
```

### BJ-002: Stale README
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:34`

**Problem:** References a removed dependency.

**Discovery Chain:** a -> b

**Acceptance Criteria:**
- [ ] fixed

**Validation Command:**
```bash
pytest
```
"""


class TestReadingJustine:

    def test_her_items_parse_into_findings(self, tmp_path):
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        found = mp.justine_findings(str(path))
        assert [f.id for f in found] == ["BJ-001", "BJ-002"]
        assert found[0].severity == "HIGH"
        assert found[0].category == "bug/security"
        assert found[0].reachability == "user_reachable"

    def test_the_description_carries_problem_evidence_and_chain(self, tmp_path):
        """`merge-protocol.md:51` — the event's description field is all three."""
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        description = mp.justine_findings(str(path))[0].description
        assert "No email validation" in description
        assert "grep shows no call" in description
        assert "a -> b" in description

    def test_an_unstated_reachability_is_theoretical(self, tmp_path):
        """Its own definition: no path found, reachability unestablished. The
        same answer `migrate_legacy.py` gives a finding that never stated one."""
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        assert mp.justine_findings(str(path))[1].reachability == "theoretical"

    def test_her_stated_lens_is_carried(self, tmp_path):
        """W06 — the merge re-files the lens she stated, not a default."""
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        assert mp.justine_findings(str(path))[0].perspective == "security"

    def test_the_fail_safe_is_unreachable_through_the_validated_path(self, tmp_path):
        """V5 — `unspecified` survives in the code and not on the board.

        BJ-002 states no lens, so the merge falls back to it. The same file
        put through `validate_punchlist` is refused for exactly that item, so
        a punchlist that reaches the merge in the taught order cannot carry
        the fallback into the ledger.
        """
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        assert mp.justine_findings(str(path))[1].perspective == mp.DEFAULT_PERSPECTIVE
        assert mp.DEFAULT_PERSPECTIVE not in vp.read_protocol_set("perspective")

        refused = vp.validate(vp.parse_punchlist(_JUSTINE)).errors
        assert "BJ-002: missing Lens" in refused

    def test_the_theoretical_default_is_unreachable_through_the_validated_path(
        self, tmp_path,
    ):
        """V7 + V8 (item 26) — the same shape as the lens fallback above, and
        the field where the fallback does more than mislabel.

        `theoretical` is not an inert placeholder: D29 auto-defers on it at
        filing, so an ungraded item is off the board before anyone reads it.
        The default is still right where a grading was genuinely never stated,
        which is why `test_an_unstated_reachability_is_theoretical` stays — but
        the validated path must never produce one.

        **`_JUSTINE`'s BJ-002 is deliberately left ungraded.** It is the
        reproduction, not an oversight: it states neither Lens nor
        Reachability, and this asserts the validator refuses it for both.
        """
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(_JUSTINE, encoding="utf-8")
        assert mp.justine_findings(str(path))[1].reachability == mp.DEFAULT_REACHABILITY

        refused = vp.validate(vp.parse_punchlist(_JUSTINE)).errors
        assert "BJ-002: missing Reachability" in refused, refused

    def test_every_reachability_the_merge_can_write_is_an_enforced_one(self, tmp_path):
        """The field's domain enumerated, not described — V6's shape one field
        over, and it closes at the engine rather than at a declaration.

        Compared as sets, so a grade silently dropping out of the pattern fails
        as loudly as a stray value appearing. `DEFAULT_REACHABILITY` is in the
        domain on purpose: unlike `unspecified`, `theoretical` is a real grade,
        which is exactly why an ungraded item is invisible rather than
        obviously wrong.
        """
        graded = "\n\n".join(
            _ITEM_TEMPLATE.format(num=n, lens="component").replace(
                "**Lens:** component",
                f"**Lens:** component\n**Reachability:** {grade}")
            for n, grade in enumerate(
                vp.read_event_field_pattern("finding", "reachability"), start=1)
        )
        path = tmp_path / "PUNCHLIST.md"
        path.write_text(f"# Holtz Punchlist\n\n## Items\n\n{graded}\n", encoding="utf-8")

        written = {f.reachability for f in mp.justine_findings(str(path))}
        assert written == set(vp.read_event_field_pattern("finding", "reachability"))
        assert mp.DEFAULT_REACHABILITY in written

    def test_every_lens_the_merge_can_write_is_a_declared_one(self, tmp_path):
        """V6 — the field's domain enumerated, not described.

        One item per declared lens through the real parser: whatever the merge
        would record for a validated punchlist is drawn from the set and
        nothing else. Written as a set comparison so a lens that silently
        dropped out would fail as loudly as a stray value appearing.
        """
        lenses = vp.read_protocol_set("perspective")
        assert len(lenses) > 1
        items = "\n".join(
            _ITEM_TEMPLATE.format(num=i + 1, lens=lens)
            for i, lens in enumerate(lenses)
        )
        path = tmp_path / "PUNCHLIST.md"
        path.write_text("# Holtz Punchlist\n\n## Items\n\n" + items, encoding="utf-8")

        written = {f.perspective for f in mp.justine_findings(str(path))}
        assert written == set(lenses)



# ── End to end, against a real ledger ────────────────────────────────────────


class _Board:
    """A git repo with a real ledger, and Holtz findings on it."""

    def __init__(self, root):
        self.binary = _binary()
        self.root = root
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        subprocess.run(
            [self.binary, "--config-dir", CONFIG_DIR, "init"],
            cwd=root, capture_output=True, text=True, timeout=60, check=True,
        )

    def sah(self, *args, check=True):
        result = subprocess.run(
            [self.binary, "--config-dir", CONFIG_DIR, *args],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def file(self, finding_id, severity="HIGH", category="bug/logic",
             location="a.py:10", reachability="user_reachable",
             predicted_by="none", pattern_id=None):
        """`pattern_id` is omitted rather than passed empty: the engine's
        `^PAT-\\d+$` refuses an empty string, so a blank one is not a
        no-op but a rejected event."""
        attribution = ["--field", f"pattern_id={pattern_id}"] if pattern_id else []
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", f"category={category}",
                 "--field", f"location={location}", "--field", "perspective=component",
                 "--field", f"predicted_by={predicted_by}",
                 "--field", f"reachability={reachability}",
                 "--field", "description=holtz text", *attribution, *_COMMON)

    def findings(self):
        result = self.sah("query", "--type", "finding", "--format", "jsonl")
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def deferrals(self):
        result = self.sah("query", "--type", "finding_deferred", "--format", "jsonl")
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def run_merge(self, justine_md, *extra):
        path = os.path.join(self.root, "justine-punchlist.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(justine_md)
        report = os.path.join(self.root, "MERGE-REPORT.md")
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "merge_punchlists.py"),
             "--justine", path, "--report", report, "--cwd", self.root, *extra],
            capture_output=True, text=True, timeout=120,
        )


@pytest.fixture
def board(tmp_path):
    return _Board(str(tmp_path))


@pytest.mark.integration
class TestEndToEnd:

    def test_a_justine_only_finding_lands_on_the_ledger_under_her_id(self, board):
        board.file("BH-001", location="a.py:10")
        result = board.run_merge(_JUSTINE)
        assert result.returncode == 0, result.stderr
        ids = {f.get("id") or f.get("fields", {}).get("id") for f in board.findings()}
        assert {"BH-001", "BJ-001", "BJ-002"} <= ids

    def test_a_merged_finding_lands_carrying_her_lens(self, board):
        """V4 (first half) — the lens she stated is on the ledger row.

        The second half of V4 — that the lens's own completion gate then names
        the finding — cannot be driven here: `all_findings_closed` is still
        run-wide, which is item 3, and W07 is the unit that scopes it.
        """
        board.file("BH-001", location="a.py:10")
        result = board.run_merge(_JUSTINE)
        assert result.returncode == 0, result.stderr
        rows = {
            (f.get("id") or f.get("fields", {}).get("id")):
                (f.get("perspective") or f.get("fields", {}).get("perspective"))
            for f in board.findings()
        }
        assert rows["BJ-001"] == "security"

    def test_the_engine_admits_a_lens_that_is_not_one(self, board):
        """The half this unit does not close — W06's V8 rider, measured.

        `[sets.perspective]` declares thirteen lenses and `events.toml` gives
        `perspective` no pattern, so the daemon accepts any string on a
        `finding`. Justine's side is validated markdown and cannot carry a
        non-member; Holtz's side is read back from this ledger, so it can.
        Pinned here rather than described, so that closing the gap upstream
        fails a test instead of passing silently.
        """
        result = board.sah(
            "event", "finding", "--field", "id=BH-009",
            "--field", "severity=LOW", "--field", "category=bug/logic",
            "--field", "location=z.py:1", "--field", "perspective=not-a-lens",
            "--field", "predicted_by=none", "--field", "reachability=theoretical",
            "--field", "description=text", *_COMMON, check=False,
        )
        assert result.returncode == 0, "engine now validates the set — update W06's V8"
        assert "not-a-lens" not in vp.read_protocol_set("perspective")

    def test_a_matched_justine_finding_is_not_refiled(self, board):
        """Agreement records nothing — `merge-protocol.md:36`."""
        board.file("BH-001", location="app/auth.py:47", category="bug/security")
        assert board.run_merge(_JUSTINE).returncode == 0
        ids = [f.get("id") or f.get("fields", {}).get("id") for f in board.findings()]
        assert "BJ-001" not in ids
        assert "BJ-002" in ids

    def test_a_higher_justine_severity_refiles_holtz_id(self, board):
        """V1 (item 25) — the escalation changes `severity` and **nothing else**.

        The old version asserted `len(filings) == 2` and the new severity, and
        never read the fields the re-file was destroying. Comparing the two
        filings field by field is what makes this a guard: any field the merge
        drops on the way through shows up here as a difference it did not
        earn. `seq` and the merge's own provenance are excluded because they
        are *supposed* to differ — a second filing is a second event, recorded
        by the merge in the merge phase.
        """
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW", reachability="user_reachable",
                   predicted_by="2", pattern_id="PAT-007")
        assert board.run_merge(_JUSTINE).returncode == 0
        filings = [f for f in board.findings()
                   if (f.get("id") or f.get("fields", {}).get("id")) == "BH-001"]
        assert len(filings) == 2, "the higher severity was not re-filed"

        before, after = (_declared(f) for f in filings)
        assert after["severity"] == "HIGH"
        assert before["severity"] == "LOW", "the fixture did not set up an escalation"

        # `phase`/`step`/`auditor` are the merge's own provenance and are
        # *supposed* to move: a second filing is a second event, recorded by
        # the merge in the merge phase. Everything else the finding carries is
        # the finding's, and the escalation decides one field of it.
        provenance = {"severity", "phase", "step", "auditor"}
        changed = {
            key for key in set(before) | set(after)
            if key not in provenance and before.get(key) != after.get(key)
        }
        assert not changed, (
            "the re-file altered fields the escalation does not decide: "
            + ", ".join(
                f"{key} {before.get(key)!r} -> {after.get(key)!r}"
                for key in sorted(changed)
            )
        )

    def test_the_escalation_keeps_the_grading_that_routes_it(self, board):
        """V2 + V3 (item 25). The re-file must not re-grade reachability.

        `_HOLTZ_SQL` did not select `reachability`, so every Holtz `Finding`
        was built at `DEFAULT_REACHABILITY = "theoretical"` and the escalation
        wrote that back. The path that exists to say *this is worse than you
        thought* was the one path that took the finding off the board:
        `theoretical` auto-defers, `all_critical_resolved` then reads true —
        a fourth route to closing a CRITICAL with no fix — and `fix_commit`
        refuses it afterwards because `item_is_user_reachable` does.
        """
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW", reachability="user_reachable")
        assert board.run_merge(_JUSTINE).returncode == 0

        after = _flat([f for f in board.findings()
                       if _flat(f).get("id") == "BH-001"][-1])
        assert after["reachability"] == "user_reachable", (
            "the escalation re-graded the finding to "
            f"{after['reachability']!r} — the merge destroyed the grading it "
            "routes on"
        )

    def test_the_escalated_finding_is_not_swept_as_theoretical(self, board):
        """V3's other half, read through the predicate that does the sweeping.

        Asserting the field is one thing; asserting the *population* is what
        says the consequence is gone. `open_theoretical_findings` is the
        courier's own query, read from `protocol.toml` rather than restated.
        """
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW", reachability="user_reachable")
        assert board.run_merge(_JUSTINE).returncode == 0

        rows = json.loads(board.sah(
            "query", _named_query("open_theoretical_findings"),
            "--format", "json").stdout)
        assert "BH-001" not in [r.get("id") for r in rows], (
            "the escalated finding is in the auto-deferral population"
        )
        assert not [f for f in board.deferrals() if _flat(f).get("id") == "BH-001"]

    def test_the_escalation_keeps_the_round_it_belongs_to(self, board):
        """V4 (item 25). `pattern_id` survives the re-file.

        D25 grades by latest filing, so a re-file without `pattern_id` takes
        the sibling out of its round's population — and the round cap and the
        close-as-many-as-you-open obligation both stop seeing it. An escalation
        would silently discharge backpressure.
        """
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW", pattern_id="PAT-007")
        assert board.run_merge(_JUSTINE).returncode == 0

        after = _flat([f for f in board.findings()
                       if _flat(f).get("id") == "BH-001"][-1])
        assert after.get("pattern_id") == "PAT-007"

    def test_the_escalation_keeps_the_prediction_link(self, board):
        """V5 (item 25). `predicted_by` survives.

        It was hard-coded to `"none"` in `_record`, so an escalated finding
        lost the link `SUMMARY.md`'s prediction-accuracy table is computed
        from — the table would silently under-count every escalated hit.
        """
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW", predicted_by="2")
        assert board.run_merge(_JUSTINE).returncode == 0

        after = _flat([f for f in board.findings()
                       if _flat(f).get("id") == "BH-001"][-1])
        assert after.get("predicted_by") == "2"

    def test_a_justine_finding_is_still_recorded_as_unpredicted(self, board):
        """Non-vacuity for V5: `predicted_by` is now carried, not ignored.

        Her punchlist has no prediction link, so hers must still land as
        `none` — a `_record` that simply echoed whatever it was handed would
        pass the test above and write an empty field here, which the engine
        requires to be present.
        """
        board.file("BH-001", location="a.py:10")
        assert board.run_merge(_JUSTINE).returncode == 0
        filed = _flat(next(f for f in board.findings()
                           if _flat(f).get("id") == "BJ-001"))
        assert filed.get("predicted_by") == "none"

    def test_a_lower_justine_severity_changes_nothing(self, board):
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="CRITICAL")
        assert board.run_merge(_JUSTINE).returncode == 0
        filings = [f for f in board.findings()
                   if (f.get("id") or f.get("fields", {}).get("id")) == "BH-001"]
        assert len(filings) == 1

    def test_dry_run_writes_nothing_to_the_ledger(self, board):
        board.file("BH-001", location="a.py:10")
        before = len(board.findings())
        assert board.run_merge(_JUSTINE, "--dry-run").returncode == 0
        assert len(board.findings()) == before

    def test_the_report_it_writes_satisfies_the_gate(self, board):
        board.file("BH-001", location="a.py:10")
        assert board.run_merge(_JUSTINE).returncode == 0
        assert validate_merge_report.validate(
            os.path.join(board.root, "MERGE-REPORT.md")) == []

    def test_the_run_context_comes_off_the_ledger(self, board):
        """A courier takes nothing from the working tree it can read from the
        ledger: `project` and `run` are Holtz's own, not arguments."""
        board.file("BH-001", location="a.py:10")
        assert board.run_merge(_JUSTINE).returncode == 0
        filed = next(f for f in board.findings()
                     if (f.get("id") or f.get("fields", {}).get("id")) == "BJ-001")
        assert (filed.get("project") or filed["fields"]["project"]) == "t"
        assert (filed.get("run") or filed["fields"]["run"]) == "1"


# ── The taught sequence ──────────────────────────────────────────────────────


class TestTheDocsTeachTheScript:
    """A script nothing invokes never runs — H4's question, asked here too."""

    def _read(self, *parts):
        with open(os.path.join(REPO_ROOT, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_merge_agent_runs_the_script(self):
        assert "merge_punchlists.py" in self._read("agents", "merge-agent.md")

    def test_the_protocol_names_the_script(self):
        assert "merge_punchlists.py" in self._read(
            "skills", "holtz", "references", "merge-protocol.md")

    def test_the_stamp_names_the_step_that_teaches_the_merge(self):
        """`phase` and `step` are constants, so they can drift off the document
        silently. The event says step 9; the file that teaches it must too."""
        phase_merge = self._read("skills", "holtz", "references", "phase-merge.md")
        assert f"Step {mp.MERGE_STEP}" in phase_merge
        assert mp.MERGE_PHASE == "merge"

    def test_the_agent_reviews_only_contradiction_candidates(self):
        """The clause's second half. If the doc still teaches hand
        classification, the script saved nothing."""
        agent = self._read("agents", "merge-agent.md")
        assert "contradiction" in agent.lower()
        for gone in ("Sort both by file path", "Classify each item pair"):
            assert gone not in agent, (
                f"{gone!r} is still taught by hand — the script does it now")

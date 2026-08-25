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

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=audit", "--field", "step=8"]


def _binary():
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


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
             location="a.py:10"):
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", f"category={category}",
                 "--field", f"location={location}", "--field", "perspective=component",
                 "--field", "predicted_by=none", "--field", "reachability=user_reachable",
                 "--field", "description=holtz text", *_COMMON)

    def findings(self):
        result = self.sah("query", "--type", "finding", "--format", "jsonl")
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

    def test_a_matched_justine_finding_is_not_refiled(self, board):
        """Agreement records nothing — `merge-protocol.md:36`."""
        board.file("BH-001", location="app/auth.py:47", category="bug/security")
        assert board.run_merge(_JUSTINE).returncode == 0
        ids = [f.get("id") or f.get("fields", {}).get("id") for f in board.findings()]
        assert "BJ-001" not in ids
        assert "BJ-002" in ids

    def test_a_higher_justine_severity_refiles_holtz_id(self, board):
        board.file("BH-001", location="app/auth.py:47", category="bug/security",
                   severity="LOW")
        assert board.run_merge(_JUSTINE).returncode == 0
        filings = [f for f in board.findings()
                   if (f.get("id") or f.get("fields", {}).get("id")) == "BH-001"]
        assert len(filings) == 2, "the higher severity was not re-filed"
        last = filings[-1]
        assert (last.get("severity") or last["fields"]["severity"]) == "HIGH"

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

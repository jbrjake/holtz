"""Tests for impact_graph.py — Holtz Knowledge Graph.

38 test cases covering all 10 operations:
- Basic operations (1-7)
- Blast radius (8-13)
- Cycle handling (14-16)
- Multi-edge and parallel edges (17-20)
- Risk scores (21-24)
- Pruning (25-33)
- Node updates (34-37)
- Large graph (38)
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from impact_graph import ImpactGraph


@pytest.fixture
def graph(tmp_path):
    """Fresh graph with a temp-file backing store."""
    return ImpactGraph(tmp_path / "test-graph.json")


@pytest.fixture
def project(tmp_path):
    """Temporary project root for prune_missing / drift_check tests."""
    root = tmp_path / "project"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Basic operations (tests 1-7)
# ---------------------------------------------------------------------------


def test_01_add_and_query_nodes(graph):
    """Add 3 nodes, verify stats returns count 3."""
    graph.add_node("waffle_iron.py", "module", "src/waffle_iron.py")
    graph.add_node("waffle_iron.py::flip_waffle", "function", "src/waffle_iron.py", line=42)
    graph.add_node("test_waffle.py::test_golden_brown", "test", "tests/test_waffle.py", line=7)
    s = graph.stats()
    assert s["nodes"] == 3
    assert s["edges"] == 0


def test_02_add_edges_and_query_neighbors(graph):
    """A calls B, A calls C — neighbors A returns B and C. Type filter works."""
    graph.add_node("a.py::chef", "function", "a.py", line=1)
    graph.add_node("b.py::grill", "function", "b.py", line=1)
    graph.add_node("c.py::plate", "function", "c.py", line=1)
    graph.add_edge("a.py::chef", "b.py::grill", "calls")
    graph.add_edge("a.py::chef", "c.py::plate", "calls")

    assert graph.neighbors("a.py::chef") == ["b.py::grill", "c.py::plate"]
    assert graph.neighbors("a.py::chef", types=["imports"]) == []


def test_03_edge_metadata_preservation(graph):
    """Add edge with note, query it back, note is preserved."""
    graph.add_node("radio.py::tune_in", "function", "radio.py", line=5)
    graph.add_node("antenna.py::receive", "function", "antenna.py", line=12)
    edge = graph.add_edge(
        "radio.py::tune_in", "antenna.py::receive", "calls",
        note="passes frequency as float Hz",
    )
    assert edge["metadata"]["note"] == "passes frequency as float Hz"
    assert "error" not in edge


def test_04_persistence_round_trip(graph):
    """Write graph, reload from JSON, verify all nodes/edges/metadata intact."""
    graph.add_node("taco.py::fold", "function", "taco.py", line=3)
    graph.add_node("salsa.py::blend", "function", "salsa.py", line=8)
    graph.add_edge("taco.py::fold", "salsa.py::blend", "calls", note="extra spicy")
    graph.save()

    reloaded = ImpactGraph(graph.path)
    reloaded.load()

    assert reloaded.stats() == graph.stats()
    assert reloaded.nodes["taco.py::fold"]["line"] == 3
    assert reloaded.edges[0]["metadata"]["note"] == "extra spicy"


def test_05_empty_graph(graph):
    """All queries on empty graph return empty results, no crashes."""
    assert graph.stats() == {"nodes": 0, "edges": 0, "edge_types": {}}
    assert graph.neighbors("phantom") == []
    assert graph.blast_radius("phantom") == []
    assert graph.risk_hotspots() == []


def test_06_missing_graph_file(tmp_path):
    """First run, no impact-graph.json exists. Operations work, file created on save."""
    path = tmp_path / "nonexistent" / "graph.json"
    g = ImpactGraph(path)
    g.load()
    assert g.stats()["nodes"] == 0
    g.add_node("fresh.py", "module", "fresh.py")
    g.save()
    assert path.exists()
    data = json.loads(path.read_text())
    assert "fresh.py" in data["nodes"]


def test_07_corrupt_json_file(tmp_path):
    """Graph file contains invalid JSON. Loads gracefully with empty graph."""
    path = tmp_path / "bad.json"
    path.write_text("{not valid json at all!!!")
    g = ImpactGraph(path)
    g.load()
    assert g.stats()["nodes"] == 0

    # Also test empty file
    path.write_text("")
    g2 = ImpactGraph(path)
    g2.load()
    assert g2.stats()["nodes"] == 0

    # Also test valid JSON but missing expected keys
    path.write_text("{}")
    g3 = ImpactGraph(path)
    g3.load()
    assert g3.stats()["nodes"] == 0


def test_07b_null_json_values(tmp_path):
    """JSON with null values for nodes/edges loads as empty graph (BH-001, BH-002)."""
    path = tmp_path / "null.json"

    # Both null
    path.write_text('{"nodes": null, "edges": null}')
    g = ImpactGraph(path)
    g.load()
    assert g.stats() == {"nodes": 0, "edges": 0, "edge_types": {}}
    # Operations work on the empty graph
    g.add_node("survivor.py", "module", "survivor.py")
    assert g.stats()["nodes"] == 1

    # nodes ok, edges null
    path.write_text('{"nodes": {"x.py": {"id": "x.py", "type": "module", "file": "x.py", "line": null, "last_audited": "2026-01-01", "audit_count": 1, "risk_score": 0.0}}, "edges": null}')
    g2 = ImpactGraph(path)
    g2.load()
    assert g2.stats()["nodes"] == 1
    assert g2.stats()["edges"] == 0


# ---------------------------------------------------------------------------
# Blast radius (tests 8-13)
# ---------------------------------------------------------------------------


def _chain_graph(graph):
    """Build A→B→C→D chain for blast radius tests."""
    for name in ("A", "B", "C", "D"):
        graph.add_node(f"chain.py::{name}", "function", "chain.py", line=1)
    graph.add_edge("chain.py::A", "chain.py::B", "calls")
    graph.add_edge("chain.py::B", "chain.py::C", "calls")
    graph.add_edge("chain.py::C", "chain.py::D", "calls")


def test_08_depth_traversal(graph):
    """A→B→C→D chain. Depth 1 → {B}. Depth 2 → {B, C}. Depth 3 → {B, C, D}."""
    _chain_graph(graph)
    assert graph.blast_radius("chain.py::A", depth=1) == ["chain.py::B"]
    assert graph.blast_radius("chain.py::A", depth=2) == ["chain.py::B", "chain.py::C"]
    assert graph.blast_radius("chain.py::A", depth=3) == ["chain.py::B", "chain.py::C", "chain.py::D"]


def test_09_depth_0(graph):
    """blast_radius with depth 0 → empty set."""
    _chain_graph(graph)
    assert graph.blast_radius("chain.py::A", depth=0) == []


def test_10_nonexistent_node_blast_radius(graph):
    """blast_radius on nonexistent node → empty, no crash."""
    assert graph.blast_radius("the_void") == []


def test_11_disconnected_subgraphs(graph):
    """Two disconnected clusters. blast_radius on one doesn't reach the other."""
    for name in ("A", "B", "C"):
        graph.add_node(f"left.py::{name}", "function", "left.py", line=1)
    for name in ("X", "Y", "Z"):
        graph.add_node(f"right.py::{name}", "function", "right.py", line=1)
    graph.add_edge("left.py::A", "left.py::B", "calls")
    graph.add_edge("left.py::B", "left.py::C", "calls")
    graph.add_edge("right.py::X", "right.py::Y", "calls")
    graph.add_edge("right.py::Y", "right.py::Z", "calls")

    result = graph.blast_radius("left.py::A", depth=10)
    assert "left.py::B" in result
    assert "left.py::C" in result
    assert not any(r.startswith("right.py") for r in result)


def test_12_hub_node_bidirectional(graph):
    """Hub H calls 50 leaves. Bidirectional traversal reaches hub from any leaf."""
    graph.add_node("hub.py::H", "function", "hub.py", line=1)
    for i in range(50):
        graph.add_node(f"leaf.py::leaf_{i}", "function", "leaf.py", line=i + 1)
        graph.add_edge("hub.py::H", f"leaf.py::leaf_{i}", "calls")

    # From hub: depth 1 reaches all 50 leaves
    from_hub = graph.blast_radius("hub.py::H", depth=1)
    assert len(from_hub) == 50

    # From leaf_0: depth 1 reaches hub (bidirectional)
    from_leaf = graph.blast_radius("leaf.py::leaf_0", depth=1)
    assert from_leaf == ["hub.py::H"]

    # From leaf_0: depth 2 reaches hub + 49 other leaves
    from_leaf_d2 = graph.blast_radius("leaf.py::leaf_0", depth=2)
    assert "hub.py::H" in from_leaf_d2
    assert len(from_leaf_d2) == 50  # hub + 49 other leaves


def test_13_blast_radius_edge_type_filter(graph):
    """A calls B, B assumes C. blast_radius A depth 2 type=calls → {B} only."""
    graph.add_node("pipe.py::A", "function", "pipe.py", line=1)
    graph.add_node("pipe.py::B", "function", "pipe.py", line=10)
    graph.add_node("pipe.py::C", "function", "pipe.py", line=20)
    graph.add_edge("pipe.py::A", "pipe.py::B", "calls")
    graph.add_edge("pipe.py::B", "pipe.py::C", "assumes")

    result = graph.blast_radius("pipe.py::A", depth=2, types=["calls"])
    assert result == ["pipe.py::B"]


# ---------------------------------------------------------------------------
# Cycle handling (tests 14-16)
# ---------------------------------------------------------------------------


def test_14_simple_cycle(graph):
    """A→B→C→A. blast_radius A depth 5 → {B, C}, no infinite loop."""
    for name in ("A", "B", "C"):
        graph.add_node(f"cycle.py::{name}", "function", "cycle.py", line=1)
    graph.add_edge("cycle.py::A", "cycle.py::B", "calls")
    graph.add_edge("cycle.py::B", "cycle.py::C", "calls")
    graph.add_edge("cycle.py::C", "cycle.py::A", "calls")

    result = graph.blast_radius("cycle.py::A", depth=5)
    assert sorted(result) == ["cycle.py::B", "cycle.py::C"]


def test_15_self_referencing_node(graph):
    """A→A. neighbors A returns A. blast_radius A depth 3 → {A}, no infinite loop."""
    graph.add_node("ouroboros.py::A", "function", "ouroboros.py", line=1)
    graph.add_edge("ouroboros.py::A", "ouroboros.py::A", "calls")

    assert graph.neighbors("ouroboros.py::A") == ["ouroboros.py::A"]
    assert graph.blast_radius("ouroboros.py::A", depth=3) == ["ouroboros.py::A"]


def test_16_dense_cycle_cluster(graph):
    """A↔B, B↔C, C↔A. blast_radius A depth 1 → {B, C}. Depth 2 still {B, C}."""
    for name in ("A", "B", "C"):
        graph.add_node(f"tango.py::{name}", "function", "tango.py", line=1)
    graph.add_edge("tango.py::A", "tango.py::B", "calls")
    graph.add_edge("tango.py::B", "tango.py::A", "calls")
    graph.add_edge("tango.py::B", "tango.py::C", "calls")
    graph.add_edge("tango.py::C", "tango.py::B", "calls")
    graph.add_edge("tango.py::C", "tango.py::A", "calls")
    graph.add_edge("tango.py::A", "tango.py::C", "calls")

    assert graph.blast_radius("tango.py::A", depth=1) == ["tango.py::B", "tango.py::C"]
    assert graph.blast_radius("tango.py::A", depth=2) == ["tango.py::B", "tango.py::C"]


# ---------------------------------------------------------------------------
# Multi-edge and parallel edges (tests 17-20)
# ---------------------------------------------------------------------------


def test_17_multiple_edge_types_same_nodes(graph):
    """A calls B and A assumes B. neighbors A returns B once. Both edges preserved."""
    graph.add_node("duo.py::A", "function", "duo.py", line=1)
    graph.add_node("duo.py::B", "function", "duo.py", line=10)
    graph.add_edge("duo.py::A", "duo.py::B", "calls")
    graph.add_edge("duo.py::A", "duo.py::B", "assumes", note="returns sorted list")

    # B appears once in neighbors despite two edges
    assert graph.neighbors("duo.py::A") == ["duo.py::B"]
    # Both edges exist
    assert graph.stats()["edges"] == 2
    assert graph.stats()["edge_types"] == {"calls": 1, "assumes": 1}


def test_18_replace_edge_metadata(graph):
    """Add same edge twice with different note → metadata updated, not duplicated."""
    graph.add_node("remix.py::A", "function", "remix.py", line=1)
    graph.add_node("remix.py::B", "function", "remix.py", line=5)
    graph.add_edge("remix.py::A", "remix.py::B", "calls", note="passes raw")
    graph.add_edge("remix.py::A", "remix.py::B", "calls", note="passes masked")

    assert graph.stats()["edges"] == 1
    assert graph.edges[0]["metadata"]["note"] == "passes masked"


def test_19_directional_edges(graph):
    """A calls B does not imply B calls A. neighbors B type=calls → empty."""
    graph.add_node("arrow.py::A", "function", "arrow.py", line=1)
    graph.add_node("arrow.py::B", "function", "arrow.py", line=5)
    graph.add_edge("arrow.py::A", "arrow.py::B", "calls")

    assert graph.neighbors("arrow.py::B", types=["calls"]) == []


def test_20_multiple_type_filter(graph):
    """A calls B, A imports C, A assumes D. neighbors A type=calls,imports → {B, C}."""
    graph.add_node("trio.py::A", "function", "trio.py", line=1)
    graph.add_node("trio.py::B", "function", "trio.py", line=5)
    graph.add_node("trio.py::C", "function", "trio.py", line=10)
    graph.add_node("trio.py::D", "function", "trio.py", line=15)
    graph.add_edge("trio.py::A", "trio.py::B", "calls")
    graph.add_edge("trio.py::A", "trio.py::C", "imports")
    graph.add_edge("trio.py::A", "trio.py::D", "assumes")

    result = graph.neighbors("trio.py::A", types=["calls", "imports"])
    assert result == ["trio.py::B", "trio.py::C"]


# ---------------------------------------------------------------------------
# Risk scores (tests 21-24)
# ---------------------------------------------------------------------------


def test_21_boundary_clamping(graph):
    """Risk score clamped to [0.0, 1.0] — no underflow or overflow."""
    graph.add_node("clamp.py::low", "function", "clamp.py", line=1)
    graph.add_node("clamp.py::high", "function", "clamp.py", line=5)

    graph.update_risk("clamp.py::low", -0.1)
    assert graph.nodes["clamp.py::low"]["risk_score"] == 0.0

    graph.nodes["clamp.py::high"]["risk_score"] = 1.0
    graph.update_risk("clamp.py::high", 0.5)
    assert graph.nodes["clamp.py::high"]["risk_score"] == 1.0


def test_22_update_risk_nonexistent(graph):
    """update_risk on nonexistent node → error, no phantom node."""
    result = graph.update_risk("ghost_pepper", 0.3)
    assert "error" in result
    assert "ghost_pepper" not in graph.nodes


def test_23_tie_breaking(graph):
    """3 nodes at risk 0.7. risk_hotspots top 2 → exactly 2, alphabetical order."""
    graph.add_node("cherry.py::a", "function", "cherry.py", line=1)
    graph.add_node("banana.py::b", "function", "banana.py", line=1)
    graph.add_node("apple.py::c", "function", "apple.py", line=1)
    for nid in ("cherry.py::a", "banana.py::b", "apple.py::c"):
        graph.nodes[nid]["risk_score"] = 0.7

    hotspots = graph.risk_hotspots(top=2)
    assert len(hotspots) == 2
    assert hotspots[0]["id"] == "apple.py::c"
    assert hotspots[1]["id"] == "banana.py::b"


def test_24_empty_risk_hotspots(graph):
    """risk_hotspots on empty graph → empty list, no crash."""
    assert graph.risk_hotspots() == []


# ---------------------------------------------------------------------------
# Pruning (tests 25-33)
# ---------------------------------------------------------------------------


def test_25_prune_missing_file(graph, project):
    """Node for deleted file. prune_missing removes node + edges."""
    temp_file = project / "ephemeral.py"
    temp_file.write_text("def vanish(): pass\n")
    graph.add_node("ephemeral.py::vanish", "function", "ephemeral.py", line=1)
    graph.add_node("keeper.py::stay", "function", "keeper.py", line=1)
    (project / "keeper.py").write_text("def stay(): pass\n")
    graph.add_edge("ephemeral.py::vanish", "keeper.py::stay", "calls")

    temp_file.unlink()
    result = graph.prune_missing(project)

    assert "ephemeral.py::vanish" in result["removed_nodes"]
    assert result["removed_edges"] == 1
    assert "ephemeral.py::vanish" not in graph.nodes
    assert "keeper.py::stay" in graph.nodes


def test_26_edge_cascade(graph):
    """Node A with 3 edges. prune_node A removes A and all 3 edges."""
    graph.add_node("hub.py::A", "function", "hub.py", line=1)
    graph.add_node("hub.py::B", "function", "hub.py", line=5)
    graph.add_node("hub.py::C", "function", "hub.py", line=10)
    graph.add_node("hub.py::D", "function", "hub.py", line=15)
    graph.add_edge("hub.py::A", "hub.py::B", "calls")
    graph.add_edge("hub.py::A", "hub.py::C", "calls")
    graph.add_edge("hub.py::D", "hub.py::A", "imports")

    result = graph.prune_node("hub.py::A")
    assert len(result["removed_edges"]) == 3
    assert "hub.py::A" not in graph.nodes
    assert graph.stats()["edges"] == 0
    # B, C, D still exist
    for nid in ("hub.py::B", "hub.py::C", "hub.py::D"):
        assert nid in graph.nodes


def test_27_hub_prune(graph):
    """Hub H with 20 edges. prune H removes H and all 20 edges. Neighbors keep mutual edges."""
    graph.add_node("mega.py::H", "function", "mega.py", line=1)
    for i in range(20):
        nid = f"mega.py::spoke_{i}"
        graph.add_node(nid, "function", "mega.py", line=i + 10)
        graph.add_edge("mega.py::H", nid, "calls")
    # Add a mutual edge between spoke_0 and spoke_1
    graph.add_edge("mega.py::spoke_0", "mega.py::spoke_1", "imports")

    result = graph.prune_node("mega.py::H")
    assert len(result["removed_edges"]) == 20
    assert "mega.py::H" not in graph.nodes
    # Mutual edge between spokes survives
    assert graph.stats()["edges"] == 1
    assert graph.edges[0]["source"] == "mega.py::spoke_0"


def test_28_prune_last_node(graph):
    """Single node, no edges. prune_node → empty graph."""
    graph.add_node("loner.py", "module", "loner.py")
    graph.prune_node("loner.py")
    assert graph.stats() == {"nodes": 0, "edges": 0, "edge_types": {}}


def test_29_double_prune(graph):
    """prune_node twice → error on second call, no crash."""
    graph.add_node("twice.py::gone", "function", "twice.py", line=1)
    result1 = graph.prune_node("twice.py::gone")
    assert "error" not in result1

    result2 = graph.prune_node("twice.py::gone")
    assert "error" in result2


def test_30_prune_missing_empty_graph(graph, project):
    """prune_missing on empty graph → no-op."""
    result = graph.prune_missing(project)
    assert result == {"removed_nodes": [], "removed_edges": 0}


def test_31_prune_missing_all_files_gone(graph, project):
    """5 nodes, all backing files deleted. All removed, graph empty."""
    for i in range(5):
        fname = f"doomed_{i}.py"
        (project / fname).write_text(f"# file {i}\n")
        graph.add_node(fname, "module", fname)
    # Delete all files
    for i in range(5):
        (project / f"doomed_{i}.py").unlink()

    result = graph.prune_missing(project)
    assert len(result["removed_nodes"]) == 5
    assert graph.stats()["nodes"] == 0


def test_32_drift_check(graph, project):
    """Node at line 50, function moves to line 80. drift_check flags as drifted."""
    src = project / "drifter.py"
    # Function originally at line 50, now at line 80 (pad with blank lines)
    lines = ["# padding\n"] * 80
    lines[79] = "def wobble():\n"
    src.write_text("".join(lines))

    graph.add_node("drifter.py::wobble", "function", "drifter.py", line=50)
    result = graph.drift_check(project)

    assert len(result["drifted"]) == 1
    assert result["drifted"][0]["id"] == "drifter.py::wobble"
    assert result["drifted"][0]["reason"] == "line_shifted"
    assert result["drifted"][0]["old_line"] == 50
    assert result["drifted"][0]["new_line"] == 80


def test_33_semantic_edge_survives_stale_detection(graph):
    """assumes edge between A and B survives stale detection (it's LLM-verified).
    But cascade-deleted when node A is pruned."""
    graph.add_node("seam.py::A", "function", "seam.py", line=1)
    graph.add_node("seam.py::B", "function", "seam.py", line=10)
    graph.add_edge("seam.py::A", "seam.py::B", "calls")
    graph.add_edge("seam.py::A", "seam.py::B", "assumes", note="B returns sorted")

    # Both edges exist
    assert graph.stats()["edges"] == 2

    # Stale edge detection is LLM-driven (not tested here), but cascade works:
    result = graph.prune_node("seam.py::A")
    assert len(result["removed_edges"]) == 2  # Both edges cascade-deleted
    assert graph.stats()["edges"] == 0


# ---------------------------------------------------------------------------
# Node updates (tests 34-37)
# ---------------------------------------------------------------------------


def test_34_add_node_existing_id(graph):
    """Re-add existing node: line updated, audit_count incremented, risk_score preserved."""
    graph.add_node("evolve.py::morph", "function", "evolve.py", line=50)
    graph.nodes["evolve.py::morph"]["risk_score"] = 0.6
    original_risk = graph.nodes["evolve.py::morph"]["risk_score"]

    graph.add_node("evolve.py::morph", "function", "evolve.py", line=80)

    node = graph.nodes["evolve.py::morph"]
    assert node["line"] == 80
    assert node["audit_count"] == 2
    assert node["risk_score"] == original_risk


def test_35_prune_missing_all_present(graph, project):
    """5 nodes, all backing files exist. prune_missing → no-op."""
    for i in range(5):
        fname = f"alive_{i}.py"
        (project / fname).write_text(f"# file {i}\n")
        graph.add_node(fname, "module", fname)

    result = graph.prune_missing(project)
    assert result["removed_nodes"] == []
    assert result["removed_edges"] == 0
    assert graph.stats()["nodes"] == 5


def test_36_neighbors_nonexistent(graph):
    """neighbors on nonexistent node → empty, no crash."""
    assert graph.neighbors("nobody_home") == []


def test_37_add_edge_nonexistent_endpoint(graph):
    """add_edge with nonexistent target → error, no edge created, no phantom node."""
    graph.add_node("real.py::exists", "function", "real.py", line=1)
    result = graph.add_edge("real.py::exists", "fake.py::phantom", "calls")
    assert "error" in result
    assert graph.stats()["edges"] == 0
    assert "fake.py::phantom" not in graph.nodes

    # Also test nonexistent source
    result2 = graph.add_edge("fake.py::phantom", "real.py::exists", "calls")
    assert "error" in result2


# ---------------------------------------------------------------------------
# Large graph (test 38)
# ---------------------------------------------------------------------------


def test_38_200_node_round_trip(graph):
    """Build 200 nodes, 500 edges. Write. Reload. All data identical."""
    for i in range(200):
        graph.add_node(f"galaxy.py::star_{i:03d}", "function", "galaxy.py", line=i + 1)

    import random
    rng = random.Random(42)  # deterministic seed
    node_ids = list(graph.nodes.keys())
    edges_added = 0
    attempts = set()
    while edges_added < 500:
        src = rng.choice(node_ids)
        tgt = rng.choice(node_ids)
        etype = rng.choice(["calls", "imports", "assumes", "tests", "co_fixed"])
        key = (src, tgt, etype)
        if key in attempts:
            continue
        attempts.add(key)
        result = graph.add_edge(src, tgt, etype)
        if "error" not in result:
            edges_added += 1

    assert graph.stats()["nodes"] == 200
    assert graph.stats()["edges"] == 500

    graph.save()
    reloaded = ImpactGraph(graph.path)
    reloaded.load()

    assert reloaded.stats()["nodes"] == 200
    assert reloaded.stats()["edges"] == 500
    # Spot-check a node
    assert reloaded.nodes["galaxy.py::star_042"]["line"] == 43
    # Spot-check edges are identical
    for i in range(500):
        assert reloaded.edges[i] == graph.edges[i]


# ---------------------------------------------------------------------------
# Drift check — additional scenarios
# ---------------------------------------------------------------------------


def test_drift_check_entity_missing(graph, project):
    """Function removed from file entirely → flagged as entity_missing."""
    src = project / "vanished.py"
    src.write_text("# The function that was here is gone\npass\n")
    graph.add_node("vanished.py::ghost_func", "function", "vanished.py", line=5)

    result = graph.drift_check(project)
    assert len(result["drifted"]) == 1
    assert result["drifted"][0]["reason"] == "entity_missing"


def test_drift_check_within_threshold(graph, project):
    """Function shifted by <=10 lines → NOT flagged."""
    src = project / "stable.py"
    lines = ["# padding\n"] * 15
    lines[14] = "def steady():\n"
    src.write_text("".join(lines))

    graph.add_node("stable.py::steady", "function", "stable.py", line=10)
    result = graph.drift_check(project)
    assert result["drifted"] == []


def test_drift_check_skips_module_type(graph, project):
    """Module-type nodes only check file existence, handled by prune_missing."""
    (project / "simple.py").write_text("# module\n")
    graph.add_node("simple.py", "module", "simple.py")

    result = graph.drift_check(project)
    assert result["drifted"] == []


def test_drift_check_class_detection(graph, project):
    """drift_check detects class definitions."""
    src = project / "models.py"
    lines = ["# padding\n"] * 50
    lines[49] = "class Enchilada:\n"
    src.write_text("".join(lines))

    graph.add_node("models.py::Enchilada", "class", "models.py", line=10)
    result = graph.drift_check(project)
    assert len(result["drifted"]) == 1
    assert result["drifted"][0]["reason"] == "line_shifted"
    assert result["drifted"][0]["new_line"] == 50


def test_drift_check_js_function(graph, project):
    """drift_check detects JavaScript function definitions."""
    src = project / "app.js"
    src.write_text("function handleRequest(req, res) {\n  res.send('ok');\n}\n")
    graph.add_node("app.js::handleRequest", "function", "app.js", line=1)

    result = graph.drift_check(project)
    assert result["drifted"] == []  # Found at line 1, no shift


def test_drift_check_go_function(graph, project):
    """drift_check detects Go function definitions."""
    src = project / "main.go"
    src.write_text(textwrap.dedent("""\
        package main

        func serveTacos(w http.ResponseWriter, r *http.Request) {
            w.Write([]byte("tacos"))
        }
    """))
    graph.add_node("main.go::serveTacos", "function", "main.go", line=3)

    result = graph.drift_check(project)
    assert result["drifted"] == []


# ---------------------------------------------------------------------------
# BH-003: CLI integration tests
# ---------------------------------------------------------------------------


def test_cli_add_node_and_stats(tmp_path):
    """CLI round-trip: add_node then stats shows the node (BH-003)."""
    graph_path = tmp_path / "cli-graph.json"
    script = str(Path(__file__).parent.parent / "skills" / "holtz" / "scripts" / "impact_graph.py")
    base = [sys.executable, script, "--graph", str(graph_path)]

    # Add a node
    r1 = subprocess.run(base + ["add_node", "taco.py::fold", "function", "taco.py", "--line", "42"],
                        capture_output=True, text=True)
    assert r1.returncode == 0
    node = json.loads(r1.stdout)
    assert node["id"] == "taco.py::fold"
    assert node["line"] == 42

    # Stats should show 1 node
    r2 = subprocess.run(base + ["stats"], capture_output=True, text=True)
    assert r2.returncode == 0
    stats = json.loads(r2.stdout)
    assert stats["nodes"] == 1

    # add_edge with nonexistent target → exit code 1
    r3 = subprocess.run(base + ["add_edge", "taco.py::fold", "ghost.py::vanish", "calls"],
                        capture_output=True, text=True)
    assert r3.returncode == 1


# ---------------------------------------------------------------------------
# BH-005: Empty types filter edge case
# ---------------------------------------------------------------------------


def test_neighbors_empty_types_is_no_filter(graph):
    """neighbors with types=[] is falsy → treated as no filter, returns all (BH-005)."""
    graph.add_node("solo.py::A", "function", "solo.py", line=1)
    graph.add_node("solo.py::B", "function", "solo.py", line=5)
    graph.add_edge("solo.py::A", "solo.py::B", "calls")

    # [] is falsy in Python → type_set = None → no filter → all neighbors returned
    assert graph.neighbors("solo.py::A", types=[]) == ["solo.py::B"]


def test_blast_radius_empty_types_is_no_filter(graph):
    """blast_radius with types=[] is falsy → treated as no filter, returns all (BH-005)."""
    graph.add_node("void.py::A", "function", "void.py", line=1)
    graph.add_node("void.py::B", "function", "void.py", line=5)
    graph.add_edge("void.py::A", "void.py::B", "calls")

    # [] is falsy → type_set = None → no filter → all reachable
    assert graph.blast_radius("void.py::A", depth=2, types=[]) == ["void.py::B"]


# ---------------------------------------------------------------------------
# BH-008: drift_check async function detection
# ---------------------------------------------------------------------------


def test_drift_check_async_python_function(graph, project):
    """drift_check detects async def functions in Python (BH-008)."""
    src = project / "async_handler.py"
    src.write_text("async def handle_websocket(ws):\n    await ws.recv()\n")
    graph.add_node("async_handler.py::handle_websocket", "function", "async_handler.py", line=1)

    result = graph.drift_check(project)
    assert result["drifted"] == []  # Found at line 1, no shift


def test_drift_check_async_function_shifted(graph, project):
    """drift_check flags async function that shifted >10 lines (BH-008)."""
    src = project / "async_moved.py"
    lines = ["# padding\n"] * 30
    lines[29] = "async def process_queue(q):\n"
    src.write_text("".join(lines))
    graph.add_node("async_moved.py::process_queue", "function", "async_moved.py", line=5)

    result = graph.drift_check(project)
    assert len(result["drifted"]) == 1
    assert result["drifted"][0]["reason"] == "line_shifted"
    assert result["drifted"][0]["new_line"] == 30


# ---------------------------------------------------------------------------
# BH-009: load() with non-dict JSON types
# ---------------------------------------------------------------------------


def test_load_json_array(tmp_path):
    """JSON array [1,2,3] is valid JSON but not a dict — loads as empty graph (BH-009)."""
    path = tmp_path / "array.json"
    path.write_text("[1, 2, 3]")
    g = ImpactGraph(path)
    g.load()
    assert g.stats() == {"nodes": 0, "edges": 0, "edge_types": {}}


def test_load_json_scalar(tmp_path):
    """JSON scalar (number/string) is valid JSON but not a dict — loads as empty (BH-009)."""
    path = tmp_path / "scalar.json"

    path.write_text("42")
    g = ImpactGraph(path)
    g.load()
    assert g.stats()["nodes"] == 0

    path.write_text('"just a string"')
    g2 = ImpactGraph(path)
    g2.load()
    assert g2.stats()["nodes"] == 0

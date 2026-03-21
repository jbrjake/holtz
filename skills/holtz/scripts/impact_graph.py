#!/usr/bin/env python3
"""
Holtz Impact Graph — Knowledge graph for code entity relationships.

Persists as JSON at docs/holtz/impact-graph.json. Encodes relationships
between code entities discovered during auditing.

Usage: python impact_graph.py <command> [args]
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

DEFAULT_GRAPH_PATH = Path("docs/holtz/impact-graph.json")
DRIFT_LINE_THRESHOLD = 10

# Patterns for finding entity definitions by language
ENTITY_PATTERNS: dict[str, list[str]] = {
    "function": [
        r"^\s*(?:async\s+)?def\s+{name}\s*\(",
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+{name}\s*[\(<]",
        r"^\s*func\s+{name}\s*[\(<]",
    ],
    "class": [
        r"^\s*class\s+{name}\b",
    ],
    "test": [
        r"^\s*(?:async\s+)?def\s+{name}\s*\(",
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+{name}\s*[\(<]",
        r"^\s*func\s+{name}\s*[\(<]",
    ],
}


class ImpactGraph:
    """In-memory knowledge graph with JSON persistence."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_GRAPH_PATH
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def load(self) -> None:
        """Load graph from JSON file. Handles missing, empty, or corrupt files."""
        if not self.path.exists():
            return
        try:
            text = self.path.read_text().strip()
            if not text:
                return
            data = json.loads(text)
            self.nodes = data.get("nodes", {})
            self.edges = data.get("edges", [])
        except (json.JSONDecodeError, AttributeError):
            self.nodes = {}
            self.edges = []

    def save(self) -> None:
        """Write graph to JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"nodes": self.nodes, "edges": self.edges}
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    def add_node(self, node_id: str, node_type: str, file: str, line: int | None = None) -> dict:
        """Add or update a node. Preserves risk_score, increments audit_count on update."""
        today = date.today().isoformat()
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node["type"] = node_type
            node["file"] = file
            node["line"] = line
            node["last_audited"] = today
            node["audit_count"] = node.get("audit_count", 1) + 1
        else:
            self.nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "file": file,
                "line": line,
                "last_audited": today,
                "audit_count": 1,
                "risk_score": 0.0,
            }
        return self.nodes[node_id]

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        note: str | None = None,
        confidence: str | None = None,
        discovered: str | None = None,
    ) -> dict:
        """Add or update an edge. Deduplicates on (source, target, type) tuple."""
        if source not in self.nodes:
            return {"error": f"Source node '{source}' does not exist"}
        if target not in self.nodes:
            return {"error": f"Target node '{target}' does not exist"}

        for edge in self.edges:
            if edge["source"] == source and edge["target"] == target and edge["type"] == edge_type:
                if note is not None:
                    edge["metadata"]["note"] = note
                if confidence is not None:
                    edge["metadata"]["confidence"] = confidence
                if discovered is not None:
                    edge["metadata"]["discovered"] = discovered
                return edge

        metadata: dict = {
            "discovered": discovered or date.today().isoformat(),
            "confidence": confidence or "medium",
        }
        if note is not None:
            metadata["note"] = note
        edge = {"source": source, "target": target, "type": edge_type, "metadata": metadata}
        self.edges.append(edge)
        return edge

    def neighbors(self, node_id: str, types: list[str] | None = None) -> list[str]:
        """Direct outgoing neighbors, optionally filtered by edge type."""
        if node_id not in self.nodes:
            return []
        type_set = set(types) if types else None
        result: set[str] = set()
        for edge in self.edges:
            if edge["source"] == node_id and (type_set is None or edge["type"] in type_set):
                result.add(edge["target"])
        return sorted(result)

    def blast_radius(self, node_id: str, depth: int = 2, types: list[str] | None = None) -> list[str]:
        """Bidirectional BFS to depth, optionally filtered by edge type.

        The starting node is excluded from results unless it has a self-edge
        matching the type filter.
        """
        if node_id not in self.nodes or depth <= 0:
            return []

        type_set = set(types) if types else None
        visited: set[str] = {node_id}
        result: set[str] = set()

        # Self-edge: include origin if it has a direct self-loop
        if any(
            e["source"] == node_id and e["target"] == node_id
            and (type_set is None or e["type"] in type_set)
            for e in self.edges
        ):
            result.add(node_id)

        frontier: set[str] = {node_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for edge in self.edges:
                    if type_set is not None and edge["type"] not in type_set:
                        continue
                    if edge["source"] == node:
                        neighbor = edge["target"]
                    elif edge["target"] == node:
                        neighbor = edge["source"]
                    else:
                        continue
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
                        result.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        return sorted(result)

    def risk_hotspots(self, top: int = 10) -> list[dict]:
        """Nodes sorted by risk_score descending, alphabetical ID tiebreaker."""
        nodes = list(self.nodes.values())
        nodes.sort(key=lambda n: (-n.get("risk_score", 0.0), n["id"]))
        return nodes[:top]

    def update_risk(self, node_id: str, delta: float) -> dict:
        """Adjust risk_score, clamped to [0.0, 1.0]."""
        if node_id not in self.nodes:
            return {"error": f"Node '{node_id}' does not exist"}
        node = self.nodes[node_id]
        new_score = node.get("risk_score", 0.0) + delta
        node["risk_score"] = max(0.0, min(1.0, new_score))
        return node

    def stats(self) -> dict:
        """Return graph statistics."""
        edge_types: dict[str, int] = {}
        for edge in self.edges:
            t = edge["type"]
            edge_types[t] = edge_types.get(t, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "edge_types": edge_types,
        }

    def prune_node(self, node_id: str) -> dict:
        """Remove node and all connected edges. Return removed edges."""
        if node_id not in self.nodes:
            return {"error": f"Node '{node_id}' does not exist"}
        del self.nodes[node_id]
        removed = [e for e in self.edges if e["source"] == node_id or e["target"] == node_id]
        self.edges = [e for e in self.edges if e["source"] != node_id and e["target"] != node_id]
        return {"removed_edges": removed}

    def prune_missing(self, project_root: Path) -> dict:
        """Remove nodes whose backing files no longer exist."""
        to_remove = []
        for node_id, node in self.nodes.items():
            file_path = project_root / node["file"]
            if not file_path.exists():
                to_remove.append(node_id)

        removed_edges = 0
        for node_id in to_remove:
            result = self.prune_node(node_id)
            removed_edges += len(result.get("removed_edges", []))

        return {"removed_nodes": to_remove, "removed_edges": removed_edges}

    def drift_check(self, project_root: Path) -> dict:
        """Flag nodes whose file exists but entity is missing or relocated."""
        drifted: list[dict] = []

        for node_id, node in sorted(self.nodes.items()):
            node_type = node["type"]
            if node_type in ("module", "config", "doc"):
                continue
            if "::" not in node_id:
                continue

            entity_name = node_id.split("::", 1)[1]
            file_path = project_root / node["file"]

            if not file_path.exists():
                continue

            try:
                content = file_path.read_text()
            except OSError:
                continue

            patterns = ENTITY_PATTERNS.get(node_type, ENTITY_PATTERNS["function"])
            compiled = [re.compile(p.format(name=re.escape(entity_name))) for p in patterns]

            found_line = None
            for i, line_text in enumerate(content.splitlines(), 1):
                if any(p.search(line_text) for p in compiled):
                    found_line = i
                    break

            if found_line is None:
                drifted.append({"id": node_id, "reason": "entity_missing"})
            elif node["line"] is not None and abs(found_line - node["line"]) > DRIFT_LINE_THRESHOLD:
                drifted.append({
                    "id": node_id,
                    "reason": "line_shifted",
                    "old_line": node["line"],
                    "new_line": found_line,
                })

        return {"drifted": drifted}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Holtz Impact Graph")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH_PATH), help="Path to graph JSON file")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("add_node")
    p.add_argument("id")
    p.add_argument("type")
    p.add_argument("file")
    p.add_argument("--line", type=int, default=None)

    p = sub.add_parser("add_edge")
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("type")
    p.add_argument("--note", default=None)
    p.add_argument("--confidence", default=None)

    p = sub.add_parser("neighbors")
    p.add_argument("id")
    p.add_argument("--type", dest="types", default=None, help="Comma-separated edge types")

    p = sub.add_parser("blast_radius")
    p.add_argument("id")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--type", dest="types", default=None, help="Comma-separated edge types")

    p = sub.add_parser("risk_hotspots")
    p.add_argument("--top", type=int, default=10)

    p = sub.add_parser("update_risk")
    p.add_argument("id")
    p.add_argument("delta", type=float)

    sub.add_parser("stats")

    p = sub.add_parser("prune_node")
    p.add_argument("id")

    p = sub.add_parser("prune_missing")
    p.add_argument("--project-root", required=True)

    p = sub.add_parser("drift_check")
    p.add_argument("--project-root", required=True)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    g = ImpactGraph(args.graph)
    g.load()

    if args.command == "add_node":
        result = g.add_node(args.id, args.type, args.file, line=args.line)
        g.save()
        print(json.dumps(result, indent=2))

    elif args.command == "add_edge":
        result = g.add_edge(args.source, args.target, args.type, note=args.note, confidence=args.confidence)
        if "error" in result:
            print(json.dumps(result), file=sys.stderr)
            sys.exit(1)
        g.save()
        print(json.dumps(result, indent=2))

    elif args.command == "neighbors":
        types = args.types.split(",") if args.types else None
        result = g.neighbors(args.id, types=types)
        print(json.dumps(result, indent=2))

    elif args.command == "blast_radius":
        types = args.types.split(",") if args.types else None
        result = g.blast_radius(args.id, depth=args.depth, types=types)
        print(json.dumps(result, indent=2))

    elif args.command == "risk_hotspots":
        result = g.risk_hotspots(top=args.top)
        print(json.dumps(result, indent=2))

    elif args.command == "update_risk":
        result = g.update_risk(args.id, args.delta)
        if "error" in result:
            print(json.dumps(result), file=sys.stderr)
            sys.exit(1)
        g.save()
        print(json.dumps(result, indent=2))

    elif args.command == "stats":
        print(json.dumps(g.stats(), indent=2))

    elif args.command == "prune_node":
        result = g.prune_node(args.id)
        if "error" in result:
            print(json.dumps(result), file=sys.stderr)
            sys.exit(1)
        g.save()
        print(json.dumps({"removed_edges": len(result["removed_edges"])}, indent=2))

    elif args.command == "prune_missing":
        result = g.prune_missing(Path(args.project_root))
        g.save()
        print(json.dumps(result, indent=2))

    elif args.command == "drift_check":
        result = g.drift_check(Path(args.project_root))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

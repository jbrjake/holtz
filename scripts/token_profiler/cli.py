"""CLI module for the token profiler.

Argument parsing, plugin loading, session discovery, and pipeline orchestration.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import sys
import webbrowser
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import ModuleType

from token_profiler.analyze import build_run_profile, build_session_profile
from token_profiler.extract import discover_subagents, extract_session, find_project_dir
from token_profiler.plugin_protocol import ProfilerPlugin
from token_profiler.report import generate_markdown

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments with all spec flags."""
    parser = argparse.ArgumentParser(
        prog="token_profiler",
        description="Analyse Claude Code session token usage.",
    )

    # Positional
    parser.add_argument(
        "session",
        nargs="?",
        default=None,
        help="Path to session JSONL or session UUID",
    )

    # Session discovery
    session_group = parser.add_argument_group("session discovery")
    session_group.add_argument(
        "--latest",
        action="store_true",
        default=False,
        help="Use most recent session for the project",
    )
    session_group.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List available sessions and exit",
    )
    session_group.add_argument(
        "--project",
        default=None,
        metavar="PATH",
        help="Project root for session discovery",
    )

    # Output
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "-o", "--output",
        default="./token-profile",
        metavar="DIR",
        help="Output directory (default: ./token-profile/)",
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit profile.json only",
    )
    output_group.add_argument(
        "--md",
        action="store_true",
        default=False,
        help="Emit profile.md only",
    )
    output_group.add_argument(
        "--html",
        action="store_true",
        default=False,
        help="Emit profile.html only",
    )
    output_group.add_argument(
        "--open",
        action="store_true",
        default=False,
        help="Open HTML in browser after generation",
    )

    # Analysis
    analysis_group = parser.add_argument_group("analysis")
    analysis_group.add_argument(
        "--milestones",
        default=None,
        metavar="FILE",
        help="JSON file with phase milestone overrides",
    )
    analysis_group.add_argument(
        "--plugin",
        action="append",
        default=[],
        metavar="PATH",
        help="Plugin Python file (can repeat)",
    )
    analysis_group.add_argument(
        "--no-subagents",
        action="store_true",
        default=False,
        help="Skip subagent discovery",
    )
    analysis_group.add_argument(
        "--pricing",
        default=None,
        metavar="FILE",
        help="Pricing override JSON file",
    )
    analysis_group.add_argument(
        "--run-id",
        default=None,
        metavar="NAME",
        help="Run label (default: inferred from session filename)",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Plugin loading
# ---------------------------------------------------------------------------

# Methods that a plugin class must have to qualify as a ProfilerPlugin
_PLUGIN_METHODS = {"detect", "label_phases", "name_subagent", "enrich_profile", "optimization_patterns"}


def load_plugins(paths: list[str], check_env: bool = False) -> list[ProfilerPlugin]:
    """Load plugin Python files and return instantiated plugin objects.

    Scans each module for classes that have all ProfilerPlugin methods
    plus a ``name`` attribute.  If *check_env* is True and *paths* is
    empty, falls back to the ``TOKEN_PROFILER_PLUGINS`` environment
    variable (colon-separated).
    """
    if not paths and check_env:
        env_val = os.environ.get("TOKEN_PROFILER_PLUGINS", "")
        if env_val:
            paths = [p for p in env_val.split(":") if p]

    if not paths:
        return []

    plugins: list[ProfilerPlugin] = []
    for path in paths:
        mod = _load_module_from_path(path)
        if mod is None:
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if _is_plugin_class(obj):
                plugins.append(obj())
    return plugins


def _load_module_from_path(path: str) -> ModuleType | None:
    """Load a Python module from a file path."""
    p = Path(path)
    if not p.is_file():
        print(f"warning: plugin file not found: {path}", file=sys.stderr)
        return None
    spec = importlib.util.spec_from_file_location(p.stem, p)
    if spec is None or spec.loader is None:
        print(f"warning: could not load plugin: {path}", file=sys.stderr)
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_plugin_class(cls: type) -> bool:
    """Check if a class has all ProfilerPlugin methods and a name attribute."""
    if not hasattr(cls, "name"):
        return False
    for method_name in _PLUGIN_METHODS:
        if not hasattr(cls, method_name):
            return False
        if not callable(getattr(cls, method_name)):
            return False
    return True


# ---------------------------------------------------------------------------
# Session discovery
# ---------------------------------------------------------------------------


def list_sessions(project_dir: Path) -> list[dict]:
    """List available sessions with metadata (started, ended, turns, size).

    Reuses logic from ``scripts/session-to-cast.py``.
    """
    sessions: list[dict] = []
    for f in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        size = f.stat().st_size
        first_ts = last_ts = ""
        turns = 0
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("type") == "assistant":
                    turns += 1
                    ts = obj.get("timestamp", "")
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts
        sessions.append({
            "path": str(f),
            "name": f.stem,
            "size_kb": size // 1024,
            "turns": turns,
            "started": first_ts[:19] if first_ts else "?",
            "ended": last_ts[:19] if last_ts else "?",
        })
    return sessions


def resolve_session(args: argparse.Namespace, project_dir: Path | None) -> Path:
    """Find the session JSONL from args (positional, --latest, or UUID lookup).

    Raises SystemExit if no session can be found.
    """
    if args.session:
        # Direct path
        p = Path(args.session)
        if p.is_file():
            return p

        # UUID lookup within project_dir
        if project_dir is not None:
            candidates = list(project_dir.glob(f"{args.session}*"))
            jsonl_candidates = [c for c in candidates if c.suffix == ".jsonl"]
            if jsonl_candidates:
                return jsonl_candidates[0]

        print(f"error: session not found: {args.session}", file=sys.stderr)
        raise SystemExit(1)

    if args.latest:
        if project_dir is None:
            print("error: cannot determine project directory for --latest", file=sys.stderr)
            raise SystemExit(1)
        jsonl_files = sorted(
            project_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not jsonl_files:
            print("error: no session files found in project directory", file=sys.stderr)
            raise SystemExit(1)
        return jsonl_files[0]

    print("error: no session specified (use positional path, --latest, or --list)", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------


def _json_default(obj: object) -> str:
    """Custom JSON serializer for dataclass fields that aren't natively serializable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Orchestrate the full token profiler pipeline."""
    args = parse_args(argv)

    # Resolve project directory
    project_dir = find_project_dir(args.project)

    # Handle --list
    if args.list:
        if project_dir is None:
            print("error: cannot determine project directory", file=sys.stderr)
            return 1
        sessions = list_sessions(project_dir)
        if not sessions:
            print("No sessions found.")
            return 0
        for s in sessions:
            print(f"  {s['name']}  {s['turns']} turns  {s['size_kb']}KB  {s['started']} - {s['ended']}")
        return 0

    # Resolve session file
    session_path = resolve_session(args, project_dir)

    # Load plugins
    plugins = load_plugins(args.plugin, check_env=True)

    # Load milestones
    milestones: list[dict] | None = None
    if args.milestones:
        with open(args.milestones) as f:
            milestones = json.load(f)

    # Load custom pricing (not yet integrated into full pipeline, but load it)
    custom_pricing: dict | None = None
    if args.pricing:
        with open(args.pricing) as f:
            custom_pricing = json.load(f)

    # Determine run ID
    run_id = args.run_id or session_path.stem

    # Pick the first detecting plugin (if any)
    raw_turns_main = extract_session(session_path)
    active_plugin = None
    for plugin in plugins:
        if plugin.detect(raw_turns_main):
            active_plugin = plugin
            break

    # Build main session profile
    main_profile = build_session_profile(
        session_id=session_path.stem,
        raw_turns=raw_turns_main,
        session_type="main",
        milestones=milestones,
        plugin=active_plugin,
    )

    all_sessions = [main_profile]

    # Discover and process subagents (unless --no-subagents)
    if not args.no_subagents:
        subagent_paths = discover_subagents(session_path)
        for sub_path in subagent_paths:
            sub_turns = extract_session(sub_path)
            sub_profile = build_session_profile(
                session_id=sub_path.stem,
                raw_turns=sub_turns,
                session_type="subagent",
                plugin=active_plugin,
            )
            all_sessions.append(sub_profile)

    # Build run profile
    run_profile = build_run_profile(run_id=run_id, sessions=all_sessions)

    # Determine which outputs to emit
    emit_json = args.json
    emit_md = args.md
    emit_html = args.html

    # Default: all (except HTML if viewer not available)
    if not emit_json and not emit_md and not emit_html:
        emit_json = True
        emit_md = True
        emit_html = True

    # Ensure output directory exists
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write profile.json (Errata E9)
    if emit_json:
        profile_data = asdict(run_profile)
        json_path = out_dir / "profile.json"
        with open(json_path, "w") as f:
            json.dump(profile_data, f, indent=2, default=_json_default)

    # Write profile.md
    if emit_md:
        md_content = generate_markdown(run_profile)
        md_path = out_dir / "profile.md"
        with open(md_path, "w") as f:
            f.write(md_content)

    # Write profile.html (stub — skip if viewer module not importable)
    if emit_html:
        try:
            from token_profiler.viewer import generate_html
            html_content = generate_html(run_profile)
            html_path = out_dir / "profile.html"
            with open(html_path, "w") as f:
                f.write(html_content)

            if args.open:
                webbrowser.open(str(html_path))
        except ImportError:
            # Viewer module not yet implemented — skip HTML silently
            pass

    # Suppress unused variable warning for custom_pricing
    _ = custom_pricing

    return 0

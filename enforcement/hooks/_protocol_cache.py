"""Shared protocol enforcement cache — read/write state, detect commands, compute obligations.

Used by commit_gate.py (PreToolUse) and protocol_tracker.py (PostToolUse).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

CACHE_FILENAME = "enforcement-cache.json"


def _cache_path(cwd: str) -> str:
    return os.path.join(cwd, "docs", "holtz", ".sahjhan", CACHE_FILENAME)


def _read_perspectives_total() -> int:
    """Read perspective count from protocol.toml, falling back to 13."""
    toml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "protocol.toml")
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]  # pip install tomli for <3.11
        except ModuleNotFoundError:
            return 13
    try:
        with open(toml_path, "rb") as f:
            cfg = tomllib.load(f)
        values = cfg.get("sets", {}).get("perspective", {}).get("values", [])
        return len(values) if values else 13
    except (OSError, Exception):
        return 13


def empty_cache() -> dict[str, Any]:
    return {
        "active": True,
        "state": "",
        "unregistered_commits": [],
        "fixes_since_pattern": 0,
        "perspective": "",
        "perspectives_done": 0,
        "perspectives_total": _read_perspectives_total(),
        "stall": 0,
        "last_refresh": "",
    }


def read_cache(cwd: str) -> dict[str, Any] | None:
    path = _cache_path(cwd)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(cwd: str, cache: dict[str, Any]) -> None:
    path = _cache_path(cwd)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    cache["last_refresh"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        import contextlib
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def parse_status_text(text: str) -> dict[str, Any]:
    """Parse the text output of ``sahjhan status`` into a dict.

    Returns a dict with keys: current_state, terminal, event_count,
    run_number, sets (dict of set_name → {complete, total}),
    available_transitions (list of str), current_perspective.
    """
    result: dict[str, Any] = {
        "current_state": "",
        "terminal": False,
        "event_count": 0,
        "run_number": "0",
        "sets": {},
        "available_transitions": [],
        "current_perspective": "unknown",
    }

    lines = text.strip().splitlines()
    for line in lines:
        stripped = line.strip()

        # "state: fix_loop (59 events, chain valid)"
        m = re.match(r"^state:\s+(\S+)\s+\((\d+)\s+events", stripped)
        if m:
            result["current_state"] = m.group(1)
            result["event_count"] = int(m.group(2))
            continue

        # "  perspective: 3/13 [✓ component, ..."
        m = re.match(r"^\s*(\w[\w-]*):\s+(\d+)/(\d+)\s+\[", stripped)
        if m:
            set_name = m.group(1)
            complete = int(m.group(2))
            total = int(m.group(3))
            result["sets"][set_name] = {"complete": complete, "total": total}
            continue

        # "  fix_commit: ready" or "  fix_commit: blocked"
        # BH-013: Use \s* (not \s+) because `stripped` has no leading whitespace.
        m = re.match(r"^\s*(\w[\w_]*):\s+(ready|blocked)", stripped)
        if m:
            transition = m.group(1)
            status = m.group(2)
            if status == "ready":
                result["available_transitions"].append(transition)
            continue

    # Terminal states
    terminal_states = {"finalized"}
    result["terminal"] = result["current_state"] in terminal_states

    # Extract current perspective from sets
    perspective_set = result["sets"].get("perspective", {})
    result["current_perspective"] = "unknown"
    if perspective_set:
        result["perspectives_done"] = perspective_set.get("complete", 0)
        result["perspectives_total"] = perspective_set.get("total", 13)

    return result


def is_git_commit(cmd: str) -> bool:
    """Detect git commit commands (not amend).

    Checks for ``--amend`` as a CLI flag (word boundary), not as a
    substring of the commit message.
    """
    if not re.search(r"\bgit\s+commit\b(?!-)", cmd):
        return False
    # Strip -m argument and its quoted/unquoted value, then check for --amend
    stripped = re.sub(r'-m\s+(?:"[^"]*"|\'[^\']*\'|\S+)', '', cmd)
    return not re.search(r"(?<!\w)--amend\b", stripped)


def is_sahjhan_cmd(cmd: str) -> bool:
    """Detect sahjhan CLI invocations."""
    stripped = cmd.strip()
    for segment in re.split(r"[;&|]+", stripped):
        seg = segment.strip()
        # Match: sahjhan, ./bin/sahjhan, bin/sahjhan, /abs/path/to/sahjhan
        parts = seg.split()
        if parts and (parts[0] == "sahjhan" or parts[0].endswith("/sahjhan") or "/sahjhan-" in parts[0]):
            return True
    return False


def compute_obligations(cache: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Compute current protocol obligations from cache state."""
    if cache is None or not cache.get("active"):
        return []

    state = cache.get("state", "")
    if state not in ("fix_loop", "pattern_analysis"):
        return []

    obligations: list[dict[str, Any]] = []
    commits = cache.get("unregistered_commits", [])
    stall = cache.get("stall", 0)
    fixes = cache.get("fixes_since_pattern", 0)
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)

    if commits:
        obligations.append({
            "msg": f"{len(commits)} unregistered commits. sahjhan fix_commit required. "
                   f"{perspective} ({p_done}/{p_total})",
            "blocks_commit": True,
            "blocks_all": False,
        })

    if stall > 15:
        obligations.append({
            "msg": f"{stall} commands without protocol event. Run sahjhan status.",
            "blocks_commit": True,
            "blocks_all": True,
        })

    if fixes >= 3 and not commits and state == "fix_loop":
        obligations.append({
            "msg": f"pattern_check due ({fixes} fixes). sahjhan transition pattern_check",
            "blocks_commit": False,
            "blocks_all": False,
        })

    return obligations


def format_injection(obligations: list[dict[str, Any]], cache: dict[str, Any] | None) -> str:
    """Format obligations into terse injection text. Max ~30 tokens."""
    if not obligations:
        return ""
    ob = obligations[0]
    blocks = "BLOCKED" if ob.get("blocks_commit") or ob.get("blocks_all") else "PROTOCOL"
    return f"{blocks}: {ob['msg']}"


def format_state_line(cache: dict[str, Any] | None) -> str:
    """One-line state summary for primer injection. Max ~20 tokens."""
    if cache is None or not cache.get("active"):
        return ""
    state = cache.get("state", "?")
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)
    commits = len(cache.get("unregistered_commits", []))
    parts = [f"Protocol: {state}", f"{perspective} {p_done}/{p_total}"]
    if commits:
        parts.append(f"{commits} pending commits")
    fixes = cache.get("fixes_since_pattern", 0)
    if fixes >= 3:
        parts.append("pattern_check due")
    return " | ".join(parts)

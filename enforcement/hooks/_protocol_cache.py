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
_ENFORCEMENT_FRESHNESS_MINUTES = 30


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
    except (OSError, KeyError, ValueError):
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
        "last_sahjhan_cmd": "",
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


def is_enforcement_fresh(
    cache: dict[str, Any] | None,
    threshold_minutes: int = _ENFORCEMENT_FRESHNESS_MINUTES,
) -> bool:
    """Check if enforcement should be active based on sahjhan command recency.

    Returns True if a sahjhan command was run within the threshold window,
    indicating an active audit session. Returns False if the cache is
    missing, the timestamp is absent/unparseable, or the timestamp is stale.
    """
    if cache is None:
        return False
    ts = cache.get("last_sahjhan_cmd", "")
    if not ts:
        return False
    try:
        from datetime import timedelta
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)  # noqa: UP017
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)  # noqa: UP017
        return last >= cutoff
    except (ValueError, TypeError):
        return False


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
        m = re.match(r"^\s*(\w[\w-]*):\s+(\d+)/(\d+)\s+\[(.+)\]", stripped)
        if m:
            set_name = m.group(1)
            complete = int(m.group(2))
            total = int(m.group(3))
            members_text = m.group(4)
            result["sets"][set_name] = {"complete": complete, "total": total}
            # Parse individual members to find the first incomplete one
            if set_name == "perspective":
                for member in members_text.split(","):
                    member = member.strip()
                    if member.startswith("\u2713"):
                        continue  # ✓ = complete
                    # First member without ✓ is the current perspective
                    # Strip any prefix markers (· etc)
                    name = re.sub(r"^[·\s]+", "", member).strip()
                    if name:
                        result["_first_incomplete_perspective"] = name
                        break
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
    if perspective_set:
        result["perspectives_done"] = perspective_set.get("complete", 0)
        result["perspectives_total"] = perspective_set.get("total", 13)
        if "_first_incomplete_perspective" in result:
            result["current_perspective"] = result.pop("_first_incomplete_perspective")
        elif perspective_set.get("complete", 0) == perspective_set.get("total", 13):
            result["current_perspective"] = "all_complete"

    return result


def _split_shell_segments(cmd: str) -> list[str]:
    """Split a shell command on operators (&&, ||, ;, |) but not redirects.

    Strips shell redirections like 2>&1, >&2, 2>/dev/null before splitting,
    so they don't produce spurious segments. Also strips leading export
    statements and variable assignments from each segment.
    """
    # Strip shell redirections: 2>&1, >&2, 2>/dev/null, etc.
    cleaned = re.sub(r'\d*>&?\d+', '', cmd)
    cleaned = re.sub(r'\d*>/dev/null', '', cleaned)
    # Split on actual shell operators: &&, ||, ;, |
    # Use specific multi-char operators first to avoid splitting on single &
    segments = re.split(r'&&|\|\||[;|]', cleaned)
    result = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Strip leading export and variable assignments
        seg = re.sub(r'^(?:export\s+)?\w+=\S*\s*', '', seg).strip()
        # May need multiple rounds for "export FOO=bar" (export stripped, then nothing left)
        if seg:
            result.append(seg)
    return result


def is_git_commit(cmd: str) -> bool:
    """Detect git commit commands (not amend).

    Only matches ``git commit`` at the start of a shell segment (after
    ;, &&, ||, |, or start of string). Does not match git commit inside
    echo, comments, or quoted strings.

    Checks for ``--amend`` as a CLI flag (word boundary), not as a
    substring of the commit message.
    """
    for segment in _split_shell_segments(cmd):
        seg = segment.strip()
        # Strip leading env var assignments (VAR=x git commit ...)
        stripped_seg = re.sub(r"^\s*(?:\w+=\S*\s+)*", "", seg)
        if not re.match(r"git\s+commit\b(?!-)", stripped_seg):
            continue
        # This segment starts with git commit — check for --amend
        stripped = re.sub(r'-m\s+(?:"[^"]*"|\'[^\']*\'|\S+)', '', seg)
        if not re.search(r"(?<!\w)--amend\b", stripped):
            return True
    return False


def is_sahjhan_cmd(cmd: str) -> bool:
    """Detect commands that are exclusively sahjhan CLI invocations.

    Returns True only when ALL non-empty segments are sahjhan commands.
    A chained command like ``git commit; sahjhan status`` returns False
    because the git-commit segment is not a sahjhan invocation.

    Handles shell redirections (2>&1) and leading export/env-var prefixes
    by stripping them before segment analysis.
    """
    segments = _split_shell_segments(cmd)
    if not segments:
        return False
    for seg in segments:
        parts = seg.split()
        p0 = parts[0] if parts else ""
        is_sahjhan = (
            p0 == "sahjhan"
            or p0.endswith("/sahjhan")
            or "/sahjhan-" in p0
            or p0.startswith("sahjhan-")
        )
        if not (parts and is_sahjhan):
            return False
    return True


def is_fix_loop_state(cache: dict[str, Any] | None) -> bool:
    """Check if the current protocol state is fix_loop."""
    if cache is None:
        return False
    return cache.get("state") == "fix_loop"


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

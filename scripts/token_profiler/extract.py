"""JSONL extraction module for the token profiler.

Reads Claude Code session JSONL files and produces RawTurn objects.
Handles streaming chunk merging, tool result pairing, and subagent discovery.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from token_profiler.models import ContentBlock, RawTurn, ToolResult, Usage

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_session(session_path: Path) -> list[RawTurn]:
    """Read a session JSONL file and return a list of RawTurn objects.

    Groups ``assistant`` messages by ``requestId``, merges streaming chunks,
    and pairs tool results from subsequent ``user`` messages.

    CRITICAL: ``output_tokens`` is cumulative across streaming chunks.
    Only the value from the *final* chunk (where ``stop_reason`` is non-null)
    is correct.  ``input_tokens`` / cache tokens are stable across chunks.
    """
    records = _read_jsonl(session_path)

    # Pass 1: group assistant chunks by requestId (preserving encounter order)
    request_order: list[str] = []
    chunks_by_request: dict[str, list[dict]] = {}
    # Collect tool_use_ids per request so we can pair results
    tool_ids_by_request: dict[str, set[str]] = {}

    # Collect tool results from user messages (keyed by tool_use_id)
    pending_tool_results: dict[str, ToolResult] = {}

    for rec in records:
        msg_type = rec.get("type")

        if msg_type == "assistant":
            rid = rec.get("requestId", "")
            if not rid:
                continue
            if rid not in chunks_by_request:
                request_order.append(rid)
                chunks_by_request[rid] = []
                tool_ids_by_request[rid] = set()
            chunks_by_request[rid].append(rec)

            # Track tool_use ids produced by this request
            api_msg = rec.get("message", {})
            for block in api_msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_id = block.get("id", "")
                    if tool_id:
                        tool_ids_by_request[rid].add(tool_id)

        elif msg_type == "user":
            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_use_id = item.get("tool_use_id", "")
                        is_error = item.get("is_error", False)
                        raw_content = item.get("content")
                        if is_error:
                            ctype, csize = "error", len(raw_content) if isinstance(raw_content, str) else 0
                        else:
                            ctype, csize = classify_tool_result_content(raw_content)
                        pending_tool_results[tool_use_id] = ToolResult(
                            tool_use_id=tool_use_id,
                            content_type=ctype,
                            content_size_chars=csize,
                        )

    # Pass 2: build RawTurns from grouped chunks
    turns: list[RawTurn] = []
    for idx, rid in enumerate(request_order):
        chunks = chunks_by_request[rid]
        turn = _merge_chunks(rid, idx, chunks)

        # Pair tool results
        for tool_id in tool_ids_by_request.get(rid, set()):
            if tool_id in pending_tool_results:
                turn.tool_results.append(pending_tool_results[tool_id])

        # Sort tool_results to match content_block order
        tool_id_order = [b.tool_use_id for b in turn.content_blocks if b.tool_use_id]
        result_map = {tr.tool_use_id: tr for tr in turn.tool_results}
        turn.tool_results = [result_map[tid] for tid in tool_id_order if tid in result_map]

        turns.append(turn)

    return turns


def classify_tool_result_content(content: str | list | None) -> tuple[str, int]:
    """Classify a tool result's content and return (content_type, content_size_chars).

    Content types:
    - ``"text"``: plain string content
    - ``"tool_references"``: list of tool_reference objects
    - ``"empty"``: None, empty string, or empty list
    - ``"error"``: error result (handled separately in caller via is_error)
    """
    if content is None:
        return ("empty", 0)

    if isinstance(content, str):
        if not content:
            return ("empty", 0)
        return ("text", len(content))

    if isinstance(content, list):
        if not content:
            return ("empty", 0)

        # Check if all items are tool_reference objects
        if all(isinstance(item, dict) and item.get("type") == "tool_reference" for item in content):
            return ("tool_references", 0)

        # Otherwise it's a list with text items — compute total text size
        total_size = 0
        for item in content:
            if isinstance(item, dict):
                total_size += len(item.get("text", ""))
            elif isinstance(item, str):
                total_size += len(item)
        return ("text", total_size)

    return ("empty", 0)


def tool_description(name: str, inp: dict) -> str:
    """Compact one-liner describing a tool call."""
    if name == "Bash":
        return inp.get("description", inp.get("command", "")[:80])
    elif name in ("Read", "Write", "Edit"):
        p = inp.get("file_path", "")
        return "/".join(p.split("/")[-2:]) if "/" in p else p
    elif name == "Grep":
        return f"/{inp.get('pattern', '')}/"
    elif name == "Glob":
        return inp.get("pattern", "")
    elif name == "Agent":
        desc = inp.get("description", "")
        st = inp.get("subagent_type", "")
        bg = " (background)" if inp.get("run_in_background") else ""
        return f"[{st}] {desc}{bg}" if st else desc
    elif name in ("TaskCreate", "TaskUpdate"):
        desc = inp.get("subject", inp.get("taskId", ""))
        if name == "TaskUpdate":
            return f"#{desc} \u2192 {inp.get('status', '')}"
        return desc
    elif name == "Skill":
        return inp.get("skill", "")
    elif name == "ToolSearch":
        return inp.get("query", "")
    else:
        return ""


def discover_subagents(session_path: Path) -> list[Path]:
    """Find subagent JSONL files relative to a session file.

    Checks two locations (Claude Code layout varies):
    1. ``<parent>/<session_stem>/subagents/*.jsonl`` — standard Claude Code layout
       where ``<session_uuid>.jsonl`` sits next to ``<session_uuid>/subagents/``.
    2. ``<parent>/subagents/*.jsonl`` — fallback for sessions already inside
       a session-specific directory.
    """
    # Primary: sibling directory named after session stem
    stem_dir = session_path.parent / session_path.stem / "subagents"
    if stem_dir.is_dir():
        return sorted(stem_dir.glob("*.jsonl"))

    # Fallback: subagents directly under session file's parent
    sub_dir = session_path.parent / "subagents"
    if sub_dir.is_dir():
        return sorted(sub_dir.glob("*.jsonl"))

    return []


def find_project_dir(project_root: str | None = None) -> Path | None:
    """Resolve project root to ``~/.claude/projects/<mangled-path>/``.

    Path mangling replaces ``/`` with ``-``.  Auto-detects from git root
    or cwd when *project_root* is not given.
    """
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return None

    if project_root:
        mangled = project_root.replace("/", "-")
        candidate = claude_dir / mangled
        if candidate.exists():
            return candidate

    # Auto-detect from git root or cwd
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = str(Path.cwd())

    mangled = root.replace("/", "-")
    candidate = claude_dir / mangled
    if candidate.exists():
        return candidate

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    """Read all lines from a JSONL file, skipping blank lines."""
    records: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _merge_chunks(request_id: str, index: int, chunks: list[dict]) -> RawTurn:
    """Merge multiple streaming chunks for a single requestId into one RawTurn.

    - ``output_tokens`` from final chunk only (cumulative in stream).
    - ``input_tokens`` / cache tokens are stable — taken from final chunk.
    - Content blocks are collected from all chunks.
    - ``assistant_text`` is the concatenation of all text blocks.
    """
    content_blocks: list[ContentBlock] = []
    text_parts: list[str] = []
    model = "unknown"
    timestamp: str | None = None
    stop_reason = "end_turn"

    # Find the final chunk (the one with non-null stop_reason)
    final_chunk: dict | None = None
    for chunk in chunks:
        api_msg = chunk.get("message", {})
        sr = api_msg.get("stop_reason")
        if sr is not None:
            final_chunk = chunk

    # If no chunk has a stop_reason, use the last one
    if final_chunk is None:
        final_chunk = chunks[-1]

    # Extract usage from final chunk only
    final_usage_data = final_chunk.get("message", {}).get("usage", {})
    usage = Usage.from_dict(final_usage_data)

    # Extract stop_reason from final chunk
    stop_reason = final_chunk.get("message", {}).get("stop_reason") or "end_turn"

    # Process all chunks for content blocks, model, timestamp
    for chunk in chunks:
        api_msg = chunk.get("message", {})

        # Extract model (take from any chunk — they're all the same)
        chunk_model = api_msg.get("model")
        if chunk_model:
            model = chunk_model

        # Extract timestamp from first chunk
        if timestamp is None:
            ts = chunk.get("timestamp")
            if ts:
                timestamp = ts

        # Collect content blocks
        for block in api_msg.get("content", []):
            if not isinstance(block, dict):
                continue

            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                content_blocks.append(ContentBlock(
                    type="text",
                    size=len(text),
                    text_content=text,
                ))
                text_parts.append(text)

            elif btype == "thinking":
                thinking = block.get("thinking", "")
                content_blocks.append(ContentBlock(
                    type="thinking",
                    size=len(thinking),
                    thinking_content=thinking,
                ))

            elif btype == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                tool_id = block.get("id", "")
                desc = tool_description(tool_name, tool_input)
                input_json = json.dumps(tool_input)
                content_blocks.append(ContentBlock(
                    type="tool_use",
                    size=len(input_json),
                    tool_name=tool_name,
                    tool_input_summary=desc,
                    tool_use_id=tool_id,
                ))

    return RawTurn(
        request_id=request_id,
        index=index,
        timestamp=timestamp,
        usage=usage,
        stop_reason=stop_reason,
        content_blocks=content_blocks,
        tool_results=[],
        assistant_text="".join(text_parts),
        model=model,
    )

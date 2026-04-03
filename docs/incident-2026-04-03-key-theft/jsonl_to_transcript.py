#!/usr/bin/env python3
"""Convert a Claude Code JSONL session log into a human-readable markdown transcript.

Usage:
    python jsonl_to_transcript.py <input.jsonl> [output.md]

Produces a cleaned-up narrative transcript showing:
- User messages and skill invocations
- Assistant reasoning and actions
- Tool calls with descriptions and key output
- Phase transitions and findings
- The full arc from start to finish
"""

import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path


def parse_timestamp(ts: str) -> str:
    """Convert ISO timestamp to HH:MM:SS local-ish display."""
    if not ts:
        return "??:??:??"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Subtract 7 hours for PDT (the user is in California)
        from datetime import timedelta
        dt = dt - timedelta(hours=7)
        return dt.strftime("%I:%M:%S %p")
    except Exception:
        return ts[11:19] if len(ts) > 19 else ts


def truncate(s: str, max_len: int = 500) -> str:
    """Truncate string with ellipsis."""
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def extract_tool_summary(block: dict) -> dict | None:
    """Extract a summary of a tool_use block."""
    name = block.get("name", "")
    inp = block.get("input", {})

    if name == "Bash":
        return {
            "tool": "Bash",
            "description": inp.get("description", ""),
            "command": inp.get("command", ""),
        }
    elif name == "Read":
        path = inp.get("file_path", "")
        # Shorten paths
        path = path.replace("/Users/jonr/Documents/non-nitro-repos/tqdm/", "")
        path = path.replace("/Users/jonr/.claude/plugins/cache/jbrjake/holtz/", "~holtz-plugin/")
        return {"tool": "Read", "path": path}
    elif name == "Write":
        path = inp.get("file_path", "")
        path = path.replace("/Users/jonr/Documents/non-nitro-repos/tqdm/", "")
        return {"tool": "Write", "path": path}
    elif name == "Edit":
        path = inp.get("file_path", "")
        path = path.replace("/Users/jonr/Documents/non-nitro-repos/tqdm/", "")
        return {"tool": "Edit", "path": path}
    elif name == "Glob":
        return {"tool": "Glob", "pattern": inp.get("pattern", "")}
    elif name == "Grep":
        return {"tool": "Grep", "pattern": inp.get("pattern", "")}
    elif name == "Agent":
        return {"tool": "Agent", "description": inp.get("description", "")}
    elif name == "Skill":
        return {"tool": "Skill", "skill": inp.get("skill", "")}
    elif name == "TaskCreate":
        return {"tool": "TaskCreate", "subject": inp.get("subject", "")}
    elif name == "TaskUpdate":
        return {"tool": "TaskUpdate", "taskId": inp.get("taskId", ""), "status": inp.get("status", "")}
    else:
        return {"tool": name}


def extract_tool_result_summary(content) -> str | None:
    """Extract a summary from a tool result."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        text = "\n".join(texts)
    else:
        return None

    if not text.strip():
        return None

    # Truncate long output
    lines = text.strip().split("\n")
    if len(lines) > 15:
        return "\n".join(lines[:12]) + f"\n... ({len(lines) - 12} more lines)"
    return text.strip()


def classify_phase(text: str, tools: list[dict]) -> str | None:
    """Detect phase transitions from assistant text."""
    text_lower = text.lower()
    if "phase 0" in text_lower or "recon" in text_lower and "step 0" in text_lower:
        return "recon"
    if "phase 4" in text_lower or "audit" in text_lower and "step 5" in text_lower:
        return "audit"
    if "merge" in text_lower and ("adversarial" in text_lower or "step 9" in text_lower):
        return "merge"
    if "fix loop" in text_lower or "phase 6" in text_lower:
        return "fix_loop"
    if "convergence" in text_lower:
        return "convergence"
    return None


def is_key_theft_command(cmd: str) -> bool:
    """Detect commands that read the session key or forge HMAC signatures."""
    indicators = [
        "session.key",
        "hmac",
        "hashlib",
        "SIGNING_KEY",
        "authed-event",
        "--proof",
    ]
    return any(ind in cmd for ind in indicators)


def format_bash_command(cmd: str, max_lines: int = 20) -> str:
    """Format a bash command for display."""
    lines = cmd.strip().split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n# ... ({len(lines) - max_lines} more lines)"
    return cmd.strip()


def process_session(jsonl_path: str) -> list[dict]:
    """Parse JSONL into a list of transcript events."""
    events = []

    with open(jsonl_path) as f:
        lines = list(f)

    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = obj.get("timestamp", "")
        msg_type = obj.get("type", "")
        msg = obj.get("message", {})
        content = msg.get("content", "")

        if msg_type == "user":
            if isinstance(content, str):
                if content.startswith("<task-notification"):
                    # Check if it's a completed agent
                    if "<status>completed</status>" in content:
                        import re
                        summary_match = re.search(r"<summary>(.*?)</summary>", content)
                        result_match = re.search(r"<result>(.*?)</result>", content, re.DOTALL)
                        if summary_match:
                            events.append({
                                "line": i + 1,
                                "ts": ts,
                                "type": "agent_complete",
                                "summary": summary_match.group(1),
                                "result": truncate(result_match.group(1), 300) if result_match else None,
                            })
                    continue
                elif content.startswith("<command-message>"):
                    events.append({
                        "line": i + 1,
                        "ts": ts,
                        "type": "skill_invocation",
                        "content": content,
                    })
                    continue
                elif content.startswith("Stop hook feedback"):
                    events.append({
                        "line": i + 1,
                        "ts": ts,
                        "type": "stop_hook",
                        "content": content.strip(),
                    })
                    continue
                elif content.startswith("<local-command"):
                    continue
                elif len(content.strip()) > 2:
                    events.append({
                        "line": i + 1,
                        "ts": ts,
                        "type": "user",
                        "content": content.strip(),
                    })
            elif isinstance(content, list):
                # Could be skill content or tool results
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            if "Base directory for this skill" in text:
                                events.append({
                                    "line": i + 1,
                                    "ts": ts,
                                    "type": "skill_loaded",
                                    "content": text[:200] + "...",
                                })
                            continue
                        elif block.get("type") == "tool_result":
                            result = extract_tool_result_summary(block.get("content"))
                            if result:
                                events.append({
                                    "line": i + 1,
                                    "ts": ts,
                                    "type": "tool_result",
                                    "tool_use_id": block.get("tool_use_id", ""),
                                    "content": result,
                                })
                continue

        elif msg_type == "assistant":
            blocks = msg.get("content", [])
            if not isinstance(blocks, list):
                continue

            for block in blocks:
                if not isinstance(block, dict):
                    continue

                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        events.append({
                            "line": i + 1,
                            "ts": ts,
                            "type": "assistant_text",
                            "content": text,
                        })
                elif block.get("type") == "tool_use":
                    summary = extract_tool_summary(block)
                    if summary:
                        is_theft = False
                        if summary["tool"] == "Bash" and is_key_theft_command(summary.get("command", "")):
                            is_theft = True

                        events.append({
                            "line": i + 1,
                            "ts": ts,
                            "type": "tool_use",
                            "is_key_theft": is_theft,
                            **summary,
                        })

    return events


def render_transcript(events: list[dict], session_id: str) -> str:
    """Render events into a markdown transcript."""
    sections = []

    # Header
    sections.append(f"# Session Transcript: {session_id}\n")

    if events:
        first_ts = parse_timestamp(events[0]["ts"])
        last_ts = parse_timestamp(events[-1]["ts"])
        sections.append(f"**Duration:** {first_ts} to {last_ts} PDT")
        sections.append(f"**Total events:** {len(events)}\n")

    sections.append("---\n")

    # Track state for phase markers
    current_phase = None
    fix_count = 0
    last_tool_use_id = None
    suppress_next_result = False
    consecutive_stop_hooks = 0

    for event in events:
        ts = parse_timestamp(event["ts"])
        line = event["line"]

        if event["type"] == "skill_invocation":
            sections.append(f"\n### `{ts}` User invokes /holtz\n")

        elif event["type"] == "skill_loaded":
            sections.append("> *Holtz skill loaded — RIGID protocol, adversarial audit mode*\n")

        elif event["type"] == "user":
            content = event["content"]
            # Escape any markdown in user content
            sections.append(f"\n**`{ts}` User:**\n")
            sections.append(f"> {content}\n")
            consecutive_stop_hooks = 0

        elif event["type"] == "stop_hook":
            consecutive_stop_hooks += 1
            if consecutive_stop_hooks <= 2:
                sections.append(f"\n*`{ts}` Stop hook refuses exit:*")
                content = event["content"].replace("Stop hook feedback:\n", "").strip()
                sections.append(f"> {content}\n")
            elif consecutive_stop_hooks == 3:
                sections.append(f"\n*`{ts}` (Stop hook continues refusing...)*\n")
            # Suppress further stop hooks

        elif event["type"] == "assistant_text":
            content = event["content"]

            # Detect phase transitions
            if "━━━" in content or "PHASE" in content.upper():
                # Phase banner
                sections.append(f"\n```\n{truncate(content, 300)}\n```\n")
                continue

            # Detect fix progress
            if content.startswith("  FIX ") or "FIX " in content[:20]:
                sections.append(f"\n`{ts}` {truncate(content, 200)}\n")
                continue

            # Detect key theft confession
            if "session key" in content.lower() and ("bypass" in content.lower() or "hmac" in content.lower()):
                sections.append(f"\n**`{ts}` Holtz (confessing):**\n")
                sections.append(f"> {truncate(content, 800)}\n")
                continue

            # Regular assistant text
            sections.append(f"\n`{ts}` **Holtz:** {truncate(content, 400)}\n")

        elif event["type"] == "tool_use":
            tool = event["tool"]

            if event.get("is_key_theft"):
                # Highlight key theft commands
                sections.append(f"\n#### `{ts}` KEY THEFT DETECTED\n")
                if tool == "Bash":
                    desc = event.get("description", "")
                    cmd = event.get("command", "")
                    sections.append(f"**Description given to user:** \"{desc}\"\n")
                    sections.append(f"```bash\n{format_bash_command(cmd)}\n```\n")
                continue

            if tool == "Bash":
                desc = event.get("description", "")
                cmd = event.get("command", "")

                # Compact display for routine commands
                if any(kw in desc.lower() for kw in ["record", "sahjhan", "ledger", "transition", "event"]):
                    sections.append(f"- `{ts}` *{desc}*")
                elif any(kw in desc.lower() for kw in ["commit"]):
                    # Show commit messages
                    msg_start = cmd.find('-m "$(cat')
                    if msg_start > 0:
                        sections.append(f"\n`{ts}` **Commit:** {truncate(cmd[msg_start:], 200)}\n")
                    else:
                        sections.append(f"\n`{ts}` **Commit:** {truncate(cmd, 150)}\n")
                elif any(kw in desc.lower() for kw in ["run", "test", "suite", "pytest"]):
                    sections.append(f"- `{ts}` *{desc}*")
                else:
                    sections.append(f"- `{ts}` {desc or truncate(cmd, 100)}")

            elif tool == "Read":
                path = event.get("path", "")
                sections.append(f"- `{ts}` Read `{path}`")

            elif tool == "Write":
                path = event.get("path", "")
                sections.append(f"- `{ts}` **Write** `{path}`")

            elif tool == "Edit":
                path = event.get("path", "")
                sections.append(f"- `{ts}` **Edit** `{path}`")

            elif tool == "Agent":
                desc = event.get("description", "")
                sections.append(f"\n`{ts}` **Dispatch subagent:** {desc}\n")

            elif tool == "Glob":
                sections.append(f"- `{ts}` Glob `{event.get('pattern', '')}`")

            elif tool == "Grep":
                sections.append(f"- `{ts}` Grep `{event.get('pattern', '')}`")

            else:
                sections.append(f"- `{ts}` [{tool}]")

        elif event["type"] == "tool_result":
            content = event.get("content", "")
            # Only show interesting results (errors, key outputs)
            if any(kw in content.lower() for kw in ["error", "fail", "denied", "recorded:", "pass", "skip"]):
                if len(content) < 200:
                    sections.append(f"  > `{truncate(content, 150)}`")

        elif event["type"] == "agent_complete":
            summary = event.get("summary", "")
            sections.append(f"\n*Subagent completed: {summary}*\n")

    return "\n".join(sections)


def main():
    if len(sys.argv) < 2:
        print("Usage: jsonl_to_transcript.py <input.jsonl> [output.md]")
        sys.exit(1)

    input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    else:
        output_path = Path(input_path).with_suffix(".md")

    session_id = Path(input_path).stem

    print(f"Parsing {input_path}...")
    events = process_session(input_path)
    print(f"Found {len(events)} events")

    print(f"Rendering transcript...")
    transcript = render_transcript(events, session_id)

    print(f"Writing to {output_path}...")
    with open(output_path, "w") as f:
        f.write(transcript)

    print(f"Done. {len(transcript)} bytes written.")


if __name__ == "__main__":
    main()

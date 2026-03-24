#!/usr/bin/env python3
"""Extract a real asciinema .cast from a Claude Code session JSONL.

Reads the session history and reconstructs what the user actually saw
in the terminal, including tool calls, results, and text output.
Injects token count commentary at milestones.
"""
import json
import sys
from pathlib import Path

# ANSI codes
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"

# Playback speed: how many real seconds = 1 cast second
# The actual session was ~49 minutes for the audit portion.
# At 10:1 compression, that's ~5 minutes of playback.
SPEED = 10.0

# Cut the recording at this user message (end of the audit, before showcase work)
CUT_MARKER = "take this last holtz run"


def cast_header():
    return json.dumps({
        "version": 2,
        "width": 140,
        "height": 50,
        "timestamp": 1742860800,
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": "Holtz Run 14 — Full Audit (real session history)",
    })


def event(t, text):
    """Output event. Convert \n to \r\n for terminal."""
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 3), "o", text])


def token_comment(t, usage):
    """Inject a token count comment."""
    inp = usage.get("input_tokens", 0)
    cw = usage.get("cache_creation_input_tokens", 0)
    cr = usage.get("cache_read_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    ctx = inp + cw + cr
    return event(t, f"\n{DIM}╌╌╌ context: {ctx:,} tokens (cache read: {cr:,}, write: {cw:,}, output: {out:,}) ╌╌╌{RESET}\n")


def extract(session_path, output_path):
    messages = []
    with open(session_path) as f:
        for line in f:
            messages.append(json.loads(line.strip()))

    events = [cast_header()]
    t = 0.0
    start_ts = None
    tool_names = {}  # tool_use_id -> tool name + description
    hit_cut = False

    for msg in messages:
        if hit_cut:
            break

        ts_str = msg.get("timestamp", "")
        msg_type = msg.get("type")

        # Parse timestamp for real timing
        if ts_str and start_ts is None:
            start_ts = ts_str

        if ts_str and start_ts:
            # Calculate real elapsed time, then compress
            try:
                from datetime import datetime
                current = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                start = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                real_elapsed = (current - start).total_seconds()
                t = real_elapsed / SPEED
            except Exception:
                pass

        # ─── User messages ───────────────────────────────────
        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")

            # Check for cut marker
            if isinstance(content, str) and CUT_MARKER in content.lower():
                hit_cut = True
                events.append(event(t, f"\n{DIM}╌╌╌ [audit complete — session continues with showcase work] ╌╌╌{RESET}\n"))
                break

            # Direct user text input (not tool results, not meta)
            if isinstance(content, str) and content.strip() and not content.startswith("<") and not msg.get("isMeta"):
                events.append(event(t, f"\n{BOLD}{MAGENTA}> {content.strip()}{RESET}\n\n"))

            # Tool results — show abbreviated
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        tool_info = tool_names.get(tool_id, "")
                        result_text = ""
                        rc = block.get("content", "")
                        if isinstance(rc, str):
                            result_text = rc
                        elif isinstance(rc, list):
                            for rb in rc:
                                if isinstance(rb, dict) and rb.get("type") == "text":
                                    result_text = rb.get("text", "")
                                    break

                        is_error = block.get("is_error", False)

                        if result_text.strip():
                            # Truncate long results
                            lines = result_text.strip().split("\n")
                            if len(lines) > 20:
                                shown = "\n".join(lines[:15])
                                shown += f"\n{DIM}    ... ({len(lines) - 15} more lines){RESET}"
                            else:
                                shown = result_text.strip()

                            color = RED if is_error else DIM
                            if tool_info:
                                events.append(event(t, f"  {color}{tool_info}{RESET}\n"))
                            # Indent the result
                            indented = "\n".join(f"    {l}" for l in shown.split("\n"))
                            events.append(event(t + 0.01, f"{color}{indented}{RESET}\n"))

        # ─── Assistant messages ──────────────────────────────
        elif msg_type == "assistant":
            api_msg = msg.get("message", {})
            content = api_msg.get("content", [])
            usage = api_msg.get("usage", {})

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    # Text output — this is what the user sees
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            events.append(event(t, f"{text}\n"))

                    # Tool use — show the tool name and key params
                    elif block.get("type") == "tool_use":
                        name = block.get("name", "?")
                        tool_id = block.get("id", "")
                        inp = block.get("input", {})

                        # Build a compact description of the tool call
                        desc = ""
                        if name == "Bash":
                            cmd = inp.get("command", "")
                            desc_text = inp.get("description", "")
                            if len(cmd) > 100:
                                cmd = cmd[:97] + "..."
                            desc = f"{desc_text}" if desc_text else cmd
                        elif name == "Read":
                            path = inp.get("file_path", "")
                            desc = path.split("/")[-1] if "/" in path else path
                        elif name == "Write":
                            path = inp.get("file_path", "")
                            desc = path.split("/")[-1] if "/" in path else path
                        elif name == "Edit":
                            path = inp.get("file_path", "")
                            desc = path.split("/")[-1] if "/" in path else path
                        elif name == "Grep":
                            pattern = inp.get("pattern", "")
                            desc = f"/{pattern}/"
                        elif name == "Glob":
                            pattern = inp.get("pattern", "")
                            desc = pattern
                        elif name == "Agent":
                            desc = inp.get("description", inp.get("prompt", "")[:60])
                        elif name in ("TaskCreate", "TaskUpdate"):
                            desc = inp.get("subject", inp.get("status", ""))
                        elif name == "Skill":
                            desc = inp.get("skill", "")
                        else:
                            desc = name

                        tool_names[tool_id] = f"{name}: {desc}"
                        events.append(event(t, f"  {CYAN}⎿ {name}{RESET} {DIM}{desc}{RESET}\n"))

            # Inject token count after every text-containing assistant message
            if usage and any(isinstance(b, dict) and b.get("type") == "text" for b in (content if isinstance(content, list) else [])):
                events.append(token_comment(t + 0.02, usage))

    # Final summary
    events.append(event(t + 0.5, f"\n{BOLD}{'═' * 80}{RESET}\n"))
    events.append(event(t + 0.6, f"{BOLD}  Recording ends here. Total playback: {t:.0f}s at {SPEED:.0f}x compression.{RESET}\n"))
    events.append(event(t + 0.7, f"{BOLD}{'═' * 80}{RESET}\n"))

    with open(output_path, "w") as f:
        for e in events:
            f.write(e + "\n")

    print(f"Written {len(events)} events to {output_path}")
    print(f"Duration: {t:.1f}s at {SPEED:.0f}x (real session: ~{t * SPEED / 60:.0f} min)")


if __name__ == "__main__":
    session = sys.argv[1] if len(sys.argv) > 1 else str(
        Path.home() / ".claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl"
    )
    output = sys.argv[2] if len(sys.argv) > 2 else "docs/runs/run-14.cast"
    extract(session, output)

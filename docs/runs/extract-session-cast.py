#!/usr/bin/env python3
"""Extract a condensed asciinema .cast from a Claude Code session JSONL.

Shows what the user sees in Claude Code with tool calls collapsed:
assistant text output, tool call indicators (name + description),
user prompts, and injected token metadata. Tool results are omitted
(they're behind expandable sections in the real UI).

After the audit portion ends, appends the full SUMMARY.md content.
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

# Playback pacing
TEXT_DELAY = 1.5
TOOL_DELAY = 0.15
USER_DELAY = 2.0
TOKEN_DELAY = 0.8
SUMMARY_LINE_DELAY = 0.06

# Cut the recording at this user message
CUT_MARKER = "take this last holtz run"


def cast_header() -> str:
    return json.dumps({
        "version": 2,
        "width": 120,
        "height": 40,
        "timestamp": 1742860800,
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": "Holtz Run 14 \u2014 Full Audit with Adversarial Self-Play",
    })


def ev(t: float, text: str) -> str:
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 3), "o", text])


def extract(session_path: str, output_path: str, summary_path: str | None = None) -> None:
    messages = []
    with open(session_path) as f:
        for line in f:
            messages.append(json.loads(line.strip()))

    events = [cast_header()]
    t = 0.0
    tool_batch = []

    def flush_tools() -> None:
        nonlocal t
        if not tool_batch:
            return
        if len(tool_batch) <= 3:
            for name, desc in tool_batch:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += TOOL_DELAY
        else:
            for name, desc in tool_batch[:2]:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += TOOL_DELAY
            events.append(ev(t, f"  {DIM}  ... +{len(tool_batch) - 3} more tool calls ...{RESET}\n"))
            t += TOOL_DELAY
            name, desc = tool_batch[-1]
            events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
            t += TOOL_DELAY
        tool_batch.clear()

    for msg in messages:
        msg_type = msg.get("type")

        # ─── User messages ───────────────────────────────────
        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")

            if isinstance(content, str) and CUT_MARKER in content.lower():
                flush_tools()
                break

            if isinstance(content, str) and content.strip() and not content.startswith("<") and not msg.get("isMeta"):
                flush_tools()
                events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {content.strip()}{RESET}\n\n"))
                t += USER_DELAY

        # ─── Assistant messages ──────────────────────────────
        elif msg_type == "assistant":
            api_msg = msg.get("message", {})
            content = api_msg.get("content", [])
            usage = api_msg.get("usage", {})

            if not isinstance(content, list):
                continue

            has_text = False
            for block in content:
                if not isinstance(block, dict):
                    continue

                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        flush_tools()
                        events.append(ev(t, f"\n{text}\n"))
                        t += TEXT_DELAY
                        has_text = True

                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})

                    if name == "Bash":
                        desc = inp.get("description", inp.get("command", "")[:80])
                    elif name in ("Read", "Write", "Edit"):
                        p = inp.get("file_path", "")
                        desc = "/".join(p.split("/")[-2:]) if "/" in p else p
                    elif name == "Grep":
                        desc = f"/{inp.get('pattern', '')}/"
                    elif name == "Glob":
                        desc = inp.get("pattern", "")
                    elif name == "Agent":
                        desc = inp.get("description", "")
                        st = inp.get("subagent_type", "")
                        bg = " (background)" if inp.get("run_in_background") else ""
                        if st:
                            desc = f"[{st}] {desc}{bg}"
                    elif name in ("TaskCreate", "TaskUpdate"):
                        desc = inp.get("subject", inp.get("taskId", ""))
                        if name == "TaskUpdate":
                            desc = f"#{desc} \u2192 {inp.get('status', '')}"
                    elif name == "Skill":
                        desc = inp.get("skill", "")
                    elif name == "ToolSearch":
                        desc = inp.get("query", "")
                    else:
                        desc = ""

                    tool_batch.append((name, desc))

            # Token marker after text output (tokens only, no cost)
            if usage and has_text:
                flush_tools()
                u_in = usage.get("input_tokens", 0)
                u_cw = usage.get("cache_creation_input_tokens", 0)
                u_cr = usage.get("cache_read_input_tokens", 0)
                u_out = usage.get("output_tokens", 0)
                ctx = u_in + u_cw + u_cr

                events.append(ev(t, f"{DIM}  [{ctx:,} ctx | {u_out:,} out]{RESET}\n"))
                t += TOKEN_DELAY

    flush_tools()

    # ─── Append SUMMARY.md ──────────────────────────────────
    if summary_path is None:
        # Try to find it relative to the session
        candidates = [
            Path("docs/holtz/SUMMARY.md"),
            Path(session_path).parent.parent / "docs" / "holtz" / "SUMMARY.md",
        ]
        for c in candidates:
            if c.exists():
                summary_path = str(c)
                break

    if summary_path and Path(summary_path).exists():
        summary_text = Path(summary_path).read_text()
        t += 1.0
        events.append(ev(t, f"\n{BOLD}{'━' * 80}{RESET}\n"))
        t += 0.3
        events.append(ev(t, f"{BOLD}  SUMMARY.md{RESET}\n"))
        events.append(ev(t + 0.1, f"{BOLD}{'━' * 80}{RESET}\n\n"))
        t += 0.5

        for line in summary_text.split("\n"):
            events.append(ev(t, f"{line}\n"))
            t += SUMMARY_LINE_DELAY

        t += 1.0

    with open(output_path, "w") as f:
        for e in events:
            f.write(e + "\n")

    print(f"Written {len(events)} events to {output_path}")
    print(f"Playback duration: {t:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract-session-cast.py <session.jsonl> [output.cast]", file=sys.stderr)
        sys.exit(1)
    session = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "docs/runs/run-14.cast"
    extract(session, output)

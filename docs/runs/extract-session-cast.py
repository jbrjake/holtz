#!/usr/bin/env python3
"""Extract a condensed asciinema .cast from a Claude Code session JSONL.

Shows what the user sees in Claude Code with tool calls collapsed:
assistant text output, tool call indicators (name + description),
user prompts, and injected token/cost metadata. Tool results are
omitted (they're behind expandable sections in the real UI).
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

# Opus pricing
CACHE_READ_RATE = 1.50 / 1_000_000
CACHE_WRITE_RATE = 18.75 / 1_000_000
INPUT_RATE = 15.0 / 1_000_000
OUTPUT_RATE = 75.0 / 1_000_000

# Playback pacing: fixed delay between events (not real-time).
# Text gets a bit more time so it's readable. Tool calls are fast.
TEXT_DELAY = 1.5       # seconds per text block
TOOL_DELAY = 0.15      # seconds per tool call indicator
USER_DELAY = 2.0       # pause on user messages
TOKEN_DELAY = 0.8      # pause on token markers

# Cut the recording at this user message
CUT_MARKER = "take this last holtz run"


def cast_header():
    return json.dumps({
        "version": 2,
        "width": 120,
        "height": 40,
        "timestamp": 1742860800,
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": "Holtz Run 14 \u2014 Full Audit with Adversarial Self-Play",
    })


def ev(t, text):
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 3), "o", text])


def cost_so_far(cum):
    """Calculate running cost from cumulative token counts."""
    return (cum["input"] * INPUT_RATE +
            cum["cache_write"] * CACHE_WRITE_RATE +
            cum["cache_read"] * CACHE_READ_RATE +
            cum["output"] * OUTPUT_RATE)


def extract(session_path, output_path):
    messages = []
    with open(session_path) as f:
        for line in f:
            messages.append(json.loads(line.strip()))

    events = [cast_header()]
    t = 0.0
    cum = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    tool_batch = []  # accumulate consecutive tool calls, show as compact group

    def flush_tools():
        """Write accumulated tool calls as a compact block."""
        nonlocal t
        if not tool_batch:
            return
        if len(tool_batch) <= 3:
            for name, desc in tool_batch:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += TOOL_DELAY
        else:
            # Show first 2, count, last 1
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
                events.append(ev(t, f"\n{DIM}\u2500\u2500\u2500 audit complete \u2500\u2500\u2500{RESET}\n"))
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

                    # Compact description
                    if name == "Bash":
                        desc = inp.get("description", inp.get("command", "")[:80])
                    elif name == "Read":
                        p = inp.get("file_path", "")
                        desc = "/".join(p.split("/")[-2:]) if "/" in p else p
                    elif name == "Write":
                        p = inp.get("file_path", "")
                        desc = "/".join(p.split("/")[-2:]) if "/" in p else p
                    elif name == "Edit":
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

            # Token + cost marker after text output
            if usage and has_text:
                flush_tools()
                u_in = usage.get("input_tokens", 0)
                u_cw = usage.get("cache_creation_input_tokens", 0)
                u_cr = usage.get("cache_read_input_tokens", 0)
                u_out = usage.get("output_tokens", 0)
                ctx = u_in + u_cw + u_cr

                cum["input"] += u_in
                cum["cache_write"] += u_cw
                cum["cache_read"] += u_cr
                cum["output"] += u_out

                running_cost = cost_so_far(cum)
                events.append(ev(t, f"{DIM}  [{ctx:,} ctx tokens | ${running_cost:.2f} running cost]{RESET}\n"))
                t += TOKEN_DELAY

    flush_tools()

    # Final tally
    total_cost = cost_so_far(cum)
    events.append(ev(t + 0.5, f"\n{BOLD}\u2550{'=' * 78}{RESET}\n"))
    events.append(ev(t + 0.6, f"  Main context: {cum['cache_read'] + cum['cache_write'] + cum['input']:,} billed input tokens\n"))
    events.append(ev(t + 0.7, f"  Output: {cum['output']:,} tokens | API cost (main only): ${total_cost:.2f}\n"))
    events.append(ev(t + 0.8, f"  + Justine subagent: $33.20 | + other subagents: $20.18\n"))
    events.append(ev(t + 0.9, f"  {BOLD}Total API cost: $164.38{RESET}  (Opus pricing, prompt caching)\n"))
    events.append(ev(t + 1.0, f"{BOLD}\u2550{'=' * 78}{RESET}\n"))

    with open(output_path, "w") as f:
        for e in events:
            f.write(e + "\n")

    print(f"Written {len(events)} events to {output_path}")
    print(f"Playback duration: {t:.0f}s")


if __name__ == "__main__":
    session = sys.argv[1] if len(sys.argv) > 1 else str(
        Path.home() / ".claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl"
    )
    output = sys.argv[2] if len(sys.argv) > 2 else "docs/runs/run-14.cast"
    extract(session, output)

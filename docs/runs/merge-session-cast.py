#!/usr/bin/env python3
"""Merge a parent session and selected subagent(s) into one chronological cast.

Injects subagent events as a contiguous block at the point the parent dispatched
them, with visual banners showing the context switch. This avoids the noise of
interleaving concurrent events by timestamp.

Usage:
  python docs/runs/merge-session-cast.py \
    --parent SESSION.jsonl \
    --subagent SUBAGENT.jsonl::label \
    -o output.cast
"""
import argparse
import json
import sys
from pathlib import Path

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
BG_BLUE = "\x1b[44m"
BG_YELLOW = "\x1b[43m"
WHITE = "\x1b[37m"


def tool_description(name: str, inp: dict) -> str:
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
    elif name == "Skill":
        return inp.get("skill", "")
    else:
        return ""


def ev(t: float, text: str) -> str:
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 3), "o", text])


def process_messages(messages, events, t, text_delay, tool_delay, user_delay, token_delay):
    """Process a list of messages into cast events. Returns updated t."""
    tool_batch = []

    def flush_tools():
        nonlocal t
        if not tool_batch:
            return
        if len(tool_batch) <= 3:
            for name, desc in tool_batch:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += tool_delay
        else:
            for name, desc in tool_batch[:2]:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += tool_delay
            events.append(ev(t, f"  {DIM}  ... +{len(tool_batch) - 3} more tool calls ...{RESET}\n"))
            t += tool_delay
            name, desc = tool_batch[-1]
            events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
            t += tool_delay
        tool_batch.clear()

    for msg in messages:
        msg_type = msg.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            if msg.get("isMeta"):
                continue
            if isinstance(content, str) and content.startswith("<"):
                continue
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item["text"])
                content = "\n".join(text_parts)
            if isinstance(content, str) and content.strip():
                text = content.strip()
                flush_tools()
                if len(text) > 2000:
                    first_line = text.split("\n")[0][:120]
                    events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {first_line}...{RESET}\n\n"))
                elif len(text) > 500:
                    events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {text[:500]}\n{DIM}  ... ({len(text)} chars total){RESET}\n\n"))
                else:
                    events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {text}{RESET}\n\n"))
                t += user_delay

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
                        t += text_delay
                        has_text = True
                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    desc = tool_description(name, block.get("input", {}))
                    tool_batch.append((name, desc))

            if usage and has_text:
                flush_tools()
                u_in = usage.get("input_tokens", 0)
                u_cw = usage.get("cache_creation_input_tokens", 0)
                u_cr = usage.get("cache_read_input_tokens", 0)
                u_out = usage.get("output_tokens", 0)
                ctx = u_in + u_cw + u_cr
                events.append(ev(t, f"{DIM}  [{ctx:,} ctx | {u_out:,} out]{RESET}\n"))
                t += token_delay

    flush_tools()
    return t


def merge_cast(
    parent_path: str,
    subagent_specs: list[tuple[str, str]],
    output_path: str,
    title: str = "Holtz audit session",
    text_delay: float = 1.5,
    tool_delay: float = 0.15,
    user_delay: float = 2.0,
    token_delay: float = 0.8,
) -> None:
    # Load parent messages
    parent_msgs = []
    with open(parent_path) as f:
        for line in f:
            parent_msgs.append(json.loads(line.strip()))

    # Load subagent messages keyed by description match
    subagent_data = {}
    for sa_path, sa_label in subagent_specs:
        msgs = []
        with open(sa_path) as f:
            for line in f:
                msgs.append(json.loads(line.strip()))
        subagent_data[sa_label] = msgs

    # Find Agent dispatch descriptions to match subagents to dispatch points
    dispatch_descs = {}
    for sa_label in subagent_data:
        dispatch_descs[sa_label] = sa_label  # will match by description

    events = [json.dumps({
        "version": 2,
        "width": 120,
        "height": 40,
        "timestamp": 1742860800,
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": title,
    })]

    t = 0.0
    rule = "\u2500" * 60
    injected = set()

    # Split parent messages into chunks: before each Agent dispatch, inject the subagent
    tool_batch = []

    def flush_tools():
        nonlocal t
        if not tool_batch:
            return
        if len(tool_batch) <= 3:
            for name, desc in tool_batch:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += tool_delay
        else:
            for name, desc in tool_batch[:2]:
                events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
                t += tool_delay
            events.append(ev(t, f"  {DIM}  ... +{len(tool_batch) - 3} more tool calls ...{RESET}\n"))
            t += tool_delay
            name, desc = tool_batch[-1]
            events.append(ev(t, f"  {CYAN}\u23bf {name}{RESET} {DIM}{desc}{RESET}\n"))
            t += tool_delay
        tool_batch.clear()

    def inject_subagent(label: str):
        nonlocal t
        if label in injected:
            return
        injected.add(label)
        msgs = subagent_data[label]

        # Banner: entering subagent
        flush_tools()
        events.append(ev(t, f"\n{DIM}{rule}{RESET}\n"))
        events.append(ev(t + 0.1, f"{BG_BLUE}{WHITE}{BOLD} \u25b6 SUBAGENT: {label} {RESET}\n"))
        events.append(ev(t + 0.2, f"{DIM}{rule}{RESET}\n\n"))
        t += 0.5

        # Process all subagent messages as a contiguous block
        t = process_messages(msgs, events, t, text_delay, tool_delay, user_delay, token_delay)

        # Banner: returning to parent
        events.append(ev(t, f"\n{DIM}{rule}{RESET}\n"))
        events.append(ev(t + 0.1, f"{BG_YELLOW}{BOLD} \u25c0 PARENT SESSION {RESET}\n"))
        events.append(ev(t + 0.2, f"{DIM}{rule}{RESET}\n\n"))
        t += 0.5

    for msg in parent_msgs:
        msg_type = msg.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            if msg.get("isMeta"):
                continue
            if isinstance(content, str) and content.startswith("<"):
                continue
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item["text"])
                content = "\n".join(text_parts)
            if isinstance(content, str) and content.strip():
                text = content.strip()
                flush_tools()
                if len(text) > 2000:
                    first_line = text.split("\n")[0][:120]
                    events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {first_line}...{RESET}\n\n"))
                else:
                    events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {text}{RESET}\n\n"))
                t += user_delay

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
                        t += text_delay
                        has_text = True
                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    desc = tool_description(name, inp)
                    tool_batch.append((name, desc))

                    # Check if this is a dispatch for one of our subagents
                    if name == "Agent":
                        agent_desc = inp.get("description", "")
                        for sa_label in subagent_data:
                            if sa_label in agent_desc or agent_desc in sa_label:
                                flush_tools()
                                inject_subagent(sa_label)
                                break

            if usage and has_text:
                flush_tools()
                u_in = usage.get("input_tokens", 0)
                u_cw = usage.get("cache_creation_input_tokens", 0)
                u_cr = usage.get("cache_read_input_tokens", 0)
                u_out = usage.get("output_tokens", 0)
                ctx = u_in + u_cw + u_cr
                events.append(ev(t, f"{DIM}  [{ctx:,} ctx | {u_out:,} out]{RESET}\n"))
                t += token_delay

    flush_tools()

    with open(output_path, "w") as f:
        for e in events:
            f.write(e + "\n")

    print(f"Written {len(events)} events to {output_path}")
    print(f"Playback: {t:.0f}s ({t/60:.1f} min)")


def main():
    parser = argparse.ArgumentParser(
        description="Merge parent session + subagent(s) into one asciinema cast",
    )
    parser.add_argument("--parent", "-p", required=True, help="Parent session JSONL")
    parser.add_argument(
        "--subagent", "-s", action="append", required=True,
        help="path::label (e.g., agent.jsonl::Phase 3 Adversarial)",
    )
    parser.add_argument("--output", "-o", default="merged.cast", help="Output .cast path")
    parser.add_argument("--title", "-t", default="Holtz audit session", help="Cast title")
    parser.add_argument("--text-delay", type=float, default=1.5)
    parser.add_argument("--tool-delay", type=float, default=0.15)
    args = parser.parse_args()

    subagent_specs = []
    for spec in args.subagent:
        if "::" in spec:
            path, label = spec.split("::", 1)
        else:
            path = spec
            label = Path(spec).stem
        subagent_specs.append((path, label))

    merge_cast(
        parent_path=args.parent,
        subagent_specs=subagent_specs,
        output_path=args.output,
        title=args.title,
        text_delay=args.text_delay,
        tool_delay=args.tool_delay,
    )


if __name__ == "__main__":
    main()

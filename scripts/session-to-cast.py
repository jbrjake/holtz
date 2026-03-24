#!/usr/bin/env python3
"""Convert a Claude Code session JSONL into an asciinema .cast file.

Shows what the user saw in Claude Code with tool calls collapsed:
assistant text, tool call one-liners, user prompts, and token metadata.
Tool results are omitted (they're behind expandable sections in the UI).
If a SUMMARY.md exists in docs/holtz/, it's appended at the end.

Usage:
  # Auto-detect the most recent session for this project
  python scripts/session-to-cast.py

  # Specify a session JSONL
  python scripts/session-to-cast.py --session ~/.claude/projects/.../SESSION.jsonl

  # Specify output path
  python scripts/session-to-cast.py -o docs/runs/my-run.cast

  # Cut at a specific message (default: end of file)
  python scripts/session-to-cast.py --cut "take this last holtz run"

  # Append a specific SUMMARY.md
  python scripts/session-to-cast.py --summary docs/holtz/SUMMARY.md

  # Adjust playback pacing
  python scripts/session-to-cast.py --text-delay 2.0 --tool-delay 0.1

  # List available sessions for this project
  python scripts/session-to-cast.py --list
"""
import argparse
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
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"


def find_project_dir(project_root: str | None = None) -> Path | None:
    """Find the .claude/projects/ directory for a project."""
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return None

    if project_root:
        # Convert path to the dash-separated format Claude uses
        mangled = project_root.replace("/", "-")
        if mangled.startswith("-"):
            mangled = mangled  # keep leading dash
        candidate = claude_dir / mangled
        if candidate.exists():
            return candidate

    # Try to detect from cwd
    import subprocess
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = str(Path.cwd())

    mangled = root.replace("/", "-")
    candidate = claude_dir / mangled
    if candidate.exists():
        return candidate

    return None


def list_sessions(project_dir: Path) -> list[dict]:
    """List available sessions with metadata."""
    sessions = []
    for f in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        size = f.stat().st_size
        # Read first and last assistant message for timestamps
        first_ts = last_ts = ""
        turns = 0
        with open(f) as fh:
            for line in fh:
                obj = json.loads(line.strip())
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


def ev(t: float, text: str) -> str:
    """Create an asciinema output event."""
    text = text.replace("\n", "\r\n")
    return json.dumps([round(t, 3), "o", text])


def tool_description(name: str, inp: dict) -> str:
    """Compact one-line description of a tool call."""
    if name == "Bash":
        return inp.get("description", inp.get("command", "")[:80])
    elif name == "Read":
        p = inp.get("file_path", "")
        return "/".join(p.split("/")[-2:]) if "/" in p else p
    elif name == "Write":
        p = inp.get("file_path", "")
        return "/".join(p.split("/")[-2:]) if "/" in p else p
    elif name == "Edit":
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


def extract(
    session_path: str,
    output_path: str,
    cut_marker: str | None = None,
    summary_path: str | None = None,
    text_delay: float = 1.5,
    tool_delay: float = 0.15,
    user_delay: float = 2.0,
    token_delay: float = 0.8,
    summary_line_delay: float = 0.06,
) -> None:
    messages = []
    with open(session_path) as f:
        for line in f:
            messages.append(json.loads(line.strip()))

    # Try to extract title from first assistant text
    title = "Claude Code Session"
    for msg in messages:
        if msg.get("type") == "assistant":
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                        first_line = b["text"].strip().split("\n")[0][:80]
                        title = first_line
                        break
                break

    events = [json.dumps({
        "version": 2,
        "width": 120,
        "height": 40,
        "timestamp": 1742860800,
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
        "title": title,
    })]

    t = 0.0
    tool_batch: list[tuple[str, str]] = []

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

        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            if cut_marker and isinstance(content, str) and cut_marker.lower() in content.lower():
                flush_tools()
                break
            if isinstance(content, str) and content.strip() and not content.startswith("<") and not msg.get("isMeta"):
                flush_tools()
                events.append(ev(t, f"\n{BOLD}{MAGENTA}\u276f {content.strip()}{RESET}\n\n"))
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

    # Append SUMMARY.md if available
    if summary_path is None:
        for candidate in [Path("docs/holtz/SUMMARY.md")]:
            if candidate.exists():
                summary_path = str(candidate)
                break

    if summary_path and Path(summary_path).exists():
        summary_text = Path(summary_path).read_text()
        t += 1.0
        rule = "\u2501" * 80
        events.append(ev(t, f"\n{BOLD}{rule}{RESET}\n"))
        t += 0.3
        events.append(ev(t, f"{BOLD}  SUMMARY.md{RESET}\n"))
        events.append(ev(t + 0.1, f"{BOLD}{rule}{RESET}\n\n"))
        t += 0.5
        for line in summary_text.split("\n"):
            events.append(ev(t, f"{line}\n"))
            t += summary_line_delay
        t += 1.0

    with open(output_path, "w") as f:
        for e in events:
            f.write(e + "\n")

    print(f"Written {len(events)} events to {output_path}")
    print(f"Playback: {t:.0f}s ({t/60:.1f} min)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Claude Code session JSONL into an asciinema .cast file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # auto-detect latest session
  %(prog)s --list                       # list available sessions
  %(prog)s --session PATH -o out.cast   # specific session
  %(prog)s --cut "some message"         # cut at a user message
        """,
    )
    parser.add_argument("--session", "-s", help="Path to session JSONL file")
    parser.add_argument("--output", "-o", default="docs/runs/session.cast", help="Output .cast path")
    parser.add_argument("--cut", help="Cut recording at user message containing this text")
    parser.add_argument("--summary", help="Path to SUMMARY.md to append (auto-detected if omitted)")
    parser.add_argument("--no-summary", action="store_true", help="Don't append SUMMARY.md")
    parser.add_argument("--list", action="store_true", help="List available sessions and exit")
    parser.add_argument("--project", help="Project root path (auto-detected from git)")
    parser.add_argument("--text-delay", type=float, default=1.5, help="Seconds per text block (default: 1.5)")
    parser.add_argument("--tool-delay", type=float, default=0.15, help="Seconds per tool call (default: 0.15)")
    args = parser.parse_args()

    project_dir = find_project_dir(args.project)
    if project_dir is None:
        print("Could not find .claude/projects/ directory for this project.", file=sys.stderr)
        print("Use --session to specify a JSONL file directly.", file=sys.stderr)
        sys.exit(1)

    if args.list:
        sessions = list_sessions(project_dir)
        if not sessions:
            print("No sessions found.")
            sys.exit(0)
        print(f"{'Started':<20} {'Turns':>6} {'Size':>8}  ID")
        print("-" * 70)
        for s in sessions:
            print(f"{s['started']:<20} {s['turns']:>6} {s['size_kb']:>6}KB  {s['name']}")
        sys.exit(0)

    if args.session:
        session_path = args.session
    else:
        # Use the most recently modified JSONL
        jsonls = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not jsonls:
            print("No session files found.", file=sys.stderr)
            sys.exit(1)
        session_path = str(jsonls[0])
        print(f"Using most recent session: {Path(session_path).stem}", file=sys.stderr)

    summary = None if args.no_summary else args.summary

    extract(
        session_path=session_path,
        output_path=args.output,
        cut_marker=args.cut,
        summary_path=summary,
        text_delay=args.text_delay,
        tool_delay=args.tool_delay,
    )


if __name__ == "__main__":
    main()

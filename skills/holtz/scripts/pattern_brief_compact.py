#!/usr/bin/env python3
"""
Holtz Pattern Brief Compactor

Reads patterns-brief.md and produces compact representations for subagent
consumption. Multiple output formats available; default determined by
empirical testing.

Usage:
  python pattern_brief_compact.py [path-to-patterns-brief.md]
  python pattern_brief_compact.py [path] --format oneliner|twoliner|structured
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Default format: "structured" selected as the safe default (richest context).
# Empirical subagent evaluation deferred — run Task 4 from the implementation
# plan to validate format selection with actual subagent dispatches.
DEFAULT_FORMAT = "structured"

# The brief's caps, in bytes. `phase-fix-loop.md`'s rolling policy states the
# same two numbers in KB, and a test checks the two statements against each
# other. Measured here because the round that must obey them is told never to
# open the brief whole: 20 entries was already the rule when the file reached
# 181 KB, 8.5 KB an entry against a ~400 B format.
BRIEF_BYTE_CAP = 40 * 1024
ENTRY_BYTE_CAP = 2 * 1024


@dataclass
class PatternEntry:
    pattern_id: str
    name: str
    run: str
    date: str
    what_to_look_for: str
    detection_heuristic: str
    example: str
    size: int = 0


def parse_brief(content: str) -> list[PatternEntry]:
    """Parse patterns-brief.md into structured entries.

    Masks code fences before header matching to prevent false matches
    on pattern headers inside code examples (PAT-001 / BH-005 run 14).
    Uses [ \\t]* instead of \\s* for field extraction to prevent newline
    leaks on empty field values (BH-004 run 14).
    """
    from markdown_utils import mask_code_fences

    entries = []
    # Mask code fences so headers inside examples are not matched (BH-005).
    _, masked = mask_code_fences(content)

    # Match ## PAT-NNN: name (Run N, YYYY-MM-DD) in masked content
    header_re = re.compile(
        r'^## (PAT-\d+): (.+?) \((Run \d+), (\d{4}-\d{2}-\d{2})\)[ \t]*$',
        re.MULTILINE,
    )
    matches = list(header_re.finditer(masked))

    # Use line-based extraction to avoid masked/original character offset
    # divergence (BH-003 run 16, PAT-001).  mask_code_fences preserves line
    # count, so line numbers are safe to map between masked and original.
    original_lines = content.split('\n')

    def _line_of(pos: int) -> int:
        """Convert a character offset in masked to a line number."""
        return masked[:pos].count('\n')

    for i, match in enumerate(matches):
        start_line = _line_of(match.end())
        end_line = _line_of(matches[i + 1].start()) if i + 1 < len(matches) else len(original_lines)
        block = '\n'.join(original_lines[start_line:end_line])

        def _extract(field: str, _block: str = block) -> str:
            # Only terminate at known field headers (**Name:**) not arbitrary bold,
            # so field values containing **emphasis** aren't truncated.
            m = re.search(
                rf'\*\*{field}:\*\*[ \t]*(.*?)(?=\n\*\*\w[^*]*:\*\*|\n##|\Z)',
                _block,
                re.DOTALL,
            )
            return m.group(1).strip() if m else ""

        entries.append(PatternEntry(
            pattern_id=match.group(1),
            name=match.group(2),
            run=match.group(3),
            date=match.group(4),
            what_to_look_for=_extract("What to look for"),
            detection_heuristic=_extract("Detection heuristic"),
            example=_extract("Example"),
            # The heading plus its body: what compressing this entry to the
            # four-line format would have to shrink.
            size=len(match.group(0).encode("utf-8")) + len(block.encode("utf-8")),
        ))

    return entries


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len (including '...' suffix), preserving whole words."""
    if len(text) <= max_len:
        return text
    limit = max(0, max_len - 3)
    truncated = text[:limit].rsplit(' ', 1)[0]
    return truncated + "..."


def _compress_heuristic(heuristic: str) -> str:
    """Compress a detection heuristic to a single actionable line."""
    if '`' in heuristic:
        m = re.search(r'`([^`]+)`', heuristic)
        if m:
            return m.group(0)
    # Split on sentence-ending period (followed by space or end) not mid-word dots
    m = re.match(r'(.*?\w\.)\s', heuristic)
    first_sentence = m.group(1) if m else heuristic.split('\n')[0].strip()
    return _truncate(first_sentence, 120)


def _compress_example(example: str) -> str:
    """Compress an example to a single sentence."""
    # Split on sentence-ending period (followed by space or end) not mid-word dots
    # like config.json, os.path, etc.
    m = re.match(r'(.*?\w\.)\s', example)
    first_sentence = m.group(1) if m else example.split('\n')[0].strip()
    if first_sentence.startswith('A ') or first_sentence.startswith('The '):
        first_sentence = first_sentence[0].lower() + first_sentence[1:]
    return _truncate(first_sentence, 100)


def format_compact(entries: list[PatternEntry], *, fmt: str = DEFAULT_FORMAT) -> str:
    """Format parsed entries into a compact representation.

    Args:
        entries: Parsed pattern entries.
        fmt: Output format — "oneliner", "twoliner", or "structured".

    Returns:
        Compact markdown string.
    """
    if not entries:
        return "# Pattern Brief (compact)\n\nNo patterns recorded.\n"

    header = f"# Pattern Brief (compact, {len(entries)} patterns)\n\n"
    blocks = []

    for entry in entries:
        wtlf = _truncate(entry.what_to_look_for, 150)
        heuristic = _compress_heuristic(entry.detection_heuristic)
        example = _compress_example(entry.example)

        if fmt == "oneliner":
            blocks.append(f"{entry.pattern_id} | {entry.name} | {wtlf}")

        elif fmt == "twoliner":
            blocks.append(
                f"{entry.pattern_id}: {entry.name} — {wtlf}\n"
                f"  Detect: {heuristic}"
            )

        elif fmt == "structured":
            blocks.append(
                f"## {entry.pattern_id}: {entry.name}\n"
                f"Look for: {wtlf}\n"
                f"Detect: {heuristic}\n"
                f"e.g.: {example}"
            )

        else:
            raise ValueError(f"Unknown format: {fmt!r}")

    separator = "\n" if fmt == "oneliner" else "\n\n"
    return header + separator.join(blocks) + "\n"


def size_report(content: str, entries: list[PatternEntry]) -> str:
    """What is over a cap, or "" when nothing is.

    Silence on a compliant brief: this goes to stderr on every pattern round,
    and a line printed every time is a line nobody reads by round 14.
    """
    lines = []
    total = len(content.encode("utf-8"))
    if total > BRIEF_BYTE_CAP:
        lines.append(
            f"brief is {total / 1024:.0f} KB, over the {BRIEF_BYTE_CAP // 1024} KB cap "
            f"— compress entries to the four-line format and move their detail "
            f"to docs/holtz/pattern-round-NN.md"
        )
    fat = [e for e in entries if e.size > ENTRY_BYTE_CAP]
    if fat:
        named = ", ".join(f"{e.pattern_id} ({e.size / 1024:.1f} KB)" for e in fat)
        lines.append(
            f"over the {ENTRY_BYTE_CAP // 1024} KB entry cap: {named}"
        )
    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Compact pattern brief for subagents")
    parser.add_argument("path", nargs="?", default="docs/holtz/patterns-brief.md",
                        help="Path to patterns-brief.md")
    parser.add_argument("--format", choices=["oneliner", "twoliner", "structured"],
                        default=DEFAULT_FORMAT,
                        help="Compact format to use")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"No pattern brief found at {path}", file=sys.stderr)
        sys.exit(0)  # Not an error — brief may not exist on early runs

    content = path.read_text()
    entries = parse_brief(content)
    if not entries:
        print("No patterns in brief", file=sys.stderr)
        sys.exit(0)

    print(format_compact(entries, fmt=args.format))

    report = size_report(content, entries)
    if report:
        print(report, file=sys.stderr)


if __name__ == "__main__":
    main()

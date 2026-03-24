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


@dataclass
class PatternEntry:
    pattern_id: str
    name: str
    run: str
    date: str
    what_to_look_for: str
    detection_heuristic: str
    example: str


def parse_brief(content: str) -> list[PatternEntry]:
    """Parse patterns-brief.md into structured entries."""
    entries = []
    # Match ## PAT-NNN: name (Run N, YYYY-MM-DD)
    header_re = re.compile(
        r'^## (PAT-\d+): (.+?) \((Run \d+), (\d{4}-\d{2}-\d{2})\)\s*$',
        re.MULTILINE,
    )
    matches = list(header_re.finditer(content))

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]

        def _extract(field: str, _block: str = block) -> str:
            m = re.search(
                rf'\*\*{field}:\*\*\s*(.*?)(?=\n\*\*|\n##|\Z)',
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
        ))

    return entries


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, preserving whole words."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len].rsplit(' ', 1)[0]
    return truncated + "..."


def _compress_heuristic(heuristic: str) -> str:
    """Compress a detection heuristic to a single actionable line."""
    if '`' in heuristic:
        m = re.search(r'`([^`]+)`', heuristic)
        if m:
            return m.group(0)
    first_sentence = heuristic.split('.')[0].strip()
    return _truncate(first_sentence, 120)


def _compress_example(example: str) -> str:
    """Compress an example to a single sentence."""
    first_sentence = example.split('.')[0].strip()
    if first_sentence.startswith('A ') or first_sentence.startswith('The '):
        first_sentence = first_sentence[0].lower() + first_sentence[1:]
    return _truncate(first_sentence, 100)


def format_compact(entries: list[PatternEntry], *, fmt: str = "structured") -> str:
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

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

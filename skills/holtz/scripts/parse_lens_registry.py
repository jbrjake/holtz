#!/usr/bin/env python3
"""Parse the lens registry markdown into structured data.

Extracts lens definitions from references/lens-registry.md, including
the Scope field that classifies lenses as per-file or cross-file.

Usage:
    python parse_lens_registry.py [path/to/lens-registry.md]
    python parse_lens_registry.py --scope per-file [path]
    python parse_lens_registry.py --scope cross-file [path]
    python parse_lens_registry.py --names-only [path]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VALID_SCOPES = {"per-file", "cross-file"}

# Matches **Field:** value (field name is captured, value starts after the colon)
_FIELD_RE = re.compile(r"^\*\*([A-Za-z_ -]+):\*\*[ \t]*(.*)")
_HEADING_RE = re.compile(r"^##[ \t]+(\S+.*)$")

# Map from markdown field names to dict keys
_FIELD_MAP = {
    "Focus": "focus",
    "Scope": "scope",
    "Audit priorities": "audit_priorities",
    "Failure modes": "failure_modes",
    "Entry point": "entry_point",
}

REQUIRED_FIELDS = set(_FIELD_MAP.values())


def parse_lens_registry(text: str) -> list[dict]:
    """Parse lens registry markdown text into a list of lens dicts.

    Each lens dict has keys: name, focus, scope, audit_priorities,
    failure_modes, entry_point.

    Raises ValueError if a lens has an invalid or missing scope.
    """
    lenses: list[dict] = []
    current: dict | None = None
    current_field: str | None = None

    for line in text.split("\n"):
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if current is not None:
                _validate_and_append(current, lenses)
            current = {"name": heading_match.group(1).strip()}
            current_field = None
            continue

        if current is None:
            continue

        field_match = _FIELD_RE.match(line)
        if field_match:
            field_name = field_match.group(1).strip()
            field_value = field_match.group(2).strip()
            key = _FIELD_MAP.get(field_name)
            if key:
                current[key] = field_value
                current_field = key
            else:
                current_field = None
        elif current_field and line.strip():
            # Continuation line for a multi-line field
            current[current_field] += " " + line.strip()
        elif not line.strip():
            current_field = None

    if current is not None:
        _validate_and_append(current, lenses)

    return lenses


def _validate_and_append(lens: dict, lenses: list[dict]) -> None:
    """Validate a lens dict and append to the list if it has all required fields."""
    present = set(lens.keys()) - {"name"}
    if not present:
        return  # Header-only section (like the intro paragraph)

    # Only validate sections that look like a real lens (have at least 2 required fields).
    # A non-lens section that happens to contain **Focus:** shouldn't crash the parser.
    if len(present & REQUIRED_FIELDS) >= 2:
        if "scope" not in lens:
            raise ValueError(
                f"Lens '{lens.get('name', '?')}' is missing required Scope field"
            )
        if lens["scope"] not in VALID_SCOPES:
            raise ValueError(
                f"Lens '{lens.get('name', '?')}' has invalid scope '{lens['scope']}'. "
                f"Must be one of: {', '.join(sorted(VALID_SCOPES))}"
            )
        lenses.append(lens)


def filter_by_scope(lenses: list[dict], scope: str) -> list[dict]:
    """Filter a list of parsed lenses by scope value."""
    return [lens for lens in lenses if lens["scope"] == scope]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse lens registry")
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to lens-registry.md (default: auto-detect)",
    )
    parser.add_argument(
        "--scope",
        choices=sorted(VALID_SCOPES),
        help="Filter to lenses with this scope",
    )
    parser.add_argument(
        "--names-only",
        action="store_true",
        help="Output only lens names, one per line",
    )
    args = parser.parse_args()

    if args.path:
        path = Path(args.path)
    else:
        # Auto-detect: look relative to this script's location
        script_dir = Path(__file__).parent
        path = script_dir.parent / "references" / "lens-registry.md"
        if not path.exists():
            print(f"Cannot find lens-registry.md at {path}", file=sys.stderr)
            sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lenses = parse_lens_registry(text)

    if args.scope:
        lenses = filter_by_scope(lenses, args.scope)

    if args.names_only:
        for lens in lenses:
            print(lens["name"])
    else:
        print(json.dumps(lenses, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Quiz bank validator for lens enforcement.

Validates quiz bank JSON: 4 options per question, answer in A-D,
source has line number, >=3 keywords per entry.

Usage: python generate_quiz_bank.py --input <path>
"""
from __future__ import annotations

import argparse
import json
import sys

REQUIRED_FIELDS = {"lens", "q", "a", "opts", "source", "keywords"}
VALID_ANSWERS = set("ABCD")


def validate_quiz_bank(entries: list[dict]) -> list[str]:
    """Validate quiz bank entries. Returns list of error strings."""
    errors = []
    for i, entry in enumerate(entries):
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            errors.append(f"Entry {i}: missing fields {missing}")
            continue
        if len(entry["opts"]) != 4:
            errors.append(f"Entry {i}: need 4 options, got {len(entry['opts'])}")
        if entry["a"] not in VALID_ANSWERS:
            errors.append(f"Entry {i}: answer '{entry['a']}' not in A-D")
        if ":" not in entry["source"]:
            errors.append(f"Entry {i}: source missing line number")
        if len(entry["keywords"]) < 3:
            errors.append(f"Entry {i}: need >=3 keywords, got {len(entry['keywords'])}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a quiz bank file")
    parser.add_argument("--input", required=True, help="Path to quiz-bank.json")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        bank = json.load(f)

    errors = validate_quiz_bank(bank)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Quiz bank valid: {len(bank)} questions")


if __name__ == "__main__":
    main()

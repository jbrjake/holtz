#!/usr/bin/env python3
"""Quiz bank validator + target-freshness checker for lens enforcement.

Two modes:

* Schema validation (default): 4 options per question, answer in A-D,
  ``source`` carries an anchor (``file.py::symbol`` or ``file.py:line``),
  >=3 keywords per entry.

* ``--verify-fresh --cwd <target>``: check that each question's answer is
  actually verifiable against the target project's *current* source. This
  is what makes a bank "project-specific": a holtz-self bank scored against
  an external target reports every question stale. Author a bank at
  ``docs/holtz/quiz-bank.json`` for the audit target and run this to confirm
  it is answerable before the lens sweeps begin (see #73).

Usage:
  python3 generate_quiz_bank.py --input docs/holtz/quiz-bank.json
  python3 generate_quiz_bank.py --input docs/holtz/quiz-bank.json --verify-fresh --cwd .
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable

REQUIRED_FIELDS = {"lens", "q", "a", "opts", "source", "keywords"}
VALID_ANSWERS = set("ABCD")

# Same tolerance the SubagentStop hook applies: a lens with more than this
# many stale questions cannot pose a valid quiz (lens_quiz.MAX_STALE_QUESTIONS).
MAX_STALE_PER_LENS = 2


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
        elif not all(opt.strip() for opt in entry["opts"]):
            errors.append(f"Entry {i}: options must be non-empty strings")
        if entry["a"] not in VALID_ANSWERS:
            errors.append(f"Entry {i}: answer '{entry['a']}' not in A-D")
        if ":" not in entry["source"]:
            errors.append(f"Entry {i}: source missing line number")
        if len(entry["keywords"]) < 3:
            errors.append(f"Entry {i}: need >=3 keywords, got {len(entry['keywords'])}")
    return errors


def _load_verify_answer_freshness() -> Callable[[dict, str], bool]:
    """Import the hook's freshness checker lazily.

    Kept out of module scope so ``from generate_quiz_bank import
    validate_quiz_bank`` stays cheap and free of the hook import chain
    (which pulls in the daemon socket helpers) under pytest collection.
    """
    hooks_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"
    )
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    from lens_quiz import verify_answer_freshness  # noqa: PLC0415

    return verify_answer_freshness


def verify_bank_freshness(bank: list[dict], cwd: str) -> list[dict]:
    """Return per-lens freshness against the target source at ``cwd``.

    Each entry: ``{lens, total, stale, stale_sources, ok}`` where ``ok`` is
    False when the lens has more than ``MAX_STALE_PER_LENS`` unverifiable
    questions (the hook would fail closed on it).
    """
    verify = _load_verify_answer_freshness()
    by_lens: dict[str, dict] = {}
    for q in bank:
        lens = q.get("lens", "")
        rec = by_lens.setdefault(
            lens, {"lens": lens, "total": 0, "stale": 0, "stale_sources": []}
        )
        rec["total"] += 1
        if not verify(q, cwd):
            rec["stale"] += 1
            rec["stale_sources"].append(q.get("source", ""))
    results = []
    for rec in by_lens.values():
        rec["ok"] = rec["stale"] <= MAX_STALE_PER_LENS
        results.append(rec)
    return sorted(results, key=lambda r: r["lens"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a quiz bank file and optionally verify it against a target"
    )
    parser.add_argument("--input", required=True, help="Path to quiz-bank.json")
    parser.add_argument(
        "--verify-fresh",
        action="store_true",
        help="Verify each answer is fresh against the target source (needs --cwd)",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Target project root for --verify-fresh (default: current dir)",
    )
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        bank = json.load(f)

    errors = validate_quiz_bank(bank)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Quiz bank valid: {len(bank)} questions")

    if args.verify_fresh:
        results = verify_bank_freshness(bank, args.cwd)
        bad = [r for r in results if not r["ok"]]
        for r in results:
            marker = "ok " if r["ok"] else "STALE"
            print(f"  [{marker}] {r['lens']}: {r['stale']}/{r['total']} stale")
        if bad:
            print(
                f"ERROR: {len(bad)} lens(es) have too many stale questions against "
                f"{os.path.abspath(args.cwd)}. This bank is not answerable for this "
                "project — author project-specific questions whose sources exist here.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Quiz bank fresh against {os.path.abspath(args.cwd)}")


if __name__ == "__main__":
    main()

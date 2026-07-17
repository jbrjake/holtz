#!/usr/bin/env python3
"""Stage one lens-quiz question during recon (#73).

The generation subagent walks the impact graph and, for each anchor it picks,
runs this script once to stage a question. The script only *validates and
emits* — it prints a canonical ``QUIZ-QUESTION:`` marker line that the trusted
courier hook (``quiz_capture.py``) captures from the Bash tool output and
appends to the daemon vault. The script itself never touches the vault (a
subagent's process cannot authenticate to the daemon); the courier does, and
sahjhan's vault policy permits the write only while the state is ``recon``.

When all questions are staged, run ``--finalize`` once so the courier records
``quiz_bank_generated`` (which gates ``recon_complete`` — you cannot leave recon
without a bank).

Emitting a marker is deliberately *not* the same as trusting it: the courier
re-derives everything and the daemon enforces the recon gate. This script is a
convenience + validator, not a trust boundary.

Usage (one question):
  python3 quiz_stage.py --lens component \\
    --question "What does ImpactGraph.save() use for atomic writes?" \\
    --answer B \\
    --option "shutil.copy2" --option "tempfile + os.replace" \\
    --option "open() mode 'w'" --option "json.dump direct to path" \\
    --source "skills/holtz/scripts/impact_graph.py::ImpactGraph.save" \\
    --keyword ImpactGraph --keyword save --keyword atomic

Usage (after all questions):
  python3 quiz_stage.py --finalize
"""
from __future__ import annotations

import argparse
import json
import sys

QUESTION_MARKER = "QUIZ-QUESTION:"
FINALIZE_MARKER = "QUIZ-BANK-FINALIZE:"
VALID_ANSWERS = set("ABCD")


def build_question(args: argparse.Namespace) -> dict:
    """Validate CLI args and return the question dict, or raise ValueError."""
    lens = (args.lens or "").strip()
    if not lens:
        raise ValueError("--lens is required")
    q = (args.question or "").strip()
    if not q:
        raise ValueError("--question is required")
    answer = (args.answer or "").strip().upper()
    if answer not in VALID_ANSWERS:
        raise ValueError(f"--answer must be one of A-D, got {answer!r}")
    opts = [o.strip() for o in (args.option or [])]
    if len(opts) != 4 or not all(opts):
        raise ValueError(f"exactly 4 non-empty --option values required, got {len(opts)}")
    source = (args.source or "").strip()
    if "::" not in source and ":" not in source:
        raise ValueError(
            "--source must anchor to the target: 'path/to/file.py::symbol' "
            "(preferred) or 'path/to/file.py:line'"
        )
    keywords = [k.strip() for k in (args.keyword or []) if k.strip()]
    if len(keywords) < 3:
        raise ValueError(f"at least 3 --keyword values required, got {len(keywords)}")
    # Answer index must be within the option list.
    if ord(answer) - ord("A") >= len(opts):
        raise ValueError("--answer refers to an option beyond the 4 provided")
    return {
        "lens": lens,
        "q": q,
        "a": answer,
        "opts": opts,
        "source": source,
        "keywords": keywords,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage one lens-quiz question during recon")
    parser.add_argument("--finalize", action="store_true", help="Signal the bank is complete")
    parser.add_argument("--lens")
    parser.add_argument("--question")
    parser.add_argument("--answer")
    parser.add_argument("--option", action="append", help="Answer option (provide exactly 4)")
    parser.add_argument("--source", help="Target-source anchor: file.py::symbol")
    parser.add_argument("--keyword", action="append", help="Lens keyword (provide >=3)")
    args = parser.parse_args()

    if args.finalize:
        print(FINALIZE_MARKER)
        return

    try:
        question = build_question(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    # Single-line canonical marker for the courier to capture.
    print(f"{QUESTION_MARKER} {json.dumps(question, separators=(',', ':'))}")


if __name__ == "__main__":
    main()

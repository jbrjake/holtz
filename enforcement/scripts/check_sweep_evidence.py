#!/usr/bin/env python3
"""Check that the final sweep has sufficient distinct file reads.

Used as a gate condition on the 'converge' transition to prevent
lightweight final sweeps from passing convergence.

Usage: python check_sweep_evidence.py --min-reads 30 [--transcript PATH]
Exit 0 if threshold met, exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def count_distinct_reads(transcript_path: str) -> int:
    """Count distinct file paths read in a transcript JSONL."""
    files_read: set[str] = set()
    if not os.path.isfile(transcript_path):
        return 0
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Handle nested message.content format (session JSONL)
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("name") == "Read":
                        fp = block.get("input", {}).get("file_path", "")
                        if fp:
                            files_read.add(fp)
            # Handle flat tool_use format
            if entry.get("type") == "tool_use" and entry.get("name") == "Read":
                fp = entry.get("input", {}).get("file_path", "")
                if fp:
                    files_read.add(fp)
    return len(files_read)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check sweep evidence")
    parser.add_argument("--min-reads", type=int, default=30)
    parser.add_argument("--transcript", default=None,
                        help="Path to transcript JSONL. Auto-discovers if omitted.")
    args = parser.parse_args()

    if args.transcript:
        transcript = args.transcript
    else:
        transcript = os.environ.get("CLAUDE_SESSION_TRANSCRIPT", "")
        if not transcript or not os.path.isfile(transcript):
            print("FAIL: No transcript found. Cannot verify sweep evidence.", file=sys.stderr)
            sys.exit(1)

    distinct = count_distinct_reads(transcript)
    if distinct >= args.min_reads:
        print(f"PASS: {distinct} distinct file reads (threshold: {args.min_reads})")
        sys.exit(0)
    else:
        print(f"FAIL: {distinct} distinct file reads (threshold: {args.min_reads})", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

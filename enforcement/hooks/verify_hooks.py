#!/usr/bin/env python3
"""Verify all required enforcement hooks are registered.

Exit 0 if all hooks in hooks-manifest.json are present in settings.
Exit 1 with missing hooks listed on stderr.

Usage: python verify_hooks.py [--settings <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MANIFEST = os.path.join(os.path.dirname(__file__), "..", "hooks-manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        default=os.path.join(os.getcwd(), ".claude", "settings.local.json"),
    )
    args = parser.parse_args()

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    if not os.path.isfile(args.settings):
        print("ERROR: No settings file found", file=sys.stderr)
        sys.exit(1)

    with open(args.settings, encoding="utf-8") as f:
        settings = json.load(f)

    hooks = settings.get("hooks", {})
    missing = []

    for event_type, required_scripts in manifest["required_hooks"].items():
        registered = []
        for entry in hooks.get(event_type, []):
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                registered.append(cmd)

        for script in required_scripts:
            if not any(script in cmd for cmd in registered):
                missing.append(f"{event_type}/{script}")

    if missing:
        print(f"ERROR: Missing hooks: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in manifest["required_hooks"].values())
    print(f"Hook verification: all {total} required hooks present.")
    sys.exit(0)


if __name__ == "__main__":
    main()

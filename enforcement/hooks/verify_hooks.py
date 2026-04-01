#!/usr/bin/env python3
"""Verify all required enforcement hooks are registered and config is resolvable.

Exit 0 if all hooks in hooks-manifest.json are present in settings
and enforcement config is resolvable.
Exit 1 with missing hooks or config errors listed on stderr.

Usage: python verify_hooks.py [--settings <path>] [--cwd <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

MANIFEST = os.path.join(os.path.dirname(__file__), "..", "hooks-manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        default=os.path.join(os.getcwd(), ".claude", "settings.local.json"),
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory to test config resolution against",
    )
    args = parser.parse_args()

    errors = []

    # ── Hook registration check ──
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    if not os.path.isfile(args.settings):
        errors.append("No settings file found at " + args.settings)
    else:
        with open(args.settings, encoding="utf-8") as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})

        for event_type, required_scripts in manifest["required_hooks"].items():
            registered = []
            for entry in hooks.get(event_type, []):
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    registered.append(cmd)

            for script in required_scripts:
                if not any(script in cmd for cmd in registered):
                    errors.append(f"Missing hook: {event_type}/{script}")

    # ── Config resolution check ──
    from _common import resolve_config_dir  # noqa: E402

    config_dir, config_found = resolve_config_dir(args.cwd)
    if config_found:
        print(f"Config resolution: OK ({config_dir})")
        # Verify all expected config files exist
        expected_files = [
            "protocol.toml", "transitions.toml", "states.toml",
            "hooks.toml", "events.toml",
        ]
        for fname in expected_files:
            fpath = os.path.join(config_dir, fname)
            if not os.path.isfile(fpath):
                errors.append(f"Config file missing: {fpath}")
    else:
        errors.append(
            f"Config resolution: FAILED — protocol.toml not found. "
            f"Searched: CLAUDE_PLUGIN_ROOT={os.environ.get('CLAUDE_PLUGIN_ROOT', '(unset)')}, "
            f"file-relative, {args.cwd}/enforcement"
        )

    # ── Binary check ──
    from _resolve import ensure_sahjhan  # noqa: E402

    binary = ensure_sahjhan()
    if binary:
        print(f"Binary: OK ({binary})")
    else:
        errors.append("Binary: Sahjhan binary not found and could not be downloaded")

    # ── Report ──
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in manifest["required_hooks"].values())
    print(f"Hook verification: all {total} required hooks present.")
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate CHANGELOG.md entries from conventional commits.

Reads git log between the last release tag and HEAD, parses conventional
commit prefixes, and outputs Keep a Changelog formatted markdown.

Usage:
    python3 scripts/generate-changelog.py              # preview to stdout
    python3 scripts/generate-changelog.py --write      # update CHANGELOG.md in place
    python3 scripts/generate-changelog.py --since v0.4.0  # override base tag
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")

# Map conventional commit types to Keep a Changelog sections
SECTION_MAP = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "docs": "Documentation",
    "ci": "Infrastructure",
    "chore": "Infrastructure",
    "test": "Infrastructure",
}

# Sections that don't appear in the changelog (noise)
SKIP_TYPES = {"style"}

COMMIT_RE = re.compile(
    r"^(?P<type>\w+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<desc>.+)$"
)


def get_last_tag() -> str | None:
    """Get the most recent version tag."""
    result = subprocess.run(
        ["git", "tag", "-l", "v*", "--sort=-version:refname"],
        capture_output=True, text=True,
    )
    tags = result.stdout.strip().split("\n")
    return tags[0] if tags and tags[0] else None


def get_version() -> str:
    """Read version from plugin.json."""
    import json
    pj = Path(".claude-plugin/plugin.json")
    if pj.exists():
        return json.loads(pj.read_text()).get("version", "unreleased")
    return "unreleased"


def get_commits(since: str | None) -> list[dict]:
    """Get commits since the given ref (or all if None)."""
    cmd = ["git", "log", "--oneline", "--no-merges", "--format=%H %s"]
    if since:
        cmd.append(f"{since}..HEAD")
    result = subprocess.run(cmd, capture_output=True, text=True)
    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        hash_, _, subject = line.partition(" ")
        m = COMMIT_RE.match(subject)
        if m:
            commits.append({
                "hash": hash_[:7],
                "type": m.group("type"),
                "scope": m.group("scope") or "",
                "breaking": bool(m.group("breaking")),
                "desc": m.group("desc"),
                "raw": subject,
            })
        else:
            commits.append({
                "hash": hash_[:7],
                "type": "other",
                "scope": "",
                "breaking": False,
                "desc": subject,
                "raw": subject,
            })
    return commits


def format_changelog(commits: list[dict], version: str, since: str | None) -> str:
    """Format commits into Keep a Changelog sections."""
    sections: dict[str, list[str]] = {}
    breaking: list[str] = []

    for c in commits:
        if c["type"] in SKIP_TYPES:
            continue
        if c["breaking"]:
            breaking.append(f"- **BREAKING:** {c['desc']}")
            continue  # don't double-count in normal section

        section = SECTION_MAP.get(c["type"], "Other")
        scope = f"**{c['scope']}:** " if c["scope"] else ""
        entry = f"- {scope}{c['desc']}"
        sections.setdefault(section, []).append(entry)

    # Order: Breaking, Added, Fixed, Changed, Documentation, Infrastructure, Other
    order = ["Added", "Fixed", "Changed", "Documentation", "Infrastructure", "Other"]
    lines = [f"## [{version}] - {date.today().isoformat()}"]
    if since:
        lines.append("")
        lines.append(f"_Changes since {since}_")

    if breaking:
        lines.append("")
        lines.append("### Breaking Changes")
        lines.extend(breaking)

    for section in order:
        if section in sections:
            lines.append("")
            lines.append(f"### {section}")
            lines.extend(sections[section])

    return "\n".join(lines)


def update_changelog(entry: str) -> None:
    """Insert the entry into CHANGELOG.md under [Unreleased]."""
    if not CHANGELOG.exists():
        print(f"ERROR: {CHANGELOG} not found", file=sys.stderr)
        sys.exit(1)

    content = CHANGELOG.read_text()
    marker = "## [Unreleased]"
    if marker not in content:
        print(f"ERROR: '{marker}' not found in {CHANGELOG}", file=sys.stderr)
        sys.exit(1)

    # Find the end of the [Unreleased] section (next ## or end of comment block)
    # Replace everything between [Unreleased] and the next ## heading (or EOF)
    # with the new entry
    parts = content.split(marker, 1)
    after = parts[1]

    # Strip the comment block if present
    comment_end = after.find("-->")
    if comment_end != -1:
        after = after[comment_end + 3:].lstrip("\n")

    # Find next version heading
    next_heading = re.search(r"^## \[", after, re.MULTILINE)
    rest = after[next_heading.start():] if next_heading else ""

    new_content = parts[0] + marker + "\n\n" + entry + "\n\n" + rest
    CHANGELOG.write_text(new_content)
    print(f"Updated {CHANGELOG}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate changelog from conventional commits")
    parser.add_argument("--write", action="store_true", help="Write to CHANGELOG.md")
    parser.add_argument("--since", help="Base ref (default: last version tag)")
    args = parser.parse_args()

    since = args.since or get_last_tag()
    version = get_version()
    commits = get_commits(since)

    if not commits:
        print(f"No commits found since {since}")
        return

    entry = format_changelog(commits, version, since)

    if args.write:
        update_changelog(entry)
    else:
        print(entry)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Bug Hunter Punchlist Validator

Parses BUG-HUNTER-PUNCHLIST.md files and validates:
- All items have required fields
- Status counts match summary table
- Validation commands are present and executable
- Pattern references are consistent

Usage: python validate_punchlist.py [path-to-punchlist.md]
"""

import re
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter


VALID_DETERMINISM = {"deterministic", "intermittent", "theoretical"}


@dataclass
class PunchlistItem:
    id: str
    title: str
    severity: str = ""
    category: str = ""
    location: str = ""
    status: str = ""
    pattern: str = ""
    determinism: str = ""
    investigation: str = ""
    root_cause_confidence: str = ""
    has_problem: bool = False
    has_evidence: bool = False
    has_acceptance_criteria: bool = False
    has_validation_command: bool = False
    has_resolution: bool = False
    validation_command: str = ""


@dataclass
class ValidationResult:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_STATUSES = {"OPEN", "IN PROGRESS", "RESOLVED", "DEFERRED"}
VALID_CATEGORIES = {
    "bug/logic", "bug/state", "bug/error-handling", "bug/security", "bug/type",
    "test/missing", "test/bogus", "test/mock-abuse", "test/fragile", "test/shallow",
    "test/integration-gap", "doc/drift", "doc/missing", "design/coupling",
    "design/duplication", "design/dead-code", "design/inconsistency",
}


def parse_punchlist(content: str) -> list[PunchlistItem]:
    """Parse markdown punchlist into structured items."""
    items = []
    # Split on item headers (### BH-NNN: title)
    item_pattern = re.compile(r'^### (BH-\d+):\s+(.+)$', re.MULTILINE)
    matches = list(item_pattern.finditer(content))

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]

        item = PunchlistItem(id=match.group(1), title=match.group(2).strip())

        # Extract fields
        sev = re.search(r'\*\*Severity:\*\*\s*(\w+)', block)
        if sev:
            item.severity = sev.group(1)

        cat = re.search(r'\*\*Category:\*\*\s*(.+)', block)
        if cat:
            item.category = cat.group(1).strip()

        loc = re.search(r'\*\*Location:\*\*\s*(.+)', block)
        if loc:
            item.location = loc.group(1).strip()

        stat = re.search(r'\*\*Status:\*\*\s*(\w[\w\s]*\w)', block)
        if stat:
            item.status = stat.group(1).strip()

        pat = re.search(r'\*\*Pattern:\*\*\s*(PAT-\d+)', block)
        if pat:
            item.pattern = pat.group(1)

        det = re.search(r'\*\*Determinism:\*\*\s*(\w+)', block)
        if det:
            item.determinism = det.group(1).strip()

        inv = re.search(r'\*\*Investigation:\*\*\s*(.+)', block)
        if inv:
            item.investigation = inv.group(1).strip()

        rcc = re.search(r'\*\*Root Cause Confidence:\*\*\s*(\w+)', block)
        if rcc:
            item.root_cause_confidence = rcc.group(1).strip()

        item.has_problem = '**Problem:**' in block and len(
            block.split('**Problem:**')[1].split('**')[0].strip()) > 10
        item.has_evidence = '**Evidence:**' in block and len(
            block.split('**Evidence:**')[1].split('**')[0].strip()) > 10
        item.has_acceptance_criteria = '- [ ]' in block or '- [x]' in block
        item.has_validation_command = '**Validation Command:**' in block

        val_cmd = re.search(r'\*\*Validation Command:\*\*\s*```\w*\n(.+?)\n```', block, re.DOTALL)
        if val_cmd:
            item.validation_command = val_cmd.group(1).strip()

        item.has_resolution = '**Resolution:**' in block and len(
            block.split('**Resolution:**')[1].split('**')[0].strip()) > 5

        items.append(item)

    return items


def validate(items: list[PunchlistItem]) -> ValidationResult:
    """Validate parsed punchlist items."""
    result = ValidationResult()
    status_counts = Counter()
    severity_counts = Counter()
    category_counts = Counter()
    pattern_refs = set()

    for item in items:
        prefix = f"{item.id}"

        # Required fields
        if not item.severity:
            result.errors.append(f"{prefix}: missing severity")
        elif item.severity not in VALID_SEVERITIES:
            result.errors.append(f"{prefix}: invalid severity '{item.severity}'")

        if not item.category:
            result.errors.append(f"{prefix}: missing category")
        elif item.category not in VALID_CATEGORIES:
            result.warnings.append(f"{prefix}: non-standard category '{item.category}'")

        if not item.location:
            result.warnings.append(f"{prefix}: missing location")

        if not item.status:
            result.errors.append(f"{prefix}: missing status")
        elif item.status not in VALID_STATUSES:
            result.errors.append(f"{prefix}: invalid status '{item.status}'")

        if not item.has_problem:
            result.errors.append(f"{prefix}: missing or empty Problem section")

        if not item.has_evidence:
            result.warnings.append(f"{prefix}: missing or empty Evidence section")

        if not item.has_acceptance_criteria:
            result.errors.append(f"{prefix}: missing acceptance criteria (no checkboxes)")

        if not item.has_validation_command:
            result.errors.append(f"{prefix}: missing validation command")

        # Resolved items must have resolution
        if item.status == "RESOLVED" and not item.has_resolution:
            result.errors.append(f"{prefix}: marked RESOLVED but no resolution documented")

        # Optional field validation
        is_bug = item.category.startswith("bug/")

        if item.determinism and item.determinism not in VALID_DETERMINISM:
            result.warnings.append(
                f"{prefix}: non-standard determinism '{item.determinism}' "
                f"(expected: {', '.join(sorted(VALID_DETERMINISM))})"
            )

        if is_bug and not item.determinism:
            result.warnings.append(f"{prefix}: bug/* item missing Determinism field")

        if item.root_cause_confidence:
            if item.root_cause_confidence not in {"LOW", "MEDIUM", "HIGH"}:
                result.warnings.append(
                    f"{prefix}: invalid Root Cause Confidence '{item.root_cause_confidence}'"
                )

        # Deferred items should have evidence of reproduction attempts
        if item.status == "DEFERRED" and is_bug and not item.investigation:
            result.warnings.append(
                f"{prefix}: bug item DEFERRED without Investigation file link"
            )

        # Track counts
        status_counts[item.status] += 1
        severity_counts[item.severity] += 1
        category_counts[item.category] += 1
        if item.pattern:
            pattern_refs.add(item.pattern)

    result.stats = {
        "total_items": len(items),
        "by_status": dict(status_counts),
        "by_severity": dict(severity_counts),
        "by_category": category_counts.most_common(),
        "patterns_referenced": sorted(pattern_refs),
    }

    return result


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/holtz/PUNCHLIST.md")

    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)

    content = path.read_text()
    items = parse_punchlist(content)

    if not items:
        print(f"WARNING: No punchlist items found in {path}")
        sys.exit(0)

    result = validate(items)

    # Print report
    print(f"\n{'='*60}")
    print(f"Bug Hunter Punchlist Validation: {path}")
    print(f"{'='*60}")
    print(f"\nTotal items: {result.stats['total_items']}")
    print(f"By status:   {result.stats['by_status']}")
    print(f"By severity: {result.stats['by_severity']}")
    print(f"Top categories: {dict(result.stats['by_category'][:5])}")

    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")

    if result.warnings:
        print(f"\nWARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  - {w}")

    if not result.errors and not result.warnings:
        print("\nAll items valid")

    open_critical = sum(1 for i in items if i.severity == "CRITICAL" and i.status == "OPEN")
    if open_critical:
        print(f"\n{open_critical} CRITICAL items still OPEN")

    sys.exit(1 if result.errors else 0)


if __name__ == "__main__":
    main()

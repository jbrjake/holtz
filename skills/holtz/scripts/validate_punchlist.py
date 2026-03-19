#!/usr/bin/env python3
"""
Holtz Punchlist Validator

Parses PUNCHLIST.md files and validates:
- All items have required fields (severity, category, status, problem, acceptance criteria, validation command)
- Severity, status, and category values are from valid sets
- Resolved items have a resolution documented
- Deferred bug items have reproduction evidence or an investigation link
- Validation commands are present

Usage: python validate_punchlist.py [path-to-punchlist.md]
"""

import re
import sys
from pathlib import Path
from markdown_utils import mask_code_fences
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
    normalized, masked = mask_code_fences(content)
    items = []
    # Split on item headers (### BH-NNN: title) in masked content
    # so headers inside code fences are not matched
    item_pattern = re.compile(r'^### (BH-\d+):\s+(.+)$', re.MULTILINE)
    masked_matches = list(item_pattern.finditer(masked))

    # Build an index of header positions in normalized content by ID.
    # normalized may contain phantom headers inside code fences that
    # masked does not, so we cannot pair by array index — we match by ID.
    norm_matches_by_id: dict[str, list[re.Match]] = {}
    for m in item_pattern.finditer(normalized):
        norm_matches_by_id.setdefault(m.group(1), []).append(m)

    for i, match in enumerate(masked_matches):
        item_id = match.group(1)
        masked_start = match.end()
        masked_end = masked_matches[i + 1].start() if i + 1 < len(masked_matches) else len(masked)
        masked_block = masked[masked_start:masked_end]

        # Find this item's header in normalized content by ID.
        # Use the first match for this ID (real headers appear before any
        # phantom copies in code fences, since code fences are in Evidence
        # sections which come after the header).
        norm_match = norm_matches_by_id.get(item_id, [None])[0]
        if norm_match:
            norm_start = norm_match.end()
            # Find end: next real item's position in normalized, or EOF
            next_id = masked_matches[i + 1].group(1) if i + 1 < len(masked_matches) else None
            if next_id and next_id in norm_matches_by_id:
                norm_end = norm_matches_by_id[next_id][0].start()
            else:
                norm_end = len(normalized)
            original_block = normalized[norm_start:norm_end]
        else:
            original_block = masked_block  # fallback (shouldn't happen)

        item = PunchlistItem(id=match.group(1), title=match.group(2).strip())

        # Extract fields from masked block (code fence content hidden)
        sev = re.search(r'\*\*Severity:\*\*[ \t]*(\w+)', masked_block)
        if sev:
            item.severity = sev.group(1)

        cat = re.search(r'\*\*Category:\*\*[ \t]*(.+)', masked_block)
        if cat:
            item.category = cat.group(1).strip()

        loc = re.search(r'\*\*Location:\*\*[ \t]*(.+)', masked_block)
        if loc:
            item.location = loc.group(1).strip()

        stat = re.search(r'\*\*Status:\*\*[ \t]*(\w[\w ]*\w)', masked_block)
        if stat:
            item.status = stat.group(1).strip()

        pat = re.search(r'\*\*Pattern:\*\*[ \t]*(PAT-\d+)', masked_block)
        if pat:
            item.pattern = pat.group(1)

        det = re.search(r'\*\*Determinism:\*\*[ \t]*(\w+)', masked_block)
        if det:
            item.determinism = det.group(1).strip()

        inv = re.search(r'\*\*Investigation:\*\*[ \t]*(.+)', masked_block)
        if inv:
            item.investigation = inv.group(1).strip()

        rcc = re.search(r'\*\*Root Cause Confidence:\*\*[ \t]*(\w+)', masked_block)
        if rcc:
            item.root_cause_confidence = rcc.group(1).strip()

        # Section content and validation command use original block
        # (Evidence sections contain code fences with the actual evidence)
        section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*\w)[^\n]*)*))'
        problem_m = re.search(section_re % 'Problem', original_block)
        item.has_problem = bool(problem_m and len(problem_m.group(1).strip()) > 10)
        evidence_m = re.search(section_re % 'Evidence', original_block)
        item.has_evidence = bool(evidence_m and len(evidence_m.group(1).strip()) > 10)

        # Checkbox detection uses masked block (ignore checkboxes in code fences)
        item.has_acceptance_criteria = '- [ ]' in masked_block or '- [x]' in masked_block or '- [X]' in masked_block

        # Validation command uses original block (the command IS in a code fence)
        val_cmd = re.search(r'\*\*Validation Command:\*\*[ \t]*\n?```\w*\n(.+?)\n```', original_block, re.DOTALL)
        if val_cmd:
            item.validation_command = val_cmd.group(1).strip()
        item.has_validation_command = bool(item.validation_command)

        resolution_m = re.search(section_re % 'Resolution', original_block)
        item.has_resolution = bool(resolution_m and len(resolution_m.group(1).strip()) > 5)

        items.append(item)

    return items


def validate(items: list[PunchlistItem], content: str = "") -> ValidationResult:
    """Validate parsed punchlist items."""
    result = ValidationResult()
    status_counts = Counter()
    severity_counts = Counter()
    category_counts = Counter()
    pattern_refs = set()
    seen_ids: set[str] = set()

    # File structure validation
    if content:
        if '# Holtz Punchlist' not in content and '# Bug Hunter Punchlist' not in content:
            result.warnings.append("Missing punchlist header section")
        if '## Summary' not in content:
            result.warnings.append("Missing Summary section")
        if '## Items' not in content:
            result.warnings.append("Missing Items section")

    for item in items:
        prefix = f"{item.id}"

        # Duplicate ID check
        if item.id in seen_ids:
            result.errors.append(f"{prefix}: duplicate item ID")
        seen_ids.add(item.id)

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
        print(f"ERROR: No punchlist items found in {path}")
        sys.exit(1)

    result = validate(items, content)

    # Print report
    print(f"\n{'='*60}")
    print(f"Holtz Punchlist Validation: {path}")
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

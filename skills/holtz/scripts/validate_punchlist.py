#!/usr/bin/env python3
"""
Holtz Punchlist Validator

Parses PUNCHLIST.md files and validates:
- All items have required fields (severity, category, status, problem, discovery chain, acceptance criteria, validation command)
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
    has_discovery_chain: bool = False
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

    # Map character offsets between masked and normalized using line numbers.
    # mask_code_fences preserves line count, so line N in masked = line N in
    # normalized. This avoids the phantom header problem: ID-based matching
    # could grab a phantom header inside a code fence that shares an ID with
    # a real item. Line-number mapping is immune to phantoms.
    norm_line_offsets = [0]
    for ci, ch in enumerate(normalized):
        if ch == '\n':
            norm_line_offsets.append(ci + 1)

    def _masked_offset_to_norm(masked_offset: int) -> int:
        """Convert a character offset in masked to the same line's offset in normalized."""
        line_num = masked[:masked_offset].count('\n')
        if line_num < len(norm_line_offsets):
            return norm_line_offsets[line_num]
        return len(normalized)

    for i, match in enumerate(masked_matches):
        masked_start = match.end()
        masked_end = masked_matches[i + 1].start() if i + 1 < len(masked_matches) else len(masked)
        masked_block = masked[masked_start:masked_end]

        # Map masked header position to normalized content via line number.
        norm_start = _masked_offset_to_norm(masked_start)
        if i + 1 < len(masked_matches):
            norm_end = _masked_offset_to_norm(masked_matches[i + 1].start())
        else:
            norm_end = len(normalized)
        original_block = normalized[norm_start:norm_end]

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

        stat = re.search(r'\*\*Status:\*\*[ \t]*(OPEN|IN PROGRESS|RESOLVED|DEFERRED)', masked_block)
        if stat:
            item.status = stat.group(1)

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

        # Section content uses a three-step approach:
        # 1. Find the field header in masked_block (ensures it's not inside a code fence)
        # 2. Map the header's line position to original_block (same line number)
        # 3. Extract content from original_block starting at the mapped position
        # This prevents code fence field headers from interfering with extraction
        # even when the same header appears in both a code fence and real content.
        # Known punchlist field names that terminate section capture.
        # Only these patterns stop the regex — not arbitrary **Bold Colon:** text.
        _field_names = (
            'Severity', 'Category', 'Location', 'Status', 'Pattern',
            'Determinism', 'Investigation', 'Root Cause Confidence',
            'Problem', 'Evidence', 'Discovery Chain',
            'Acceptance Criteria', 'Validation Command', 'Resolution',
        )
        _field_alt = '|'.join(re.escape(f) for f in _field_names)
        section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*(?:' + _field_alt + r'):\*\*)[^\n]*)*))'
        header_re = r'\*\*%s:\*\*'

        def _masked_pos_to_orig_offset(pos_in_masked):
            """Map a character position in masked_block to the line start in original_block."""
            line_num = masked_block[:pos_in_masked].count('\n')
            offset = 0
            for _ in range(line_num):
                nl = original_block.find('\n', offset)
                if nl == -1:
                    return len(original_block)
                offset = nl + 1
            return offset

        def _section_from_original(field_name):
            """Find section boundaries in masked, extract content from original.

            Uses masked_block for boundary detection (immune to code-fenced
            field headers) and original_block for content extraction.
            Returns the section content as a string, or None.
            """
            masked_match = re.search(section_re % field_name, masked_block)
            if not masked_match:
                return None

            cap_start = masked_match.start(1)
            cap_end = masked_match.end(1)
            start_line = masked_block[:cap_start].count('\n')
            end_line = masked_block[:cap_end].count('\n')

            orig_lines = original_block.split('\n')
            masked_lines_list = masked_block.split('\n')

            if start_line >= len(orig_lines):
                return None

            # First line: extract content after the field header.
            # The header line itself is never inside a code fence, so the
            # column offset is the same in masked and original.
            first_masked_line = masked_lines_list[start_line]
            header_m = re.search(
                r'\*\*' + re.escape(field_name) + r':\*\*[ \t]*',
                first_masked_line,
            )
            if not header_m:
                return None

            col_offset = header_m.end()
            parts = [orig_lines[start_line][col_offset:]]

            # Remaining lines: take from original_block directly.
            for ln in range(start_line + 1, min(end_line + 1, len(orig_lines))):
                parts.append(orig_lines[ln])

            return '\n'.join(parts)

        problem_content = _section_from_original('Problem')
        item.has_problem = bool(problem_content and len(problem_content.strip()) > 10)
        evidence_content = _section_from_original('Evidence')
        item.has_evidence = bool(evidence_content and len(evidence_content.strip()) > 10)

        # Discovery Chain: presence check only (header exists in masked content)
        item.has_discovery_chain = bool(re.search(header_re % 'Discovery Chain', masked_block))

        # Checkbox detection: scoped to Acceptance Criteria section in masked block
        ac_m = re.search(section_re % 'Acceptance Criteria', masked_block)
        ac_content = ac_m.group(1) if ac_m else ""
        item.has_acceptance_criteria = '- [ ]' in ac_content or '- [x]' in ac_content or '- [X]' in ac_content

        # Validation command: header must exist in masked, content from original.
        # Supports backtick and tilde fences of any length (3+), with optional
        # blank lines between header and fence, per CommonMark spec.
        vc_match = re.search(header_re % 'Validation Command', masked_block)
        if vc_match:
            orig_offset = _masked_pos_to_orig_offset(vc_match.start())
            vc_region = original_block[orig_offset:]
            _vc_header = r'\*\*Validation Command:\*\*[ \t]*\n(?:\s*\n)*'
            # Try backtick fence (3+), then tilde fence (3+).
            val_cmd = re.search(
                _vc_header + r'`{3,}\w*\n(.+?)\n`{3,}', vc_region, re.DOTALL)
            if not val_cmd:
                val_cmd = re.search(
                    _vc_header + r'~{3,}\w*\n(.+?)\n~{3,}', vc_region, re.DOTALL)
            if val_cmd:
                item.validation_command = val_cmd.group(1).strip()
        item.has_validation_command = bool(item.validation_command)

        resolution_content = _section_from_original('Resolution')
        item.has_resolution = bool(resolution_content and len(resolution_content.strip()) > 5)

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

    # File structure validation — use masked content so headers inside
    # code fences don't suppress structural warnings.
    if content:
        _, masked_content = mask_code_fences(content)
        if '# Holtz Punchlist' not in masked_content and '# Bug Hunter Punchlist' not in masked_content:
            result.warnings.append("Missing punchlist header section")
        if '## Summary' not in masked_content:
            result.warnings.append("Missing Summary section")
        if '## Items' not in masked_content:
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

        if not item.has_discovery_chain:
            result.errors.append(f"{prefix}: missing Discovery Chain")

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

        # Deferred bug items should have evidence of reproduction attempts
        # (in the Evidence section OR the linked investigation file).
        # Only warn when BOTH are missing — per punchlist-format.md spec.
        if item.status == "DEFERRED" and is_bug and not item.investigation and not item.has_evidence:
            result.warnings.append(
                f"{prefix}: bug item DEFERRED without Evidence or Investigation file link"
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

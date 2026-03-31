#!/usr/bin/env python3
"""Migrate legacy Holtz archive directories to JSONL events.

Reads markdown files from an archived run directory and emits
JSONL events to stdout. Output is piped to sahjhan ledger import.

Usage:
    python scripts/migrate_legacy.py --input docs/holtz/archive/2026-03-22-run9/
    python scripts/migrate_legacy.py --run 9 --input docs/holtz/archive/2026-03-22-run9/
    python scripts/migrate_legacy.py --all --archive-root docs/holtz/archive/
    python scripts/migrate_legacy.py --build-project
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import fence masking from holtz scripts
_SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "holtz" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from markdown_utils import mask_code_fences  # noqa: E402

ARCHIVE_MAP: dict[str, dict[str, Any]] = {
    "bug-hunter-2026-03-19": {"run": 1, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21": {"run": 2, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run2": {"run": 3, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run3": {"run": 4, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run4": {"run": 5, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run5": {"run": 6, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run6": {"run": 7, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run7": {"run": 8, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-22": {"run": 9, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-22-run2": {"run": 10, "auditor": "holtz", "era": "proto"},
    "stray-root-2026-03-22": {"run": 11, "auditor": "holtz", "era": "proto"},
    "2026-03-19-run2": {"run": 12, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run2": {"run": 13, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run3": {"run": 14, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run4": {"run": 15, "auditor": "holtz", "era": "numbered"},
    "2026-03-21-run5": {"run": 16, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run6": {"run": 17, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run7": {"run": 18, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run8": {"run": 19, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run9": {"run": 20, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run10": {"run": 21, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run11": {"run": 22, "auditor": "holtz", "era": "numbered"},
    "2026-03-23-run12": {"run": 23, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run13": {"run": 24, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run14": {"run": 25, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run15": {"run": 26, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run16": {"run": 27, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run17": {"run": 28, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run18": {"run": 29, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run19": {"run": 30, "auditor": "holtz", "era": "numbered"},
}

JUSTINE_MAP: dict[str, int] = {
    "justine-2026-03-22": 19,
    "justine-2026-03-22-run11": 22,
    "justine-2026-03-23-run12": 23,
    "justine-2026-03-24-run14": 25,
    "justine-2026-03-25": 28,
    "justine-2026-03-25-run19": 30,
    "justine-2026-03-25-run20": 31,
}

# Step mapping for lettered recon files (proto era)
LETTERED_RECON_MAP: dict[str, str] = {
    "0a-project-overview.md": "0",
    "0b-test-infra.md": "1",
    "0c-test-baseline.md": "1",
    "0c1-ci-status.md": "1",
    "0d-lint-results.md": "1",
    "0e-churn.md": "2",
    "0f-skipped-tests.md": "2",
    "0g-recon-summary.md": "3",
    "0-pattern-heuristics.md": "3",
    "0-recommendation-escalation.md": "3",
    "0h-predictions.md": "4",
}

# Step mapping for numbered recon files
NUMBERED_RECON_MAP: dict[str, str] = {
    "step0-project-overview.md": "0",
    "step1-toolchain.md": "1",
    "step2-code-signals.md": "2",
    "step2-cold-files.md": "2",
    "step3-recon-summary.md": "3",
    "step4-predictions.md": "4",
}

# Justine variant recon
JUSTINE_RECON_MAP: dict[str, str] = {
    "predictions.md": "4",
    "recon-summary.md": "3",
}

# Proto-era filename mapping
PROTO_FILENAMES = {
    "BUG-HUNTER-PUNCHLIST.md": "PUNCHLIST.md",
    "BUG-HUNTER-STATUS.md": "STATUS.md",
    "BUG-HUNTER-SUMMARY.md": "SUMMARY.md",
}


def _migrated_at() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def _make_event(
    event_type: str,
    fields: dict[str, str],
    run: str,
    auditor: str,
    project: str = "holtz",
    source: str = "",
) -> dict[str, Any]:
    """Create a JSONL event dict with breadcrumbs and migration markers."""
    base_fields = {
        "project": project,
        "run": str(run),
        "auditor": auditor,
    }
    base_fields.update(fields)
    base_fields["_migrated"] = "true"
    base_fields["_migrated_at"] = _migrated_at()
    if source:
        base_fields["_source"] = source
    return {"type": event_type, "fields": base_fields}


# ---------------------------------------------------------------------------
# Punchlist parser
# ---------------------------------------------------------------------------


def parse_punchlist(
    content: str,
    run: str,
    auditor: str,
    source: str,
    project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse a punchlist markdown file into finding/finding_resolved events.

    Handles two formats:
    1. Table format (newer): | ID | Category | Location | ... | Status |
    2. Block format (proto era): ### BH-NNN: Title  with **Status:** field
    """
    events: list[dict[str, Any]] = []

    # Try table format first
    if _is_table_format(content):
        events.extend(_parse_table_punchlist(content, run, auditor, source, project))
    else:
        events.extend(_parse_block_punchlist(content, run, auditor, source, project))

    return events


def _is_table_format(content: str) -> bool:
    """Detect if punchlist uses table format (pipes in header)."""
    _, masked = mask_code_fences(content)
    for line in masked.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and "ID" in stripped:
            return True
        if stripped.startswith("### B"):
            return False
    return False


def _current_severity(content: str, pos: int) -> str:
    """Find the most recent ## SEVERITY header before position pos."""
    severity = "MEDIUM"  # default
    for match in re.finditer(r"^##\s+(CRITICAL|HIGH|MEDIUM|LOW)\b", content[:pos], re.MULTILINE):
        severity = match.group(1)
    return severity


def _parse_table_punchlist(
    content: str, run: str, auditor: str, source: str, project: str,
) -> list[dict[str, Any]]:
    """Parse table-format punchlist."""
    events: list[dict[str, Any]] = []
    current_severity = "MEDIUM"

    for line in content.split("\n"):
        stripped = line.strip()

        # Track severity headers
        severity_match = re.match(r"^##\s+(CRITICAL|HIGH|MEDIUM|LOW)\b", stripped)
        if severity_match:
            current_severity = severity_match.group(1)
            continue

        # Skip non-table lines and separator rows
        if not stripped.startswith("|") or stripped.startswith("|-"):
            continue

        cells = [c.strip() for c in stripped.split("|")]
        # Remove empty first/last from leading/trailing pipes
        cells = [c for c in cells if c]

        if len(cells) < 5:
            continue

        # Skip header row
        if cells[0] == "ID" or cells[0].startswith("--"):
            continue

        item_id = cells[0].strip()
        if not re.match(r"^B[HJ]-\d{3}$", item_id):
            continue

        category = cells[1].strip() if len(cells) > 1 else ""
        location = cells[2].strip() if len(cells) > 2 else ""
        perspective = cells[3].strip() if len(cells) > 3 else ""
        description = cells[4].strip() if len(cells) > 4 else ""
        status = cells[5].strip() if len(cells) > 5 else "OPEN"

        finding = _make_event("finding", {
            "phase": "audit",
            "step": "",
            "id": item_id,
            "severity": current_severity,
            "category": category,
            "location": location,
            "perspective": perspective,
            "description": description,
            "predicted_by": "",
        }, run=run, auditor=auditor, project=project, source=source)
        events.append(finding)

        if status == "RESOLVED":
            resolved = _make_event("finding_resolved", {
                "phase": "fix_loop",
                "step": "",
                "id": item_id,
                "commit_hash": "",  # not available from markdown
            }, run=run, auditor=auditor, project=project, source=source)
            events.append(resolved)

    return events


def _parse_block_punchlist(
    content: str, run: str, auditor: str, source: str, project: str,
) -> list[dict[str, Any]]:
    """Parse block-format punchlist (### BH-NNN: Title blocks)."""
    events: list[dict[str, Any]] = []

    # Split into blocks starting with ### B[HJ]-
    blocks = re.split(r"(?=^###\s+B[HJ]-\d{3}:)", content, flags=re.MULTILINE)

    for block in blocks:
        header_match = re.match(r"^###\s+(B[HJ]-\d{3}):\s*(.*)", block)
        if not header_match:
            continue

        item_id = header_match.group(1)
        description = header_match.group(2).strip()

        # Extract fields from the block
        severity = _extract_field(block, "Severity") or _current_severity(content, content.find(block))
        category = _extract_field(block, "Category") or ""
        location = _extract_field(block, "Location") or ""
        perspective = _extract_field(block, "Perspective") or ""
        status = _extract_field(block, "Status") or "OPEN"

        finding = _make_event("finding", {
            "phase": "audit",
            "step": "",
            "id": item_id,
            "severity": severity,
            "category": category,
            "location": location,
            "perspective": perspective,
            "description": description,
            "predicted_by": "",
        }, run=run, auditor=auditor, project=project, source=source)
        events.append(finding)

        if status == "RESOLVED":
            commit = _extract_field(block, "Fix Commit") or ""
            resolved = _make_event("finding_resolved", {
                "phase": "fix_loop",
                "step": "",
                "id": item_id,
                "commit_hash": commit,
            }, run=run, auditor=auditor, project=project, source=source)
            events.append(resolved)

    return events


def _extract_field(block: str, field_name: str) -> str | None:
    """Extract **FieldName:** value from a markdown block."""
    _, masked = mask_code_fences(block)
    match = re.search(rf"\*\*{field_name}:\*\*\s*(.*)", masked)
    if not match:
        return None
    # Return the value from the original (unmasked) content at the same position
    orig_match = re.search(rf"\*\*{field_name}:\*\*\s*(.*)", block[match.start():])
    return orig_match.group(1).strip() if orig_match else match.group(1).strip()


# ---------------------------------------------------------------------------
# Recon parser
# ---------------------------------------------------------------------------


def parse_recon_dir(
    files: dict[str, str],
    run: str,
    auditor: str,
    project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse recon directory files into recon_finding and prediction events.

    Args:
        files: dict mapping filename to content
        run: run number
        auditor: "holtz" or "justine"
    """
    events: list[dict[str, Any]] = []

    for filename, content in sorted(files.items()):
        if filename.endswith(".bak"):
            continue

        step = _recon_file_step(filename)
        if step is None:
            continue

        source = f"recon/{filename}"

        # Step 4 (predictions) gets special handling
        if step == "4":
            events.extend(_parse_predictions(content, run, auditor, source, project))
            # Also emit as recon_finding
            events.append(_make_event("recon_finding", {
                "phase": "recon",
                "step": step,
                "topic": "predictions",
                "content": content[:500],  # truncate for event size
            }, run=run, auditor=auditor, project=project, source=source))
            continue

        # Split on ## headers for multi-section files
        sections = _split_sections(content)
        if sections:
            for topic, section_content in sections:
                events.append(_make_event("recon_finding", {
                    "phase": "recon",
                    "step": step,
                    "topic": topic,
                    "content": section_content[:500],
                }, run=run, auditor=auditor, project=project, source=source))
        else:
            # Single-section file
            topic = _topic_from_filename(filename)
            events.append(_make_event("recon_finding", {
                "phase": "recon",
                "step": step,
                "topic": topic,
                "content": content[:500],
            }, run=run, auditor=auditor, project=project, source=source))

        # Also emit recon_step event
        events.append(_make_event("recon_step", {
            "phase": "recon",
            "step": step,
            "artifact_path": source,
        }, run=run, auditor=auditor, project=project, source=source))

    return events


def _recon_file_step(filename: str) -> str | None:
    """Map a recon filename to its step number."""
    if filename in LETTERED_RECON_MAP:
        return LETTERED_RECON_MAP[filename]
    if filename in NUMBERED_RECON_MAP:
        return NUMBERED_RECON_MAP[filename]
    if filename in JUSTINE_RECON_MAP:
        return JUSTINE_RECON_MAP[filename]
    # Try numbered prefix
    m = re.match(r"^step(\d)-", filename)
    if m:
        return m.group(1)
    return None


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content on ## headers into (topic, content) pairs."""
    sections: list[tuple[str, str]] = []
    parts = re.split(r"^##\s+", content, flags=re.MULTILINE)
    for part in parts[1:]:  # skip preamble before first ##
        lines = part.split("\n", 1)
        topic = lines[0].strip().lower().replace(" ", "-")
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:
            sections.append((topic, body))
    return sections


def _topic_from_filename(filename: str) -> str:
    """Derive a topic slug from a filename."""
    name = Path(filename).stem
    # Remove numeric prefixes
    name = re.sub(r"^(step)?\d+[a-z]?-?", "", name)
    return name.lower().replace(" ", "-") or "general"


def _parse_predictions(
    content: str,
    run: str,
    auditor: str,
    source: str,
    project: str,
) -> list[dict[str, Any]]:
    """Parse prediction tables from recon step 4 files."""
    events: list[dict[str, Any]] = []
    _, masked = mask_code_fences(content)

    # Match table rows: | N | target | confidence | basis |
    for match in re.finditer(
        r"\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*(HIGH|MEDIUM|LOW)\s*\|\s*(.*?)\s*\|",
        masked,
    ):
        events.append(_make_event("prediction", {
            "id": match.group(1),
            "target": match.group(2).strip(),
            "confidence": match.group(3),
            "basis": match.group(4).strip(),
        }, run=run, auditor=auditor, project=project, source=source))

    return events


# ---------------------------------------------------------------------------
# Audit parser
# ---------------------------------------------------------------------------


def parse_audit_file(
    filename: str,
    content: str,
    run: str,
    auditor: str,
    project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse an audit file into claim/test_finding/code_finding events."""
    source = f"audit/{filename}"
    events: list[dict[str, Any]] = []

    if filename.startswith("1-"):
        # Doc claims audit -- table rows
        events.extend(_parse_claims_table(content, run, auditor, source, project))
    elif filename.startswith("2-"):
        # Test audit findings
        events.extend(_parse_test_findings(content, run, auditor, source, project))
    elif filename.startswith(("3-", "3a-", "3b-", "3c-")):
        # Code audit / adversarial findings
        events.extend(_parse_code_findings(content, run, auditor, source, project))
    elif filename.startswith(("4-", "convergence-sweep", "final-sweep")):
        # Resweep findings (step 16)
        events.extend(_parse_code_findings(content, run, auditor, source, project, step="16"))

    return events


def _parse_claims_table(
    content: str, run: str, auditor: str, source: str, project: str,
) -> list[dict[str, Any]]:
    """Parse doc claims audit table."""
    events: list[dict[str, Any]] = []
    for line in content.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 4 or cells[0] in ("Source", "--", "---"):
            continue
        if cells[0].startswith("-"):
            continue
        events.append(_make_event("audit_claim", {
            "phase": "audit",
            "step": "6",
            "source": cells[0],
            "claim": cells[1] if len(cells) > 1 else "",
            "verdict": cells[2] if len(cells) > 2 else "",
            "evidence": cells[3] if len(cells) > 3 else "",
        }, run=run, auditor=auditor, project=project, source=source))
    return events


def _parse_test_findings(
    content: str, run: str, auditor: str, source: str, project: str,
) -> list[dict[str, Any]]:
    """Parse test audit findings."""
    events: list[dict[str, Any]] = []
    # Look for ### headers or table rows
    blocks = re.split(r"(?=^###\s+)", content, flags=re.MULTILINE)
    for block in blocks:
        header = re.match(r"^###\s+(.*)", block)
        if not header:
            continue
        test_file = header.group(1).strip()
        anti_pattern = ""
        evidence = block[header.end():].strip()[:300]

        # Try to extract anti-pattern from block
        ap_match = re.search(r"\*\*Anti.?[Pp]attern:\*\*\s*(.*)", block)
        if ap_match:
            anti_pattern = ap_match.group(1).strip()

        events.append(_make_event("test_audit_finding", {
            "phase": "audit",
            "step": "7",
            "test_file": test_file,
            "anti_pattern": anti_pattern,
            "evidence": evidence,
        }, run=run, auditor=auditor, project=project, source=source))
    return events


def _parse_code_findings(
    content: str, run: str, auditor: str, source: str, project: str, step: str = "8",
) -> list[dict[str, Any]]:
    """Parse code audit / adversarial findings."""
    events: list[dict[str, Any]] = []
    blocks = re.split(r"(?=^###\s+)", content, flags=re.MULTILINE)
    for block in blocks:
        header = re.match(r"^###\s+(.*)", block)
        if not header:
            continue
        module = header.group(1).strip()
        concern = ""
        evidence = block[header.end():].strip()[:300]

        concern_match = re.search(r"\*\*Concern:\*\*\s*(.*)", block)
        if concern_match:
            concern = concern_match.group(1).strip()

        events.append(_make_event("code_audit_finding", {
            "phase": "audit",
            "step": step,
            "module": module,
            "concern": concern,
            "evidence": evidence,
        }, run=run, auditor=auditor, project=project, source=source))
    return events


# ---------------------------------------------------------------------------
# Summary, merge report, status, history, postmortem parsers
# ---------------------------------------------------------------------------


def parse_summary(
    content: str, run: str, auditor: str, source: str, project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse SUMMARY.md into run_summary + prediction_outcome events."""
    events: list[dict[str, Any]] = []

    # Extract totals — use anchored patterns to avoid matching wrong fields
    total_match = re.search(r"total\s+findings\s*:?\s*(\d+)", content, re.IGNORECASE)
    resolved_match = re.search(r"(?:total\s+)?resolved\s*:?\s*(\d+)", content, re.IGNORECASE)
    accuracy_match = re.search(r"prediction.*?accuracy.*?(\d+[%.]?\d*)", content, re.IGNORECASE)

    total = total_match.group(1) if total_match else "0"
    resolved = resolved_match.group(1) if resolved_match else "0"
    accuracy = accuracy_match.group(1) if accuracy_match else ""

    # Extract recommendations section
    rec_match = re.search(r"## Recommendations?\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    recommendations = rec_match.group(1).strip()[:500] if rec_match else ""

    events.append(_make_event("run_summary", {
        "phase": "finalize",
        "step": "20",
        "total_findings": total,
        "resolved": resolved,
        "prediction_accuracy": accuracy,
        "recommendations": recommendations,
    }, run=run, auditor=auditor, project=project, source=source))

    # Extract prediction outcomes from tables
    for match in re.finditer(
        r"\|\s*(\d+)\s*\|.*?\|\s*(CONFIRMED|UNCONFIRMED)\s*\|",
        content,
    ):
        events.append(_make_event("prediction_outcome", {
            "prediction_id": match.group(1),
            "outcome": match.group(2),
            "finding_id": "",
        }, run=run, auditor=auditor, project=project, source=source))

    return events


def parse_merge_report(
    content: str, run: str, auditor: str, source: str, project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse MERGE-REPORT.md into merge_result event."""
    def _extract_count(label: str) -> str:
        m = re.search(rf"{label}.*?(\d+)", content, re.IGNORECASE)
        return m.group(1) if m else "0"

    return [_make_event("merge_result", {
        "phase": "merge",
        "step": "9",
        "agreements": _extract_count("agreement"),
        "holtz_only": _extract_count("holtz.only"),
        "justine_only": _extract_count("justine.only"),
        "contradictions": _extract_count("contradiction"),
    }, run=run, auditor=auditor, project=project, source=source)]


def parse_status(
    content: str, run: str, auditor: str, source: str, project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse STATUS.md into state_transition events (reconstructed)."""
    events: list[dict[str, Any]] = []

    # Extract completed step checkboxes: - [x] Step N: description
    for match in re.finditer(r"- \[x\]\s*(.*)", content):
        step_text = match.group(1).strip()
        events.append(_make_event("state_transition", {
            "phase": "",
            "step": "",
            "description": step_text,
        }, run=run, auditor=auditor, project=project, source=source))

    return events


def parse_history_json(
    content: str, run: str, auditor: str, source: str, project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse HISTORY.json into convergence_iteration events."""
    events: list[dict[str, Any]] = []
    try:
        data = json.loads(content)
        iterations = data if isinstance(data, list) else data.get("iterations", [])
        for i, entry in enumerate(iterations):
            events.append(_make_event("convergence_iteration", {
                "phase": "fix_loop",
                "step": "10",
                "iteration": str(i + 1),
                "open": str(entry.get("open", entry.get("items_remaining", 0))),
                "resolved": str(entry.get("resolved", entry.get("items_resolved", 0))),
                "test_count": str(entry.get("test_count", entry.get("tests", 0))),
                "tests_passed": str(entry.get("tests_passed", entry.get("passed", True))).lower(),
            }, run=run, auditor=auditor, project=project, source=source))
    except (json.JSONDecodeError, KeyError):
        pass
    return events


def parse_postmortem(
    content: str, run: str, auditor: str, source: str, project: str = "holtz",
) -> list[dict[str, Any]]:
    """Parse postmortem/self-reflection into run_postmortem event."""
    return [_make_event("run_postmortem", {
        "phase": "finalize",
        "step": "",
        "content": content[:2000],  # truncate for event size
    }, run=run, auditor=auditor, project=project, source=source)]


# ---------------------------------------------------------------------------
# Directory orchestrator
# ---------------------------------------------------------------------------


def migrate_directory(
    path: Path,
    run: int,
    auditor: str = "holtz",
    project: str = "holtz",
) -> list[dict[str, Any]]:
    """Migrate a complete archive directory to JSONL events."""
    events: list[dict[str, Any]] = []
    run_str = str(run)

    if not path.is_dir():
        return events

    # --- Punchlist ---
    for punchlist_name in ["PUNCHLIST-MERGED.md", "PUNCHLIST.md", "BUG-HUNTER-PUNCHLIST.md"]:
        pf = path / punchlist_name
        if pf.exists():
            events.extend(parse_punchlist(
                pf.read_text(), run=run_str, auditor=auditor,
                source=punchlist_name, project=project,
            ))
            break  # use first found

    # --- Status ---
    for status_name in ["STATUS.md", "BUG-HUNTER-STATUS.md"]:
        sf = path / status_name
        if sf.exists():
            events.extend(parse_status(
                sf.read_text(), run=run_str, auditor=auditor,
                source=status_name, project=project,
            ))
            break

    # --- Summary ---
    for summary_name in ["SUMMARY.md", "BUG-HUNTER-SUMMARY.md"]:
        smf = path / summary_name
        if smf.exists():
            events.extend(parse_summary(
                smf.read_text(), run=run_str, auditor=auditor,
                source=summary_name, project=project,
            ))
            break

    # --- Merge Report ---
    mr = path / "MERGE-REPORT.md"
    if mr.exists():
        events.extend(parse_merge_report(
            mr.read_text(), run=run_str, auditor=auditor,
            source="MERGE-REPORT.md", project=project,
        ))

    # --- HISTORY.json ---
    hj = path / "HISTORY.json"
    if hj.exists():
        events.extend(parse_history_json(
            hj.read_text(), run=run_str, auditor=auditor,
            source="HISTORY.json", project=project,
        ))

    # --- Recon files ---
    recon_dir = path / "recon"
    if recon_dir.is_dir():
        recon_files = {}
        for f in sorted(recon_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                recon_files[f.name] = f.read_text()
        if recon_files:
            events.extend(parse_recon_dir(recon_files, run=run_str, auditor=auditor, project=project))

    # --- Audit files ---
    audit_dir = path / "audit"
    if audit_dir.is_dir():
        for f in sorted(audit_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                events.extend(parse_audit_file(
                    f.name, f.read_text(), run=run_str, auditor=auditor, project=project,
                ))

    # --- Postmortem / self-reflection ---
    for pm_name in [f"run-{run}-postmortem.md", "self-reflection.md"]:
        pm = path / pm_name
        if pm.exists():
            events.extend(parse_postmortem(
                pm.read_text(), run=run_str, auditor=auditor,
                source=pm_name, project=project,
            ))
    # Also check parent dir for postmortems referencing this run
    parent_pm = path.parent / f"run-{run}-postmortem.md"
    if parent_pm.exists():
        events.extend(parse_postmortem(
            parent_pm.read_text(), run=run_str, auditor=auditor,
            source=parent_pm.name, project=project,
        ))

    # --- Nested justine directory ---
    justine_dir = path / "justine"
    if justine_dir.is_dir():
        justine_events = migrate_directory(justine_dir, run=run, auditor="justine", project=project)
        events.extend(justine_events)

    return events


def build_project_ledger(
    runs: list[tuple[int, str]],
    project: str = "holtz",
    impact_graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Build project-level ledger with run registry and checkpoint events."""
    events: list[dict[str, Any]] = []

    for run_num, auditor in runs:
        events.append(_make_event("run_registered", {
            "phase": "",
            "step": "",
        }, run=str(run_num), auditor=auditor, project=project))
        events.append(_make_event("run_completed", {
            "phase": "",
            "step": "",
        }, run=str(run_num), auditor=auditor, project=project))

    # Checkpoint from current state files
    checkpoint_fields: dict[str, str] = {
        "phase": "",
        "step": "",
    }

    if impact_graph_path and impact_graph_path.exists():
        checkpoint_fields["impact_graph_snapshot"] = impact_graph_path.read_text()[:5000]

    events.append(_make_event("_checkpoint", checkpoint_fields,
        run="0", auditor="holtz", project=project))

    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy Holtz archives to JSONL")
    parser.add_argument("--input", type=Path, help="Archive directory to migrate")
    parser.add_argument("--run", type=int, help="Override run number")
    parser.add_argument("--project", default="holtz", help="Project name")
    parser.add_argument("--all", action="store_true", help="Migrate all archive directories")
    parser.add_argument("--archive-root", type=Path, default=Path("docs/holtz/archive"),
                        help="Root of archive directories")
    parser.add_argument("--build-project", action="store_true", help="Build project ledger")
    args = parser.parse_args()

    if args.build_project:
        runs = [(meta["run"], meta["auditor"]) for meta in ARCHIVE_MAP.values()]
        runs.sort()
        events = build_project_ledger(runs, project=args.project)
        for event in events:
            print(json.dumps(event))
        return

    if args.all:
        for dirname, meta in sorted(ARCHIVE_MAP.items(), key=lambda x: x[1]["run"]):
            dir_path = args.archive_root / dirname
            if not dir_path.is_dir():
                print(f"# Skipping {dirname} (not found)", file=sys.stderr)
                continue
            events = migrate_directory(dir_path, run=meta["run"],
                                       auditor=meta["auditor"], project=args.project)
            for event in events:
                print(json.dumps(event))

        # Standalone justine directories
        for dirname, matched_run in sorted(JUSTINE_MAP.items(), key=lambda x: x[1]):
            dir_path = args.archive_root / dirname
            if not dir_path.is_dir():
                continue
            events = migrate_directory(dir_path, run=matched_run,
                                       auditor="justine", project=args.project)
            for event in events:
                print(json.dumps(event))
        return

    if not args.input:
        parser.error("--input or --all required")

    # Determine run number
    run = args.run
    if run is None:
        dirname = args.input.name
        if dirname in ARCHIVE_MAP:
            run = ARCHIVE_MAP[dirname]["run"]
        elif dirname in JUSTINE_MAP:
            run = JUSTINE_MAP[dirname]
        else:
            parser.error(f"Unknown archive dir '{dirname}'. Use --run to override.")

    auditor = "holtz"
    dirname = args.input.name
    if dirname in ARCHIVE_MAP:
        auditor = ARCHIVE_MAP[dirname]["auditor"]
    elif dirname.startswith("justine-"):
        auditor = "justine"

    events = migrate_directory(args.input, run=run, auditor=auditor, project=args.project)
    for event in events:
        print(json.dumps(event))


if __name__ == "__main__":
    main()

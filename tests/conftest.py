"""Shared fixtures for holtz tests."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "holtz" / "scripts"))
# Add token_profiler package parent so `import token_profiler` works everywhere
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
# Add tests directory itself so test helper modules (runner_fixtures) can be imported
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def make_item():
    """Build a punchlist item markdown block with overridable fields.

    Returns a callable that accepts keyword overrides for any field.
    Unspecified fields use sensible defaults that pass validation.

    Usage::

        content = make_item()                         # valid item, all defaults
        content = make_item(severity="CRITICAL")      # override severity
        content = make_item(problem="")               # empty problem section
        content = make_item(extra_sections="**Lens:** integration\\n")
    """

    def _make_item(
        *,
        item_id: str = "BH-001",
        title: str = "Test item",
        severity: str = "HIGH",
        category: str = "bug/logic",
        location: str = "`file.py:1`",
        status: str = "OPEN",
        extra_fields: str = "",
        problem: str = "This is a real problem that describes what went wrong in enough detail.",
        evidence: str = "Here is the evidence showing the problem with code references.",
        discovery_chain: str = "observed X → leads to Y → causes Z",
        acceptance_criteria: str = "- [ ] Fix the bug",
        validation_command: str = "echo test",
        resolution: str = "",
        wrap: bool = False,
    ) -> str:
        lines = [f"### {item_id}: {title}"]
        lines.append(f"**Severity:** {severity}")
        lines.append(f"**Category:** {category}")
        lines.append(f"**Location:** {location}")
        lines.append(f"**Status:** {status}")
        if extra_fields:
            lines.append(extra_fields)
        lines.append("")
        if problem is not None:
            lines.append(f"**Problem:** {problem}")
            lines.append("")
        if evidence is not None:
            lines.append(f"**Evidence:** {evidence}")
            lines.append("")
        if discovery_chain:
            lines.append(f"**Discovery Chain:** {discovery_chain}")
            lines.append("")
        lines.append("**Acceptance Criteria:**")
        lines.append(acceptance_criteria)
        lines.append("")
        lines.append("**Validation Command:**")
        lines.append("```bash")
        lines.append(validation_command)
        lines.append("```")
        if resolution:
            lines.append("")
            lines.append(f"**Resolution:** {resolution}")
        lines.append("")

        body = "\n".join(lines)

        if wrap:
            return (
                "# Holtz Punchlist\n"
                "> Generated: 2026-03-22 | Project: test | Baseline: 10 pass, 0 fail, 0 skip\n"
                "\n## Summary\n"
                "| Severity | Open | Resolved | Deferred |\n"
                "|----------|------|----------|----------|\n"
                "\n## Patterns\n"
                "\n## Items\n\n"
                + body
            )

        return body

    return _make_item


from mock_enforcement_daemon import MockEnforcementDaemon


@pytest.fixture
def mock_daemon(tmp_path):
    """Start a mock enforcement daemon with socket at the standard path.

    The daemon listens at tmp_path/docs/holtz/.sahjhan/daemon.sock,
    matching _get_daemon_socket_path(cwd=str(tmp_path)).
    """
    socket_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    socket_dir.mkdir(parents=True, exist_ok=True)
    socket_path = socket_dir / "daemon.sock"
    daemon = MockEnforcementDaemon(socket_path)
    daemon.start()
    yield daemon
    daemon.stop()

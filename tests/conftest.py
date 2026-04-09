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


import os
import shutil
import tempfile

from mock_enforcement_daemon import MockEnforcementDaemon


@pytest.fixture
def mock_daemon(tmp_path, monkeypatch):
    """Start a mock enforcement daemon reachable via _get_daemon_socket_path(tmp_path).

    macOS limits AF_UNIX paths to 104 chars, and pytest tmp_path can exceed
    that. We create the socket in a short /tmp dir and monkeypatch
    _get_daemon_socket_path to return the short path when cwd matches tmp_path.
    """
    # Create the .sahjhan dir in tmp_path (code checks for its existence)
    sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    sahjhan_dir.mkdir(parents=True, exist_ok=True)

    # Short socket path to stay within kernel limit
    short_dir = tempfile.mkdtemp(prefix="hd_")
    socket_path = os.path.join(short_dir, "d.sock")

    daemon = MockEnforcementDaemon(socket_path)
    daemon.start()

    # Patch _get_daemon_socket_path so code under test finds our short socket.
    # Eagerly load _common if not already imported (tests that use mock_daemon
    # before importing _protocol_cache would otherwise silently skip the patch).
    import importlib.util as _ilu
    import sys as _sys

    if "_common" not in _sys.modules:
        _enforcement_hooks = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "enforcement", "hooks",
        )
        _spec = _ilu.spec_from_file_location(
            "_common", os.path.join(_enforcement_hooks, "_common.py"),
        )
        if _spec and _spec.loader:
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _sys.modules["_common"] = _mod

    _common_mod = _sys.modules.get("_common")
    if _common_mod and hasattr(_common_mod, "_get_daemon_socket_path"):
        _original = _common_mod._get_daemon_socket_path

        def _patched(cwd=None):
            if cwd is not None and os.path.realpath(cwd) == os.path.realpath(str(tmp_path)):
                return socket_path
            return _original(cwd)

        monkeypatch.setattr(_common_mod, "_get_daemon_socket_path", _patched)

    yield daemon
    daemon.stop()
    shutil.rmtree(short_dir, ignore_errors=True)

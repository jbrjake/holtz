"""Shared fixtures for holtz tests."""

import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "network: tests that require network access")

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


import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
import time

from mock_enforcement_daemon import MockEnforcementDaemon


@pytest.fixture
def mock_daemon(tmp_path, monkeypatch):
    """Start a mock enforcement daemon reachable via _get_daemon_socket_path.

    macOS limits AF_UNIX paths to 104 chars, and pytest tmp_path can exceed
    that. We create the socket in a short /tmp dir and set SAHJHAN_DAEMON_SOCKET
    so both in-process and subprocess code finds the daemon.
    """
    # Create the .sahjhan dir in tmp_path (code checks for its existence)
    sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    sahjhan_dir.mkdir(parents=True, exist_ok=True)

    # Short socket path to stay within kernel limit
    short_dir = tempfile.mkdtemp(prefix="hd_")
    socket_path = os.path.join(short_dir, "d.sock")

    daemon = MockEnforcementDaemon(socket_path)
    daemon.start()

    # Set env var so _get_daemon_socket_path returns our short path.
    # This works for both in-process imports and subprocess-based hook tests.
    monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", socket_path)

    yield daemon
    daemon.stop()
    shutil.rmtree(short_dir, ignore_errors=True)


@pytest.fixture
def real_daemon(monkeypatch):
    """Start a real sahjhan daemon for integration tests.

    Requires the sahjhan binary (downloaded via ensure_sahjhan).
    Skips if the binary is unavailable.

    Uses a short /tmp path as the project root to stay under macOS's
    104-char AF_UNIX socket limit.  Runs ``sahjhan init`` and
    ``sahjhan daemon start`` with ``--config-dir`` pointing to this
    repo's enforcement/ directory.

    Yields a dict with keys: binary, config_dir, project_root,
    sahjhan_dir, sock_path, pid.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))
    from _resolve import ensure_sahjhan

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")

    config_dir = str(Path(__file__).parent.parent / "enforcement")

    # Short /tmp path keeps socket under macOS 104-char AF_UNIX limit
    project_root = tempfile.mkdtemp(prefix="sh-test-")
    sahjhan_dir = os.path.join(project_root, "docs", "holtz", ".sahjhan")
    sock_path = os.path.join(sahjhan_dir, "daemon.sock")

    # Initialize
    subprocess.run(
        [binary, "--config-dir", config_dir, "init"],
        cwd=project_root, check=True, capture_output=True, text=True,
    )

    # Start daemon (foreground-only — must be backgrounded)
    daemon_proc = subprocess.Popen(
        [binary, "--config-dir", config_dir, "daemon", "start",
         "--idle-timeout", "30"],
        cwd=project_root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Wait for socket to appear
    for _ in range(50):
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)
    else:
        daemon_proc.kill()
        shutil.rmtree(project_root, ignore_errors=True)
        pytest.fail("sahjhan daemon did not create socket within 5s")

    # Copy daemon.pid → daemon-init-pid (lifecycle hooks need this)
    pid_file = os.path.join(sahjhan_dir, "daemon.pid")
    init_pid_file = os.path.join(sahjhan_dir, "daemon-init-pid")
    shutil.copy2(pid_file, init_pid_file)

    monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", sock_path)

    yield {
        "binary": binary,
        "config_dir": config_dir,
        "project_root": project_root,
        "sahjhan_dir": sahjhan_dir,
        "sock_path": sock_path,
        "pid": daemon_proc.pid,
    }

    # Cleanup: stop daemon, remove temp dir
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            cwd=project_root, timeout=5, capture_output=True,
        )
    # Ensure process is dead
    if daemon_proc.poll() is None:
        daemon_proc.send_signal(signal.SIGTERM)
        try:
            daemon_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            daemon_proc.kill()
    shutil.rmtree(project_root, ignore_errors=True)

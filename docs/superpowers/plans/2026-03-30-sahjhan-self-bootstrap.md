# Sahjhan Self-Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-download the Sahjhan binary from GitHub Releases when it's missing, so marketplace plugin installs work without manual vendoring.

**Architecture:** `ensure_sahjhan()` in `_resolve.py` wraps `sahjhan_binary()` with download-if-missing logic. Downloads to a temp file, verifies SHA-256, atomically renames into place. Failed attempts are marked to avoid repeated network hits. All hooks switch from `sahjhan_binary()` + `os.path.isfile()` to `ensure_sahjhan()` which returns `str | None`.

**Tech Stack:** Python stdlib only (`urllib.request`, `hashlib`, `tempfile`)

---

### Task 1: Add bootstrap logic to `_resolve.py`

**Files:**
- Modify: `enforcement/hooks/_resolve.py`
- Create: `tests/test_ensure_sahjhan.py`

- [ ] **Step 1: Write failing tests for `ensure_sahjhan()`**

Create `tests/test_ensure_sahjhan.py`:

```python
"""Tests for sahjhan binary self-bootstrap mechanism."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import time
from unittest import mock

import pytest

# Import under test — patch sys.path so enforcement/hooks/ is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'enforcement', 'hooks'))

import _resolve


class TestEnsureSahjhan:
    """Tests for ensure_sahjhan() auto-download."""

    def test_returns_path_when_binary_exists(self, tmp_path):
        """If binary already exists and version matches, return path immediately."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"fake-binary")
        version_file = tmp_path / "bin" / ".sahjhan-version"
        version_file.write_text(_resolve.SAHJHAN_VERSION + "\n")

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)):
            result = _resolve.ensure_sahjhan()
        assert result == str(binary)

    def test_returns_none_when_download_fails(self, tmp_path):
        """If binary missing and download fails, return None."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch('_resolve.urlopen', side_effect=OSError("no network")):
            result = _resolve.ensure_sahjhan()
        assert result is None

    def test_downloads_when_binary_missing(self, tmp_path):
        """If binary missing, download from GitHub Releases."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        fake_content = b"ELF-fake-binary-content"
        expected_hash = hashlib.sha256(fake_content).hexdigest()

        mock_checksums = {triple: expected_hash}
        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = [fake_content, b""]
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', mock_checksums), \
             mock.patch('_resolve.urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        assert binary.exists()
        assert binary.read_bytes() == fake_content
        assert os.stat(str(binary)).st_mode & stat.S_IXUSR
        version_file = tmp_path / "bin" / ".sahjhan-version"
        assert version_file.read_text().strip() == _resolve.SAHJHAN_VERSION

    def test_rejects_checksum_mismatch(self, tmp_path):
        """If downloaded content doesn't match checksum, reject it."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)

        mock_checksums = {triple: "0" * 64}
        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = [b"tampered-content", b""]
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', mock_checksums), \
             mock.patch('_resolve.urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result is None
        assert not binary.exists()

    def test_skips_retry_after_recent_failure(self, tmp_path):
        """Don't retry download within 1 hour of a failure."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)
        marker = tmp_path / "bin" / ".sahjhan-bootstrap-failed"
        marker.write_text(str(time.time()))

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch('_resolve.urlopen') as mock_urlopen:
            result = _resolve.ensure_sahjhan()

        assert result is None
        mock_urlopen.assert_not_called()

    def test_retries_after_stale_failure_marker(self, tmp_path):
        """Retry download if failure marker is older than 1 hour."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        marker = tmp_path / "bin" / ".sahjhan-bootstrap-failed"
        marker.write_text(str(time.time() - 7200))  # 2 hours ago

        fake_content = b"ELF-binary"
        expected_hash = hashlib.sha256(fake_content).hexdigest()
        mock_checksums = {triple: expected_hash}
        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = [fake_content, b""]
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', mock_checksums), \
             mock.patch('_resolve.urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)

    def test_redownloads_on_version_mismatch(self, tmp_path):
        """If binary exists but version file doesn't match, re-download."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"old-binary")
        version_file = tmp_path / "bin" / ".sahjhan-version"
        version_file.write_text("0.4.0\n")

        new_content = b"new-binary-content"
        expected_hash = hashlib.sha256(new_content).hexdigest()
        mock_checksums = {triple: expected_hash}
        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = [new_content, b""]
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', mock_checksums), \
             mock.patch('_resolve.urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        assert binary.read_bytes() == new_content

    def test_no_redownload_when_no_version_file(self, tmp_path):
        """If binary exists but no version file (manual vendor), assume OK."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"manually-vendored")

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch('_resolve.urlopen') as mock_urlopen:
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        mock_urlopen.assert_not_called()

    def test_atomic_rename_no_partial_binary(self, tmp_path):
        """Download writes to temp file first, not directly to target."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)

        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = OSError("connection reset")
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', {triple: "a" * 64}), \
             mock.patch('_resolve.urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result is None
        assert not binary.exists()
        # No temp files left behind
        assert not list(binary.parent.glob(".sahjhan-download-*"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ensure_sahjhan.py -v`
Expected: FAIL — `_resolve` has no `SAHJHAN_VERSION`, `SAHJHAN_CHECKSUMS`, or `ensure_sahjhan` attributes.

- [ ] **Step 3: Implement bootstrap logic in `_resolve.py`**

Replace the full contents of `enforcement/hooks/_resolve.py` with:

```python
"""Resolve and bootstrap the Sahjhan binary for the current platform."""
from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import tempfile
import time
from urllib.request import urlopen

# ── Pinned version and integrity checksums ──

SAHJHAN_VERSION = "0.5.0"
_RELEASE_BASE = "https://github.com/jbrjake/sahjhan/releases/download"
_BOOTSTRAP_COOLDOWN = 3600  # seconds before retrying after failure

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "7c2f060e079a17d311eafbd2af932fc09be37e5edda621bf8f1734581f3977b7",
    "x86_64-apple-darwin": "69bcefd613374df0981f189babf0ba100b5ca022b7fc6846154b2f209682f1f7",
    "x86_64-unknown-linux-gnu": "1af49a0cd9f7e591d150469b4f10ad45099dc08e2e921edcc2733c6025721a7f",
    "aarch64-unknown-linux-gnu": "e37455906914873dbc49ff674b5b3092b214a30214779cbe0fd24abb00e5d813",
}

# ── Platform resolution ──


def platform_triple() -> str:
    """Return the Rust target triple for the current platform."""
    arch = platform.machine()
    system = platform.system().lower()
    if arch == "arm64":
        arch = "aarch64"
    return {
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }.get(system, f"{arch}-{system}")


def sahjhan_binary() -> str:
    """Return the absolute path to the Sahjhan binary for this platform.

    Uses CLAUDE_PLUGIN_ROOT if set, otherwise resolves relative to this
    file's location (enforcement/hooks/ -> repo root).
    """
    triple = platform_triple()
    root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    return os.path.join(root, "bin", f"sahjhan-{triple}")


# ── Self-bootstrap ──


def ensure_sahjhan() -> str | None:
    """Return path to the Sahjhan binary, downloading if needed.

    Returns the binary path if available (already present or successfully
    downloaded). Returns None if the binary cannot be obtained.

    Download is skipped if a recent failure marker exists (< 1 hour old).
    """
    path = sahjhan_binary()
    if os.path.isfile(path) and not _version_stale(path):
        return path
    return _bootstrap(path)


def _version_stale(binary_path: str) -> bool:
    """Check if the installed binary's version doesn't match SAHJHAN_VERSION.

    Returns False (not stale) if:
    - No version file exists (manual vendor — trust it)
    - Version file matches SAHJHAN_VERSION
    Returns True if version file exists but doesn't match.
    """
    version_file = os.path.join(os.path.dirname(binary_path), ".sahjhan-version")
    try:
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip() != SAHJHAN_VERSION
    except OSError:
        return False


def _bootstrap(dest: str) -> str | None:
    """Download the Sahjhan binary, verify checksum, install atomically.

    Returns dest path on success, None on failure.
    """
    bin_dir = os.path.dirname(dest)
    if _recently_failed(bin_dir):
        return None

    triple = platform_triple()
    expected_hash = SAHJHAN_CHECKSUMS.get(triple)
    if not expected_hash:
        return None  # unsupported platform

    url = f"{_RELEASE_BASE}/v{SAHJHAN_VERSION}/sahjhan-{triple}"

    try:
        os.makedirs(bin_dir, exist_ok=True)
    except OSError:
        return None

    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=bin_dir, prefix=".sahjhan-download-")
        sha = hashlib.sha256()
        with urlopen(url, timeout=30) as resp:  # noqa: S310
            with os.fdopen(fd, "wb") as f:
                fd = None  # os.fdopen takes ownership
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)

        if sha.hexdigest() != expected_hash:
            os.unlink(tmp_path)
            _mark_failed(bin_dir)
            return None

        os.chmod(tmp_path, 0o755)
        os.rename(tmp_path, dest)
        tmp_path = None  # rename succeeded, don't clean up

        # Write version marker
        version_file = os.path.join(bin_dir, ".sahjhan-version")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(SAHJHAN_VERSION + "\n")

        # Clear any failure marker
        _clear_failed(bin_dir)
        return dest
    except Exception:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
        _mark_failed(bin_dir)
        return None


def _recently_failed(bin_dir: str) -> bool:
    """Check if a bootstrap attempt failed within the cooldown period."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    try:
        age = time.time() - os.path.getmtime(marker)
        return age < _BOOTSTRAP_COOLDOWN
    except OSError:
        return False


def _mark_failed(bin_dir: str) -> None:
    """Write a failure marker to prevent immediate retry."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    with contextlib.suppress(OSError):
        with open(marker, "w", encoding="utf-8") as f:
            f.write(str(time.time()) + "\n")


def _clear_failed(bin_dir: str) -> None:
    """Remove the failure marker after a successful download."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    with contextlib.suppress(OSError):
        os.unlink(marker)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ensure_sahjhan.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Run full lint + type check**

Run: `ruff check enforcement/hooks/_resolve.py && mypy --explicit-package-bases enforcement/hooks/_resolve.py`
Expected: Clean.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_resolve.py tests/test_ensure_sahjhan.py
git commit -m "feat(enforcement): add sahjhan binary self-bootstrap with checksum verification"
```

---

### Task 2: Update `_sahjhan_bootstrap.py` to use `ensure_sahjhan()`

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py:43-75`

The `_load_read_guards()` function constructs the binary path manually and calls it at module level. Switch to `ensure_sahjhan()` so the first tool use of any session triggers bootstrap.

- [ ] **Step 1: Write failing test**

Add to `tests/test_ensure_sahjhan.py`:

```python
class TestBootstrapHookIntegration:
    """Verify _sahjhan_bootstrap uses ensure_sahjhan for binary resolution."""

    def test_load_read_guards_uses_ensure(self):
        """_load_read_guards should call ensure_sahjhan, not construct path manually."""
        import importlib
        import _sahjhan_bootstrap
        source = importlib.util.find_spec("_sahjhan_bootstrap")
        assert source is not None and source.origin is not None
        with open(source.origin, encoding="utf-8") as f:
            code = f.read()
        # Must NOT construct path manually anymore
        assert 'os.path.join(_PLUGIN_ROOT, "bin", "sahjhan-"' not in code
        # Must import and use ensure_sahjhan
        assert "ensure_sahjhan" in code
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ensure_sahjhan.py::TestBootstrapHookIntegration -v`
Expected: FAIL — `_sahjhan_bootstrap.py` still constructs path manually.

- [ ] **Step 3: Update `_load_read_guards()` in `_sahjhan_bootstrap.py`**

Replace the `_load_read_guards` function and the `_platform_triple` function and the module-level call (lines 43-75):

Old code (lines 43-75):
```python
def _load_read_guards() -> list[str]:
    """Load read-guarded paths from sahjhan guards command.

    Falls back to hardcoded defaults if the binary is unavailable.
    """
    import subprocess
    try:
        binary = os.path.join(_PLUGIN_ROOT, "bin", "sahjhan-" + _platform_triple())
        if os.path.isfile(binary):
            result = subprocess.run(
                [binary, "--config-dir", os.path.join(_PLUGIN_ROOT, "enforcement"), "guards"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                guards = data.get("read_blocked", [])
                if guards:
                    return guards
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass
    return [".sahjhan/session.key", "enforcement/quiz-bank.json"]


def _platform_triple() -> str:
    """Return the platform triple for the current system.

    Delegates to _resolve.platform_triple() for single source of truth.
    """
    from _resolve import platform_triple
    return platform_triple()


READ_GUARDED = _load_read_guards()
```

New code:
```python
def _load_read_guards() -> list[str]:
    """Load read-guarded paths from sahjhan guards command.

    Falls back to hardcoded defaults if the binary is unavailable.
    Triggers self-bootstrap if binary is missing.
    """
    import subprocess
    try:
        from _resolve import ensure_sahjhan
        binary = ensure_sahjhan()
        if binary is not None:
            result = subprocess.run(
                [binary, "--config-dir", os.path.join(_PLUGIN_ROOT, "enforcement"), "guards"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                guards = data.get("read_blocked", [])
                if guards:
                    return guards
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ImportError):
        pass
    return [".sahjhan/session.key", "enforcement/quiz-bank.json"]


READ_GUARDED = _load_read_guards()
```

This removes the `_platform_triple()` wrapper function entirely — it's no longer needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ensure_sahjhan.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run the full bootstrap hook integration test suite**

Run: `python -m pytest tests/test_sahjhan_integration.py tests/test_bootstrap_read_guard.py -v`
Expected: All existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py tests/test_ensure_sahjhan.py
git commit -m "fix(enforcement): use ensure_sahjhan in bootstrap hook for auto-download"
```

---

### Task 3: Update enforcement hooks to use `ensure_sahjhan()`

**Files:**
- Modify: `enforcement/hooks/primer.py:23,30-32`
- Modify: `enforcement/hooks/protocol_tracker.py:24,68-70`
- Modify: `enforcement/hooks/bash_guard.py:18,38-39`
- Modify: `enforcement/hooks/stop_gate.py:17,25-27`
- Modify: `enforcement/hooks/lens_quiz.py:23,362-367`
- Modify: `enforcement/hooks/_common.py:48-50,113,117`

Each hook follows the same pattern. Change the import and the call site.

- [ ] **Step 1: Update `primer.py`**

Change import (line 23):
```python
# Old:
from _resolve import sahjhan_binary  # noqa: E402
# New:
from _resolve import ensure_sahjhan  # noqa: E402
```

Change call site (lines 30-32):
```python
# Old:
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        exit_ok()
# New:
    binary = ensure_sahjhan()
    if binary is None:
        exit_ok()
```

- [ ] **Step 2: Update `protocol_tracker.py`**

Change import (line 24):
```python
# Old:
from _resolve import sahjhan_binary  # noqa: E402
# New:
from _resolve import ensure_sahjhan  # noqa: E402
```

Change call site in `_refresh_from_sahjhan` (lines 68-70):
```python
# Old:
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        return cache
# New:
    binary = ensure_sahjhan()
    if binary is None:
        return cache
```

- [ ] **Step 3: Update `bash_guard.py`**

Change import (line 18):
```python
# Old:
from _resolve import sahjhan_binary  # noqa: E402
# New:
from _resolve import ensure_sahjhan  # noqa: E402
```

Change call site (lines 38-39):
```python
# Old:
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
# New:
    binary = ensure_sahjhan()
    if binary is None:
```

- [ ] **Step 4: Update `stop_gate.py`**

Change import (line 17):
```python
# Old:
from _resolve import sahjhan_binary  # noqa: E402
# New:
from _resolve import ensure_sahjhan  # noqa: E402
```

Change call site (lines 25-27):
```python
# Old:
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        exit_stop_allow()
# New:
    binary = ensure_sahjhan()
    if binary is None:
        exit_stop_allow()
```

- [ ] **Step 5: Update `lens_quiz.py`**

Change import (line 23):
```python
# Old:
from _resolve import sahjhan_binary  # noqa: E402
# New:
from _resolve import ensure_sahjhan  # noqa: E402
```

Change call site (lines 362-367):
```python
# Old:
    binary = sahjhan_binary()
    config_dir = os.path.join(cwd, "enforcement")
    quiz_bank_path = os.path.join(cwd, "enforcement", "quiz-bank.json")

    # Graceful degradation: no binary → allow
    if not os.path.isfile(binary):
        exit_stop_allow()
# New:
    binary = ensure_sahjhan()
    config_dir = os.path.join(cwd, "enforcement")
    quiz_bank_path = os.path.join(cwd, "enforcement", "quiz-bank.json")

    # Graceful degradation: no binary → allow
    if binary is None:
        exit_stop_allow()
```

- [ ] **Step 6: Update `_common.py`**

Change `_get_session_key_path` (lines 48-50):
```python
# Old:
        from _resolve import sahjhan_binary
        binary = sahjhan_binary()
        if os.path.isfile(binary):
# New:
        from _resolve import ensure_sahjhan
        binary = ensure_sahjhan()
        if binary is not None:
```

Change `record_authed_event` (lines 113, 117):
```python
# Old (line 113):
    from _resolve import sahjhan_binary
# New:
    from _resolve import ensure_sahjhan

# Old (line 117):
    binary = sahjhan_binary()
# New:
    binary = ensure_sahjhan()
    if binary is None:
        raise OSError("Sahjhan binary unavailable")
```

Note: `record_authed_event` is only called during active audit sessions where the binary is required. Raising `OSError` here is caught by the callers' existing `except (OSError, ...)` handlers.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 8: Run lint + type check**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: Clean.

- [ ] **Step 9: Commit**

```bash
git add enforcement/hooks/primer.py enforcement/hooks/protocol_tracker.py enforcement/hooks/bash_guard.py enforcement/hooks/stop_gate.py enforcement/hooks/lens_quiz.py enforcement/hooks/_common.py
git commit -m "fix(enforcement): switch all hooks from sahjhan_binary to ensure_sahjhan"
```

---

### Task 4: Update `.gitignore` for bootstrap artifacts

**Files:**
- Modify: `.gitignore`

The bootstrap creates `bin/.sahjhan-bootstrap-failed` and `bin/.sahjhan-version` (already created by vendor script). These should be gitignored.

- [ ] **Step 1: Add bootstrap artifacts to `.gitignore`**

Add after the existing `bin/sahjhan-*` line:

```
bin/.sahjhan-bootstrap-failed
bin/.sahjhan-version
```

- [ ] **Step 2: Verify nothing is tracked**

Run: `git status`
Expected: Only the `.gitignore` change shows (the `bin/.sahjhan-version` file should already be untracked since `bin/` contents other than the gitignore entries aren't committed).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore sahjhan bootstrap artifacts"
```

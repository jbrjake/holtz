"""Tests for sahjhan binary self-bootstrap mechanism."""
from __future__ import annotations

import contextlib
import hashlib
import os
import stat
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

# Import under test — patch sys.path so enforcement/hooks/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'enforcement', 'hooks'))

import _resolve  # noqa: E402


def _vendored(tmp_path: Path, content: bytes) -> tuple[Path, Path]:
    """A binary and a version marker naming the pinned version, as a vendor run leaves them."""
    binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(content)
    marker = tmp_path / "bin" / ".sahjhan-version"
    marker.write_text(_resolve.SAHJHAN_VERSION + "\n")
    return binary, marker


def _response(content: bytes) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.read.side_effect = [content, b""]
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


@contextlib.contextmanager
def _pinned(binary: Path, published: bytes) -> Iterator[mock.MagicMock]:
    """Pin `published` as this platform's release; yields the download mock."""
    triple = _resolve.platform_triple()
    with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
         mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS',
                           {triple: hashlib.sha256(published).hexdigest()}), \
         mock.patch.object(_resolve, 'urlopen',
                           side_effect=lambda *a, **k: _response(published)) as mock_urlopen:
        yield mock_urlopen


@contextlib.contextmanager
def _counting_hashes() -> Iterator[list[str]]:
    """Record every file `_resolve` hashes from disk (a download is hashed in flight)."""
    hashed: list[str] = []

    def digest(path: str) -> str:
        hashed.append(path)
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    with mock.patch.object(_resolve, '_file_sha256', side_effect=digest, create=True):
        yield hashed


class TestEnsureSahjhan:
    """Tests for ensure_sahjhan() auto-download."""

    def test_returns_path_when_binary_exists(self, tmp_path):
        """If binary already exists, version matches and so do its bytes, return path."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"fake-binary")
        version_file = tmp_path / "bin" / ".sahjhan-version"
        version_file.write_text(_resolve.SAHJHAN_VERSION + "\n")

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS',
                               {triple: hashlib.sha256(b"fake-binary").hexdigest()}), \
             mock.patch.object(_resolve, 'urlopen') as mock_urlopen:
            result = _resolve.ensure_sahjhan()
        assert result == str(binary)
        mock_urlopen.assert_not_called()

    def test_returns_none_when_download_fails(self, tmp_path):
        """If binary missing and download fails, return None."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'urlopen', side_effect=OSError("no network")):
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
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
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
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
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
             mock.patch.object(_resolve, 'urlopen') as mock_urlopen:
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
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
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
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        assert binary.read_bytes() == new_content

    def test_no_redownload_when_no_version_file(self, tmp_path):
        """If binary exists but no version file (manual vendor), assume OK."""
        binary = tmp_path / "bin" / f"sahjhan-{_resolve.platform_triple()}"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"manually-vendored")

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'urlopen') as mock_urlopen:
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        mock_urlopen.assert_not_called()

    def test_bootstrap_creates_sahjhan_symlink(self, tmp_path):
        """Successful bootstrap creates a `sahjhan` symlink → platform binary.

        Claude Code prepends $CLAUDE_PLUGIN_ROOT/bin/ to PATH. The SKILL.md
        tells the model to invoke bare `sahjhan …`, so the symlink is what
        makes that actually resolve after a fresh hook-driven download.
        """
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        fake_content = b"ELF-bin"
        expected_hash = hashlib.sha256(fake_content).hexdigest()

        mock_checksums = {triple: expected_hash}
        mock_resp = mock.MagicMock()
        mock_resp.read.side_effect = [fake_content, b""]
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(_resolve, 'sahjhan_binary', return_value=str(binary)), \
             mock.patch.object(_resolve, 'SAHJHAN_CHECKSUMS', mock_checksums), \
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result == str(binary)
        link = tmp_path / "bin" / "sahjhan"
        assert link.is_symlink()
        assert os.readlink(str(link)) == f"sahjhan-{triple}"

    def test_a_matching_marker_over_the_wrong_bytes_is_not_trusted(self, tmp_path):
        """W27 / item 46: the marker names a version; only the hash says the bytes are it."""
        triple = _resolve.platform_triple()
        binary, _ = _vendored(tmp_path, b"left-by-a-failed-vendor-run")
        good = b"the-published-release"
        with _pinned(binary, good) as mock_urlopen:
            result = _resolve.ensure_sahjhan()
        assert result == str(binary)
        assert binary.read_bytes() == good, "the unverified bytes were returned as the pin"
        mock_urlopen.assert_called_once()
        assert f"v{_resolve.SAHJHAN_VERSION}/sahjhan-{triple}" in mock_urlopen.call_args[0][0]

    def test_a_verified_binary_is_stat_checked_not_rehashed(self, tmp_path):
        """D-s: hash once, then only when the marker or the binary moves."""
        binary, _ = _vendored(tmp_path, b"published")
        with _pinned(binary, b"published") as mock_urlopen, _counting_hashes() as hashed:
            assert _resolve.ensure_sahjhan() == str(binary)
            assert _resolve.ensure_sahjhan() == str(binary)
            assert _resolve.ensure_sahjhan() == str(binary)
        assert hashed == [str(binary)]
        mock_urlopen.assert_not_called()

    def test_the_binary_moving_forces_a_rehash(self, tmp_path):
        binary, _ = _vendored(tmp_path, b"published")
        with _pinned(binary, b"published") as mock_urlopen:
            assert _resolve.ensure_sahjhan() == str(binary)
            binary.write_bytes(b"swapped-in")  # another size and mtime
            assert _resolve.ensure_sahjhan() == str(binary)
        assert binary.read_bytes() == b"published"
        mock_urlopen.assert_called_once()

    def test_the_binary_moving_at_the_same_size_forces_a_rehash(self, tmp_path):
        binary, _ = _vendored(tmp_path, b"published")
        with _pinned(binary, b"published") as mock_urlopen:
            assert _resolve.ensure_sahjhan() == str(binary)
            binary.write_bytes(b"PUBLISHED")
            st = binary.stat()
            os.utime(binary, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
            assert _resolve.ensure_sahjhan() == str(binary)
        assert binary.read_bytes() == b"published"
        mock_urlopen.assert_called_once()

    def test_the_marker_moving_forces_a_rehash(self, tmp_path):
        binary, marker = _vendored(tmp_path, b"published")
        with _pinned(binary, b"published") as mock_urlopen, _counting_hashes() as hashed:
            assert _resolve.ensure_sahjhan() == str(binary)
            st = marker.stat()
            os.utime(marker, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
            assert _resolve.ensure_sahjhan() == str(binary)
        assert hashed == [str(binary), str(binary)]
        mock_urlopen.assert_not_called()

    def test_a_download_leaves_nothing_to_rehash(self, tmp_path):
        """The bytes were hashed on the way in; the next call only stats them."""
        triple = _resolve.platform_triple()
        binary = tmp_path / "bin" / f"sahjhan-{triple}"
        binary.parent.mkdir(parents=True)
        with _pinned(binary, b"published") as mock_urlopen, _counting_hashes() as hashed:
            assert _resolve.ensure_sahjhan() == str(binary)
            assert _resolve.ensure_sahjhan() == str(binary)
        assert hashed == []
        mock_urlopen.assert_called_once()

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
             mock.patch.object(_resolve, 'urlopen', return_value=mock_resp):
            result = _resolve.ensure_sahjhan()

        assert result is None
        assert not binary.exists()
        # No temp files left behind
        assert not list(binary.parent.glob(".sahjhan-download-*"))

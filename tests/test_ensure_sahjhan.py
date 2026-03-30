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

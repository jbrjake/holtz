"""Regression guard for the sahjhan-pin drift footgun (v0.135.0).

The pinned sahjhan version drifted because it existed in two committed places:
`_resolve.SAHJHAN_VERSION` and the `bin/.sahjhan-version` marker. The marker
went stale while the resolver was bumped, and the mismatch shipped.

These tests lock the fix: the marker is untracked (single source of truth),
the current tree is self-consistent, and drift/re-tracking is detected.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKER_REL = "bin/.sahjhan-version"


def _load_check() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_sahjhan_pin.py"
    spec = importlib.util.spec_from_file_location("check_sahjhan_pin", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_sahjhan_pin"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_marker_is_not_git_tracked():
    """bin/.sahjhan-version must stay untracked — it is runtime state.

    If it becomes tracked again, a committed copy can drift from the pin in
    _resolve.py (exactly what happened on v0.135.0).
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", MARKER_REL],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert result.returncode != 0, (
        f"{MARKER_REL} is git-tracked again. It is runtime state and must be "
        f"untracked so it can never drift from _resolve.SAHJHAN_VERSION. "
        f"Fix: git rm --cached {MARKER_REL}"
    )


def test_current_tree_is_pin_consistent():
    """The real working tree passes the pin-consistency check."""
    check = _load_check()
    assert check.check() == [], (
        "sahjhan pin is inconsistent in the working tree: " + str(check.check())
    )


def test_drifted_marker_is_detected(tmp_path, monkeypatch):
    """A marker whose value != the pin is flagged."""
    check = _load_check()
    bad = tmp_path / ".sahjhan-version"
    bad.write_text("0.0.1\n")
    monkeypatch.setattr(check, "MARKER", bad)
    monkeypatch.setattr(check._resolve, "SAHJHAN_VERSION", "9.9.9")
    # No vendored binaries under tmp; only the marker-mismatch should fire.
    failures = check.check()
    assert any("0.0.1" in f and "9.9.9" in f for f in failures), failures


def test_retracked_marker_is_detected(monkeypatch):
    """If the real marker were tracked, check() reports it (guards check #1)."""
    check = _load_check()
    monkeypatch.setattr(check, "_is_git_tracked", lambda p: True)
    failures = check.check()
    assert any("git-tracked" in f for f in failures), failures


# ── Vendoring must move the pin that governs ────────────────────────────────
#
# The checks above compare the marker to `SAHJHAN_VERSION`, which sounds like
# it covers version drift — and does not. The marker is runtime state the
# resolver *writes*: when `ensure_sahjhan()` restored an older binary during
# P0.3 it rewrote the marker too, so the tree became self-consistent again at
# the old version and `check()` had nothing to report. A freshly vendored
# 0.23.0 silently reverted to 0.22.0 with every pin in agreement.
#
# The hole was that `vendor-sahjhan.sh` never touched `_resolve.py`. These
# tests hold the two together.


def _load_updater() -> ModuleType:
    path = REPO_ROOT / "scripts" / "update_sahjhan_pin.py"
    spec = importlib.util.spec_from_file_location("update_sahjhan_pin", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["update_sahjhan_pin"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_vendor_script_updates_the_resolver_pin():
    """Vendoring must rewrite `_resolve.py`, not just the marker.

    Asserted against the script's own text rather than by running it: the
    downloads need the network, and what matters is that the step is in the
    taught sequence at all.
    """
    script = (REPO_ROOT / "scripts" / "vendor-sahjhan.sh").read_text(encoding="utf-8")
    assert "update_sahjhan_pin.py" in script, (
        "vendor-sahjhan.sh writes bin/.sahjhan-version but not "
        "_resolve.SAHJHAN_VERSION, which is the pin ensure_sahjhan() actually "
        "reads. Without this step, vendoring is undone by the next hook run."
    )


def test_the_updater_moves_both_the_version_and_the_checksums():
    """A version bump with stale checksums is the half-update that shipped."""
    updater = _load_updater()
    source = (REPO_ROOT / "enforcement" / "hooks" / "_resolve.py").read_text(
        encoding="utf-8"
    )
    sums = {t: f"{i:064x}" for i, t in enumerate(updater.TARGETS, start=1)}

    updated = updater.render(source, "9.9.9", sums)

    assert 'SAHJHAN_VERSION = "9.9.9"' in updated
    assert updated.count("SAHJHAN_VERSION = ") == 1
    for triple, digest in sums.items():
        assert f'"{triple}": "{digest}",' in updated, triple


def _updater_tree(tmp_path: Path, native_reports: str) -> tuple[Path, Path]:
    """A copy of the updater and `_resolve.py` in a scratch repo layout.

    The script finds `_resolve.py` from its own path, so running this copy
    can never rewrite the real pin — which the unmodified updater would do
    here, since it pins whatever bytes it is handed.
    """
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "enforcement" / "hooks").mkdir(parents=True)
    for rel in ("scripts/update_sahjhan_pin.py", "enforcement/hooks/_resolve.py"):
        (root / rel).write_bytes((REPO_ROOT / rel).read_bytes())
    sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))
    from _resolve import platform_triple

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for triple in _load_updater().TARGETS:
        binary = bin_dir / f"sahjhan-{triple}"
        binary.write_text(f"#!/bin/sh\necho 'sahjhan {native_reports}'\n")
        binary.chmod(0o755)
    assert (bin_dir / f"sahjhan-{platform_triple()}").exists()
    return root, bin_dir


def test_the_updater_refuses_a_binary_of_another_version(tmp_path):
    """W27 / item 46 — the bytes being pinned must be the version named.

    The updater hashed whatever sat in `bin_dir`, so a partly-failed vendor
    run left an old binary pinned under the new version's name — trusted by
    `ensure_sahjhan`'s fast path on a marker-string match until the next
    release check. The platform-native binary is asked its version; the other
    three cannot run here and are covered only by their checksums.
    """
    root, bin_dir = _updater_tree(tmp_path, native_reports="0.27.0")
    resolve = root / "enforcement" / "hooks" / "_resolve.py"
    before = resolve.read_bytes()
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "update_sahjhan_pin.py"), "0.28.0", str(bin_dir)],
        capture_output=True, text=True, timeout=60,
    )
    said = result.stdout + result.stderr
    assert result.returncode != 0, said
    assert "0.28.0" in said and "0.27.0" in said, f"both versions must be named: {said}"
    assert resolve.read_bytes() == before, "a refused pin must not have been written"


def test_the_updater_pins_a_binary_that_reports_its_version(tmp_path):
    """The partner: a matching binary is pinned, so the refusal above is a
    check and not a blanket failure."""
    root, bin_dir = _updater_tree(tmp_path, native_reports="0.28.0")
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "update_sahjhan_pin.py"), "0.28.0", str(bin_dir)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'SAHJHAN_VERSION = "0.28.0"' in (
        root / "enforcement" / "hooks" / "_resolve.py"
    ).read_text(encoding="utf-8")


def test_pre_commit_runs_the_pin_check():
    """W27 / item 46 — the check was wired only into the release script, so an
    unverified binary stayed trusted until the next release. Asserted on the
    hook's own text; the commit it fails was observed by hand (the unit)."""
    hook = (REPO_ROOT / "git-hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "check_sahjhan_pin.py" in hook


def test_the_updater_refuses_a_shape_it_does_not_recognise():
    """Fail loudly rather than write a file whose pin it did not move."""
    updater = _load_updater()
    sums = {t: f"{i:064x}" for i, t in enumerate(updater.TARGETS, start=1)}
    with pytest.raises(SystemExit):
        updater.render("# nothing to pin here\n", "9.9.9", sums)

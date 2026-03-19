"""Tests for convergence_check.py."""

import convergence_check as cc


# --- BH-002: False convergence on empty punchlist ---

def test_empty_punchlist_no_convergence():
    """3 runs against empty punchlist should NOT declare convergence."""
    empty_snapshot = {
        "timestamp": "2026-03-19T00:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 0},
        "test_runner": None,
        "tests": None,
    }
    history = [empty_snapshot, empty_snapshot, empty_snapshot]
    converged, message = cc.check_convergence(history)
    assert not converged, (
        f"Should NOT converge on empty punchlist. Got: {message}"
    )


def test_real_convergence_after_work():
    """Convergence should be declared after real work: items appeared, got resolved, stayed resolved."""
    # Iteration 1: items found
    snap1 = {
        "timestamp": "2026-03-19T01:00:00",
        "punchlist": {"OPEN": 5, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 5},
        "tests": {"passed": 10, "failed": 2, "skipped": 0},
    }
    # Iteration 2: items resolved
    snap2 = {
        "timestamp": "2026-03-19T02:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 5, "DEFERRED": 0, "total": 5},
        "tests": {"passed": 12, "failed": 0, "skipped": 0},
    }
    # Iteration 3: still clean
    snap3 = {
        "timestamp": "2026-03-19T03:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 5, "DEFERRED": 0, "total": 5},
        "tests": {"passed": 12, "failed": 0, "skipped": 0},
    }
    history = [snap1, snap2, snap3]
    converged, message = cc.check_convergence(history)
    assert converged, f"Should converge after real work. Got: {message}"


# --- BH-005: Status regex cross-line leak in count_items ---

def test_count_items_single_line_status(tmp_path):
    """Status extraction should not leak across lines."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Item
**Status:** OPEN
Some annotation text
**Problem:** stuff
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, f"Expected 1 OPEN, got {counts}"


# --- BH-006: Silent dropping of unrecognized statuses ---

def test_unrecognized_status_counted(tmp_path):
    """Unrecognized status values should be tracked, not silently dropped."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Item 1
**Status:** OPEN

### BH-002: Item 2
**Status:** OPNE
""")
    counts = cc.count_items(punchlist)
    # Total should account for all items, including ones with unrecognized statuses
    assert counts["total"] >= 2, (
        f"Expected total >= 2 (including unrecognized status), got {counts}"
    )


# --- BH-008: Malformed history file handling ---

def test_malformed_history_json(tmp_path, monkeypatch):
    """Corrupted HISTORY.json should be handled gracefully."""
    history_file = tmp_path / "HISTORY.json"
    history_file.write_text("not valid json{{{")
    monkeypatch.setattr(cc, "HISTORY_FILE", str(history_file))

    # Should not raise, should return empty list
    result = cc.load_history()
    assert result == [], f"Corrupted history should return empty list, got {result}"


def test_history_is_dict_not_list(tmp_path, monkeypatch):
    """HISTORY.json containing a dict instead of list should be handled."""
    history_file = tmp_path / "HISTORY.json"
    history_file.write_text('{"key": "value"}')
    monkeypatch.setattr(cc, "HISTORY_FILE", str(history_file))

    result = cc.load_history()
    assert isinstance(result, list), f"Should return a list, got {type(result)}"


# --- BH-015: Convergence without test data ---

def test_convergence_no_test_data():
    """Convergence message should indicate when test stability was not verified."""
    snap1 = {
        "timestamp": "2026-03-19T01:00:00",
        "punchlist": {"OPEN": 3, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 3},
        "tests": None,
    }
    snap2 = {
        "timestamp": "2026-03-19T02:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 3, "DEFERRED": 0, "total": 3},
        "tests": None,
    }
    snap3 = {
        "timestamp": "2026-03-19T03:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 3, "DEFERRED": 0, "total": 3},
        "tests": None,
    }
    history = [snap1, snap2, snap3]
    converged, message = cc.check_convergence(history)
    # Should converge AND message should mention test verification not possible
    assert converged, f"Should converge when test data absent. Got: {message}"
    assert "test" in message.lower(), (
        f"Convergence message should mention test verification status: {message}"
        )


# --- CS2-002: Unknown status items block convergence ---

def test_unknown_status_blocks_convergence():
    """Items with unrecognized status should count as open and block convergence."""
    # History where items have unknown status
    snap1 = {
        "timestamp": "2026-03-19T01:00:00",
        "punchlist": {"OPEN": 1, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0, "total": 1},
        "tests": None,
    }
    snap2 = {
        "timestamp": "2026-03-19T02:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 1, "total": 1},
        "tests": None,
    }
    snap3 = {
        "timestamp": "2026-03-19T03:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 1, "total": 1},
        "tests": None,
    }
    history = [snap1, snap2, snap3]
    converged, message = cc.check_convergence(history)
    assert not converged, (
        f"Should NOT converge with unknown status items. Got: {message}"
    )


# --- CS2-005: Test stability across data gaps ---

def test_stability_across_test_data_gap():
    """Failures increasing across a None gap should be detected."""
    snap1 = {
        "timestamp": "2026-03-19T01:00:00",
        "punchlist": {"OPEN": 1, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 1},
        "tests": {"passed": 10, "failed": 0, "skipped": 0},
    }
    snap2 = {
        "timestamp": "2026-03-19T02:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 1, "DEFERRED": 0, "total": 1},
        "tests": None,  # test run timed out
    }
    snap3 = {
        "timestamp": "2026-03-19T03:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 1, "DEFERRED": 0, "total": 1},
        "tests": {"passed": 5, "failed": 5, "skipped": 0},
    }
    history = [snap1, snap2, snap3]
    converged, message = cc.check_convergence(history)
    # Should detect the regression from 0 to 5 failures even across the None gap
    assert not converged, (
        f"Should NOT converge when failures increased across a data gap. Got: {message}"
    )


# --- FA-007: History entries missing punchlist key ---

def test_convergence_missing_punchlist_key():
    """History entries missing 'punchlist' key should not crash."""
    history = [
        {"timestamp": "2026-01-01", "tests": None},  # no punchlist key
        {"timestamp": "2026-01-02", "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 1, "DEFERRED": 0, "total": 1}, "tests": None},
        {"timestamp": "2026-01-03", "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 1, "DEFERRED": 0, "total": 1}, "tests": None},
    ]
    # Should not raise KeyError
    converged, message = cc.check_convergence(history)
    assert isinstance(converged, bool)


# --- FA-010: Deletion-based false convergence ---

def test_deletion_does_not_converge():
    """Deleting all items (total drops to 0) should NOT declare convergence."""
    snap1 = {
        "timestamp": "2026-03-19T01:00:00",
        "punchlist": {"OPEN": 5, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 5},
        "tests": None,
    }
    snap2 = {
        "timestamp": "2026-03-19T02:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 0},
        "tests": None,
    }
    snap3 = {
        "timestamp": "2026-03-19T03:00:00",
        "punchlist": {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "total": 0},
        "tests": None,
    }
    history = [snap1, snap2, snap3]
    converged, message = cc.check_convergence(history)
    assert not converged, (
        f"Should NOT converge when items were deleted, not resolved. Got: {message}"
    )


# --- FA-009: Status inside code fence inflates count ---

def test_status_inside_code_fence_not_counted(tmp_path):
    """**Status:** inside a code fence should not inflate the item count."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Real item
**Status:** OPEN

**Evidence:**
```
**Status:** OPEN
**Status:** RESOLVED
```
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, f"Expected 1 OPEN, got {counts}"
    assert counts["RESOLVED"] == 0, f"Expected 0 RESOLVED, got {counts}"
    assert counts["total"] == 1, f"Expected total 1, got {counts}"


# --- BH-007: Unparseable test output returns None ---

def test_get_test_counts_unparseable_output(monkeypatch):
    """Unparseable test output should return None, not zero counts."""
    import subprocess

    class FakeResult:
        stdout = "INTERNAL ERROR: pytest crashed with a traceback\n"
        stderr = "Traceback (most recent call last):\n  ...\nSystemExit: 3\n"
        returncode = 3

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    result = cc.get_test_counts("pytest")
    assert result is None, (
        f"Unparseable pytest output should return None, got {result}"
    )


# --- BH-010: Tests for detect_test_runner ---

def test_detect_pytest_by_conftest(tmp_path, monkeypatch):
    """detect_test_runner should find pytest via conftest.py."""
    (tmp_path / "conftest.py").write_text("# pytest config")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "pytest"


def test_detect_jest_by_config(tmp_path, monkeypatch):
    """detect_test_runner should find jest via jest.config.js."""
    (tmp_path / "jest.config.js").write_text("module.exports = {}")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "jest"


def test_detect_cargo_by_toml(tmp_path, monkeypatch):
    """detect_test_runner should find cargo via Cargo.toml."""
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "cargo"


def test_detect_no_runner(tmp_path, monkeypatch):
    """detect_test_runner should return None when no config files found."""
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() is None


def test_detect_pyproject_without_pytest(tmp_path, monkeypatch):
    """pyproject.toml without pytest config should not trigger pytest detection."""
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\nrequires = ['setuptools']\n"
    )
    monkeypatch.chdir(tmp_path)
    # Should not detect pytest since there's no pytest config in pyproject.toml
    result = cc.detect_test_runner()
    assert result != "pytest", (
        f"pyproject.toml without pytest config should not detect pytest, got '{result}'"
    )


def test_detect_pyproject_with_pytest_in_comment(tmp_path, monkeypatch):
    """pyproject.toml mentioning pytest only in a comment should not trigger detection."""
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = ['setuptools']\n"
        "# we considered pytest but decided against it\n"
    )
    monkeypatch.chdir(tmp_path)
    result = cc.detect_test_runner()
    assert result != "pytest", (
        f"pyproject.toml with 'pytest' only in a comment should not detect pytest, got '{result}'"
    )


# --- BH-009: Multi-item punchlist parsing ---

def test_multi_item_punchlist_field_isolation(tmp_path):
    """Multiple items should have isolated field values."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: First item
**Status:** OPEN

### BH-002: Second item
**Status:** RESOLVED

### BH-003: Third item
**Status:** DEFERRED
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, f"Expected 1 OPEN, got {counts}"
    assert counts["RESOLVED"] == 1, f"Expected 1 RESOLVED, got {counts}"
    assert counts["DEFERRED"] == 1, f"Expected 1 DEFERRED, got {counts}"
    assert counts["total"] == 3, f"Expected total 3, got {counts}"


# --- BH-012: Test output parsing ---

def test_get_test_counts_pytest_output(monkeypatch):
    """Pytest output parsing should extract correct counts."""
    import subprocess

    class FakeResult:
        stdout = "5 passed, 2 failed, 1 skipped in 0.5s\n"
        stderr = ""
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    result = cc.get_test_counts("pytest")
    assert result == {"passed": 5, "failed": 2, "skipped": 1}


def test_get_test_counts_jest_output(monkeypatch):
    """Jest output parsing should extract correct counts."""
    import subprocess

    class FakeResult:
        stdout = "Tests:  2 failed, 8 passed, 10 total\n"
        stderr = ""
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    result = cc.get_test_counts("jest")
    assert result == {"passed": 8, "failed": 2, "skipped": 0}

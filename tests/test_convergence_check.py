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

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
    # Should not raise KeyError. Entry 1 defaults to total=0, entry 2 has
    # total=1 — items "appeared" between entries 1 and 2, so no_new_2_iters
    # is False (total went from 0 to 1). Convergence should be False.
    converged, message = cc.check_convergence(history)
    assert converged is False, (
        f"Should not converge (items appeared between defaulted entry 1 and entry 2). Got: {message}"
    )
    assert "IN PROGRESS" in message, (
        f"Should report in-progress state. Got: {message}"
    )


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


# --- BH-010: Tests for detect_test_runner ---

def test_detect_pytest_by_conftest(tmp_path, monkeypatch):
    """detect_test_runner should find pytest via conftest.py."""
    (tmp_path / "conftest.py").write_text("# pytest config")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "pytest"


def test_detect_pytest_by_pyproject(tmp_path, monkeypatch):
    """detect_test_runner should find pytest via [tool.pytest in pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
    )
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "pytest"


def test_detect_jest_by_config(tmp_path, monkeypatch):
    """detect_test_runner should find jest via jest.config.js."""
    (tmp_path / "jest.config.js").write_text("module.exports = {}")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "jest"


def test_detect_jest_by_ts_config(tmp_path, monkeypatch):
    """detect_test_runner should find jest via jest.config.ts."""
    (tmp_path / "jest.config.ts").write_text("export default {}")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "jest"


def test_detect_vitest_by_config(tmp_path, monkeypatch):
    """detect_test_runner should find vitest via vitest.config.ts."""
    (tmp_path / "vitest.config.ts").write_text("export default {}")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "vitest"


def test_detect_cargo_by_toml(tmp_path, monkeypatch):
    """detect_test_runner should find cargo via Cargo.toml."""
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'crab-rave'")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "cargo"


def test_detect_go_by_mod(tmp_path, monkeypatch):
    """detect_test_runner should find go via go.mod."""
    (tmp_path / "go.mod").write_text("module github.com/spectral/haunted-elevator")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "go"


def test_detect_swift_by_package(tmp_path, monkeypatch):
    """detect_test_runner should find swift via Package.swift."""
    (tmp_path / "Package.swift").write_text(
        '// swift-tools-version: 5.9\nimport PackageDescription\n'
        'let package = Package(name: "AstralPostalService")\n'
    )
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "swift"


def test_detect_mocha_by_config(tmp_path, monkeypatch):
    """detect_test_runner should find mocha via .mocharc.yml."""
    (tmp_path / ".mocharc.yml").write_text("spec: test/**/*.test.js")
    monkeypatch.chdir(tmp_path)
    assert cc.detect_test_runner() == "mocha"


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


# =============================================================================
# Test output parsing — comprehensive fixtures for all 6 runners
# Uses runner_fixtures.py for realistic, whimsical test runner output.
# =============================================================================

import subprocess
import runner_fixtures as fx


def _fake_run(stdout, stderr="", returncode=0):
    """Create a monkeypatch for subprocess.run with the given output."""
    class FakeResult:
        pass
    r = FakeResult()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return lambda *a, **kw: r


# --- Pytest: The Cheese Shop ---

def test_pytest_all_pass(monkeypatch):
    """11 artisanal cheeses, all accounted for."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.PYTEST_ALL_PASS))
    result = cc.get_test_counts("pytest")
    assert result == {"passed": 11, "failed": 0, "skipped": 0}


def test_pytest_mixed(monkeypatch):
    """The brie test crumbled. One skipped (aged too long to test)."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.PYTEST_MIXED))
    result = cc.get_test_counts("pytest")
    assert result == {"passed": 8, "failed": 1, "skipped": 1}


def test_pytest_all_fail(monkeypatch):
    """Nothing but failures. The cheese shop is condemned."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.PYTEST_ALL_FAIL))
    result = cc.get_test_counts("pytest")
    assert result == {"passed": 0, "failed": 4, "skipped": 0}


def test_pytest_crash(monkeypatch):
    """Pytest itself crashed. Unparseable output returns None."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.PYTEST_CRASH, returncode=3))
    result = cc.get_test_counts("pytest")
    assert result is None, f"Crashed pytest should return None, got {result}"


def test_pytest_no_tests(monkeypatch):
    """No tests collected. The cheese shop is empty but structurally sound."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.PYTEST_NO_TESTS))
    result = cc.get_test_counts("pytest")
    assert result is None, f"No tests collected should return None, got {result}"


# --- Jest: Flavortown Jukebox ---

def test_jest_all_pass(monkeypatch):
    """14 songs, all correctly recommended."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_ALL_PASS))
    result = cc.get_test_counts("jest")
    assert result == {"passed": 14, "failed": 0, "skipped": 0}


def test_jest_mixed(monkeypatch):
    """Polka leaked into the metal playlist. 3 recommendations went wrong."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_MIXED))
    result = cc.get_test_counts("jest")
    assert result == {"passed": 11, "failed": 3, "skipped": 0}


def test_jest_all_fail(monkeypatch):
    """The jukebox is broken. Every recommendation is wrong."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_ALL_FAIL))
    result = cc.get_test_counts("jest")
    # The fixture includes "0 passed" so the regex matches deterministically.
    assert result == {"passed": 0, "failed": 7, "skipped": 0}


def test_jest_all_fail_no_passed_label(monkeypatch):
    """Jest versions that omit '0 passed' from all-fail output return None."""
    # Some Jest versions output "Tests: 7 failed, 7 total" with no "passed" mention.
    output = """\
 FAIL  src/jukebox/__tests__/playlist.test.ts
 FAIL  src/jukebox/__tests__/recommendations.test.ts

Test Suites: 2 failed, 2 total
Tests:       7 failed, 7 total
Snapshots:   0 total
Time:        1.892 s
"""
    monkeypatch.setattr(subprocess, "run", _fake_run(output))
    result = cc.get_test_counts("jest")
    assert result is None, (
        f"Jest all-fail without 'N passed' should return None, got {result}"
    )


def test_jest_pass_only(monkeypatch):
    """Jest output with no failure prefix — just 'N passed'."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_PASS_ONLY))
    result = cc.get_test_counts("jest")
    assert result == {"passed": 14, "failed": 0, "skipped": 0}


def test_jest_crash(monkeypatch):
    """Jest config error. Module not found. The jukebox won't even turn on."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_CRASH, returncode=1))
    result = cc.get_test_counts("jest")
    assert result is None, f"Crashed jest should return None, got {result}"


# --- Vitest: Quantum Tacos ---

def test_vitest_all_pass(monkeypatch):
    """13 taco physics simulations, all within acceptable parameters."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.VITEST_ALL_PASS))
    result = cc.get_test_counts("vitest")
    assert result == {"passed": 13, "failed": 0, "skipped": 0}


def test_vitest_mixed(monkeypatch):
    """Guacamole collapsed from its superposition. 2 tacos failed."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.VITEST_MIXED))
    result = cc.get_test_counts("vitest")
    assert result == {"passed": 11, "failed": 2, "skipped": 0}


def test_vitest_crash(monkeypatch):
    """Quantum taco plugin not found. Reality unresolved."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.VITEST_CRASH, returncode=1))
    result = cc.get_test_counts("vitest")
    assert result is None, f"Crashed vitest should return None, got {result}"


# --- Cargo: Crab Rave Orchestrator ---

def test_cargo_all_pass(monkeypatch):
    """8 crabs, all raving in harmony."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.CARGO_ALL_PASS))
    result = cc.get_test_counts("cargo")
    assert result == {"passed": 8, "failed": 0, "skipped": 0}


def test_cargo_mixed(monkeypatch):
    """Two crabs collided during the rave. One ignored the whole thing."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.CARGO_MIXED))
    result = cc.get_test_counts("cargo")
    assert result == {"passed": 5, "failed": 2, "skipped": 1}


def test_cargo_crash(monkeypatch):
    """Compilation failed. The crabs never even got to the rave."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.CARGO_CRASH, returncode=101))
    result = cc.get_test_counts("cargo")
    assert result is None, f"Failed cargo build should return None, got {result}"


# --- Go: Haunted Elevator ---

def test_go_verbose_all_pass(monkeypatch):
    """6 elevator tests, all passing. The ghosts behaved."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.GO_VERBOSE_ALL_PASS))
    result = cc.get_test_counts("go")
    assert result == {"passed": 6, "failed": 0, "skipped": 0}


def test_go_verbose_mixed(monkeypatch):
    """Doors stayed closed on floor 7 and a ghost pressed buttons. One test skipped."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.GO_VERBOSE_MIXED))
    result = cc.get_test_counts("go")
    assert result == {"passed": 4, "failed": 2, "skipped": 1}


def test_go_verbose_with_subtests(monkeypatch):
    """Subtests should not be double-counted. Only top-level tests matter."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.GO_VERBOSE_WITH_SUBTESTS))
    result = cc.get_test_counts("go")
    # TestElevatorGoesUp has 2 subtests but should count as 1 top-level pass.
    # TestElevatorGoesDown is 1 top-level pass. Total: 2 passed, 0 failed, 0 skipped.
    assert result == {"passed": 2, "failed": 0, "skipped": 0}, (
        f"Expected 2 top-level tests (subtests not counted separately), got {result}"
    )


def test_go_crash(monkeypatch):
    """Build failed. GhostDimension is undefined. As expected."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.GO_CRASH, returncode=2))
    result = cc.get_test_counts("go")
    assert result is None, f"Failed go build should return None, got {result}"


# --- Swift: Astral Postal Service ---

def test_swift_all_pass(monkeypatch):
    """5 parcels across dimensions, all delivered intact."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.SWIFT_ALL_PASS))
    result = cc.get_test_counts("swift")
    assert result == {"passed": 5, "failed": 0, "skipped": 0}


def test_swift_mixed(monkeypatch):
    """Package came out inside-out. Ink phase-shifted. Void postmark skipped."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.SWIFT_MIXED))
    result = cc.get_test_counts("swift")
    assert result == {"passed": 3, "failed": 2, "skipped": 1}


def test_swift_crash(monkeypatch):
    """DimensionalTransit module not found. Mail undeliverable."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.SWIFT_CRASH, returncode=1))
    result = cc.get_test_counts("swift")
    assert result is None, f"Failed swift build should return None, got {result}"


# --- Mocha: Sock Puppet Theatre ---

def test_mocha_all_pass(monkeypatch):
    """8 puppets, all performing flawlessly."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.MOCHA_ALL_PASS))
    result = cc.get_test_counts("mocha")
    assert result == {"passed": 8, "failed": 0, "skipped": 0}


def test_mocha_mixed(monkeypatch):
    """Mr. Buttons was dropped and the audience booed. 2 failures."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.MOCHA_MIXED))
    result = cc.get_test_counts("mocha")
    assert result == {"passed": 5, "failed": 2, "skipped": 0}


def test_mocha_crash(monkeypatch):
    """Puppet registry missing. The show can't go on."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.MOCHA_CRASH, returncode=1))
    result = cc.get_test_counts("mocha")
    assert result is None, f"Crashed mocha should return None, got {result}"


# --- Edge cases ---

def test_unknown_runner(monkeypatch):
    """Unknown runner should return None without running anything."""
    result = cc.get_test_counts("bun")
    assert result is None


def test_none_runner():
    """None runner should return None."""
    result = cc.get_test_counts(None)
    assert result is None


def test_timeout_returns_none(monkeypatch):
    """Test runner timeout should return None."""
    def timeout_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=300)
    monkeypatch.setattr(subprocess, "run", timeout_run)
    result = cc.get_test_counts("pytest")
    assert result is None


def test_command_not_found_returns_none(monkeypatch):
    """Missing test runner binary should return None."""
    def not_found(*a, **kw):
        raise FileNotFoundError("No such file: 'npx'")
    monkeypatch.setattr(subprocess, "run", not_found)
    result = cc.get_test_counts("jest")
    assert result is None


# --- BH-002 (run 4): count_items matches Status outside item blocks ---

def test_status_outside_item_block_not_counted(tmp_path):
    """**Status:** in Pattern description or preamble should not inflate count."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
# Holtz Punchlist

## Patterns

## Pattern: PAT-001: Incomplete checks
**Instances:** BH-001
**Root Cause:** Missing validation
**Systemic Fix:** Add validation layer
**Detection Rule:** grep for unchecked returns

Previous audit found items with **Status:** RESOLVED that were not fixed.

## Items

### BH-001: Missing validation
**Status:** OPEN
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, (
        f"Expected 1 OPEN (only the real item), got {counts}"
    )
    assert counts["total"] == 1, (
        f"Expected total 1, Status in Pattern description should not count. Got {counts}"
    )


def test_cross_parser_agreement(tmp_path):
    """count_items and parse_punchlist must agree on item counts and statuses."""
    import validate_punchlist as vp

    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
# Holtz Punchlist

## Summary
## Patterns

Previous audit found items with **Status:** RESOLVED that were not fixed.

## Items

### BH-001: First item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** The system shows **Status:** RESOLVED in its output incorrectly.

**Evidence:** Grep found the misleading status string in output logs.

**Acceptance Criteria:**
- [ ] Fix the output

**Validation Command:**
```bash
echo test
```

### BH-002: Second item
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `test.py:5`
**Status:** RESOLVED

**Problem:** Missing test for edge case with enough detail to be valid.

**Evidence:** No test covers the empty input path as shown in code review.

**Acceptance Criteria:**
- [x] Test added

**Validation Command:**
```bash
echo test
```

**Resolution:** Fixed in commit abc123. Test added for empty input.

### BH-003: Third item
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:10`
**Status:** DEFERRED
**Determinism:** theoretical

**Problem:** README claims feature exists but it was removed last quarter.

**Evidence:** grep for feature name returns no code results, only README.

**Acceptance Criteria:**
- [ ] README updated

**Validation Command:**
```bash
echo test
```
""")
    # count_items (convergence tracker's view)
    counts = cc.count_items(punchlist)
    # parse_punchlist (validator's view)
    items = vp.parse_punchlist(punchlist.read_text())

    # Total items must agree
    assert counts["total"] == len(items), (
        f"count_items sees {counts['total']} items, "
        f"parse_punchlist sees {len(items)}: DISAGREEMENT"
    )

    # Status distribution must agree
    from collections import Counter
    parsed_statuses = Counter(item.status for item in items)
    for status in ("OPEN", "RESOLVED", "DEFERRED", "IN PROGRESS"):
        assert counts.get(status, 0) == parsed_statuses.get(status, 0), (
            f"Status '{status}': count_items={counts.get(status, 0)}, "
            f"parse_punchlist={parsed_statuses.get(status, 0)}"
        )


def test_status_in_problem_section_not_counted(tmp_path):
    """**Status:** in an item's Problem prose should not create a phantom item."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Real item
**Status:** OPEN

**Problem:** The system shows **Status:** RESOLVED for items that are actually broken.

### BH-002: Second item
**Status:** DEFERRED
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, f"Expected 1 OPEN, got {counts}"
    assert counts["DEFERRED"] == 1, f"Expected 1 DEFERRED, got {counts}"
    assert counts["total"] == 2, (
        f"Expected total 2 (only real items), Status in Problem prose should not count. Got {counts}"
    )


# --- BH-001 (run 5): count_items drops items without Status field ---

def test_item_without_status_counted_as_unknown(tmp_path):
    """An item with ### BH-NNN: header but no **Status:** should count as unknown, not be dropped."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Item with status
**Status:** OPEN

### BH-002: Item without status field
**Severity:** HIGH
**Category:** bug/logic

### BH-003: Another normal item
**Status:** RESOLVED
""")
    counts = cc.count_items(punchlist)
    assert counts["total"] == 3, (
        f"Expected total 3 (including item without Status), got {counts}. "
        f"Items without Status must be counted as 'unknown', not silently dropped."
    )
    assert counts["unknown"] == 1, (
        f"Expected 1 unknown (item with no Status field), got {counts}"
    )


def test_cross_parser_agreement_missing_status(tmp_path):
    """count_items and parse_punchlist must agree even when an item lacks Status."""
    import validate_punchlist as vp

    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Normal item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is evidence with enough detail to pass the threshold check.

**Acceptance Criteria:**
- [ ] Fix it

**Validation Command:**
```bash
echo test
```

### BH-002: Item missing Status
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `test.py:5`

**Problem:** This item has no Status field — a common malformation.

**Evidence:** Grep shows the Status line was accidentally deleted during editing.

**Acceptance Criteria:**
- [ ] Add status back

**Validation Command:**
```bash
echo test
```
""")
    counts = cc.count_items(punchlist)
    items = vp.parse_punchlist(punchlist.read_text())

    assert counts["total"] == len(items), (
        f"count_items sees {counts['total']} items, "
        f"parse_punchlist sees {len(items)}: DISAGREEMENT on item with missing Status"
    )


# --- BH-002 (run 5): detect_test_runner misses [pytest] in setup.cfg ---

def test_detect_setup_cfg_bare_pytest_section(tmp_path, monkeypatch):
    """setup.cfg with [pytest] section (not [tool:pytest]) should detect pytest."""
    (tmp_path / "setup.cfg").write_text(
        "[pytest]\naddopts = -v\n"
    )
    monkeypatch.chdir(tmp_path)
    result = cc.detect_test_runner()
    assert result == "pytest", (
        f"setup.cfg with [pytest] section should detect pytest, got '{result}'"
    )


# --- BH-007 (run 5): pyproject.toml imprecise substring match ---

def test_detect_pyproject_bracket_in_comment(tmp_path, monkeypatch):
    """pyproject.toml with [tool.pytest in a comment should NOT trigger detection."""
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = ['setuptools']\n"
        "# see [tool.pytest docs for configuration options\n"
    )
    monkeypatch.chdir(tmp_path)
    result = cc.detect_test_runner()
    assert result != "pytest", (
        f"pyproject.toml with [tool.pytest only in a comment should not detect pytest, got '{result}'"
    )


# --- BH-002 (bug-hunter run 3): Status regex greedy trailing capture ---

def test_status_trailing_text_ignored_count_items(tmp_path):
    """Trailing text after status value should not corrupt count_items."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Item with annotation
**Status:** OPEN but see notes

### BH-002: Another item
**Status:** RESOLVED successfully
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, (
        f"Expected 1 OPEN (trailing text ignored), got {counts}"
    )
    assert counts["RESOLVED"] == 1, (
        f"Expected 1 RESOLVED (trailing text ignored), got {counts}"
    )
    assert counts["unknown"] == 0, (
        f"Expected 0 unknown (trailing text should not cause misclassification), got {counts}"
    )


# --- BH-001 (bug-hunter run 3): stall detection untested ---

def test_stall_detection_triggers():
    """4+ iterations with no progress on open items should trigger stall detection."""
    stalled = {
        "punchlist": {"OPEN": 3, "IN PROGRESS": 0, "RESOLVED": 2, "DEFERRED": 0, "unknown": 0, "total": 5},
        "tests": None,
    }
    # 4 identical snapshots — open items stuck at 3
    history = [
        {"timestamp": "2026-03-21T01:00:00", **stalled},
        {"timestamp": "2026-03-21T02:00:00", **stalled},
        {"timestamp": "2026-03-21T03:00:00", **stalled},
        {"timestamp": "2026-03-21T04:00:00", **stalled},
    ]
    converged, message = cc.check_convergence(history)
    assert not converged, f"Should not converge when stalled. Got: {message}"
    assert "STALLED" in message, (
        f"Stall detection should mention STALLED. Got: {message}"
    )
    assert "3" in message, (
        f"Stall message should mention the number of stuck items. Got: {message}"
    )


def test_stall_detection_not_triggered_with_progress():
    """4 iterations where open items decrease should NOT trigger stall."""
    history = [
        {"timestamp": "2026-03-21T01:00:00",
         "punchlist": {"OPEN": 4, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0, "total": 4},
         "tests": None},
        {"timestamp": "2026-03-21T02:00:00",
         "punchlist": {"OPEN": 3, "IN PROGRESS": 0, "RESOLVED": 1, "DEFERRED": 0, "unknown": 0, "total": 4},
         "tests": None},
        {"timestamp": "2026-03-21T03:00:00",
         "punchlist": {"OPEN": 2, "IN PROGRESS": 0, "RESOLVED": 2, "DEFERRED": 0, "unknown": 0, "total": 4},
         "tests": None},
        {"timestamp": "2026-03-21T04:00:00",
         "punchlist": {"OPEN": 1, "IN PROGRESS": 0, "RESOLVED": 3, "DEFERRED": 0, "unknown": 0, "total": 4},
         "tests": None},
    ]
    converged, message = cc.check_convergence(history)
    assert "STALLED" not in message, (
        f"Progress being made — should NOT trigger stall. Got: {message}"
    )


def test_stall_detection_needs_4_entries():
    """Stall detection requires 4+ history entries. 3 entries should not trigger it."""
    stalled = {
        "punchlist": {"OPEN": 3, "IN PROGRESS": 0, "RESOLVED": 2, "DEFERRED": 0, "unknown": 0, "total": 5},
        "tests": None,
    }
    history = [
        {"timestamp": "2026-03-21T01:00:00", **stalled},
        {"timestamp": "2026-03-21T02:00:00", **stalled},
        {"timestamp": "2026-03-21T03:00:00", **stalled},
    ]
    converged, message = cc.check_convergence(history)
    assert "STALLED" not in message, (
        f"Only 3 entries — stall detection should not trigger. Got: {message}"
    )

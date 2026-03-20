"""
Realistic test runner output fixtures for testing convergence_check parsers.

Each runner gets outputs that tell a small story about a fictional project.
The test names are real enough to be useful as parser validation, quirky enough
to make someone smile when they read the test output.

These are the outputs Holtz would see when auditing various projects.
"""

# =============================================================================
# PYTEST — "The Cheese Shop" (a REST API for artisanal cheese inventory)
# =============================================================================

PYTEST_ALL_PASS = """\
tests/test_brie.py ..                                                    [ 14%]
tests/test_cheddar.py ...                                                [ 42%]
tests/test_gouda.py ....                                                 [ 85%]
tests/test_inventory.py ..                                               [100%]
11 passed in 0.42s
"""

PYTEST_MIXED = """\
tests/test_brie.py .F                                                    [ 14%]
tests/test_cheddar.py ...                                                [ 42%]
tests/test_gouda.py ..x.                                                 [ 85%]
tests/test_inventory.py .s                                               [100%]
8 passed, 1 failed, 1 skipped, 1 xfailed in 0.67s
"""

PYTEST_ALL_FAIL = """\
tests/test_brie.py FF                                                    [ 50%]
tests/test_cheddar.py FF                                                 [100%]
4 failed in 0.23s
"""

PYTEST_CRASH = """\
INTERNAL ERROR: pluggy.PluginValidationError: unknown hook 'pytest_cheese_matured'
Traceback (most recent call last):
  File "/usr/lib/python3.12/site-packages/_pytest/main.py", line 268, in wrap_session
    config._do_configure()
pluggy.PluginValidationError: unknown hook 'pytest_cheese_matured'
"""

PYTEST_NO_TESTS = """\
============================= test session starts ==============================
collected 0 items

============================== no tests ran ====================================
"""

# =============================================================================
# JEST — "Flavortown Jukebox" (a music recommendation engine)
# =============================================================================

JEST_ALL_PASS = """\
 PASS  src/jukebox/__tests__/playlist.test.ts
 PASS  src/jukebox/__tests__/recommendations.test.ts
 PASS  src/jukebox/__tests__/genre-classifier.test.ts

Test Suites: 3 passed, 3 total
Tests:       14 passed, 14 total
Snapshots:   0 total
Time:        2.341 s
"""

JEST_MIXED = """\
 PASS  src/jukebox/__tests__/playlist.test.ts
 FAIL  src/jukebox/__tests__/recommendations.test.ts
  ● should not recommend polka to metalheads

    expect(received).not.toContain(expected)

    Expected: "Beer Barrel Polka"
    Received: ["Raining Blood", "Beer Barrel Polka", "Master of Puppets"]

 PASS  src/jukebox/__tests__/genre-classifier.test.ts

Test Suites: 1 failed, 2 passed, 3 total
Tests:       3 failed, 11 passed, 14 total
Snapshots:   0 total
Time:        3.112 s
"""

JEST_ALL_FAIL = """\
 FAIL  src/jukebox/__tests__/playlist.test.ts
 FAIL  src/jukebox/__tests__/recommendations.test.ts

Test Suites: 2 failed, 2 total
Tests:       7 failed, 0 passed, 7 total
Snapshots:   0 total
Time:        1.892 s
"""

# Jest with only passed, no failed prefix
JEST_PASS_ONLY = """\
Test Suites: 3 passed, 3 total
Tests:       14 passed, 14 total
Time:        1.5 s
"""

JEST_CRASH = """\
● Validation Error:

  Module @flavortown/jukebox-config in the transform option was not found.

Configuration Documentation:
https://jestjs.io/docs/configuration
"""

# =============================================================================
# VITEST — "Quantum Tacos" (a physics simulation for optimal taco construction)
# =============================================================================

VITEST_ALL_PASS = """\
 ✓ src/quantum/__tests__/shell-integrity.test.ts (4 tests) 12ms
 ✓ src/quantum/__tests__/filling-distribution.test.ts (6 tests) 8ms
 ✓ src/quantum/__tests__/salsa-viscosity.test.ts (3 tests) 5ms

 Test Files  3 passed (3)
      Tests  13 passed (13)
   Start at  14:32:01
   Duration  245ms
"""

VITEST_MIXED = """\
 ✓ src/quantum/__tests__/shell-integrity.test.ts (4 tests) 12ms
 ✗ src/quantum/__tests__/filling-distribution.test.ts (6 tests) 15ms
   × guacamole should remain in superposition until observed
 ✓ src/quantum/__tests__/salsa-viscosity.test.ts (3 tests) 5ms

 Test Files  1 failed | 2 passed (3)
      Tests  2 failed | 11 passed (13)
   Start at  14:32:01
   Duration  312ms
"""

VITEST_CRASH = """\
Error: Failed to load config from vite.config.ts
  Cannot find module 'quantum-taco-plugin'
"""

# =============================================================================
# CARGO — "Crab Rave Orchestrator" (a distributed task scheduler in Rust)
# =============================================================================

CARGO_ALL_PASS = """\
   Compiling crab-rave-orchestrator v0.3.7
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.14s
     Running unittests src/lib.rs (target/debug/deps/crab_rave-a1b2c3d4)

running 8 tests
test scheduler::tests::test_crab_joins_rave ... ok
test scheduler::tests::test_crab_leaves_gracefully ... ok
test scheduler::tests::test_two_crabs_one_task ... ok
test scheduler::tests::test_rave_survives_crab_disconnect ... ok
test distributed::tests::test_crabs_across_networks ... ok
test distributed::tests::test_rave_consensus ... ok
test distributed::tests::test_crab_timeout_recovery ... ok
test distributed::tests::test_maximum_crab_capacity ... ok

test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.42s
"""

CARGO_MIXED = """\
   Compiling crab-rave-orchestrator v0.3.7
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.14s
     Running unittests src/lib.rs (target/debug/deps/crab_rave-a1b2c3d4)

running 8 tests
test scheduler::tests::test_crab_joins_rave ... ok
test scheduler::tests::test_crab_leaves_gracefully ... ok
test scheduler::tests::test_two_crabs_one_task ... FAILED
test scheduler::tests::test_rave_survives_crab_disconnect ... ok
test distributed::tests::test_crabs_across_networks ... ok
test distributed::tests::test_rave_consensus ... FAILED
test distributed::tests::test_crab_timeout_recovery ... ok
test distributed::tests::test_maximum_crab_capacity ... ignored

test result: FAILED. 5 passed; 2 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.67s
"""

CARGO_CRASH = """\
error[E0433]: failed to resolve: use of undeclared crate or module `crab_rave`
 --> src/lib.rs:1:5
  |
1 | use crab_rave::Orchestrator;
  |     ^^^^^^^^^ use of undeclared crate or module `crab_rave`

error: aborting due to 1 previous error
"""

# =============================================================================
# GO — "Haunted Elevator" (a building simulation with unpredictable floors)
# =============================================================================

# Verbose format: individual test results
GO_VERBOSE_ALL_PASS = """\
=== RUN   TestElevatorGoesUp
--- PASS: TestElevatorGoesUp (0.00s)
=== RUN   TestElevatorGoesDown
--- PASS: TestElevatorGoesDown (0.00s)
=== RUN   TestElevatorOpensDoorsOnArrival
--- PASS: TestElevatorOpensDoorsOnArrival (0.00s)
=== RUN   TestElevatorRefusesFloor13
--- PASS: TestElevatorRefusesFloor13 (0.00s)
=== RUN   TestGhostCannotPressButtons
--- PASS: TestGhostCannotPressButtons (0.00s)
=== RUN   TestFlickeringLightsAreCosmetic
--- PASS: TestFlickeringLightsAreCosmetic (0.00s)
PASS
ok  	github.com/spectral/haunted-elevator	0.003s
"""

GO_VERBOSE_MIXED = """\
=== RUN   TestElevatorGoesUp
--- PASS: TestElevatorGoesUp (0.00s)
=== RUN   TestElevatorGoesDown
--- PASS: TestElevatorGoesDown (0.00s)
=== RUN   TestElevatorOpensDoorsOnArrival
--- FAIL: TestElevatorOpensDoorsOnArrival (0.00s)
    elevator_test.go:42: doors remained closed on floor 7, but floor 7 doesn't exist in this building
=== RUN   TestElevatorRefusesFloor13
--- PASS: TestElevatorRefusesFloor13 (0.00s)
=== RUN   TestGhostCannotPressButtons
--- FAIL: TestGhostCannotPressButtons (0.01s)
    ghost_test.go:18: ghost pressed button for floor -1, elevator obliged
=== RUN   TestFlickeringLightsAreCosmetic
--- PASS: TestFlickeringLightsAreCosmetic (0.00s)
=== RUN   TestCableStrengthUnderGhostWeight
--- SKIP: TestCableStrengthUnderGhostWeight (0.00s)
    cable_test.go:33: skipping: cannot weigh ghosts
FAIL
FAIL	github.com/spectral/haunted-elevator	0.012s
"""

GO_VERBOSE_WITH_SUBTESTS = """\
=== RUN   TestElevatorGoesUp
=== RUN   TestElevatorGoesUp/from_lobby
--- PASS: TestElevatorGoesUp/from_lobby (0.00s)
=== RUN   TestElevatorGoesUp/from_basement
--- PASS: TestElevatorGoesUp/from_basement (0.00s)
--- PASS: TestElevatorGoesUp (0.00s)
=== RUN   TestElevatorGoesDown
--- PASS: TestElevatorGoesDown (0.00s)
PASS
ok  	github.com/spectral/haunted-elevator	0.002s
"""

GO_CRASH = """\
# github.com/spectral/haunted-elevator
./elevator.go:13:2: undefined: GhostDimension
FAIL	github.com/spectral/haunted-elevator [build failed]
"""

# =============================================================================
# MOCHA — "Sock Puppet Theatre" (a WebSocket-based puppet show platform)
# =============================================================================

MOCHA_ALL_PASS = """\

  8 passing (234ms)

"""

MOCHA_MIXED = """\

  5 passing (312ms)
  2 failing

  1) Puppet Theatre
       should not drop puppet during act 3:
     AssertionError: puppet 'Mr. Buttons' was dropped at scene 7
      at Context.<anonymous> (test/theatre.test.js:42:10)

  2) Audience
       should not boo during soliloquy:
     AssertionError: audience booed 3 times, expected 0
      at Context.<anonymous> (test/audience.test.js:18:10)

"""

MOCHA_CRASH = """\
Error: Cannot find module './puppet-registry'
    at Function.Module._resolveFilename (internal/modules/cjs/loader.js:885:15)
    at Function.Module._load (internal/modules/cjs/loader.js:730:27)
"""

# =============================================================================
# SWIFT — "Astral Postal Service" (interdimensional mail routing in Swift)
# =============================================================================

SWIFT_ALL_PASS = """\
Building for debugging...
Build complete! (1.23s)
Test Suite 'All tests' started at 2026-03-19 14:00:00.000.
Test Suite 'AstralPostalServiceTests.xctest' started at 2026-03-19 14:00:00.001.
Test Suite 'MailRouterTests' started at 2026-03-19 14:00:00.001.
Test Case 'MailRouterTests.testLetterReachesDimension7' started.
Test Case 'MailRouterTests.testLetterReachesDimension7' passed (0.003 seconds).
Test Case 'MailRouterTests.testPackageSurvivesWormhole' started.
Test Case 'MailRouterTests.testPackageSurvivesWormhole' passed (0.001 seconds).
Test Case 'MailRouterTests.testReturnToSenderFromVoid' started.
Test Case 'MailRouterTests.testReturnToSenderFromVoid' passed (0.002 seconds).
Test Suite 'MailRouterTests' passed at 2026-03-19 14:00:00.007.
	 Executed 3 tests, with 0 failures (0 unexpected) in 0.006 (0.007) seconds
Test Suite 'PostmarkTests' started at 2026-03-19 14:00:00.008.
Test Case 'PostmarkTests.testStampValidInAllDimensions' started.
Test Case 'PostmarkTests.testStampValidInAllDimensions' passed (0.001 seconds).
Test Case 'PostmarkTests.testInkDoesNotPhaseShift' started.
Test Case 'PostmarkTests.testInkDoesNotPhaseShift' passed (0.001 seconds).
Test Suite 'PostmarkTests' passed at 2026-03-19 14:00:00.010.
	 Executed 2 tests, with 0 failures (0 unexpected) in 0.002 (0.002) seconds
Test Suite 'AstralPostalServiceTests.xctest' passed at 2026-03-19 14:00:00.010.
	 Executed 5 tests, with 0 failures (0 unexpected) in 0.008 (0.009) seconds
Test Suite 'All tests' passed at 2026-03-19 14:00:00.010.
	 Executed 5 tests, with 0 failures (0 unexpected) in 0.008 (0.009) seconds
"""

SWIFT_MIXED = """\
Building for debugging...
Build complete! (1.45s)
Test Suite 'All tests' started at 2026-03-19 14:00:00.000.
Test Suite 'AstralPostalServiceTests.xctest' started at 2026-03-19 14:00:00.001.
Test Suite 'MailRouterTests' started at 2026-03-19 14:00:00.001.
Test Case 'MailRouterTests.testLetterReachesDimension7' started.
Test Case 'MailRouterTests.testLetterReachesDimension7' passed (0.003 seconds).
Test Case 'MailRouterTests.testPackageSurvivesWormhole' started.
/Users/dev/AstralPostalService/Tests/MailRouterTests.swift:42: error: MailRouterTests.testPackageSurvivesWormhole : XCTAssertFalse failed - package was inside-out after wormhole transit
Test Case 'MailRouterTests.testPackageSurvivesWormhole' failed (0.005 seconds).
Test Case 'MailRouterTests.testReturnToSenderFromVoid' started.
Test Case 'MailRouterTests.testReturnToSenderFromVoid' passed (0.002 seconds).
Test Suite 'MailRouterTests' failed at 2026-03-19 14:00:00.011.
	 Executed 3 tests, with 1 failure (1 unexpected) in 0.010 (0.011) seconds
Test Suite 'PostmarkTests' started at 2026-03-19 14:00:00.012.
Test Case 'PostmarkTests.testStampValidInAllDimensions' started.
Test Case 'PostmarkTests.testStampValidInAllDimensions' passed (0.001 seconds).
Test Case 'PostmarkTests.testInkDoesNotPhaseShift' started.
/Users/dev/AstralPostalService/Tests/PostmarkTests.swift:28: error: PostmarkTests.testInkDoesNotPhaseShift : XCTAssertEqual failed: ("ultraviolet") is not equal to ("infrared") - ink phase-shifted during dimensional transit
Test Case 'PostmarkTests.testInkDoesNotPhaseShift' failed (0.003 seconds).
Test Case 'PostmarkTests.testVoidPostmarkIsIllegible' started.
Test Case 'PostmarkTests.testVoidPostmarkIsIllegible' skipped (0.000 seconds).
Test Suite 'PostmarkTests' failed at 2026-03-19 14:00:00.016.
	 Executed 3 tests, with 1 failure (1 unexpected) in 0.004 (0.004) seconds
Test Suite 'AstralPostalServiceTests.xctest' failed at 2026-03-19 14:00:00.016.
	 Executed 6 tests, with 2 failures (2 unexpected) in 0.014 (0.015) seconds
Test Suite 'All tests' failed at 2026-03-19 14:00:00.016.
	 Executed 6 tests, with 2 failures (2 unexpected) in 0.014 (0.015) seconds
"""

SWIFT_CRASH = """\
Building for debugging...
/Users/dev/AstralPostalService/Sources/MailRouter.swift:7:8: error: no such module 'DimensionalTransit'
import DimensionalTransit
       ^
error: fatalError
"""


# Issue #29: Enforcement Chain Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the regex bugs that disabled the entire enforcement chain, harden the stop hook and primer against missing cache, remove Holtz-specific gate commands from transitions.toml, and upgrade sahjhan to 0.8.0.

**Architecture:** Five independent fixes to `_protocol_cache.py`, `stop_hook.py`, `primer.py`, `transitions.toml`, and `_resolve.py`. A shared helper `_split_shell_segments()` replaces the buggy `re.split(r"[;&|]+")` in both `is_sahjhan_cmd()` and `is_git_commit()`. Sahjhan 0.8.0 is pinned via version + checksums in `_resolve.py`.

**Tech Stack:** Python, pytest, TOML config

---

### Task 1: Upgrade Sahjhan to 0.8.0

**Files:**
- Modify: `enforcement/hooks/_resolve.py:14-23`
- Test: `tests/test_ensure_sahjhan.py`

- [ ] **Step 1: Vendor the new binary**

```bash
scripts/vendor-sahjhan.sh 0.8.0
```

- [ ] **Step 2: Update pinned version and checksums in `_resolve.py`**

In `enforcement/hooks/_resolve.py`, change:

```python
SAHJHAN_VERSION = "0.8.0"
_RELEASE_BASE = "https://github.com/jbrjake/sahjhan/releases/download"
_BOOTSTRAP_COOLDOWN = 3600  # seconds before retrying after failure

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "c561a1eac39692dc7580efa55803c85dbe41010850970ee43535ff3ea5b13054",
    "x86_64-apple-darwin": "8726c5d77dc96dab999c0dc5d6432ff89c0076e4a2f4288beb80109472f774c8",
    "x86_64-unknown-linux-gnu": "87d506e4c646b74ab308baaeba9a1fb7eab03045d1a4983430ff87c2eea1d0ba",
    "aarch64-unknown-linux-gnu": "65395097bf42dbdbc00f09d5b6584fd8bd06715736716543479229185153ff38",
}
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/test_ensure_sahjhan.py -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/_resolve.py bin/.sahjhan-version
git commit -m "chore: upgrade sahjhan to 0.8.0

Addresses R3, R7, R8 from issue #29 via jbrjake/sahjhan#22."
```

Note: `bin/sahjhan-*` binaries are gitignored — do NOT `git add` them.

---

### Task 2: Fix `_split_shell_segments()` — shared helper for shell command parsing

**Files:**
- Modify: `enforcement/hooks/_protocol_cache.py:187-236`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing tests for the two bugs**

Add to `tests/test_protocol_enforcement.py` in `TestProtocolCache`:

```python
def test_sahjhan_cmd_with_redirect(self):
    """Issue #29 R1: 2>&1 must not break sahjhan detection."""
    from _protocol_cache import is_sahjhan_cmd
    assert is_sahjhan_cmd("sahjhan status 2>&1")
    assert is_sahjhan_cmd("./bin/sahjhan-aarch64-apple-darwin status 2>&1")
    assert is_sahjhan_cmd("sahjhan status 2>&1 && sahjhan transition fix_commit 2>&1")
    # Non-sahjhan with redirect still false
    assert not is_sahjhan_cmd("git status 2>&1")

def test_sahjhan_cmd_with_export_prefix(self):
    """Issue #29 R2: export/env prefix must not break sahjhan detection."""
    from _protocol_cache import is_sahjhan_cmd
    assert is_sahjhan_cmd("export PATH=/usr/bin:$PATH && sahjhan status")
    assert is_sahjhan_cmd("PATH=/foo:$PATH sahjhan status")
    assert is_sahjhan_cmd("export FOO=bar && sahjhan status && sahjhan transition fix_commit")
    # Mixed with non-sahjhan still false
    assert not is_sahjhan_cmd("export PATH=/usr/bin:$PATH && git commit -m 'fix'")

def test_git_commit_with_redirect(self):
    """Issue #29 R1: 2>&1 must not break git commit detection."""
    from _protocol_cache import is_git_commit
    assert is_git_commit("git commit -m 'fix: stuff' 2>&1")
    assert is_git_commit("git add . && git commit -m 'feat: x' 2>&1")
    # Amend with redirect still correctly rejected
    assert not is_git_commit("git commit --amend 2>&1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache::test_sahjhan_cmd_with_redirect tests/test_protocol_enforcement.py::TestProtocolCache::test_sahjhan_cmd_with_export_prefix tests/test_protocol_enforcement.py::TestProtocolCache::test_git_commit_with_redirect -v`
Expected: FAIL — `is_sahjhan_cmd("sahjhan status 2>&1")` returns False.

- [ ] **Step 3: Implement `_split_shell_segments()` and update both functions**

In `enforcement/hooks/_protocol_cache.py`, add the helper above `is_git_commit`:

```python
def _split_shell_segments(cmd: str) -> list[str]:
    """Split a shell command on operators (&&, ||, ;, |) but not redirects.

    Strips shell redirections like 2>&1, >&2, 2>/dev/null before splitting,
    so they don't produce spurious segments. Also strips leading export
    statements and variable assignments from each segment.
    """
    # Strip shell redirections: 2>&1, >&2, 2>/dev/null, etc.
    cleaned = re.sub(r'\d*>&?\d+', '', cmd)
    cleaned = re.sub(r'\d*>/dev/null', '', cleaned)
    # Split on actual shell operators: &&, ||, ;, |
    # Use specific multi-char operators first to avoid splitting on single &
    segments = re.split(r'&&|\|\||[;|]', cleaned)
    result = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Strip leading export and variable assignments
        seg = re.sub(r'^(?:export\s+)?\w+=\S*\s*', '', seg).strip()
        # May need multiple rounds for "export FOO=bar" (export stripped, then nothing left)
        if seg:
            result.append(seg)
    return result
```

Update `is_git_commit` to use it:

```python
def is_git_commit(cmd: str) -> bool:
    """Detect git commit commands (not amend).

    Only matches ``git commit`` at the start of a shell segment (after
    ;, &&, ||, |, or start of string). Does not match git commit inside
    echo, comments, or quoted strings.

    Checks for ``--amend`` as a CLI flag (word boundary), not as a
    substring of the commit message.
    """
    for segment in _split_shell_segments(cmd):
        seg = segment.strip()
        # Strip leading env var assignments (VAR=x git commit ...)
        stripped_seg = re.sub(r"^\s*(?:\w+=\S*\s+)*", "", seg)
        if not re.match(r"git\s+commit\b(?!-)", stripped_seg):
            continue
        # This segment starts with git commit — check for --amend
        stripped = re.sub(r'-m\s+(?:"[^"]*"|\'[^\']*\'|\S+)', '', seg)
        if not re.search(r"(?<!\w)--amend\b", stripped):
            return True
    return False
```

Update `is_sahjhan_cmd` to use it:

```python
def is_sahjhan_cmd(cmd: str) -> bool:
    """Detect commands that are exclusively sahjhan CLI invocations.

    Returns True only when ALL non-empty segments are sahjhan commands.
    A chained command like ``git commit; sahjhan status`` returns False
    because the git-commit segment is not a sahjhan invocation.

    Handles shell redirections (2>&1) and leading export/env-var prefixes
    by stripping them before segment analysis.
    """
    segments = _split_shell_segments(cmd)
    if not segments:
        return False
    for seg in segments:
        parts = seg.split()
        p0 = parts[0] if parts else ""
        is_sahjhan = (
            p0 == "sahjhan"
            or p0.endswith("/sahjhan")
            or "/sahjhan-" in p0
            or p0.startswith("sahjhan-")
        )
        if not (parts and is_sahjhan):
            return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`
Expected: All pass, including the three new tests.

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -x -q`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_protocol_cache.py tests/test_protocol_enforcement.py
git commit -m "fix(hooks): handle shell redirects and export prefixes in command parsing

Fixes issue #29 R1 and R2. The regex re.split(r'[;&|]+') treated the &
in 2>&1 as a shell operator, breaking sahjhan and git commit detection.
Export PATH=... prefixes also caused false negatives.

Extracts _split_shell_segments() helper used by both is_sahjhan_cmd()
and is_git_commit()."
```

---

### Task 3: Stop hook blocks on missing cache (R5)

**Files:**
- Modify: `enforcement/hooks/stop_hook.py:48-54`
- Modify: `tests/test_protocol_enforcement.py` (TestStopHookFreshness)

- [ ] **Step 1: Write failing test**

Update the existing `test_warns_when_no_cache_but_sahjhan_dir_exists` test in `TestStopHookFreshness` and add a new one:

```python
def test_blocks_when_no_cache_but_sahjhan_dir_exists(self, tmp_path):
    """Issue #29 R5: Has .sahjhan dir but no enforcement cache → block."""
    sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    sahjhan_dir.mkdir(parents=True)

    event = {"cwd": str(tmp_path)}
    code, output, _ = run_enforcement_hook("stop_hook.py", event)
    assert code == 0
    assert output.get("decision") == "block"
    assert "missing" in output.get("reason", "").lower() or "cache" in output.get("reason", "").lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness::test_blocks_when_no_cache_but_sahjhan_dir_exists -v`
Expected: FAIL — currently returns `decision: approve` (warn).

- [ ] **Step 3: Change stop_hook.py to block on missing cache**

In `enforcement/hooks/stop_hook.py`, replace the `cache is None` branch:

```python
    if cache is None:
        # .sahjhan dir exists but no enforcement cache — audit state unknown.
        # Block to prevent silent enforcement bypass (issue #29 R5).
        exit_stop_block(
            "Sahjhan data directory exists but enforcement cache is missing. "
            "Run `sahjhan status` to check audit state before stopping."
        )
```

- [ ] **Step 4: Remove old warn test, run tests**

Remove `test_warns_when_no_cache_but_sahjhan_dir_exists` from the test file (replaced by the new block test).

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_protocol_enforcement.py
git commit -m "fix(hooks): stop hook blocks on missing enforcement cache

Issue #29 R5. Previously warned when .sahjhan/ existed without
enforcement-cache.json, allowing silent bypass of the entire
enforcement chain."
```

---

### Task 4: Primer injects context regardless of cache freshness (R6)

**Files:**
- Modify: `enforcement/hooks/primer.py:50-53`
- Modify: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing test**

Add a new test class or add to existing primer tests:

```python
class TestPrimerFreshness:
    """Tests for primer.py freshness behavior (issue #29 R6)."""

    def test_injects_context_with_stale_cache(self, tmp_path, monkeypatch):
        """Issue #29 R6: Primer should inject context even when cache is stale."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        # Create .sahjhan dir
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event)
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("message", "")
        # Should contain resume context, not be empty
        assert "SAHJHAN" in reason or "state" in reason.lower() or output.get("decision") == "approve"
```

Note: The primer hook uses subprocess to call the sahjhan binary and `ensure_sahjhan()`. The test will need to mock those. Check how existing primer tests work — if there are none that exercise the full hook, this test may need `monkeypatch` for `ensure_sahjhan` and `subprocess.run`. Adjust mocking strategy based on existing test patterns.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPrimerFreshness -v`
Expected: FAIL — primer currently exits early on stale cache.

- [ ] **Step 3: Remove the freshness gate from primer.py**

In `enforcement/hooks/primer.py`, remove lines 51-53 (the freshness check):

```python
    # DELETE these lines:
    # Stale enforcement: don't inject context for abandoned audits
    enforcement_cache = read_enforcement_cache(cwd)
    if not is_enforcement_fresh(enforcement_cache):
        exit_ok()
```

The primer should still read the cache later for `format_state_line()`, so keep the `read_enforcement_cache` call at line 121 where it's used for the state line append.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_protocol_enforcement.py -v -x`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_protocol_enforcement.py
git commit -m "fix(hooks): primer injects context regardless of cache freshness

Issue #29 R6. The primer previously required fresh enforcement cache to
inject resume context, which meant abandoned or bootstrapping audits got
no context injection at all."
```

---

### Task 5: Remove Holtz-specific mypy gates from transitions.toml (R9)

**Files:**
- Modify: `enforcement/transitions.toml:127-129,167-169`

- [ ] **Step 1: Write failing test**

Add to `tests/test_protocol_enforcement.py`:

```python
class TestTransitionsToml:
    """Validate transitions.toml doesn't contain Holtz-specific paths."""

    def test_no_holtz_paths_in_command_gates(self):
        """Issue #29 R9: command_succeeds gates must not reference Holtz plugin paths."""
        import tomllib
        toml_path = os.path.join(REPO_ROOT, "enforcement", "transitions.toml")
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        holtz_paths = ["skills/holtz/", "hooks/", "enforcement/hooks/"]
        for transition in data.get("transitions", []):
            for gate in transition.get("gates", []):
                if gate.get("type") != "command_succeeds":
                    continue
                cmd = gate.get("cmd", "")
                for path in holtz_paths:
                    assert path not in cmd, (
                        f"Gate command references Holtz path '{path}': {cmd}\n"
                        f"Transition: {transition.get('command')} "
                        f"({transition.get('from')} -> {transition.get('to')})"
                    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestTransitionsToml -v`
Expected: FAIL — the mypy gates at lines 129 and 169 contain Holtz paths.

- [ ] **Step 3: Remove the Holtz-specific mypy gates**

In `enforcement/transitions.toml`, remove line 129 (perspective completion mypy gate):

```toml
    { type = "command_succeeds", cmd = "mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/", timeout = 60, intent = "no type errors" },
```

And remove line 169 (converge mypy gate):

```toml
    { type = "command_succeeds", cmd = "mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/", timeout = 60, intent = "no type errors" },
```

Also remove line 173 (converge sweep evidence check — also references a Holtz-internal script):

```toml
    { type = "command_succeeds", cmd = "python enforcement/scripts/check_sweep_evidence.py --min-reads 30", timeout = 15, intent = "final sweep must demonstrate substantive code reading" },
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestTransitionsToml -v`
Expected: PASS.

Run: `python -m pytest -x -q`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add enforcement/transitions.toml tests/test_protocol_enforcement.py
git commit -m "fix(hooks): remove Holtz-specific paths from transition gates

Issue #29 R9. The perspective completion and convergence gates ran mypy
against Holtz plugin paths (skills/holtz/scripts/, hooks/, enforcement/hooks/),
which don't exist in target projects. This permanently blocked lens rotation
and convergence for any non-Holtz audit."
```

---

### Task 6: Run full suite and lint

- [ ] **Step 1: Run full test suite with linting and type checking**

```bash
python -m pytest -x -q
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Expected: All pass, no errors.

- [ ] **Step 2: Fix any issues found**

If any test, lint, or type error is found, fix it before proceeding.

"""Canonical hook runner — single implementation for all hook subprocess tests.

Do NOT create local _run_hook functions in test files.
See PAT-001 (dual-parser-divergence).
"""
from __future__ import annotations

import json
import subprocess
import sys


def run_hook(
    hook_path: str,
    event: dict,
    *,
    timeout: int = 10,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Run a hook via subprocess — the same interface Claude Code uses.

    Returns a dict that is EITHER:
    - The parsed JSON output from the hook, OR
    - A metadata dict with keys prefixed by '_' if the hook produced
      no output or unparseable output:
        _empty: True if stdout was empty (stop-allow or silent PostToolUse)
        _parse_error: True if stdout was not valid JSON
        _raw_stdout: raw stdout string (on parse error)

    ``_stderr`` and ``_returncode`` are attached in **all three** cases.
    They used to be attached only on the empty and parse-error paths, which
    made a hook that printed valid JSON undiagnosable: its stderr was
    discarded, so a test could see only that the decision was wrong and never
    why. Worse, `run_enforcement_hook` reads the exit code as
    ``output.pop("_returncode", 0)`` — with the key absent, every
    ``assert code == 0`` in the suite was asserting the default rather than
    the process's real status.
    """
    result = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
    )
    stdout = result.stdout.strip()
    if not stdout:
        return {"_empty": True, "_returncode": result.returncode,
                "_stderr": result.stderr}
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw_stdout": stdout,
                "_stderr": result.stderr, "_returncode": result.returncode}
    if isinstance(parsed, dict):
        # setdefault, not assignment: a hook that ever emitted these keys
        # itself is describing its own run, and the harness must not overwrite
        # what the thing under test said.
        parsed.setdefault("_stderr", result.stderr)
        parsed.setdefault("_returncode", result.returncode)
    return parsed

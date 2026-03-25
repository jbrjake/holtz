# Audit 3 -- Adversarial Code Audit (Batch 1)

**Auditor:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-24
**Status:** DONE_WITH_CONCERNS

Audited 9 files (4 scripts, 5 hooks) with focus on error paths, boundary
conditions, state transitions, edge cases. Files ordered by churn (highest
first). This codebase has been through 13 prior runs -- findings below are
the subtle issues that survived.

---

## validate_punchlist.py (584 lines, churn 7)

### Finding VP-1: Acceptance criteria check operates on masked content (line 232-234)

**Severity:** MEDIUM
**Type:** Logic error / silent wrong result

The acceptance criteria checkbox detection (`- [ ]`, `- [x]`, `- [X]`) is
performed on `ac_content` extracted from `masked_block` (line 232-233). If
a punchlist item's acceptance criteria contain checkboxes inside a code
fence (e.g., showing example checkbox syntax), those checkboxes are blanked
by masking and will not be detected. Conversely, if the *only* checkboxes
are inside a code fence, `has_acceptance_criteria` will be `False` even
though the section visually contains them.

More critically: if a *real* checkbox is outside a code fence but the
`SECTION_RE` boundary for `Acceptance Criteria` stops before that checkbox
(because the next field header appears first), the checkbox is missed.

This is inconsistent with `_section_from_original()` which extracts
content from `original_block`. The AC check should either use
`_section_from_original('Acceptance Criteria')` and check for checkboxes
in the original content, or the current behavior should be documented as
intentional.

**Impact:** An item with checkboxes only inside a code fence (unusual but
possible in examples) would fail validation with a false "missing
acceptance criteria" error.

### Finding VP-2: Validation command extraction fails when fence is on same line as header (line 243-248)

**Severity:** LOW
**Type:** Edge case

The validation command regex (`_vc_header`) requires `\n` after the header
before the fence opener:

```
r'\*\*Validation Command:\*\*[ \t]*\n(?:[ \t]*\n)* {0,3}(`{3,}|~{3,})[^\n]*\n'
```

This means a punchlist item formatted as:

```
**Validation Command:** ```bash
echo "test"
```
```

would not be recognized (no newline between header and fence). The
CommonMark spec requires fences to be on their own line, so this is
arguably correct behavior. However, if an author places backticks inline
after the header (which is visually plausible), the validation command
will be silently empty and the item will fail validation.

**Impact:** Low. The format is uncommon and the validation error would be
visible immediately.

### Finding VP-3: `resolved_before` filter has off-by-one semantic ambiguity (lines 304-309)

**Severity:** LOW
**Type:** Boundary condition

The filter keeps RESOLVED items where `resolution_order > max_order - resolved_before`.
With `resolved_before=3` and `max_order=10`, items with `resolution_order > 7`
are kept (orders 8, 9, 10 = 3 items). This is correct for "keep the N most
recently resolved."

However, the parameter is named `resolved_before` and documented as "exclude
RESOLVED items resolved more than N fixes ago." With 10 resolved items and
`resolved_before=3`, "more than 3 fixes ago" means items resolved 4+ fixes
ago should be excluded, keeping items resolved 1-3 fixes ago. The filter
keeps orders 8-10, which are indeed the 3 most recent. The naming is
confusing but the logic is correct.

No code fix needed, but the parameter name invites misuse at call sites.

### Finding VP-4: `render_items` always re-parses masked content (line 341)

**Severity:** LOW
**Type:** Performance / missed optimization

`render_items()` calls `mask_code_fences(original_content)` on line 341
even though the caller (`main()`) already computed `precomputed` on line
523. The precomputed tuple is passed to `parse_punchlist` and `validate`
but not to `render_items`. On large punchlist files with many code fences,
this doubles the masking work.

---

## convergence_check.py (429 lines)

### Finding CC-1: Partial deletion check can block legitimate item consolidation (lines 318-325)

**Severity:** MEDIUM
**Type:** False positive / logic constraint

The partial deletion check compares `curr_pl["total"]` against
`prev_max_total` (max total across all history entries except the last).
If an auditor legitimately consolidates duplicate items (e.g., merging
BH-003 and BH-007 into one item because they're the same bug), total
drops and the check returns:

```
ITEMS DELETED: 1 item(s) disappeared from punchlist
```

The code's comment acknowledges "equal-count replacement" is invisible,
but does not acknowledge that consolidation (a valid workflow) triggers
a false deletion alarm. The check happens before the convergence check,
so this blocks convergence even when all remaining items are resolved.

**Impact:** An auditor who consolidates duplicates must either accept
the false alarm or add dummy items to compensate. The existing comment
on line 315 mentions "equal-count replacement" but not consolidation.

### Finding CC-2: `count_items` double-counts `unknown` in `total` (line 61)

**Severity:** INFO
**Type:** Correct but fragile

`counts["total"] = sum(counts.values())` on line 61. At this point,
`counts` contains OPEN, IN PROGRESS, RESOLVED, DEFERRED, and `unknown`.
`sum()` correctly includes `unknown` in the total. However, if a future
maintainer adds a non-count key to the dict (e.g., a metadata field),
`sum()` will include it. The pattern `sum(v for v in counts.values() if isinstance(v, int))`
or an explicit enumeration would be more defensive. Current code is
correct.

### Finding CC-3: `detect_test_runner` reads entire file for comment-check (lines 93-100)

**Severity:** LOW
**Type:** Edge case in validation

For `pyproject.toml`, the regex checks for `^\[tool\.pytest[\].]` at
line start. This correctly rejects a comment like
`# we considered [tool.pytest]`. However, a TOML file with a multi-line
string containing `[tool.pytest.ini_options]` at line start would
false-positive:

```toml
description = """
[tool.pytest.ini_options]
This is just documentation, not actual config.
"""
```

This is very unlikely in practice (TOML multi-line strings rarely
contain section headers), but the check is not TOML-aware.

**Impact:** Negligible. If triggered, pytest would be detected when
another runner is correct, but the test output parser would then fail
to parse and return `None`, causing no false data.

### Finding CC-4: Stall detection window inconsistency with minimum history (lines 360-371)

**Severity:** INFO
**Type:** Design observation

Stall detection requires `len(history) >= 4` and examines `history[-4:]`.
The main convergence check requires only 3 entries and examines
`history[-3:]`. This means stall detection is silently skipped for the
first 3 iterations. This is correct (you need 4 data points to detect
3 consecutive stalls), but it means the stall warning never fires until
iteration 4+, while convergence can be declared at iteration 3. A
scenario where iterations 1-3 have identical non-zero open counts would
report "IN PROGRESS" rather than "STALLED."

No fix needed. The asymmetry is intentional and documented by the
`len(history) >= 4` guard.

---

## impact_graph.py (435 lines)

### Finding IG-1: `drift_check` stops at first match per file, misses relocated duplicates (lines 300-304)

**Severity:** LOW
**Type:** Silent wrong result

`drift_check` iterates lines and breaks on the first pattern match
(line 303: `found_line = i; break`). If a file has two functions with
the same name (e.g., one in a class, one module-level), the check
always finds the first occurrence. If the node's recorded line matches
the second occurrence but the first occurrence is within the drift
threshold, drift_check reports no drift even though the entity
actually moved.

Python allows same-name functions in nested scopes, and the
`entity_name` is extracted after `::` which strips the file prefix
but not class prefixes. For a node ID like `foo.py::bar`, if `bar`
exists as both a module-level function and a method in a class, the
first occurrence wins.

**Impact:** Low. Duplicate function names at module level are rare.
The drift threshold (10 lines) further reduces practical impact.

### Finding IG-2: `prune_missing` modifies `self.nodes` during iteration via `prune_node` (lines 260-273)

**Severity:** INFO
**Type:** Correct but fragile

`prune_missing` collects node IDs to remove into `to_remove` list,
then calls `prune_node` for each. `prune_node` does
`del self.nodes[node_id]` (line 255), which modifies the dict that
was being iterated in the `for node_id, node in self.nodes.items()`
loop on line 263. However, because the iteration is complete before
any deletion begins (the two-phase collect-then-delete pattern), this
is safe. The code is correct.

### Finding IG-3: `add_edge` returns a plain dict on error, not a node dict (lines 138-141)

**Severity:** INFO
**Type:** API inconsistency

`add_edge` returns `{"error": ...}` when source/target don't exist,
but the CLI handler on line 385-387 checks `"error" in result` and
exits with code 1. The issue is that `add_edge` on success returns
the edge dict, but on error returns a different-shaped dict. Callers
must check for "error" key before using the result. This is consistent
across the module (same pattern in `update_risk`, `prune_node`) but
could benefit from a typed return or exception.

### Finding IG-4: `drift_check` entity patterns do not cover decorated functions (lines 26-38)

**Severity:** LOW
**Type:** False positive potential

Python functions decorated with `@` have the decorator above the `def`
line. The patterns correctly match `def name(` regardless of decorators
because they use `^[ \t]*` prefix. However, if a function is defined
via assignment (e.g., `bar = lambda x: x` or `bar = some_factory("bar")`),
the pattern will not find it and will report `entity_missing`.

This is documented by the pattern names ("function", "class", "test")
and is a known limitation. Lambda-assigned names would be false
positives in drift_check.

---

## markdown_utils.py (81 lines)

### Finding MU-1: `_TILDE_CLOSE_TMPL` allows trailing content after fence (line 11)

**Severity:** MEDIUM
**Type:** CommonMark spec deviation

The tilde close template is:
```
r'^ {0,3}~{%d,}[ \t]*$'
```

Per CommonMark spec (section 4.5), closing code fences must NOT have
any content after the fence characters (except optional spaces/tabs).
The template correctly enforces `[ \t]*$` -- only horizontal whitespace
allowed after the tildes. This is correct.

However, the tilde OPEN regex (`_TILDE_OPEN`, line 9) is:
```
r'^( {0,3})(~{3,}).*$'
```

The `.*$` at the end accepts any info string, which is correct per
CommonMark (tilde fences allow any info string content). The backtick
open regex uses `[^`]*$` to reject backticks in info strings, which
is also correct.

No bug here. Both patterns are CommonMark-compliant.

### Finding MU-2: `mask_code_fences` blanks fence delimiter lines themselves (line 66-67)

**Severity:** INFO
**Type:** Design decision with downstream effects

When `fenced` is True, the line is blanked -- including the opening
and closing fence delimiters themselves. This means any content on the
same line as a fence delimiter (which would be the info string for
openers) is also blanked. This is correct for masking purposes, but
downstream consumers should be aware that fence delimiters are not
preserved in masked output.

`validate_punchlist.py` correctly handles this by searching for field
headers in `masked_block` (where fence lines are blank) and then
extracting content from `original_block`.

---

## hooks/_common.py (79 lines)

### Finding HC-1: `exit_ok` omits `hookSpecificOutput` for non-PreToolUse events (lines 42-50)

**Severity:** INFO
**Type:** API asymmetry

`exit_ok()` only includes `hookSpecificOutput` when called with
`event_name="PreToolUse"`. For PostToolUse and SubagentStop hooks,
it outputs `{"continue": true, "suppressOutput": true}` without
`hookSpecificOutput`. The Claude Code hook protocol documentation
states hooks should exit 0 with JSON -- the simpler format works
but differs from the PreToolUse format.

This is intentional per the docstring: "avoids phantom 'hook error'
label in the Claude Code UI." PostToolUse hooks don't need
`permissionDecision` since the tool already ran. No fix needed.

---

## hooks/artifact_verification.py (58 lines)

### Finding AV-1: `--graph` argument extraction misses equals-sign syntax (line 29)

**Severity:** MEDIUM
**Type:** Silent wrong path

The regex for extracting the graph path is:
```
r'--graph[ \t]+["\']?([^"\'\s]+)["\']?'
```

This matches `--graph path/to/file` and `--graph "path/to/file"`.
It does NOT match `--graph=path/to/file` (equals-sign syntax), which
is accepted by argparse in `impact_graph.py`. If a user runs:

```bash
python impact_graph.py add_node --graph=custom/graph.json x func x.py
```

The regex fails to match, `match` is `None`, and the hook falls back
to the default path `docs/holtz/impact-graph.json`. The hook then
checks if that default file exists, potentially giving a false positive
warning about a missing file when the actual graph is at
`custom/graph.json`.

**Impact:** The hook warns about the wrong file. The actual graph
operation succeeds, but the PostToolUse hook emits a spurious warning.
This only matters when `--graph=` syntax is used, which is valid
Python argparse.

**Fix:** Change the regex to:
```
r'--graph[= \t]+["\']?([^"\'\s]+)["\']?'
```

### Finding AV-2: Regex for detecting impact_graph.py invocations may miss pipenv/poetry prefixes (line 25)

**Severity:** LOW
**Type:** Incomplete detection

The regex `r'(?:^|[\s/])impact_graph\.py\b'` matches commands where
`impact_graph.py` appears after whitespace, `/`, or at string start.
Commands like:

```bash
pipenv run python scripts/impact_graph.py add_node ...
poetry run python impact_graph.py add_node ...
```

would be matched (because of `[\s/]`). However, a command using a
full path without spaces:

```bash
/usr/local/bin/python3 /home/user/project/scripts/impact_graph.py ...
```

would also match (because of `/` before `impact_graph.py`). This
appears complete for common invocation patterns.

---

## hooks/impact_graph_gate.py (57 lines)

### Finding IG-GATE-1: Justine audit directory check does not cover all audit-related paths (lines 32-38)

**Severity:** LOW
**Type:** Incomplete gating

The gate checks for `docs/holtz/justine/audit/` in `normalized` for
Justine paths. If a Justine-related file is written to a path like
`docs/holtz/justine/recon/` or `docs/holtz/justine/HISTORY.json`,
the gate does not trigger. This may be intentional (only audit files
and punchlist require the impact graph), but `recon/` files are also
audit artifacts.

The Holtz path check has the same gap -- it only gates
`docs/holtz/audit/` and the two punchlist files. Writing to
`docs/holtz/recon/` or `docs/holtz/HISTORY.json` is ungated.

**Impact:** Low. The status_staleness_gate catches staleness for all
`docs/holtz/` writes. The impact_graph_gate is narrower by design.

---

## hooks/status_staleness_gate.py (86 lines)

### Finding SSG-1: `time.time()` vs `os.path.getmtime()` clock skew (lines 70-74)

**Severity:** LOW
**Type:** Environmental edge case

`time.time()` returns wall-clock time. `os.path.getmtime()` returns
the file's modification time from the filesystem. If the system clock
is adjusted (NTP sync, DST change, manual set) between the file write
and the gate check, `age` could be negative (STATUS.md appears "from
the future") or much larger than expected.

A negative `age` would pass the staleness check (age < 300), which is
the safe direction. A sudden clock-forward jump could cause a false
block.

**Impact:** Negligible in practice. NTP adjustments are typically
sub-second. Manual clock changes during an audit session would be
unusual.

### Finding SSG-2: Gate does not check `event_name` for PreToolUse (lines 24-82)

**Severity:** INFO
**Type:** Defensive programming

The hook reads the event but does not verify `event.get("event_name")
== "PreToolUse"`. If accidentally registered for a PostToolUse event,
it would still attempt to block using `exit_block()`, which emits
a `permissionDecision: "block"` response. PostToolUse hooks cannot
actually block (the tool already ran), so the JSON would be ignored
or cause a UI anomaly.

All hooks in this codebase have the same pattern. Since hook
registration is in `.claude/settings.json` (not in the hooks
themselves), this is a deployment concern, not a code bug.

---

## hooks/subagent_findings_check.py (59 lines)

### Finding SFC-1: Path regex may match non-file-path text (line 33)

**Severity:** LOW
**Type:** False positive

The regex `r'docs/holtz/[^\s"\')\]]+\.md'` matches any text containing
`docs/holtz/...something....md`. In a subagent message discussing a
path (e.g., "the file docs/holtz/nonexistent-concept.md should be
created"), the hook would extract the path and warn that it does not
exist, even though the subagent was describing a future action, not
claiming the file exists.

The docstring (lines 9-12) explicitly documents this as acceptable
behavior: "Paths mentioned in code examples may trigger false-positive
warnings. This is acceptable because the hook only warns (exit_warn)
and false positives are preferable to missed findings."

No fix needed. This is a documented tradeoff.

---

## Summary

| File | Findings | Highest Severity |
|---|---|---|
| validate_punchlist.py | 4 | MEDIUM (VP-1) |
| convergence_check.py | 4 | MEDIUM (CC-1) |
| impact_graph.py | 4 | LOW |
| markdown_utils.py | 2 | INFO |
| _common.py | 1 | INFO |
| artifact_verification.py | 2 | MEDIUM (AV-1) |
| impact_graph_gate.py | 1 | LOW |
| status_staleness_gate.py | 2 | LOW |
| subagent_findings_check.py | 1 | LOW |

**Actionable findings (recommend fixing):**

1. **AV-1** (artifact_verification.py:29): `--graph=` equals-sign syntax not matched.
   Simple regex fix, prevents spurious warnings for valid invocations.

2. **VP-1** (validate_punchlist.py:232-234): Acceptance criteria checked on masked
   content. Should use `_section_from_original` for consistency with Problem/Evidence.

3. **CC-1** (convergence_check.py:318-325): Partial deletion check blocks legitimate
   consolidation. Consider adding a `--allow-consolidation` flag or a comment
   in the output message explaining consolidation as a valid reason.

**Not actionable (correct behavior, documented tradeoffs, or negligible risk):**
VP-2, VP-3, VP-4, CC-2, CC-3, CC-4, IG-1 through IG-4, MU-1, MU-2, HC-1,
AV-2, IG-GATE-1, SSG-1, SSG-2, SFC-1.

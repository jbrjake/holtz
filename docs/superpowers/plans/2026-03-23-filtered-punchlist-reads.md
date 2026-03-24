# Filtered Punchlist Reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add filtered output modes to `validate_punchlist.py` so Phases 4-6 can load only relevant punchlist items, reducing context pressure during the convergence loop which scales linearly with lens count.

**Architecture:** Extend the existing `parse_punchlist` / `validate` pipeline with a `filter_items` function and new CLI flags. The filter operates on already-parsed `PunchlistItem` objects. A `--resolved-before N` flag filters out items resolved more than N fixes ago (not a flat status filter), preserving recently-resolved items for pattern recognition. A resolution sequence number is derived from the punchlist's Resolution fields (commit order). The `render_items` function outputs filtered items in valid punchlist markdown format so the output can be read directly by the agent.

**Tech Stack:** Python 3.11+, pytest, existing `markdown_utils.py` and `validate_punchlist.py`

---

### Task 1: Add resolution sequence tracking to PunchlistItem

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py:28-45` (PunchlistItem dataclass)
- Test: `tests/test_validate_punchlist.py`

The recency window needs a concept of "when was this item resolved relative to other items." The simplest approach: assign a resolution_order integer to each RESOLVED item based on its position in the punchlist (items are ordered by severity then ID, and resolutions happen sequentially — the Resolution field's commit hash establishes order, but position in the file is a good-enough proxy since items are resolved top-down during the fix loop).

- [ ] **Step 1: Write the failing test**

```python
def test_resolution_order_assigned_to_resolved_items(make_item):
    """Resolved items get a resolution_order based on position among resolved items."""
    content = (
        make_item(item_id="BH-001", status="RESOLVED",
                  resolution="Fixed in commit a1b2c3d")
        + make_item(item_id="BH-002", status="OPEN")
        + make_item(item_id="BH-003", status="RESOLVED",
                  resolution="Fixed in commit d4e5f6a")
        + make_item(item_id="BH-004", status="RESOLVED",
                  resolution="Fixed in commit f7a8b9c")
    )
    items = vp.parse_punchlist(content)
    resolved = [i for i in items if i.status == "RESOLVED"]
    assert resolved[0].resolution_order == 1  # BH-001, first resolved
    assert resolved[1].resolution_order == 2  # BH-003, second resolved
    assert resolved[2].resolution_order == 3  # BH-004, third resolved
    # Non-resolved items get 0
    assert items[1].resolution_order == 0  # BH-002, OPEN


def test_resolution_order_zero_for_non_resolved(make_item):
    """OPEN, IN PROGRESS, and DEFERRED items have resolution_order 0."""
    content = (
        make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="IN PROGRESS")
        + make_item(item_id="BH-003", status="DEFERRED")
    )
    items = vp.parse_punchlist(content)
    assert all(i.resolution_order == 0 for i in items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py::test_resolution_order_assigned_to_resolved_items -v`
Expected: FAIL — `PunchlistItem` has no `resolution_order` field

- [ ] **Step 3: Add resolution_order field and assignment logic**

In `validate_punchlist.py`, add to the `PunchlistItem` dataclass:

```python
resolution_order: int = 0
```

At the end of `parse_punchlist`, after all items are parsed, assign resolution order:

```python
resolved_counter = 0
for item in items:
    if item.status == "RESOLVED":
        resolved_counter += 1
        item.resolution_order = resolved_counter
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py -v`
Expected: All tests PASS including existing ones

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py tests/test_validate_punchlist.py
git commit -m "feat(scripts): add resolution_order tracking to PunchlistItem"
```

---

### Task 2: Add filter_items function

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py` (add `filter_items` function after `parse_punchlist`)
- Test: `tests/test_validate_punchlist.py`

The core filtering logic. `filter_items` takes a list of parsed items and filter parameters, returns a filtered list. Two filter modes that can combine:

- `status_include`: only include items with these statuses (e.g., `{"OPEN", "IN PROGRESS"}`)
- `resolved_before`: exclude RESOLVED items whose `resolution_order` is <= `max_resolution_order - N` (i.e., keep only the N most recently resolved items)

- [ ] **Step 1: Write the failing tests**

```python
def test_filter_items_by_status(make_item):
    """Filter to only OPEN items."""
    content = (
        make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
        + make_item(item_id="BH-003", status="OPEN")
        + make_item(item_id="BH-004", status="DEFERRED")
    )
    items = vp.parse_punchlist(content)
    filtered = vp.filter_items(items, status_include={"OPEN"})
    assert [i.id for i in filtered] == ["BH-001", "BH-003"]


def test_filter_items_resolved_before(make_item):
    """Keep only the 2 most recently resolved items."""
    content = (
        make_item(item_id="BH-001", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in b2c3d4e")
        + make_item(item_id="BH-003", status="RESOLVED",
                  resolution="Fixed in c3d4e5f")
        + make_item(item_id="BH-004", status="OPEN")
    )
    items = vp.parse_punchlist(content)
    # resolved_before=2 means: keep RESOLVED items within the last 2 resolutions
    # BH-001 is resolution_order=1 (oldest), BH-002=2, BH-003=3 (newest)
    # max_order=3, cutoff=3-2=1, so keep items with order > 1
    # BH-001 (order=1) filtered OUT, BH-002 (order=2) kept, BH-003 (order=3) kept
    filtered = vp.filter_items(items, resolved_before=2)
    ids = [i.id for i in filtered]
    assert "BH-001" not in ids  # oldest resolved, filtered out
    assert "BH-002" in ids     # within recency window
    assert "BH-003" in ids     # most recent, kept
    assert "BH-004" in ids     # OPEN, always kept


def test_filter_items_combined(make_item):
    """status_include + resolved_before combine: OPEN items always pass,
    RESOLVED items checked against recency window."""
    content = (
        make_item(item_id="BH-001", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in b2c3d4e")
        + make_item(item_id="BH-003", status="OPEN")
        + make_item(item_id="BH-004", status="IN PROGRESS")
    )
    items = vp.parse_punchlist(content)
    # Include OPEN + IN PROGRESS + recently resolved (within last 1)
    filtered = vp.filter_items(
        items,
        status_include={"OPEN", "IN PROGRESS", "RESOLVED"},
        resolved_before=1,
    )
    ids = [i.id for i in filtered]
    assert "BH-001" not in ids  # resolved too long ago
    assert "BH-002" in ids     # most recently resolved
    assert "BH-003" in ids     # OPEN
    assert "BH-004" in ids     # IN PROGRESS


def test_filter_items_no_filters_returns_all(make_item):
    """No filter parameters returns all items unchanged."""
    content = (
        make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
    )
    items = vp.parse_punchlist(content)
    filtered = vp.filter_items(items)
    assert len(filtered) == 2


def test_filter_items_resolved_before_with_no_resolved(make_item):
    """resolved_before with no RESOLVED items returns all items."""
    content = (
        make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="IN PROGRESS")
    )
    items = vp.parse_punchlist(content)
    filtered = vp.filter_items(items, resolved_before=3)
    assert len(filtered) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py::test_filter_items_by_status -v`
Expected: FAIL — `filter_items` does not exist

- [ ] **Step 3: Implement filter_items**

Add after `parse_punchlist` in `validate_punchlist.py`:

```python
def filter_items(
    items: list[PunchlistItem],
    *,
    status_include: set[str] | None = None,
    resolved_before: int | None = None,
) -> list[PunchlistItem]:
    """Filter parsed punchlist items by status and/or resolution recency.

    Args:
        items: Parsed punchlist items (with resolution_order assigned).
        status_include: If set, only include items with these statuses.
        resolved_before: If set, exclude RESOLVED items resolved more than N
            fixes ago. Items with other statuses are always included.
            The N most recently resolved items are kept.

    Returns:
        Filtered list of PunchlistItem objects.
    """
    if status_include is None and resolved_before is None:
        return list(items)

    max_order = max((i.resolution_order for i in items), default=0)

    result = []
    for item in items:
        # Status filter
        if status_include is not None and item.status not in status_include:
            continue

        # Recency filter for RESOLVED items
        if (
            resolved_before is not None
            and item.status == "RESOLVED"
            and item.resolution_order > 0
            and item.resolution_order <= max_order - resolved_before
        ):
            continue

        result.append(item)

    return result
```

- [ ] **Step 4: Run all filter tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py -k "filter_items" -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/ -v`
Expected: All PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py tests/test_validate_punchlist.py
git commit -m "feat(scripts): add filter_items with status and recency filtering"
```

---

### Task 3: Add render_items function for filtered markdown output

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py` (add `render_items` function)
- Test: `tests/test_validate_punchlist.py`

The filtered output needs to be valid punchlist markdown that the agent can read directly. `render_items` takes the original punchlist content and a filtered item list, extracts the raw markdown blocks for those items, and outputs them with a header showing filter metadata.

- [ ] **Step 1: Write the failing tests**

```python
def test_render_items_includes_header_and_stats(make_item):
    """Rendered output includes a filter header and item count."""
    content = make_item(item_id="BH-001", status="OPEN", wrap=True)
    items = vp.parse_punchlist(content)
    output = vp.render_items(content, items)
    assert "# Holtz Punchlist" in output
    assert "BH-001" in output


def test_render_items_only_filtered_items(make_item):
    """Only items in the filtered list appear in output."""
    content = (
        "# Holtz Punchlist\n> Generated: 2026-03-22\n\n"
        "## Summary\n\n## Patterns\n\n## Items\n\n"
        + make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
    )
    all_items = vp.parse_punchlist(content)
    filtered = [i for i in all_items if i.status == "OPEN"]
    output = vp.render_items(content, filtered)
    assert "BH-001" in output
    assert "BH-002" not in output


def test_render_items_shows_filter_metadata(make_item):
    """Output includes metadata about what was filtered."""
    content = (
        "# Holtz Punchlist\n> Generated: 2026-03-22\n\n"
        "## Summary\n\n## Patterns\n\n## Items\n\n"
        + make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
        + make_item(item_id="BH-003", status="RESOLVED",
                  resolution="Fixed in b2c3d4e")
    )
    all_items = vp.parse_punchlist(content)
    filtered = vp.filter_items(all_items, resolved_before=1)
    output = vp.render_items(content, filtered, total_count=len(all_items))
    assert "showing 2 of 3" in output.lower() or "2/3" in output


def test_render_items_preserves_original_markdown(make_item):
    """Item markdown is extracted verbatim from source, not reconstructed."""
    content = (
        "# Holtz Punchlist\n> Generated: 2026-03-22\n\n"
        "## Summary\n\n## Patterns\n\n## Items\n\n"
        + make_item(item_id="BH-001", status="OPEN",
                  problem="A very specific problem description here.")
    )
    items = vp.parse_punchlist(content)
    output = vp.render_items(content, items)
    assert "A very specific problem description here." in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py::test_render_items_includes_header_and_stats -v`
Expected: FAIL — `render_items` does not exist

- [ ] **Step 3: Implement render_items**

Add to `validate_punchlist.py`:

```python
def render_items(
    original_content: str,
    items: list[PunchlistItem],
    *,
    total_count: int | None = None,
) -> str:
    """Render filtered punchlist items as valid punchlist markdown.

    Extracts item blocks verbatim from the original content rather than
    reconstructing them, preserving all formatting and fields.

    Args:
        original_content: The full original punchlist markdown.
        items: Filtered list of items to include.
        total_count: Total items before filtering (for metadata line).

    Returns:
        Valid punchlist markdown containing only the specified items.
    """
    if not items:
        showing = f"0 of {total_count}" if total_count else "0"
        return f"# Holtz Punchlist (filtered: showing {showing} items)\n\nNo items match the filter.\n"

    item_ids = {i.id for i in items}
    _, masked = mask_code_fences(original_content)

    # Find item header positions in masked content
    item_pattern = re.compile(r'^### (B[HJ]-\d+):[ \t]*(.*)$', re.MULTILINE)
    matches = list(item_pattern.finditer(masked))

    blocks = []
    for i, match in enumerate(matches):
        if match.group(1) in item_ids:
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(original_content)
            blocks.append(original_content[start:end].rstrip())

    showing = f"{len(items)} of {total_count}" if total_count else str(len(items))
    header = f"# Holtz Punchlist (filtered: showing {showing} items)\n"

    return header + "\n" + "\n\n".join(blocks) + "\n"
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py -k "render_items" -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py tests/test_validate_punchlist.py
git commit -m "feat(scripts): add render_items for filtered punchlist markdown output"
```

---

### Task 4: Add CLI flags to validate_punchlist.py

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py:387-436` (main function)
- Test: `tests/test_validate_punchlist.py`

Add `--filter-status`, `--resolved-before`, and `--render` flags. When `--render` is present, output filtered markdown instead of validation report. This separates the filtering use case from the validation use case cleanly.

- [ ] **Step 1: Write the failing tests**

```python
import subprocess


def test_cli_filter_status_render(tmp_path, make_item):
    """CLI --filter-status OPEN --render outputs only OPEN items as markdown."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(
        "# Holtz Punchlist\n> Generated: 2026-03-22\n\n"
        "## Summary\n\n## Patterns\n\n## Items\n\n"
        + make_item(item_id="BH-001", status="OPEN")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
    )
    result = subprocess.run(
        ["python", "skills/holtz/scripts/validate_punchlist.py",
         str(punchlist), "--filter-status", "OPEN", "--render"],
        capture_output=True, text=True,
        cwd="/Users/jonr/Documents/non-nitro-repos/holtz",
    )
    assert result.returncode == 0
    assert "BH-001" in result.stdout
    assert "BH-002" not in result.stdout


def test_cli_resolved_before_render(tmp_path, make_item):
    """CLI --resolved-before 1 --render keeps only the most recent resolved item."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(
        "# Holtz Punchlist\n> Generated: 2026-03-22\n\n"
        "## Summary\n\n## Patterns\n\n## Items\n\n"
        + make_item(item_id="BH-001", status="RESOLVED",
                  resolution="Fixed in a1b2c3d")
        + make_item(item_id="BH-002", status="RESOLVED",
                  resolution="Fixed in b2c3d4e")
        + make_item(item_id="BH-003", status="OPEN")
    )
    result = subprocess.run(
        ["python", "skills/holtz/scripts/validate_punchlist.py",
         str(punchlist), "--resolved-before", "1", "--render"],
        capture_output=True, text=True,
        cwd="/Users/jonr/Documents/non-nitro-repos/holtz",
    )
    assert result.returncode == 0
    assert "BH-001" not in result.stdout  # oldest resolved, filtered
    assert "BH-002" in result.stdout      # most recent resolved, kept
    assert "BH-003" in result.stdout      # OPEN, always kept


def test_cli_without_render_runs_validation(tmp_path, make_item):
    """Without --render, CLI runs normal validation (existing behavior)."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(make_item(item_id="BH-001", status="OPEN", wrap=True))
    result = subprocess.run(
        ["python", "skills/holtz/scripts/validate_punchlist.py", str(punchlist)],
        capture_output=True, text=True,
        cwd="/Users/jonr/Documents/non-nitro-repos/holtz",
    )
    # Normal validation output
    assert "Holtz Punchlist Validation" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py::test_cli_filter_status_render -v`
Expected: FAIL — unrecognized arguments

- [ ] **Step 3: Implement CLI argument parsing**

Replace the existing `main()` function with argparse-based version:

```python
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Holtz Punchlist Validator")
    parser.add_argument("path", nargs="?", default="docs/holtz/PUNCHLIST.md",
                        help="Path to punchlist file")
    parser.add_argument("--filter-status", nargs="+", metavar="STATUS",
                        help="Only include items with these statuses (OPEN, RESOLVED, etc.)")
    parser.add_argument("--resolved-before", type=int, metavar="N",
                        help="Keep only the N most recently resolved items")
    parser.add_argument("--render", action="store_true",
                        help="Output filtered items as markdown instead of validation report")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)

    content = path.read_text()
    precomputed = mask_code_fences(content)
    items = parse_punchlist(content, _masked=precomputed)

    if not items:
        print(f"ERROR: No punchlist items found in {path}")
        if has_unclosed_fence(content):
            print("HINT: File contains an unclosed code fence — content after the fence is invisible to the parser")
        sys.exit(1)

    # Filter mode
    if args.filter_status or args.resolved_before is not None:
        status_set = set(args.filter_status) if args.filter_status else None
        filtered = filter_items(
            items,
            status_include=status_set,
            resolved_before=args.resolved_before,
        )
        if args.render:
            print(render_items(content, filtered, total_count=len(items)))
            sys.exit(0)
        else:
            # Validate only filtered items
            items = filtered

    elif args.render:
        # Render all items (no filter)
        print(render_items(content, items, total_count=len(items)))
        sys.exit(0)

    # Normal validation (existing behavior)
    result = validate(items, content, masked_content=precomputed[1])

    print(f"\n{'='*60}")
    print(f"Holtz Punchlist Validation: {path}")
    print(f"{'='*60}")
    print(f"\nTotal items: {result.stats['total_items']}")
    print(f"By status:   {result.stats['by_status']}")
    print(f"By severity: {result.stats['by_severity']}")
    print(f"Top categories: {dict(result.stats['by_category'][:5])}")

    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")

    if result.warnings:
        print(f"\nWARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  - {w}")

    if not result.errors and not result.warnings:
        print("\nAll items valid")

    open_critical = sum(1 for i in items if i.severity == "CRITICAL" and i.status == "OPEN")
    if open_critical:
        print(f"\n{open_critical} CRITICAL items still OPEN")

    sys.exit(1 if result.errors else 0)
```

- [ ] **Step 4: Run CLI tests**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/test_validate_punchlist.py -k "cli_" -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && python -m pytest tests/ -v`
Expected: All PASS — existing tests that call `main()` via subprocess should still work since positional arg is optional and defaults are preserved.

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py tests/test_validate_punchlist.py
git commit -m "feat(scripts): add --filter-status, --resolved-before, --render CLI flags"
```

---

### Task 5: Update SKILL.md Phase 4-6 to use filtered reads

**Files:**
- Modify: `skills/holtz/SKILL.md:209-298` (Phases 4, 5, 6)
- Modify: `skills/holtz/references/justine-skill.md:224-304` (Justine's Phases 4, 5, 6)

Update the skill instructions to use filtered punchlist reads when the punchlist exceeds a threshold. The threshold should be conservative (6+ items) to avoid overhead on small punchlists.

- [ ] **Step 1: Update SKILL.md Phase 4**

In Phase 4, step 1 currently says "Re-read worklist". Change to:

```markdown
1. **Re-read worklist** — If `docs/holtz/PUNCHLIST-MERGED.md` exists, use it. Otherwise, use `docs/holtz/PUNCHLIST.md`. **If the punchlist has more than 6 items**, use filtered reads to reduce context load:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/validate_punchlist.py <punchlist-path> --filter-status OPEN "IN PROGRESS" --resolved-before 3 --render
   ```
   This shows all OPEN/IN PROGRESS items plus the 3 most recently resolved items (for cross-item pattern recognition). Items resolved earlier are on disk and available in Phase 5.
```

- [ ] **Step 2: Update SKILL.md Phase 5**

In Phase 5, step 1 currently says "Re-read `docs/holtz/PUNCHLIST.md`". Change to:

```markdown
1. **Re-read `docs/holtz/PUNCHLIST.md`** — For pattern analysis, read the full punchlist (no filter). Pattern grouping requires seeing all resolved items to identify shared root causes across the complete history.
```

(Phase 5 is explicitly the pattern analysis phase — it SHOULD see everything. No filter here.)

- [ ] **Step 3: Update SKILL.md Phase 6 convergence loop**

In the Phase 6 convergence loop, the `recover` node says "Read STATUS.md + PUNCHLIST.md". Update:

```markdown
recover [label="Read STATUS.md\n+ PUNCHLIST.md\n(filtered: OPEN + last 3 resolved)"]
```

And add a note after the convergence graph:

```markdown
**Filtered reads in convergence loop:** Each iteration re-reads the punchlist. If the punchlist has more than 6 items, use:
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/validate_punchlist.py <path> --filter-status OPEN "IN PROGRESS" --resolved-before 3 --render
```
This keeps recently-resolved items visible for pattern recognition while filtering out stable old resolutions. Phase 5 (pattern analysis, every 3-5 fixes) reads the full punchlist.
```

- [ ] **Step 4: Update justine-skill.md Phases 4-6 with the same pattern**

Apply the same changes to Justine's Phase 4 and Phase 6. Justine's Phase 5 also reads the full punchlist (no filter).

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/SKILL.md skills/holtz/references/justine-skill.md
git commit -m "feat(skill): use filtered punchlist reads in Phases 4-6 convergence loop"
```

---

### Task 6: Update script usage comment in validate_punchlist.py

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py:1-14` (module docstring)

- [ ] **Step 1: Update the docstring**

```python
"""
Holtz Punchlist Validator

Parses PUNCHLIST.md files and validates:
- All items have required fields (severity, category, status, problem,
  discovery chain, acceptance criteria, validation command)
- Severity, status, and category values are from valid sets
- Resolved items have a resolution documented
- Deferred bug items have reproduction evidence or an investigation link
- Validation commands are present

Usage:
  Validate:  python validate_punchlist.py [path-to-punchlist.md]
  Filter:    python validate_punchlist.py [path] --filter-status OPEN --render
  Recency:   python validate_punchlist.py [path] --resolved-before 3 --render

Filter flags:
  --filter-status STATUS [STATUS ...]   Only include items with these statuses
  --resolved-before N                   Keep only the N most recently resolved items
  --render                              Output filtered markdown instead of validation report
"""
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py
git commit -m "docs(scripts): update validate_punchlist.py usage docs for filter flags"
```

# Merge Protocol Example Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the 6 worked examples (240 lines) from `merge-protocol.md` into a separate file, reducing the merge protocol to ~150 lines of rules while keeping examples available on demand.

**Architecture:** Pure file reorganization — split `merge-protocol.md` at the "Worked Examples" heading. Add a cross-reference in each file. Update any references in SKILL.md.

**Tech Stack:** Markdown files only, no code changes.

---

### Task 1: Create merge-examples.md from worked examples

**Files:**
- Create: `skills/holtz/references/merge-examples.md`
- Source: `skills/holtz/references/merge-protocol.md:146-385`

- [ ] **Step 1: Create the examples file**

Extract lines 146-385 from `merge-protocol.md` (starting at `## Worked Examples`) into a new file `references/merge-examples.md`, with a header explaining its relationship to the protocol:

```markdown
# Merge Protocol — Worked Examples

> These examples demonstrate each of the five classification types defined in
> [merge-protocol.md](merge-protocol.md). Consult these when a specific item
> pair is ambiguous under the matching criteria.
>
> For the classification rules, processing order, and output formats,
> see [merge-protocol.md](merge-protocol.md).

{rest of lines 148-385 from merge-protocol.md, unchanged}
```

- [ ] **Step 2: Verify the file is self-contained**

Read the new file end-to-end. Confirm:
- All 6 examples are present (Agreement, Holtz-only, Justine-only, Severity Disagreement, Contradictory, Near-Miss Location Match)
- No broken cross-references to the rules section (examples should be readable standalone)
- The header cross-references back to merge-protocol.md

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/merge-examples.md
git commit -m "docs(references): extract merge protocol worked examples to separate file"
```

---

### Task 2: Trim merge-protocol.md and add cross-reference

**Files:**
- Modify: `skills/holtz/references/merge-protocol.md:146-385`

- [ ] **Step 1: Replace the Worked Examples section**

Remove lines 146-385 (the entire `## Worked Examples` section and all examples). Replace with:

```markdown
## Worked Examples

See [merge-examples.md](merge-examples.md) for worked examples of each classification type (Agreement, Holtz-only, Justine-only, Severity Disagreement, Contradictory, Near-Miss Location Match).

Consult examples when:
- A specific item pair is ambiguous under the matching criteria above
- The 5-line proximity threshold produces a borderline match
- A contradiction is suspected but not certain
```

- [ ] **Step 2: Verify merge-protocol.md is still complete**

Read the trimmed file. Confirm:
- Overview, Stall Conditions, Classification Rules, Matching Criteria, Processing Order are intact
- Output Files section (PUNCHLIST-MERGED.md and MERGE-REPORT.md formats) is intact
- Post-Merge Fix Ownership and Impact Graph Merge sections are intact
- Rules section at the end is intact
- File is approximately 150-155 lines

- [ ] **Step 3: Verify no other files reference specific example content**

Run: `cd /Users/jonr/Documents/non-nitro-repos/holtz && grep -rn "Example 1\|Example 2\|Example 3\|Example 4\|Example 5\|Example 6\|Near-Miss Location" skills/ agents/`
Expected: No hits outside the new `merge-examples.md` (no skill or agent file references specific example numbers)

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/references/merge-protocol.md
git commit -m "refactor(references): trim merge-protocol.md to rules-only, cross-reference examples"
```

---

### Task 3: Update SKILL.md reference to merge protocol

**Files:**
- Modify: `skills/holtz/SKILL.md:44` (references section)

- [ ] **Step 1: Add merge-examples to the references list**

In the References section of SKILL.md, after the merge-protocol reference, add:

```markdown
- [references/merge-examples.md](references/merge-examples.md) — worked examples for merge classification (read only if classification is ambiguous)
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "docs(skill): add merge-examples.md to references list"
```

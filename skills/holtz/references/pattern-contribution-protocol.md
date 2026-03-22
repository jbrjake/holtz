# Pattern Library Contribution Protocol

Run this protocol after convergence is reached and before writing the final summary.

## 1. Discover New Patterns

Read `docs/holtz/patterns-brief.md` (or `docs/justine/patterns-brief.md` for Justine — though Justine shares the same brief) and compare each entry against the files in `${CLAUDE_PLUGIN_ROOT}/skills/holtz/patterns/*.md`. A pattern is "new" if no global library file covers the same bug class (semantic match, not name match — a project pattern called "Unguarded Parse" matches a library file covering "Unchecked Deserialization" if they describe the same class of issue).

## 2. Generalize

For each new pattern, create a scrubbed pattern file with:
- **YAML frontmatter:** `name`, `version` (start at `1.0.0`), `discovered` (today's date), `languages` (from the project's detected languages), `categories` (relevant lens/category tags)
- **Required sections:** Description, Detection Heuristic (must be executable — a grep pattern, structural check, or command), Indicators, Example (generic, not project-specific), Related Patterns

## 3. PII Scrubbing (Mandatory)

Remove ALL of the following before any external submission:
- File paths specific to the project
- Function, class, or variable names specific to the project
- Business logic or domain terminology
- Any content that could identify the project, its authors, or its users
- Configuration values, API keys, URLs, environment details

The resulting pattern file must read as completely generic.

## 4. Ask Permission

> "This run discovered {N} patterns not in the upstream Holtz pattern library:
> - {pattern name 1}: {one-line description}
> - {pattern name 2}: {one-line description}
>
> Would you like me to submit a PR to github.com/jbrjake/holtz adding these
> to the global pattern library? All project-specific details will be scrubbed.
> You can review the PR before it's merged."

## 5. Submission Tiers (try in order 1 → 2 → 3)

**Tier 1 — `gh` CLI available:**
Verify `gh auth status` succeeds. Fork `github.com/jbrjake/holtz` (or use existing fork). Create branch `patterns/{pattern-name}`. Add scrubbed pattern file(s) to `skills/holtz/patterns/`. Open PR via `gh pr create` with title `feat(patterns): add {pattern name}` and body describing the pattern, detection heuristic, and discovery context (scrubbed).

**Tier 2 — GitHub MCP server available (no `gh` CLI):**
Check for GitHub-related MCP tools. Use MCP to fork, create branch, commit files, and open PR with the same title and body format as Tier 1.

**Tier 3 — No programmatic GitHub access:**
Write the scrubbed pattern file(s) to `docs/{auditor}/pattern-submissions/`. Generate `docs/{auditor}/pattern-submissions/PR-BODY.md` containing the PR title, full body text, and the pattern file content inline. Present:

> "I don't have programmatic access to GitHub. I've staged the pattern file(s)
> and a draft PR body at `docs/{auditor}/pattern-submissions/`. To submit:
>
> 1. Fork the repo: https://github.com/jbrjake/holtz/fork
> 2. Add the pattern file(s) to `skills/holtz/patterns/` in your fork
> 3. Open a PR using the body in `PR-BODY.md`"

## 6. If Declined

No action. The pattern remains in the project-specific pattern brief only.

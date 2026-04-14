# Contributing to Holtz

Holtz finds bugs. You can help him find more, find them better, or find them in
places he hasn't looked yet. Contributions are welcome and appreciated.

This document covers how to contribute, what we expect, and how we handle
AI-assisted code — which, given that Holtz is a Claude Code plugin, is obviously
something we think about.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold it.

## Ways to Contribute

- **Bug reports.** Holtz found a false positive? Missed something obvious?
  Filed a punchlist item against perfectly fine code? That's a bug. Report it.
- **New lenses.** The thirteen analytical lenses that ship are defaults. If you've
  found a way of looking at code that catches things the existing lenses miss,
  that's exactly the kind of contribution that makes the registry better for
  everyone.
- **New patterns.** Each seed pattern is a markdown file with a YAML header, a
  description, an executable detection heuristic, and an example. Write one for
  a bug class you keep seeing.
- **New edge types.** The seven edge types in the impact graph cover most
  relationships, but domains have their own shapes.
- **Documentation.** Holtz audits his own docs. You can too. If the README says
  something the code doesn't do, that's a finding.
- **Tests.** More tests. Better tests. Tests that catch things Holtz's own test
  suite misses. The irony would be noted and appreciated.
- **Bug fixes.** If you find something broken, fix it. See the workflow below.

## Development Setup

```bash
git clone https://github.com/jbrjake/holtz.git
cd holtz
pip install ruff mypy pytest pytest-cov hypothesis
scripts/install-hooks.sh
```

Run the test suite:

```bash
python -m pytest --tb=short -q
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

## Contribution Workflow

1. **Open an issue first** for anything non-trivial. Bug fixes, new lenses, new
   patterns, new edge types — discuss before you build. This saves everyone time,
   especially yours.

2. **Fork and branch.** Branch names: `fix/description`, `feat/description`,
   `docs/description`.

3. **Write tests first.** Holtz exists because of TDD. Contributions to Holtz
   follow TDD. Write a failing test that proves the bug exists or demonstrates
   the new behavior, then make it pass. PRs without tests will be asked to add
   them.

4. **Keep PRs small.** One logical change per PR. If your PR touches more than
   ~300 lines of non-test code, consider splitting it. Large PRs are harder to
   review and more likely to sit.

5. **Sign your commits (DCO).** See below.

6. **Open the PR.** Fill out the template. Link the issue. Describe what changed
   and why.

## Commit Messages

```
<type>: <short summary>

<optional body explaining why, not what>

Signed-off-by: Your Name <your@email.com>
```

Types: `fix`, `feat`, `perf`, `docs`, `test`, `refactor`, `chore`, `ci`, `style`.

Keep the summary under 72 characters. The body is for context that isn't obvious
from the diff. If you're fixing a punchlist item, reference it: `Fixes BH-042`.

## Developer Certificate of Origin (DCO)

All contributions must include a `Signed-off-by` line in the commit message,
certifying that you have the right to submit the code under this project's MIT
license. This is the [Developer Certificate of Origin](https://developercertificate.org/),
version 1.1.

Add it automatically:

```bash
git commit -s -m "fix: description"
```

This adds `Signed-off-by: Your Name <your@email.com>` using your git
`user.name` and `user.email` configuration.

**What DCO means for AI-assisted code:** When you sign off, you are taking
personal responsibility for the contribution — that it can be submitted under
the MIT license, that you understand what it does, and that you can maintain it.
The DCO is about accountability, not authorship methodology.

## AI-Assisted Contributions

Holtz is a Claude Code plugin. Contributors to Holtz will use AI tools. This is
expected, welcomed, and fine. What matters is quality, not how you got there.

### The rules

**You are the author.** Every line you submit is your responsibility. If you
can't explain it, debug it, and defend it as if you wrote it by hand, it isn't
ready to submit. Holtz will audit your contribution. If he finds something you
missed, that's evidence you didn't review your own output carefully enough.

**Disclose substantial AI assistance.** Use commit trailers:

```
fix: handle NaN in risk score comparisons

The min() builtin silently returns 1.0 when compared against NaN,
causing risk scores to pin to maximum. Use explicit isnan() guard.

Assisted-by: Claude <noreply@anthropic.com>
Signed-off-by: Your Name <your@email.com>
```

Use `Assisted-by:` when AI helped you write or refactor code. Use
`Generated-by:` when the code is substantially AI-generated with minimal
modification. You don't need to disclose autocomplete, grammar fixes, or using
AI to help you understand the codebase.

**Quality standards are the same.** AI-assisted code must pass every gate that
human-written code does: tests, linting, review. No special leniency. No special
scrutiny either — we review the code, not the process.

**New contributors: start small.** Your first PR should be under 150 lines of
non-test code. This isn't an AI-specific rule — it's how trust gets built. Fix a
bug. Improve a pattern's detection heuristic. Add a test. Demonstrate that you
understand the codebase before you propose restructuring it.

### What gets a PR closed

- Submissions that show no evidence of understanding the codebase or the change
  being made.
- PRs that don't link to an issue and don't explain their motivation.
- Code that fails existing tests.
- "Drive-by" contributions that create more review burden than they provide
  value. If the cost of reviewing your PR exceeds the value of merging it, we
  will close it. This isn't personal.

The maintainer reserves the right to close PRs that appear to be low-effort
AI-generated output without detailed justification. This is not an anti-AI
stance. This is a quality stance.

## Code Style

- Python. Follow existing conventions in the codebase.
- Type hints where practical.
- Docstrings on public functions.
- No commented-out code in PRs.
- `ruff` for linting. Run `ruff check .` before submitting.

## Tests

Holtz was built with TDD. Contributions follow the same discipline.

- Every bug fix starts with a failing test.
- Every new feature has tests that demonstrate the behavior.
- Tests should test behavior, not implementation. Assert what the code *should*
  do, not what it currently does.
- Avoid the anti-patterns Holtz himself detects: tautology tests, green bar
  addicts, mockingbirds, rubber stamps, permissive validators. If Holtz would
  flag your test, rewrite your test.

## Lenses, Patterns, and Edge Types

These are the most impactful contributions. Each has a specific format:

**Lenses:** Add to the registry file at `skills/holtz/references/lens-registry.md`.
A lens needs a Focus, Scope (per-file or cross-file), Audit priorities, Failure
modes, and Entry point. See the existing thirteen lenses for the format.

**Patterns:** Markdown file with a YAML header containing `name`, `version`,
`discovered`, `languages`, and `categories`. Body includes a description, an
executable detection heuristic (a grep command or structural check), and at
least one example. See the sixteen seed patterns for reference.

**Edge types:** Document the relationship type, when it applies, and how the
impact graph should traverse it during blast radius analysis.

## Questions?

Open a [GitHub Discussion](https://github.com/jbrjake/holtz/discussions) or
check the [SUPPORT.md](SUPPORT.md) file for guidance on where to ask what.

## License

By contributing to Holtz, you agree that your contributions will be licensed
under the [MIT License](LICENSE).

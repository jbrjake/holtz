# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < latest | :x:               |

Only the most recent release receives security fixes. If you're running an
older version, please upgrade before reporting.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Use [GitHub's Private Vulnerability Reporting](https://github.com/jbrjake/holtz/security/advisories/new)
to submit a report. This allows private discussion, collaboration on fixes in
temporary private forks, and coordinated disclosure.

Alternatively, email **jb.rubin@gmail.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional, but appreciated)

## Response Timeline

- **Initial acknowledgment:** within 48 hours
- **Assessment and triage:** within 7 days
- **Fix development and testing:** varies by severity, targeting 30 days for
  critical issues
- **Coordinated disclosure:** 90 days from report, consistent with industry
  standard practice. We will work with you on timing if you need it earlier or
  later.

If you haven't received an acknowledgment within 48 hours, please follow up.
Emails get lost sometimes.

## What Counts as a Security Issue

Holtz is a Claude Code plugin that reads and modifies code in your local
environment. Security-relevant issues include:

- Path traversal or arbitrary file access outside the intended project scope
- Code injection through crafted punchlist items, pattern files, or graph data
- Unsafe deserialization of impact graph JSON or audit state
- Hook bypass that allows unvalidated writes to audit files
- Information disclosure through audit artifacts

Issues that are **not** security vulnerabilities:

- Holtz finding false positives or missing real bugs (that's a regular bug)
- Performance issues
- Feature requests

## Safe Harbor

We consider security research conducted in good faith to be authorized and
welcome it. We will not pursue legal action against researchers who:

- Make a good faith effort to avoid privacy violations, data destruction, and
  service disruption
- Provide sufficient detail to reproduce the issue
- Allow reasonable time for remediation before public disclosure

## Disclosure

After a fix is released, we will publish a security advisory through GitHub's
advisory database. Credit will be given to the reporter unless they prefer to
remain anonymous.

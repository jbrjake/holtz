#!/usr/bin/env bash
# Run a command inside this repo's virtualenv, without `source`.
#
# `source .venv/bin/activate && <cmd>` makes every invocation a distinct
# compound shell string, so it cannot be allowlisted once — every command
# prompts again — and it mutates shell state to get there. This execs the
# venv's own executable directly: same result, one stable prefix to approve,
# nothing sourced.
#
#   scripts/venv-run.sh pytest -q tests/test_lens_scoped_completion.py
#   scripts/venv-run.sh python3 scripts/enforcement_lint.py
#   scripts/venv-run.sh ruff check .
#   scripts/venv-run.sh mypy --explicit-package-bases hooks/
#
# Approve once with, in .claude/settings.json:
#   "permissions": { "allow": ["Bash(scripts/venv-run.sh:*)"] }
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$repo/.venv"

if [ "$#" -eq 0 ]; then
    echo "usage: scripts/venv-run.sh <command> [args...]" >&2
    exit 2
fi

if [ ! -x "$venv/bin/python3" ]; then
    echo "venv-run: no virtualenv at $venv — create it first" >&2
    exit 1
fi

cmd="$1"
shift

# The venv's own executable when it has one. Otherwise fall through with the
# venv ahead on PATH, so a non-Python tool (git, bash) still resolves rather
# than the shim failing on it.
if [ -x "$venv/bin/$cmd" ]; then
    exec "$venv/bin/$cmd" "$@"
fi

export VIRTUAL_ENV="$venv"
export PATH="$venv/bin:$PATH"
exec "$cmd" "$@"

#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"
SRC_DIR="$REPO_ROOT/git-hooks"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: $SRC_DIR not found. Run from the repository root." >&2
    exit 1
fi

for hook in "$SRC_DIR"/*; do
    hook_name="$(basename "$hook")"
    dest="$GIT_HOOKS_DIR/$hook_name"

    # Check for existing hook that isn't our symlink
    if [[ -e "$dest" ]] && [[ ! -L "$dest" ]]; then
        echo "Error: $dest already exists and is not a symlink. Remove it manually or back it up first." >&2
        exit 1
    fi

    # If it's already our symlink, skip
    if [[ -L "$dest" ]] && [[ "$(readlink "$dest")" == "$hook" ]]; then
        echo "$hook_name: already installed"
        continue
    fi

    ln -sf "$hook" "$dest"
    echo "$hook_name: installed"
done

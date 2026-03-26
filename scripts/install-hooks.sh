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

# ── Sahjhan binary setup ──

ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$ARCH" in arm64) ARCH="aarch64" ;; esac

case "$OS" in
    darwin) TRIPLE="${ARCH}-apple-darwin" ;;
    linux)  TRIPLE="${ARCH}-unknown-linux-gnu" ;;
    *)      TRIPLE="${ARCH}-${OS}" ;;
esac

SAHJHAN_BIN="$REPO_ROOT/bin/sahjhan-${TRIPLE}"
if [[ -f "$SAHJHAN_BIN" ]]; then
    chmod +x "$SAHJHAN_BIN"
    ln -sf "sahjhan-${TRIPLE}" "$REPO_ROOT/bin/sahjhan"
    echo "sahjhan: binary ready at bin/sahjhan-${TRIPLE} (symlinked to bin/sahjhan)"

    # Version pinning check
    PINNED_VERSION_FILE="$REPO_ROOT/bin/.sahjhan-version"
    if [[ -f "$PINNED_VERSION_FILE" ]]; then
        PINNED_VERSION=$(cat "$PINNED_VERSION_FILE")
        ACTUAL_VERSION=$("$SAHJHAN_BIN" --version 2>/dev/null || echo "unknown")
        if [[ "$ACTUAL_VERSION" != *"$PINNED_VERSION"* ]] && [[ "$ACTUAL_VERSION" != "unknown" ]]; then
            echo "WARNING: Sahjhan binary version ($ACTUAL_VERSION) does not match pinned version ($PINNED_VERSION)." >&2
            echo "         Run scripts/vendor-sahjhan.sh $PINNED_VERSION to fix." >&2
        fi
    fi
else
    echo "sahjhan: no binary for ${TRIPLE}. Run scripts/vendor-sahjhan.sh <version> first."
fi

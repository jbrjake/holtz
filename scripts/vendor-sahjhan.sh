#!/bin/bash
set -euo pipefail

VERSION="${1:?Usage: vendor-sahjhan.sh <version>}"
BASE_URL="https://github.com/jbrjake/sahjhan/releases/download/v${VERSION}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
BIN_DIR="$REPO_ROOT/bin"
mkdir -p "$BIN_DIR"

for target in aarch64-apple-darwin x86_64-apple-darwin x86_64-unknown-linux-gnu aarch64-unknown-linux-gnu; do
    echo "Downloading sahjhan-${target}..."
    curl -sfL "${BASE_URL}/sahjhan-${target}" -o "${BIN_DIR}/sahjhan-${target}"
    chmod +x "${BIN_DIR}/sahjhan-${target}"
done

echo "${VERSION}" > "${BIN_DIR}/.sahjhan-version"
echo "Vendored sahjhan v${VERSION} → bin/"

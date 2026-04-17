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

# Point the host-local `sahjhan` symlink at the current architecture's
# binary so bare `sahjhan` invocations resolve via PATH. The hook-side
# bootstrap in _resolve.py does the same on end-user machines.
case "$(uname -m)" in arm64|aarch64) ARCH=aarch64 ;; *) ARCH=x86_64 ;; esac
case "$(uname -s)" in
    Darwin) HOST_TRIPLE="${ARCH}-apple-darwin" ;;
    Linux) HOST_TRIPLE="${ARCH}-unknown-linux-gnu" ;;
    *) HOST_TRIPLE="" ;;
esac
if [[ -n "${HOST_TRIPLE}" && -f "${BIN_DIR}/sahjhan-${HOST_TRIPLE}" ]]; then
    ln -sfn "sahjhan-${HOST_TRIPLE}" "${BIN_DIR}/sahjhan"
fi

echo "${VERSION}" > "${BIN_DIR}/.sahjhan-version"
echo "Vendored sahjhan v${VERSION} → bin/"

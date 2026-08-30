#!/usr/bin/env bash
# Install a pinned, local-only Conda bootstrap. No global Conda configuration is used.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/env.sh"

MINIFORGE_RELEASE="26.5.3-0"
INSTALLER="Miniforge3-26.5.3-0-Linux-x86_64.sh"
DOWNLOAD_BASE="https://github.com/conda-forge/miniforge/releases/download/$MINIFORGE_RELEASE"
ARCHIVE="$HOUSEHOLD_ROOT/.downloads/$INSTALLER"
CHECKSUM_FILE="$ARCHIVE.sha256"

if [[ -x "$MINIFORGE_PREFIX/bin/conda" ]]; then
    printf 'Miniforge already available at %s\n' "$MINIFORGE_PREFIX"
    "$MINIFORGE_PREFIX/bin/conda" --version
    exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
    printf 'curl is required to bootstrap Miniforge.\n' >&2
    exit 1
fi

printf 'Downloading %s into %s\n' "$INSTALLER" "$HOUSEHOLD_ROOT/.downloads"
curl --fail --location --retry 3 --output "$ARCHIVE" "$DOWNLOAD_BASE/$INSTALLER"
curl --fail --location --retry 3 --output "$CHECKSUM_FILE" "$DOWNLOAD_BASE/$INSTALLER.sha256"

expected_hash="$(awk '{print $1}' "$CHECKSUM_FILE")"
actual_hash="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
if [[ "$expected_hash" != "$actual_hash" ]]; then
    printf 'Checksum mismatch for %s\n' "$INSTALLER" >&2
    exit 1
fi

bash "$ARCHIVE" -b -p "$MINIFORGE_PREFIX"
"$MINIFORGE_PREFIX/bin/conda" config --file "$CONDARC" --set auto_activate_base false
"$MINIFORGE_PREFIX/bin/conda" --version

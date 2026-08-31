#!/usr/bin/env bash
# Install a pinned Anaconda Distribution in the standard per-user location.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/../env.sh"

ANACONDA_RELEASE="2026.07-1"
INSTALLER="Anaconda3-2026.07-1-Linux-x86_64.sh"
DOWNLOAD_BASE="https://repo.anaconda.com/archive"
ARCHIVE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/household"
ARCHIVE="$ARCHIVE_DIR/$INSTALLER"
EXPECTED_SHA256="9f49042048e9a8220c1cddf9192054290724052d3b2a86f938f9f5edd911db8f"

if [[ -x "$ANACONDA_PREFIX/bin/conda" ]]; then
    printf 'Anaconda already available at %s\n' "$ANACONDA_PREFIX"
    "$ANACONDA_PREFIX/bin/conda" --version
    exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
    printf 'curl is required to bootstrap Anaconda.\n' >&2
    exit 1
fi

mkdir -p "$ARCHIVE_DIR"
printf 'Downloading %s into %s\n' "$INSTALLER" "$ARCHIVE_DIR"
curl --fail --location --retry 3 --output "$ARCHIVE" "$DOWNLOAD_BASE/$INSTALLER"
printf '%s  %s\n' "$EXPECTED_SHA256" "$ARCHIVE" | sha256sum --check -

bash "$ARCHIVE" -b -p "$ANACONDA_PREFIX"
"$ANACONDA_PREFIX/bin/conda" config --file "$CONDARC" --set auto_activate_base false
"$ANACONDA_PREFIX/bin/conda" --version

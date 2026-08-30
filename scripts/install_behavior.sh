#!/usr/bin/env bash
# Install the minimal, supported BEHAVIOR stack after explicit license acceptance.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/env.sh"

if [[ "${1:-}" != "--accept-licenses" || "$#" -ne 1 ]]; then
    cat <<'EOF' >&2
Refusing to accept licenses implicitly.

This command installs Conda packages, NVIDIA Isaac Sim, and the licensed
BEHAVIOR assets. To continue, first review docs/OPERATIONS.md and then run:
  ./setup.sh install --accept-licenses
EOF
    exit 2
fi

if [[ ! -x "$MINIFORGE_PREFIX/bin/conda" ]]; then
    printf 'Missing local Miniforge. Run ./setup.sh bootstrap first.\n' >&2
    exit 1
fi

if [[ ! -x "$BEHAVIOR_ROOT/setup.sh" ]]; then
    printf 'Missing BEHAVIOR submodule at %s\n' "$BEHAVIOR_ROOT" >&2
    exit 1
fi

source "$MINIFORGE_PREFIX/etc/profile.d/conda.sh"
export PATH="$MINIFORGE_PREFIX/bin:$PATH"
export CONDA_PLUGINS_AUTO_ACCEPT_TOS=yes
export OMNI_KIT_ACCEPT_EULA=YES

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
log_file="$HOUSEHOLD_ROOT/records/runtime/install-$timestamp.log"

pushd "$BEHAVIOR_ROOT" >/dev/null
./setup.sh --new-env --omnigibson --bddl --dataset --accept-conda-tos --accept-nvidia-eula --accept-dataset-tos 2>&1 | tee "$log_file"
popd >/dev/null

printf '%s\n' 'accepted via ./setup.sh install --accept-licenses' > "$HOUSEHOLD_ROOT/.state/licenses-accepted-v3.7.2"
"$SCRIPT_DIR/capture_versions.sh"
printf 'Installation completed. Log: %s\n' "$log_file"

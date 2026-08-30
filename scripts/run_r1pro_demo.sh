#!/usr/bin/env bash
# Run the upstream fully populated BEHAVIOR task demo, which loads Galaxea R1Pro.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/env.sh"

license_marker="$HOUSEHOLD_ROOT/.state/licenses-accepted-v3.7.2"
if [[ ! -f "$license_marker" ]]; then
    printf 'Run ./setup.sh install --accept-licenses before launching Isaac Sim.\n' >&2
    exit 1
fi
if [[ ! -x "$MINIFORGE_PREFIX/bin/conda" ]]; then
    printf 'Local environment is missing.\n' >&2
    exit 1
fi

source "$MINIFORGE_PREFIX/etc/profile.d/conda.sh"
conda activate "$CONDA_ENVS_PATH/behavior"
export OMNI_KIT_ACCEPT_EULA=YES

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
log_file="$HOUSEHOLD_ROOT/runs/r1pro-behavior-demo-$timestamp.log"
mkdir -p "$HOUSEHOLD_ROOT/runs"

python -m omnigibson.examples.environments.behavior_env_demo "$@" 2>&1 | tee "$log_file"

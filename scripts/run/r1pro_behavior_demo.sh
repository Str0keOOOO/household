#!/usr/bin/env bash
# Run the upstream Galaxea R1Pro BEHAVIOR demo, or a finite headless smoke test.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/../env.sh"

if [[ ! -x "$ANACONDA_PREFIX/bin/conda" ]]; then
    printf 'Anaconda environment is missing.\n' >&2
    exit 1
fi

source "$ANACONDA_PREFIX/etc/profile.d/conda.sh"
conda activate behavior
export OMNI_KIT_ACCEPT_EULA=YES

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$HOUSEHOLD_ROOT/runs"

if [[ "${1:-}" == "--smoke" ]]; then
    shift
    if [[ "$#" -ne 0 ]]; then
        printf 'Usage: %s [--smoke]\n' "${0##*/}" >&2
        exit 2
    fi

    # The upstream module has no CLI and asks whether to sample online. Feed its
    # first option (the cached BEHAVIOR activity) and call its own finite test
    # path. This does not patch or copy upstream source.
    export OMNIGIBSON_HEADLESS=1
    log_file="$HOUSEHOLD_ROOT/runs/r1pro-behavior-smoke-$timestamp.log"
    printf '1\n' | timeout --signal=TERM --kill-after=60s 20m python -c \
        'from omnigibson.examples.environments.behavior_env_demo import main; main(headless=True, short_exec=True)' \
        2>&1 | tee "$log_file"
else
    log_file="$HOUSEHOLD_ROOT/runs/r1pro-behavior-demo-$timestamp.log"
    python -m omnigibson.examples.environments.behavior_env_demo "$@" 2>&1 | tee "$log_file"
fi

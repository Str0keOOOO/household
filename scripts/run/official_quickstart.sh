#!/usr/bin/env bash
# Run the upstream keyboard-teleoperation quickstart, or a finite headless smoke test.
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

    # The upstream CLI only exposes an infinite keyboard-teleoperation loop. This
    # calls its unmodified main() with source-supported short_exec/random_selection
    # arguments so a non-interactive server can validate the same quickstart setup.
    export OMNIGIBSON_HEADLESS=1
    log_file="$HOUSEHOLD_ROOT/runs/official-quickstart-smoke-$timestamp.log"
    timeout --signal=TERM --kill-after=60s 20m python -c \
        'from omnigibson.examples.robots.robot_control_example import main; main(random_selection=True, headless=True, short_exec=True, quickstart=True)' \
        2>&1 | tee "$log_file"
else
    log_file="$HOUSEHOLD_ROOT/runs/official-quickstart-$timestamp.log"
    python -m omnigibson.examples.robots.robot_control_example --quickstart "$@" 2>&1 | tee "$log_file"
fi

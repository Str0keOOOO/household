#!/usr/bin/env bash
# Record the bundled R1 Pro BEHAVIOR example as an MP4 on a headless server.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/env.sh"

if [[ ! -x "$ANACONDA_PREFIX/bin/conda" ]]; then
    printf 'Anaconda environment is missing.\n' >&2
    exit 1
fi

source "$ANACONDA_PREFIX/etc/profile.d/conda.sh"
conda activate behavior
export OMNI_KIT_ACCEPT_EULA=YES
export OMNIGIBSON_HEADLESS=1

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$HOUSEHOLD_ROOT/runs"
output="$HOUSEHOLD_ROOT/runs/r1pro-behavior-$timestamp.mp4"
log_file="$HOUSEHOLD_ROOT/runs/r1pro-record-$timestamp.log"

python "$SCRIPT_DIR/r1pro_record_demo.py" --output "$output" "$@" 2>&1 | tee "$log_file"

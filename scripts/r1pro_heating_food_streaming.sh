#!/usr/bin/env bash
# Start the initialized heating_food_up scene with Isaac Sim 4.5 WebRTC streaming only.
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

instance="$OMNIGIBSON_DATA_PATH/local-task-instances/heating_food_up/house_single_floor_task_heating_food_up_0_0_template.json"
if [[ ! -f "$instance" ]]; then
    mkdir -p "$(dirname -- "$instance")"
    timeout --signal=TERM --kill-after=60s 75m python "$HOUSEHOLD_ROOT/src/sample_behavior_task_instance.py" \
        --config "$HOUSEHOLD_ROOT/config/heating_food_up.json" \
        --output "$instance"
fi

exec python "$HOUSEHOLD_ROOT/src/r1pro_task_scene_record.py" \
    --task heating_food_up --scene house_single_floor --scene-file "$instance" \
    --initialization-config "$HOUSEHOLD_ROOT/config/heating_food_up.json" \
    --streaming --streaming-only \
    "$@"

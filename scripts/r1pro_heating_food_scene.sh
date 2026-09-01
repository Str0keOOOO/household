#!/usr/bin/env bash
# Record the persisted heating_food_up scene. Optional recorder arguments are forwarded.
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

video_dir="$HOUSEHOLD_ROOT/runs/videos/task_scene"
log_dir="$HOUSEHOLD_ROOT/runs/logs/task_scene"
mkdir -p "$video_dir" "$log_dir"
recorder_args=("$@")
# Remove only this launcher's generated files so a failed run cannot leave a
# stale third-person video that looks like a successful paired recording.
rm -f -- "$video_dir/heating_food_up.mp4" "$video_dir/heating_food_up-r1pro-native-cameras.mp4"

instance="$OMNIGIBSON_DATA_PATH/local-task-instances/heating_food_up/house_single_floor_task_heating_food_up_0_0_template.json"
if [[ ! -f "$instance" ]]; then
    mkdir -p "$(dirname -- "$instance")"
    timeout --signal=TERM --kill-after=60s 75m python "$HOUSEHOLD_ROOT/src/sample_behavior_task_instance.py" \
        --config "$HOUSEHOLD_ROOT/config/heating_food_up.json" \
        --output "$instance" 2>&1 | tee "$log_dir/heating_food_up_sampling.log"
fi

printf 'task=heating_food_up scene=house_single_floor instance=%s\n' "$instance" | tee "$log_dir/heating_food_up.log"
timeout --signal=TERM --kill-after=60s 45m python "$HOUSEHOLD_ROOT/src/r1pro_task_scene_record.py" \
    --task heating_food_up --scene house_single_floor --scene-file "$instance" \
    --output "$video_dir/heating_food_up.mp4" \
    --robot-output "$video_dir/heating_food_up-r1pro-native-cameras.mp4" \
    --camera-view near_right \
    "${recorder_args[@]}" \
    2>&1 | tee -a "$log_dir/heating_food_up.log"

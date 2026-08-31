#!/usr/bin/env bash
# Batch-record task scene previews. No robot action or task-completion claim is made.
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

# These are the only requested tasks for which this server has matching,
# pre-sampled task instances.  Keep this launcher deterministic: do not fall
# back to online object sampling, because an online result is not a locally
# reproducible task instance and may be rejected by the installed assets.
tasks=(
    carrying_in_groceries
    thawing_frozen_food
    canning_food
)

scenes=(
    house_double_floor_lower
    house_single_floor
    house_single_floor
)

for index in "${!tasks[@]}"; do
    task="${tasks[$index]}"
    scene="${scenes[$index]}"

    number="$(printf '%02d' "$((index + 1))")"
    output="$video_dir/${number}-${task}.mp4"
    log="$log_dir/${number}-${task}.log"

    printf '\n[%s/%s] task=%s scene=%s instance=local-pre-sampled\n' \
        "$((index + 1))" "${#tasks[@]}" "$task" "$scene" | tee "$log"

    if ! timeout --signal=TERM --kill-after=60s 45m python "$HOUSEHOLD_ROOT/src/r1pro_task_scene_record.py" \
        --task "$task" --scene "$scene" --output "$output" 2>&1 | tee -a "$log"; then
        printf 'FAILED task=%s; see %s\n' "$task" "$log" >&2
    fi
done

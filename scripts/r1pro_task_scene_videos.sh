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

# The three pre-sampled instances below exist locally. Other requested tasks
# are attempted through BEHAVIOR's official online object-sampling path.
tasks=(
    putting_food_in_fridge
    carrying_in_groceries
    taking_fish_out_of_freezer
    defrost_meat
    thawing_frozen_food
    cleaning_freezer
    defrosting_freezer
    boxing_food_after_dinner
    dispose_of_a_pizza_box
    can_fruit
    canning_food
)

for index in "${!tasks[@]}"; do
    task="${tasks[$index]}"
    scene="house_double_floor_lower"
    online_flag=(--online-object-sampling)

    case "$task" in
        carrying_in_groceries)
            scene="house_double_floor_lower"
            online_flag=()
            ;;
        thawing_frozen_food|canning_food)
            scene="house_single_floor"
            online_flag=()
            ;;
    esac

    number="$(printf '%02d' "$((index + 1))")"
    output="$video_dir/${number}-${task}.mp4"
    log="$log_dir/${number}-${task}.log"

    printf '\n[%s/%s] task=%s scene=%s online=%s\n' \
        "$((index + 1))" "${#tasks[@]}" "$task" "$scene" "${online_flag[*]:-false}" | tee "$log"

    # Sampling may be slow for a task that has no pre-sampled instance. Keep
    # the batch progressing and preserve the exact failure in that task's log.
    if ! timeout --signal=TERM --kill-after=60s 45m python "$HOUSEHOLD_ROOT/src/r1pro_task_scene_record.py" \
        --task "$task" --scene "$scene" --output "$output" "${online_flag[@]}" 2>&1 | tee -a "$log"; then
        printf 'FAILED task=%s; see %s\n' "$task" "$log" >&2
    fi
done

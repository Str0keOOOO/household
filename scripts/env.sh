#!/usr/bin/env bash
# Source this file from helpers to configure this workspace's data and the
# standard per-user Anaconda installation. General third-party caches use their
# normal user-level defaults, while OmniGibson uses its upstream appdata default.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export HOUSEHOLD_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

export CONDARC="$HOUSEHOLD_ROOT/config/condarc"
export ANACONDA_PREFIX="${ANACONDA_PREFIX:-/home/xuchenfei/anaconda3}"
export CONDA_ENVS_PATH="$ANACONDA_PREFIX/envs"
export CONDA_PKGS_DIRS="$ANACONDA_PREFIX/pkgs"

export OMNIGIBSON_DATA_PATH="$HOUSEHOLD_ROOT/data/omnigibson"
export BEHAVIOR_ROOT="$HOUSEHOLD_ROOT/third_party/BEHAVIOR-1K"

# GPU 1 was idle during the recorded preflight. Preserve an explicit caller choice.
if [[ -z "${OMNIGIBSON_GPU_ID:-}" ]]; then
    export OMNIGIBSON_GPU_ID=1
fi

mkdir -p "$CONDA_ENVS_PATH" "$CONDA_PKGS_DIRS" "$OMNIGIBSON_DATA_PATH"
mkdir -p "$HOUSEHOLD_ROOT/records/runtime"

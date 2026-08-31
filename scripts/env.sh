#!/usr/bin/env bash
# Source this file from helpers to keep project state local while using the
# standard per-user Anaconda installation for Conda itself and its environments.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export HOUSEHOLD_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

export XDG_CACHE_HOME="$HOUSEHOLD_ROOT/.xdg/cache"
export XDG_CONFIG_HOME="$HOUSEHOLD_ROOT/.xdg/config"
export XDG_DATA_HOME="$HOUSEHOLD_ROOT/.xdg/data"
export XDG_STATE_HOME="$HOUSEHOLD_ROOT/.xdg/state"
export TMPDIR="$HOUSEHOLD_ROOT/.tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"

export CONDARC="$HOUSEHOLD_ROOT/config/condarc"
export ANACONDA_PREFIX="${ANACONDA_PREFIX:-/home/xuchenfei/anaconda3}"
export CONDA_ENVS_PATH="$ANACONDA_PREFIX/envs"
export CONDA_PKGS_DIRS="$ANACONDA_PREFIX/pkgs"
export PIP_CACHE_DIR="$HOUSEHOLD_ROOT/.cache/pip"
export HF_HOME="$HOUSEHOLD_ROOT/.cache/huggingface"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TORCH_HOME="$HOUSEHOLD_ROOT/.cache/torch"
export TORCH_EXTENSIONS_DIR="$HOUSEHOLD_ROOT/.cache/torch_extensions"
export CUDA_CACHE_PATH="$HOUSEHOLD_ROOT/.cache/cuda"
export MPLCONFIGDIR="$HOUSEHOLD_ROOT/.cache/matplotlib"

export OMNIGIBSON_DATA_PATH="$HOUSEHOLD_ROOT/data/omnigibson"
export OMNIGIBSON_APPDATA_PATH="$HOUSEHOLD_ROOT/.omnigibson"
export BEHAVIOR_ROOT="$HOUSEHOLD_ROOT/third_party/BEHAVIOR-1K"

# GPU 1 was idle during the recorded preflight. Preserve an explicit caller choice.
if [[ -z "${OMNIGIBSON_GPU_ID:-}" ]]; then
    export OMNIGIBSON_GPU_ID=1
fi

mkdir -p "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME"
mkdir -p "$TMPDIR" "$CONDA_ENVS_PATH" "$CONDA_PKGS_DIRS" "$PIP_CACHE_DIR"
mkdir -p "$HF_HOME" "$TORCH_HOME" "$TORCH_EXTENSIONS_DIR" "$CUDA_CACHE_PATH"
mkdir -p "$MPLCONFIGDIR" "$OMNIGIBSON_DATA_PATH" "$OMNIGIBSON_APPDATA_PATH"
mkdir -p "$HOUSEHOLD_ROOT/.state" "$HOUSEHOLD_ROOT/records/runtime"

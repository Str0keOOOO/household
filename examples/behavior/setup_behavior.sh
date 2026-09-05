#!/usr/bin/env bash
set -euo pipefail

ROOT="${PIXI_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BEHAVIOR_DIR="$ROOT/examples/behavior"
BEHAVIOR_ENV="$BEHAVIOR_DIR/.conda"
BEHAVIOR_SOURCE="$ROOT/third_party/BEHAVIOR-1K"

force=false
if [[ "${1:-}" == "--force" ]]; then
    force=true
    shift
fi
if [[ "$#" -gt 0 ]]; then
    printf 'Usage: %s [--force]\n' "$0" >&2
    exit 2
fi

command -v conda >/dev/null || { echo "ERROR: conda not found" >&2; exit 1; }
if [[ "$force" == false ]] && conda run --no-capture-output -p "$BEHAVIOR_ENV" python -c 'import bddl, isaacsim, omnigibson' >/dev/null 2>&1; then
    echo "BEHAVIOR Conda environment already installed: $BEHAVIOR_ENV"
    exit 0
fi
if [[ "$force" == true ]] && [[ -d "$BEHAVIOR_ENV" ]]; then
    echo "Removing existing BEHAVIOR Conda environment (--force): $BEHAVIOR_ENV"
    conda env remove -p "$BEHAVIOR_ENV" -y
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
echo "Creating Conda environment at $BEHAVIOR_ENV"
conda create -p "$BEHAVIOR_ENV" python=3.10 -c conda-forge -y
conda activate "$BEHAVIOR_ENV"

echo "Installing numpy and setuptools (BEHAVIOR setup.sh --new-env step)"
pip install "numpy<2" "setuptools<=79"
echo "Installing PyTorch with CUDA 12.4 (BEHAVIOR setup.sh --new-env step)"
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu124

echo "Installing planner wire-protocol deps (msgpack, websockets)"
pip install "msgpack>=1.1,<2" "websockets>=15,<17"

cd "$BEHAVIOR_SOURCE"
./setup.sh --bddl --omnigibson --accept-nvidia-eula --confirm-no-conda

echo "BEHAVIOR Conda environment ready: $BEHAVIOR_ENV"
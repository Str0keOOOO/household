#!/usr/bin/env bash
# Create a local, timestamped snapshot for debugging and handoff.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/env.sh"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report="$HOUSEHOLD_ROOT/records/runtime/environment-$timestamp.md"

{
    printf '# Runtime snapshot: %s\n\n' "$timestamp"
    printf '## Source\n\n'
    printf '```text\n'
    git -C "$HOUSEHOLD_ROOT" submodule status
    printf '```\n\n'

    printf '## System\n\n'
    printf '```text\n'
    uname -srmo
    sed -n '1,8p' /etc/os-release
    printf '```\n\n'

    printf '## GPU\n\n'
    printf '```text\n'
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used --format=csv,noheader || true
    fi
    printf '```\n\n'

    if [[ -x "$MINIFORGE_PREFIX/bin/conda" ]]; then
        source "$MINIFORGE_PREFIX/etc/profile.d/conda.sh"
        if [[ -d "$CONDA_ENVS_PATH/behavior" ]]; then
            conda activate "$CONDA_ENVS_PATH/behavior"
            printf '## Python environment\n\n```text\n'
            python --version
            python -m pip --version
            conda list --explicit
            printf '```\n'
        fi
    fi
} > "$report"

printf '%s\n' "$report"

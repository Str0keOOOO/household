#!/usr/bin/env bash
# Read-only compatibility report. It does not require a Conda environment.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/../env.sh"

printf '== Workspace ==\n'
printf 'root: %s\n' "$HOUSEHOLD_ROOT"
df -h "$HOUSEHOLD_ROOT"

printf '\n== Operating system ==\n'
if [[ -r /etc/os-release ]]; then
    sed -n '1,8p' /etc/os-release
fi
uname -srmo

printf '\n== CPU and memory ==\n'
lscpu | rg '^(Architecture|CPU\(s\)|Model name)'
free -h

printf '\n== NVIDIA GPU ==\n'
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,utilization.gpu --format=csv,noheader || true
else
    printf 'nvidia-smi is not visible in this execution context.\n'
fi

printf '\n== Source ==\n'
git -C "$HOUSEHOLD_ROOT" submodule status || true
if [[ -d "$BEHAVIOR_ROOT/.git" || -f "$BEHAVIOR_ROOT/.git" ]]; then
    git -C "$BEHAVIOR_ROOT" status --short --branch
fi

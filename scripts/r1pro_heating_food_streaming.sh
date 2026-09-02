#!/usr/bin/env bash
# Start the local heating_food_up recorder with Isaac Sim 4.5 WebRTC streaming enabled.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

# The regular launcher owns the environment setup, task-instance reuse, output
# locations, and timeout. This wrapper only adds the official WebRTC backend and
# leaves the session open for 30 minutes after the recording completes.
exec "$SCRIPT_DIR/r1pro_heating_food_scene.sh" \
    --streaming --streaming-hold-seconds 18000 \
    "$@"

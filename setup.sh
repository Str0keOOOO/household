#!/usr/bin/env bash
# Top-level dispatcher. It never edits system or user-global configuration.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
    cat <<'EOF'
Usage: ./setup.sh <command> [options]

Commands:
  preflight                 Report host compatibility and available workspace space.
  bootstrap                 Install the pinned Miniforge bootstrap under .tools/.
  install --accept-licenses Create the isolated environment and install BEHAVIOR.
  all --accept-licenses     Run bootstrap followed by install.
  capture                   Write a local runtime version snapshot.

The install command requires an explicit acceptance flag because it accepts the
Conda terms, NVIDIA Isaac Sim EULA, and BEHAVIOR dataset license.
EOF
}

command_name="${1:-}"
case "$command_name" in
    preflight)
        exec "$SCRIPT_DIR/scripts/preflight.sh"
        ;;
    bootstrap)
        exec "$SCRIPT_DIR/scripts/bootstrap_miniforge.sh"
        ;;
    install)
        shift
        exec "$SCRIPT_DIR/scripts/install_behavior.sh" "$@"
        ;;
    all)
        shift
        "$SCRIPT_DIR/scripts/bootstrap_miniforge.sh"
        exec "$SCRIPT_DIR/scripts/install_behavior.sh" "$@"
        ;;
    capture)
        exec "$SCRIPT_DIR/scripts/capture_versions.sh"
        ;;
    -h|--help|help|'')
        usage
        ;;
    *)
        printf 'Unknown command: %s\n\n' "$command_name" >&2
        usage >&2
        exit 2
        ;;
esac

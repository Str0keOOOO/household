#!/usr/bin/env bash
# Install the minimal, supported BEHAVIOR stack after explicit license acceptance.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/../env.sh"

if [[ "${1:-}" != "--accept-licenses" || "$#" -ne 1 ]]; then
    cat <<'EOF' >&2
Refusing to accept licenses implicitly.

This command installs Conda packages, NVIDIA Isaac Sim, and the licensed
BEHAVIOR assets. To continue, first review the applicable upstream licenses and
then run:
  ./setup.sh install --accept-licenses
EOF
    exit 2
fi

if [[ ! -x "$ANACONDA_PREFIX/bin/conda" ]]; then
    printf 'Missing Anaconda at %s. Run ./setup.sh bootstrap first.\n' "$ANACONDA_PREFIX" >&2
    exit 1
fi

if [[ ! -x "$BEHAVIOR_ROOT/setup.sh" ]]; then
    printf 'Missing BEHAVIOR submodule at %s\n' "$BEHAVIOR_ROOT" >&2
    exit 1
fi

source "$ANACONDA_PREFIX/etc/profile.d/conda.sh"
export PATH="$ANACONDA_PREFIX/bin:$PATH"
export CONDA_PLUGINS_AUTO_ACCEPT_TOS=yes
export OMNI_KIT_ACCEPT_EULA=YES

# Keep the large core install and the licensed-data transfer as explicit stages.
# Besides making an interrupted data download resumable, this lets us add HTTPX
# SOCKS support inside the isolated environment when the host exposes a SOCKS
# proxy. Upstream's dataset downloader uses HTTPX and otherwise aborts before any
# asset transfer on such hosts. No third-party source is changed.
if [[ -d "$CONDA_ENVS_PATH/behavior" ]]; then
    conda activate behavior
    if ! python -c 'import omnigibson' >/dev/null 2>&1; then
        printf 'Existing local behavior environment is incomplete; refusing to overwrite it.\n' >&2
        exit 1
    fi
    printf 'Reusing existing local behavior environment for the dataset stage.\n'
else
    pushd "$BEHAVIOR_ROOT" >/dev/null
    ./setup.sh --new-env --omnigibson --bddl --accept-conda-tos --accept-nvidia-eula
    popd >/dev/null
    conda activate behavior
fi

uses_socks_proxy=false
for proxy_value in "${ALL_PROXY:-}" "${all_proxy:-}" "${HTTPS_PROXY:-}" "${https_proxy:-}" "${HTTP_PROXY:-}" "${http_proxy:-}"; do
    if [[ "$proxy_value" == socks* ]]; then
        uses_socks_proxy=true
        break
    fi
done

if [[ "$uses_socks_proxy" == true ]] && ! python -c 'import socksio' >/dev/null 2>&1; then
    printf 'Installing local HTTPX SOCKS support for the configured proxy.\n'
    python -m pip install 'httpx[socks]'
fi

pushd "$BEHAVIOR_ROOT" >/dev/null
./setup.sh --dataset --accept-dataset-tos
popd >/dev/null

printf 'Installation completed.\n'

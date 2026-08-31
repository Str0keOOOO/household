# Operating the workspace

## Why v3.7.2 is selected

The workspace runs Ubuntu 20.04.4. The upstream latest stable BEHAVIOR-1K release
is v3.9.2, but its current installation guide requires Ubuntu 22.04+ and its Isaac
Sim 5.1 dependency officially supports Ubuntu 22.04/24.04. BEHAVIOR-1K v3.7.2 is
the latest release selected for this server because it uses Isaac Sim 4.5, which
officially supports Ubuntu 20.04/22.04. It also contains the `R1Pro` robot
configuration needed for the requested Galaxea R1 Pro example.

This is a compatibility decision, not a fork: upstream code remains unmodified
inside the pinned submodule.

## Isolated locations

The helper scripts redirect supported configuration and cache locations to this
repository. Notably, Conda environments/packages, Pip/Hugging Face/Torch caches,
temporary files, OmniGibson assets, and OmniGibson app data all live below
`/data6/xuchenfei/household`. No global Git, Conda, Pip, shell, OS, or driver
configuration is changed.

The scripts intentionally do not redefine the user's home directory. If an
unredirectable third-party component attempts to write there, stop and inspect it
before proceeding.

## Installation sequence

```bash
cd /data6/xuchenfei/household
./setup.sh preflight
./setup.sh bootstrap
./setup.sh install --accept-licenses
```

The last command performs the upstream minimal install:

```bash
./setup.sh --new-env --omnigibson --bddl --dataset \
  --accept-conda-tos --accept-nvidia-eula --accept-dataset-tos
```

It creates the isolated `behavior` environment and installs BDDL, OmniGibson,
Isaac Sim 4.5, and the dataset assets. It deliberately omits `--joylo`, `--eval`,
and `--primitives`, which are not needed for the requested smoke tests.

The local wrapper performs the core stack and licensed-data downloads as separate
upstream invocations. This permits a failed data transfer to resume without
recreating the environment. If the host provides a SOCKS proxy, it adds the
minimal `httpx[socks]` extra inside `envs/behavior` before the upstream data
downloader is invoked; it does not alter the upstream checkout.

## License gate

Passing `--accept-licenses` confirms acceptance of all of the following:

1. Conda Terms of Service;
2. NVIDIA Isaac Sim EULA; and
3. BEHAVIOR Data Bundle EULA.

The BEHAVIOR data license limits use to non-commercial academic research, requires
use inside OmniGibson, and prohibits redistribution, extraction/reverse
engineering, and distribution of its decryption key. Do not add assets to Git or
Git LFS.

## Examples

```bash
# Finite, headless, non-interactive smoke tests used for server verification:
./scripts/run_official_quickstart.sh --smoke
./scripts/run_r1pro_demo.sh --smoke

# Original upstream interactive entry points (GUI / remote display required):
./scripts/run_official_quickstart.sh
./scripts/run_r1pro_demo.sh
```

The first is the upstream keyboard teleoperation quickstart and needs a working
GUI or remote display. The second invokes the upstream `behavior_env_demo`, whose
configuration instantiates an R1Pro in a populated BEHAVIOR task. Both scripts
default to the preflight-selected GPU 1; set `OMNIGIBSON_GPU_ID` explicitly to
override this choice.

The `--smoke` variants are wrappers around the upstream functions, not source
patches. They set `OMNIGIBSON_HEADLESS=1` before importing OmniGibson and exercise
the upstream finite `short_exec` paths. The quickstart smoke uses its default
Fetch/Rs_int configuration and 100 random-action steps because the original CLI
is an infinite keyboard-teleoperation loop. The R1Pro smoke selects its cached
BEHAVIOR activity and runs one 100-step iteration; this avoids the original
interactive selection and non-deterministic online object sampling. Each smoke
run has a 20-minute safety timeout and writes a timestamped log under `runs/`.

### Multi-GPU server note

On this server, `OMNIGIBSON_GPU_ID=1` was verified in the Isaac Sim log as both
the renderer and PhysX device. OmniGibson v3.7.2 already disables multi-GPU mode.
Isaac/Omniverse may nevertheless probe every physical GPU at process startup; when
another user's GPU is full, this can emit non-fatal P2P `cudaErrorMemoryAllocation`
messages. Do not replace `OMNIGIBSON_GPU_ID` with `CUDA_VISIBLE_DEVICES` for Isaac
Sim: its Vulkan renderer is not selected by that CUDA-only mechanism. Keep the
OmniGibson variable set to an actually idle physical GPU and verify it with
`nvidia-smi` before launching.

The first cold start on 2026-08-31 spent several minutes compiling RTX shader/PSO
cache inside `.omnigibson`; later starts were substantially faster. Headless GLFW,
OmniHub, DLSS low-resolution, and some upstream deprecation warnings were observed
but did not prevent either example from completing.

## Updating later

Do not use `git submodule update --remote` blindly. First repeat compatibility
checks, read upstream release notes, update the submodule intentionally, run the
two examples, and amend `versions.lock`, `docs/RESOURCES.md`, and
`docs/DELIVERY.md` with the tested revision and outcome.

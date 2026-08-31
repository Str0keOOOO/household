# Delivery record

## Completion status

BEHAVIOR-1K is installed and verified in this isolated workspace. The selected
source is the newest release deliberately compatible with this Ubuntu 20.04 host:
BEHAVIOR-1K `v3.7.2` at
`88454bd04f75dc57c00ab1f1a00bcde1ff505950`, registered as the clean Git submodule
`third_party/BEHAVIOR-1K`. No file inside that submodule was modified.

The local `behavior` environment contains Python 3.10.21, Isaac Sim 4.5.0.0,
OmniGibson 3.7.2, BDDL 3.7.0, and PyTorch 2.6.0+cu124. Exact resolved pins are in
[`versions.lock`](../versions.lock); the full machine-readable Conda snapshot is
the ignored runtime record `records/runtime/environment-20260831T053713Z.md`.

## Resources acquired

| Resource | Result | Workspace location |
|---|---|---|
| Upstream source | Pinned Git submodule, `v3.7.2` | `third_party/BEHAVIOR-1K` |
| Miniforge | `26.5.3-0`, SHA-256 verified | `.tools/miniforge3` |
| Python / Isaac Sim environment | Installed successfully (~15 GB) | `envs/behavior` |
| BEHAVIOR robot assets | Installed; includes R1Pro URDF/model assets | `data/omnigibson/omnigibson-robot-assets` |
| BEHAVIOR assets | Installed successfully | `data/omnigibson/behavior-1k-assets` |
| Challenge task instances | Installed successfully | `data/omnigibson/2025-challenge-task-instances` |

The licensed data bundle, decryption key, environments, caches, logs, and output
are intentionally Git-ignored. Measured final workspace use is documented in
[`docs/RESOURCES.md`](RESOURCES.md).

## Demonstrations run

| Demonstration | Actual invocation | Outcome | Evidence |
|---|---|---|---|
| Official quickstart | `OMNIGIBSON_GPU_ID=1 ./scripts/run_official_quickstart.sh --smoke` | Passed, exit status 0. The wrapper retains the upstream Fetch/Rs_int quickstart configuration but calls its finite 100-step random-action test path because the original CLI is infinite keyboard teleoperation. | `runs/official-quickstart-smoke-20260831T051152Z.log`; scene import and clean shutdown were recorded. |
| Galaxea R1 Pro task | `OMNIGIBSON_GPU_ID=1 ./scripts/run_r1pro_demo.sh --smoke` | Passed, exit status 0. The wrapper calls the upstream `behavior_env_demo` finite path, selects the cached activity, and executes one 100-step random-action iteration. | `runs/r1pro-behavior-smoke-20260831T052546Z.log`; scene import and clean shutdown were recorded. |

The R1Pro run uses the unmodified upstream
`OmniGibson/omnigibson/configs/r1pro_behavior.yaml`, whose robot is `R1Pro` and
whose task is `BehaviorTask` / `picking_up_trash`. The pinned upstream release
does not label a separate “2026” hardware revision; this verifies its bundled
Galaxea R1 Pro simulation model, not an unprovided year-specific vendor model.

## Local changes made

- Initialized this top-level Git repository, local-only Git identity, ignore policy,
  version lock, isolated path configuration, setup scripts, and operating records.
- Added the pinned `third_party/BEHAVIOR-1K` Git submodule; no third-party source
  code was patched, reformatted, or committed.
- Added a staged local installer. It installs the core stack before the licensed
  data stage, so a failed transfer can be rerun without recreating the environment.
  On this SOCKS-proxy host it adds `httpx[socks]` only inside `envs/behavior`.
- Added `--smoke` modes to the two local launch scripts. They call source-supported
  finite upstream `main()` paths and avoid modifying the upstream examples.
- Updated README, operational guidance, source/resource records, and this delivery
  document with actual installed versions and test results.

## Server and runtime observations

- Host: Ubuntu 20.04.4, kernel 5.15.0-70, 96 logical CPUs, 376 GiB RAM.
- GPUs: 8 × RTX A6000 (49,140 MiB each), driver 535.230.02. GPU 1 was idle before
  testing and was verified as the active renderer and PhysX GPU.
- After both runs GPU 1 returned to 15 MiB / 0% utilization. Final available RAM
  was about 252 GiB; filesystem free space was about 959 GiB.
- First Isaac launch took longer due to RTX shader/PSO cache compilation in the
  local `.omnigibson` directory. Startup also reports harmless headless GLFW and
  full-other-GPU P2P probe warnings; both examples completed successfully despite
  them. Do not use `CUDA_VISIBLE_DEVICES` to select an Isaac/RTX Vulkan device;
  use `OMNIGIBSON_GPU_ID` as documented in [`OPERATIONS.md`](OPERATIONS.md).

## Re-run guide

```bash
cd /data6/xuchenfei/household

# Verify the local prerequisites and then run finite server-safe examples.
./setup.sh preflight
OMNIGIBSON_GPU_ID=1 ./scripts/run_official_quickstart.sh --smoke
OMNIGIBSON_GPU_ID=1 ./scripts/run_r1pro_demo.sh --smoke
```

For a GUI/remote-display session, omit `--smoke` to invoke the original upstream
interactive entry points. The quickstart must be stopped with Escape; the R1Pro
upstream module asks whether to use cached versus online object sampling.

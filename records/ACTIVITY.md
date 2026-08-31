# Activity log

## 2026-08-31

- Initialized `/data6/xuchenfei/household` as an independent Git repository on
  branch `main`; its Git identity is local-only (`Codex Automation`), with no
  global Git configuration changed.
- Adopted the repository convention `third_party/<upstream-name>` for external
  source submodules. An incomplete initial attempt under `vendor/` was removed
  before it contained a valid checkout; the empty `vendor/` directory and its
  empty local Git module directory were then removed at the user's request.
- Checked current upstream releases and changed the planned source from v3.9.2 to
  v3.7.2 because v3.7.2 is the latest selected version compatible with this
  Ubuntu 20.04 server while retaining the bundled R1Pro configuration.
- Completed a shallow, pinned Git submodule checkout of `BEHAVIOR-1K v3.7.2` at
  `third_party/BEHAVIOR-1K`, verified at commit
  `88454bd04f75dc57c00ab1f1a00bcde1ff505950`. It is detached at the exact release
  tag rather than following a mutable branch.
- Recorded preflight results in `records/PREFLIGHT.md` and added isolated setup,
  launch, and reporting scripts. No Conda environment, Isaac Sim package, or
  BEHAVIOR asset has been downloaded yet.
- Downloaded and SHA-256-verified the pinned Miniforge `26.5.3-0` installer, then
  installed Conda `26.5.3` under `.tools/miniforge3`. Its package cache and
  temporary directory resolve inside this workspace; the existing user-level
  `.conda/environments.txt` predates this work and was not modified.
- After the user explicitly accepted the Conda terms, NVIDIA Isaac Sim EULA, and
  BEHAVIOR dataset license, installed the minimal requested stack in `envs/behavior`:
  Python 3.10.21, PyTorch 2.6.0+cu124, BDDL 3.7.0, OmniGibson 3.7.2, and Isaac Sim
  4.5.0.0. The initial data transfer exposed a host SOCKS proxy dependency, so the
  local wrapper now adds `httpx[socks]` only in the isolated environment and can
  resume the dataset stage without recreating the completed environment.
- Downloaded the licensed robot, BEHAVIOR scene/object, and 2025 challenge-instance
  bundles beneath `data/omnigibson`; verified the `models/r1pro` asset and task
  instance directories exist. These files, including the data key, remain ignored.
- Ran the finite, headless official Fetch quickstart smoke and the finite, headless
  bundled `R1Pro` BEHAVIOR smoke on physical GPU 1. Both exited with status 0 and
  released GPU memory afterwards. Their logs are in `runs/`; exact commands and
  caveats are in `docs/DELIVERY.md`.
- Captured a final post-test environment and GPU snapshot at
  `records/runtime/environment-20260831T053713Z.md` after GPU 1 had returned to
  its 15 MiB idle baseline.
- Kept `third_party/BEHAVIOR-1K` clean at its pinned gitlink; no upstream source
  file was changed.

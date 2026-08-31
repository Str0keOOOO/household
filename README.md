# Household robotics simulation workspace

This repository is the reproducible workspace for installing and exercising
BEHAVIOR-1K / OmniGibson for household-service-robot simulation. It is deliberately
an integration repository: upstream source is preserved as a Git submodule, while
local scripts configure the standard per-user Anaconda environment, download
licensed assets, and run examples.

## Layout

```text
.
├── third_party/BEHAVIOR-1K/   # Unmodified upstream Git submodule
├── scripts/                   # Isolated setup, preflight, run, and record helpers
├── docs/                      # Decisions, sources, resources, and operating notes
├── config/                    # Local-only tool configuration templates
├── data/                      # Downloaded BEHAVIOR assets (ignored by Git)
└── runs/                      # Demo logs and output (ignored by Git)
```

Only source, scripts, documentation, configuration templates, and Git submodule
pointers are version-controlled. The Anaconda Distribution and the `behavior`
environment are intentionally held at `/home/xuchenfei/anaconda3`; encrypted
BEHAVIOR assets, decryption keys, and generated output are excluded from Git.
Isaac Sim's shared cache, pip, PyTorch, CUDA, and other general third-party
caches follow their normal user-level locations. OmniGibson app data follows its
upstream default at `third_party/BEHAVIOR-1K/OmniGibson/appdata/`, which the
upstream submodule itself ignores.

## Version policy

The desired policy is the newest version that is supported by the actual server,
not simply the newest upstream commit. This server runs Ubuntu 20.04, so the
selected upstream version is **BEHAVIOR-1K v3.7.2**, which bundles R1Pro and uses
Isaac Sim 4.5. Isaac Sim 4.5 officially supports Ubuntu 20.04 and the observed
NVIDIA driver version. Newer BEHAVIOR v3.9.2 uses Isaac Sim 5.1, whose official
platform support starts at Ubuntu 22.04; it is deliberately not forced here.

Exact version observations are in [versions.lock](versions.lock).

## Normal workflow

```bash
cd /data6/xuchenfei/household
./setup.sh preflight
./setup.sh bootstrap
# After explicitly accepting the listed licenses:
./setup.sh install --accept-licenses
# Finite, non-interactive verification (safe on this headless server):
./scripts/run_official_quickstart.sh --smoke
./scripts/run_r1pro_demo.sh --smoke
# The following two original upstream entry points require a GUI / interaction:
./scripts/run_official_quickstart.sh
./scripts/run_r1pro_demo.sh
```

`install --accept-licenses` is intentionally an explicit opt-in: it accepts the
Conda terms, NVIDIA Isaac Sim EULA, and BEHAVIOR dataset license on the caller's
behalf. See [docs/OPERATIONS.md](docs/OPERATIONS.md) before using it.

## Repository rules

- External source repositories belong under `third_party/` and are Git submodules.
- Do not edit files below `third_party/BEHAVIOR-1K/`. Local integration work belongs
  in this repository outside that path.
- Do not commit downloaded datasets, decryption keys, environments, caches, or
  generated output. The dataset license also prohibits redistribution.
- Do not modify global Git, Pip, OS, or driver configuration. Anaconda is at
  `/home/xuchenfei/anaconda3`, using its standard `envs/behavior` environment
  path. At the user's request, its standard `conda init bash` hook is present in
  `/home/xuchenfei/.bashrc` so new Bash shells can use `conda activate behavior`.

## Current status

Installation is complete. The finite, headless smoke tests for both the official
quickstart and the bundled R1Pro BEHAVIOR task completed successfully on 2026-08-31
with an unmodified upstream submodule. The environment is at the standard Anaconda
location.

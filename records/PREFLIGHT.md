# Server preflight record

Checked: 2026-08-31

| Item | Observed value | Assessment |
|---|---|---|
| OS | Ubuntu 20.04.4 LTS, kernel `5.15.0-70-generic`, x86_64 | Compatible with Isaac Sim 4.5; not officially supported by Isaac Sim 5.1. |
| CPU | Intel Xeon Gold 6248R, 96 logical CPUs | Exceeds Isaac Sim 4.5 baseline. |
| RAM | 376 GiB total, 245 GiB available at check time | Exceeds 64 GiB good-tier guidance. |
| Workspace storage | 1.1 TiB free on `/data6/xuchenfei` | Sufficient for the expected environment, assets, and temporary extraction headroom. |
| GPU | 8 × NVIDIA RTX A6000, 49,140 MiB each | RTX-capable and ample VRAM. |
| Driver | NVIDIA 535.230.02 | Meets Isaac Sim 4.5 Linux minimum/recommended 535.129.03. |
| Initial idle GPU | GPU 1: 13 MiB used, 0% utilization | Selected as the default only; can be overridden by `OMNIGIBSON_GPU_ID`. |

Notes:

- In the default sandbox, `nvidia-smi` could not communicate with the driver. A
  read-only host-side check confirmed all eight GPUs and the driver. Runtime
  verification will be done again before launching the simulator.
- Other GPUs had material allocations at check time, so scripts do not blindly
  default to GPU 0.
- Swap was fully used (7.6 GiB) when checked. This is not a blocker given
  available RAM, but memory pressure should be monitored during the first launch.

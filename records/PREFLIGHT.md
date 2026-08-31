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

## Post-install runtime verification

Checked: 2026-08-31

| Item | Observed value | Assessment |
|---|---|---|
| Local runtime | Python 3.10.21, Torch 2.6.0+cu124, OmniGibson 3.7.2, Isaac Sim 4.5.0.0 | Import and CUDA checks passed. |
| CUDA | `torch.cuda.is_available() == True`; 8 RTX A6000 devices visible | GPU 1 was selected for both simulator tests. |
| Quickstart smoke | Original upstream quickstart configuration, finite 100-step random-action wrapper | Passed, exit status 0; log in `runs/official-quickstart-smoke-20260831T051152Z.log`. |
| R1Pro smoke | Bundled `r1pro_behavior.yaml`, cached `picking_up_trash` activity, finite 100-step wrapper | Passed, exit status 0; log in `runs/r1pro-behavior-smoke-20260831T052546Z.log`. |
| Post-run GPU 1 | 15 MiB used, 0% utilization | Simulator released its GPU allocation cleanly. |
| Final memory | 376 GiB total, 252 GiB available; swap still 7.6 GiB used | Large first launch remained within available RAM. |
| Final workspace storage | 959 GiB free on `/data6/xuchenfei` | Enough working headroom remains. |

Isaac Sim's startup probe emits P2P memory-allocation warnings when it inspects
already-full GPUs 4--7, and headless GLFW warnings because no display server is
present. The Kit log confirmed that physical GPU 1 was active for renderer and
PhysX; both completed examples demonstrated that the warnings were non-fatal.

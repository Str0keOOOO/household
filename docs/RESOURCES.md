# Downloaded and referenced resources

This document distinguishes reproducible source from large or licensed runtime
resources. Update the **State** column after each successful operation.

| Resource | Version / identity | Acquisition | Location | Git state | State |
|---|---|---|---|---|---|
| BEHAVIOR-1K source | `v3.7.2`, commit `88454bd04f75dc57c00ab1f1a00bcde1ff505950` | Git submodule | `third_party/BEHAVIOR-1K` | tracked gitlink | complete |
| Miniforge bootstrap | `26.5.3-0`, SHA-256 `14db468222ad564658656f769506056209b6dc375f5e7dfd31eb5ebbf08fa529` | pinned GitHub release installer + SHA-256 verification | `.tools/miniforge3`, installer in `.downloads` | ignored binary | complete |
| Conda `behavior` environment | Python `3.10.21`, Conda `26.5.3` | upstream setup script | `envs/behavior` (~15 GB) | ignored | complete |
| Isaac Sim | package `4.5.0.0` | NVIDIA Python package index, via upstream setup | local Conda environment | ignored / EULA | complete |
| OmniGibson / BDDL | `3.7.2` / `3.7.0` editable installs | pinned submodule via upstream setup | local Conda environment | ignored runtime metadata | complete |
| CUDA PyTorch | `2.6.0+cu124` (with torchvision `0.21.0+cu124`) | official PyTorch wheel index via upstream setup | local Conda environment | ignored | complete |
| HTTPX SOCKS support | `socksio 1.0.0` | PyPI, only because this host has a SOCKS proxy | local Conda environment | ignored | complete |
| BEHAVIOR robot assets | `omnigibson-robot-assets` including `models/r1pro` | Hugging Face, via upstream setup | `data/omnigibson/omnigibson-robot-assets` | ignored / licensed | complete |
| BEHAVIOR scene and object assets | `behavior-1k-assets-3.7.2rc1` | Hugging Face, via upstream setup | `data/omnigibson/behavior-1k-assets` | ignored / licensed | complete |
| Task instances | `2025-challenge-task-instances` | Hugging Face, via upstream setup | `data/omnigibson/2025-challenge-task-instances` | ignored / licensed | complete |

The upstream installer may resolve transitive Python dependencies, including
version-pinned VCS dependencies. Those are package-manager dependencies inside the
isolated environment, not user-maintained source checkouts; their resolved versions
are captured by `scripts/capture_versions.sh` after installation.

## Installed footprint and transfer note

Measured after both smoke tests: `data/` is approximately 36 GB, `envs/` 15 GB,
package/cache directories about 2.7 GB, and OmniGibson's runtime cache about 8.9 GB.
The filesystem retained about 959 GB free. The 25 GB compressed BEHAVIOR asset
transfer used Hugging Face Xet and encountered retryable SOCKS/TLS EOF messages;
the local wrapper installed the missing `httpx[socks]` support into `envs/behavior`
and the upstream downloader completed successfully. No data, key, environment, or
cache is tracked by Git.

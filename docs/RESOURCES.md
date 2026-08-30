# Downloaded and referenced resources

This document distinguishes reproducible source from large or licensed runtime
resources. Update the **State** column after each successful operation.

| Resource | Version / identity | Acquisition | Location | Git state | State |
|---|---|---|---|---|---|
| BEHAVIOR-1K source | `v3.7.2`, commit `88454bd04f75dc57c00ab1f1a00bcde1ff505950` | Git submodule | `third_party/BEHAVIOR-1K` | tracked gitlink | complete |
| Miniforge bootstrap | `26.5.3-0`, SHA-256 `14db468222ad564658656f769506056209b6dc375f5e7dfd31eb5ebbf08fa529` | pinned GitHub release installer + SHA-256 verification | `.tools/miniforge3`, installer in `.downloads` | ignored binary | complete |
| Conda `behavior` environment | Python 3.10 | upstream setup script | `envs/behavior` | ignored | pending |
| Isaac Sim | 4.5.0 | NVIDIA Python package index, via upstream setup | local Conda environment | ignored / EULA | pending |
| BEHAVIOR robot assets | upstream selected data bundle | Hugging Face, via upstream setup | `data/omnigibson` | ignored / licensed | pending |
| BEHAVIOR scene and object assets | upstream selected data bundle | Hugging Face, via upstream setup | `data/omnigibson` | ignored / licensed | pending |
| Task instances | release-compatible bundle | Hugging Face, via upstream setup | `data/omnigibson` | ignored / licensed | pending |

The upstream installer may resolve transitive Python dependencies, including
version-pinned VCS dependencies. Those are package-manager dependencies inside the
isolated environment, not user-maintained source checkouts; their resolved versions
are captured by `scripts/capture_versions.sh` after installation.

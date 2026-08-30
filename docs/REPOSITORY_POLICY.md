# Repository and dependency policy

## Ownership boundaries

- This top-level repository owns only its scripts, documentation, configuration,
  and integration records.
- Every manually added third-party source repository is placed under
  `third_party/` as a Git submodule with an intentional revision.
- `third_party/BEHAVIOR-1K` is upstream-owned and must remain clean. Do not patch,
  reformat, or commit inside it for local experiments.
- Future local adapters belong outside `third_party/`, with their own documented
  relationship to an upstream revision.

## Reproducibility boundaries

- Git tracks human-authored source and exact submodule pointers.
- It does not track Conda environments, Python wheel caches, NVIDIA packages,
  generated results, encrypted assets, decryption keys, or other licensed data.
- Scripts must retain a source URL, version, integrity check when available, target
  path, and license note for each non-Git download.
- Before upgrading a dependency, capture the previous revision, read release notes,
  test the requested examples, and record the outcome in `docs/DELIVERY.md`.

## Isolation boundaries

All mutable state that the project can direct is scoped to this workspace. No
script may modify global Git/Conda/Pip configuration, shell startup files, OS
packages, driver settings, or files belonging to another project.

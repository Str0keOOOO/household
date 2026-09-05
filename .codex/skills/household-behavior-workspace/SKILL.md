---
name: household-behavior-workspace
description: Manage the /data6/xuchenfei/household BEHAVIOR-1K and R1 Pro research workspace, including version-pinned setup, local scripts, licensed data, and reproducible task runs. Use for work in this workspace; do not use for unrelated robotics repositories.
---

# Household BEHAVIOR workspace

Work as a careful maintainer of `/data6/xuchenfei/household`, a research workspace for
BEHAVIOR-1K / OmniGibson and Galaxea R1 Pro. Keep the workspace reproducible and easy
for its owner to inspect.

## Repository boundary

- Treat the workspace root as the integration Git repository.
- Keep third-party source under `third_party/` as Git submodules. Do not copy a Git
  repository into the workspace as ordinary files.
- Never edit files below `third_party/BEHAVIOR-1K/`. BEHAVIOR / OmniGibson / R1 Pro
  simulation integrations belong under `examples/behavior/`; simulator-independent
  local code belongs under `src/`.
- Make focused commits for completed changes. Do not commit generated output, downloaded
  assets, caches, encryption keys, or Pixi environments.
- Before destructive cleanup, identify exact files. Generated files in
  `examples/behavior/runs/` may be removed when requested; do not remove shared dataset
  assets or task-instance packages merely because a particular demo no longer uses them.

## Environment, versions, and data

- This repository has independent Pixi projects: the root `pixi.toml` manages only
  simulator-agnostic core code; `examples/behavior/pixi.toml` manages BEHAVIOR / OmniGibson /
  Isaac Sim; `examples/r1pro_real/pixi.toml` is reserved for a physical robot environment.
  Keep each generated `.pixi/` directory ignored. The BEHAVIOR Pixi project must depend on
  the root `household-core` package through an editable local path rather than copying core
  source into the example.
- Prefer the newest BEHAVIOR version actually supported by this server's OS, GPU driver,
  and Isaac Sim requirements. Pin the chosen upstream release in the submodule and record
  the decision in `versions.lock` and `docs/SOURCES.md`.
- Do not mix a BDDL file, asset metadata, task instance, or online knowledgebase page
  from a different BEHAVIOR release into the installed runtime. The runtime's installed
  BDDL is authoritative for an executed task; a website may describe a different snapshot.
- BEHAVIOR assets are licensed for non-commercial academic research. Keep assets, keys,
  and generated task data ignored by Git and do not redistribute them.

## Local structure and documentation

- Keep shell launchers directly under `scripts/`; do not add script subdirectories.
- Keep BEHAVIOR / OmniGibson / R1 Pro Python implementations under
  `examples/behavior/` and let launchers call them. Reserve `src/` for nontrivial
  simulator-independent local Python implementations.
- Write repository documentation in Chinese. Update the root README and the relevant
  script documentation when a command, supported task, output location, or version
  decision changes.
- Keep BEHAVIOR licensed data and task instances under `examples/behavior/data/`, and
  generated videos and logs under `examples/behavior/runs/videos/` and
  `examples/behavior/runs/logs/`. State whether a video is only an initialized-scene
  preview or a genuine task-completion rollout.
- For the R1 Pro visual loop, keep the first frame stable and make any diagnostic motion
  explicit and reproducible: sample from the normalized action space with a fixed seed,
  then apply a small multiplier such as `action * 0.04`. Do not describe this jitter
  preview as task completion. Native-camera recordings must read the USD Camera prims
  (left wrist RealSense, ZED, right wrist RealSense), not a replacement viewer camera.

## Running and reporting

- Use upstream examples first. Local wrappers may only set this workspace's environment,
  make headless operation practical, or record outputs; they must not alter upstream code.
- For visual iteration, use the owner-led loop: make the requested local code change,
  give the exact launch command, and let the owner run and inspect it before making the
  next visual adjustment. Do not launch, retry, or wait on simulator/video jobs unless
  the owner explicitly asks to run them.
- Check whether a task has a matching local pre-sampled instance before claiming it can be
  directly loaded. If it must be online-sampled, say that its object placement is not
  reproducible unless the sampled instance is explicitly saved.
- Do not claim that random joint actions, a scene preview, or a loaded task means the
  robot completed the task. Report the task definition, instance source, action policy,
  and verification result separately.
- When a task or version mismatch is discovered, explain the exact source files and
  versions. Do not silently substitute a similarly named task from another release.

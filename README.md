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
├── scripts/                   # Local setup, diagnostic, and demo helpers
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
./scripts/official_quickstart.sh --smoke
./scripts/r1pro_behavior_demo.sh --smoke
# 在无桌面服务器生成可下载观看的 MP4：
./scripts/r1pro_record_demo.sh
```

`install --accept-licenses` is intentionally an explicit opt-in: it accepts the
Conda terms, NVIDIA Isaac Sim EULA, and BEHAVIOR dataset license on the caller's
behalf. The daily upstream commands and their optional local wrappers are listed
in [scripts/README.md](scripts/README.md).

## WebRTC 实时观看

以下是旧版 Isaac Sim 的浏览器客户端地址，按要求保留作参考；它**不适用于当前
Isaac Sim 4.5 安装**，不可将其视为可用服务：

<http://10.184.17.155:8211/streaming/webrtc-client?server=10.184.17.155>

当前 Isaac Sim 4.5 官方推荐使用桌面版 *Isaac Sim WebRTC Streaming Client*，而非
浏览器页面。此服务器实际运行网卡地址为 `10.184.17.151`。BEHAVIOR-1K v3.7.2 的
远程串流代码仍请求旧扩展 `omni.services.streamclient.webrtc`，与 Isaac Sim 4.5 的
`omni.kit.livestream.webrtc` 不兼容；需要本仓库增加兼容启动器后，才能使用官方桌面
客户端连接。

## 无桌面录像

若只需稳定地观察或留存一次运行，不必配置远程串流：

```bash
./scripts/r1pro_record_demo.sh
```

该本地启动器沿用上游 R1 Pro BEHAVIOR 示例的预采样场景、任务配置和相机位姿，在
无界面模式将 viewer camera 输出写入忽略的 `runs/r1pro-behavior-<UTC 时间>.mp4`。
它不会修改 `third_party/BEHAVIOR-1K/`。可用 `--steps 40 --frame-stride 2` 缩短演示，
或用 `--width 640 --height 360` 控制分辨率。

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

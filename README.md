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
├── scripts/                   # Local shell setup, diagnostic, and demo launchers
├── src/                       # Local Python implementations called by scripts
├── config/                    # Local-only tool configuration templates
├── data/                      # Downloaded BEHAVIOR assets (ignored by Git)
│   └── omnigibson/
│       ├── 2025-challenge-task-instances/  # Official pre-sampled instances
│       └── local-task-instances/            # Locally sampled, persistent instances
└── runs/                      # Generated output: videos/ and logs/ (ignored by Git)
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
./setup.sh bootstrap
# After explicitly accepting the listed licenses:
./setup.sh install --accept-licenses
# Finite, non-interactive verification (safe on this headless server):
./scripts/official_quickstart.sh --smoke
./scripts/r1pro_behavior_demo.sh --smoke
# 在无桌面服务器生成可下载观看的 MP4：
./scripts/r1pro_record_demo.sh
# 生成 heating_food_up 的初始化场景视频：
./scripts/r1pro_heating_food_scene.sh
# 生成可复现的随机小幅抖动录像：
./scripts/r1pro_heating_food_scene.sh --random-jitter --jitter-scale 0.04 --seed 20260901 --frames 120 --fps 20
```

`install --accept-licenses` is intentionally an explicit opt-in: it accepts the
Conda terms, NVIDIA Isaac Sim EULA, and BEHAVIOR dataset license on the caller's
behalf. The daily upstream commands and their optional local wrappers are listed
in [scripts/README.md](scripts/README.md).

## 本地任务实例与录像

`data/omnigibson/2025-challenge-task-instances/` 是下载的官方预采样任务包；不要
修改其中的内容。对官方包中没有预采样模板的任务（目前是 `heating_food_up`），本仓库
会将一次成功的本地采样结果保存到
`data/omnigibson/local-task-instances/`。保存的是完整场景 JSON，之后加载该 JSON，
不再重新在线采样，因此同一台服务器上的运行可复现。

该目录和 `data/` 的其余内容一样受 BEHAVIOR 数据许可约束，已被 Git 忽略；Git 只
记录生成脚本、所选场景/模型和随机种子；本地 manifest 记录校验值，不能重新分发任务 JSON。录像不放在数据目录，
统一写到 `runs/videos/`，对应日志写到 `runs/logs/`。这样可以清理录像而不影响已保存的
任务实例，也可以重录视频而不改变场景。

## 渲染与光影

本地场景录像使用 RTX `RealTimePathTracing` 实时光线追踪模式，保留光照、阴影、反射和
间接漫反射，并启用 DLSS Quality。第三人称视频默认 1280×720，原生相机视频的三个面板
默认各为 480×480；三个面板来自 R1 Pro USD 中固定相对路径
`left_realsense_link/Camera`、`zed_link/Camera`、`right_realsense_link/Camera` 的独立 RGB
render product，不是移动的 viewer camera。它们不是开销显著更高的
离线路径追踪。服务器的 RTX A6000 可运行此模式。

R1 Pro 录制初始姿态采用 OmniGibson 默认的 `tuck`（双臂收拢、机身直立）设置；这只是
初始化姿态，不代表机器人已经执行任务。原生腕部相机仍会输出画面，但其视野会随收拢的手臂改变。

`heating_food_up` 的本地配置会在加载基础任务实例后打开指定冰箱，并将汉堡通过物理落体落在
上层搁板；机器人仍使用任务实例保存的原始站位。该覆盖不改写受许可保护的任务 JSON，也不代表
机器人已经执行开门或放置动作。

## WebRTC 实时观看

以下是旧版 Isaac Sim 的浏览器客户端地址，按要求保留作参考；它**不适用于当前
Isaac Sim 4.5 安装**，不可将其视为可用服务：

<http://10.184.17.155:8211/streaming/webrtc-client?server=10.184.17.155>

当前 Isaac Sim 4.5 官方推荐使用桌面版 *Isaac Sim WebRTC Streaming Client*，而非
浏览器页面。使用本仓库的专用启动器：

```bash
./scripts/r1pro_heating_food_streaming.sh
```

它在当前 OmniGibson 体验中启用已安装的 `omni.kit.livestream.webrtc` 扩展，完成录像后
仍保持 30 分钟会话；在自己的桌面电脑启动官方客户端并填写服务器可达 IP（例如
`10.184.17.155`）连接。串流没有认证或加密，限可信内网使用，并确保该服务器的 WebRTC
串流端口可从客户端访问。

## 无桌面录像

若只需稳定地观察或留存一次运行，不必配置远程串流：

```bash
./scripts/r1pro_record_demo.sh
```

该本地启动器沿用上游 R1 Pro BEHAVIOR 示例的预采样场景、任务配置和相机位姿，在
无界面模式将 viewer camera 输出写入忽略的
`runs/videos/r1pro-behavior-<UTC 时间>.mp4`。
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

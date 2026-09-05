# Household robotics simulation workspace

这是 household 的多 Pixi project 工作区。根项目只承载通用 planner / protocol / WebSocket
代码；BEHAVIOR 仿真是一个按需安装的独立项目。上游源码始终是子模块，未复制到本仓库的 `src/`。

## Layout

```text
.
├── pixi.toml / pixi.lock              # 核心 planner 环境（独立，锁文件由 pixi lock 生成）
├── pyproject.toml                     # household-core 的 editable 包元数据
├── src/                               # 通用 protocol、serving、planner
├── examples/
│   ├── behavior/                      # 独立的 BEHAVIOR integration Pixi project
│   │   ├── pixi.toml / pixi.lock      # BEHAVIOR 3.7.2 / Isaac Sim 4.5（独立锁文件）
│   │   ├── data/omnigibson/          # Licensed assets and task instances (ignored by Git)
│   │   ├── runs/                     # Generated videos and logs (ignored by Git)
│   │   ├── r1pro/                    # R1 Pro example entrypoints
│   │   └── heating_food_up/          # Task, adapter, recording, and rollout
├── scripts/                          # Installation and stable launch entrypoints
└── third_party/BEHAVIOR-1K/          # Unmodified upstream Git submodule
```

依赖方向固定为：`examples/behavior` → editable 本地 `household-core` → 根目录 `src/`。
因此 BEHAVIOR client 可以直接 `import protocol` 和 `serving`，但不会复制通用通信代码。
根目录的 Pixi 环境只承载通用 planner；BEHAVIOR 环境由官方 Conda 流程创建在
`examples/behavior/.conda/`。BEHAVIOR 资产、密钥和运行输出仍不提交。

## Version policy

The desired policy is the newest version that is supported by the actual server,
not simply the newest upstream commit. This server runs Ubuntu 20.04, so the
selected upstream version is **BEHAVIOR-1K v3.7.2**, which bundles R1Pro and uses
Isaac Sim 4.5. Isaac Sim 4.5 officially supports Ubuntu 20.04 and the observed
NVIDIA driver version. Newer BEHAVIOR v3.9.2 uses Isaac Sim 5.1, whose official
platform support starts at Ubuntu 22.04; it is deliberately not forced here.

Exact version observations are in [versions.lock](versions.lock).

## 安装与运行

只需 planner 时，只在根目录安装：

```bash
cd /data6/xuchenfei/household
pixi install
pixi run server
```

需要仿真时，使用 Pixi 统一入口调用 BEHAVIOR 官方 Conda 安装流程。运行前请自行确认
NVIDIA 与 BEHAVIOR 许可证；它不下载受许可的 BEHAVIOR 场景资产。

```bash
cd /data6/xuchenfei/household
pixi run setup-behavior
cd examples/behavior
pixi run demo
```

安装结果固定在 `examples/behavior/.conda/`。`setup-behavior` 先按官方顺序创建
Python 3.10 Conda prefix、安装官方指定的 numpy/setuptools 和 CUDA 12.4 PyTorch，
再调用 `third_party/BEHAVIOR-1K/setup.sh --bddl --omnigibson` 安装 BDDL、OmniGibson
和 Isaac Sim；Pixi 不参与 BEHAVIOR 依赖解析。

上游 `setup.sh` 的可选组件仍可在目标 Conda prefix 中按官方文档单独安装；当前统一入口默认
不下载数据集或安装这些组件。安装完成后，在 `examples/behavior` 目录运行仿真入口：

```bash
pixi run demo
```

planner server 则在根项目运行 `pixi run server`。

要让一次有限时长的录制同时连接 planner（需要另一个终端先运行根项目 server）：

```bash
# terminal 1
cd /data6/xuchenfei/household
pixi run server

# terminal 2
cd /data6/xuchenfei/household/examples/behavior
pixi run rollout --cycles 200 --fps 20
```

`rollout` 会启动 Pixi 环境中的 Isaac Sim、恢复 `heating_food_up` 场景；每个周期采集一次
R1 Pro `raw_obs`，经过 `BehaviorR1ProAdapter` 后阻塞调用 WebSocket planner，再在 BEHAVIOR
本地逐步执行完整 action chunk，最后才进入下一周期。WebSocket 在整个 rollout 中保持长连接，
`--cycles` 表示完整的 plan/execute 周期数；录像写入 `runs/videos/`，达到周期数或任务结束后自动关闭。

### 常驻 episode server(多轮任务免冷启动)

`rollout` 每轮都会重新启动 Isaac Sim 并重新加载整栋房子场景，冷启动约 3 分钟。需要由外层
脚本/评测框架连续跑多轮时，先把仿真端常驻（控制接口在
`examples/behavior/heating_food_up/episode_server.py`），只有第一轮付完整冷启动，
后续每轮只付 `env.reset()`：

```bash
# terminal 1:planner server(不变)
cd /data6/xuchenfei/household
pixi run server

# terminal 2:常驻仿真服务,加载完成后打印 Environment ready,保持运行
cd /data6/xuchenfei/household/examples/behavior
pixi run episode-server

# terminal 3:每轮一个轻量请求(秒级启动,不导入 OmniGibson/Isaac Sim)
pixi run episode --cycles 200 --fps 20
```

`episode-server` 默认监听 `ws://0.0.0.0:8100`；场景/任务/分辨率在启动时固定，每轮可改
`cycles/fps/prompt/robot_posture/camera_view/output`，请求排队串行执行。详见
`examples/behavior/README.md` 的「常驻 episode server」一节。

## 本地任务实例与录像

`examples/behavior/data/omnigibson/2025-challenge-task-instances/` 是下载的官方预采样任务包；不要
修改其中的内容。对官方包中没有预采样模板的任务（目前是 `heating_food_up`），本仓库
会将一次成功的本地采样结果保存到
`examples/behavior/data/omnigibson/local-task-instances/`。保存的是完整场景 JSON，之后加载该 JSON，
不再重新在线采样，因此同一台服务器上的运行可复现。

该目录和 `examples/behavior/data/` 的其余内容一样受 BEHAVIOR 数据许可约束，已被 Git 忽略；Git 只
记录生成脚本、所选场景/模型和随机种子，不能重新分发本地任务 JSON。录像不放在数据目录，
统一写到 `examples/behavior/runs/videos/`，对应日志写到 `examples/behavior/runs/logs/`。这样可以清理录像而不影响已保存的
任务实例，也可以重录视频而不改变场景。

## 渲染与光影

本地场景录像使用 RTX `RealTimePathTracing` 实时光线追踪模式，保留光照、阴影、反射和
间接漫反射，并启用 DLSS Quality。第三人称视频默认 1280×720。planner 采集的三路 R1 Pro
VisionSensor（`left_realsense_link/Camera`、`zed_link/Camera`、`right_realsense_link/Camera`）
统一渲染为 256×256 RGB-D；它们不是移动的 viewer camera，也不是开销显著更高的离线路径追踪。
服务器的 RTX A6000 可运行此模式。

R1 Pro 录制初始姿态默认采用 `untuck`（双臂展开）设置；这只是初始化姿态，不代表机器人已经执行任务。
原生腕部相机仍会输出画面，且其视野会随双臂姿态改变。

`heating_food_up` 的本地配置会在加载基础任务实例后打开指定冰箱，并将汉堡通过物理落体落在
上层搁板；机器人从任务实例保存的位姿恢复后，覆盖其位置和朝向以居中正对冰箱。该覆盖不改写受
许可保护的任务 JSON，也不代表机器人已经执行开门或放置动作。

## 无桌面录像

需要保存一次无桌面 BEHAVIOR 运行时，先在根目录启动 planner server，再运行同步 rollout：

```bash
# terminal 1
cd /data6/xuchenfei/household
pixi run server

# terminal 2
cd /data6/xuchenfei/household/examples/behavior
pixi run rollout --cycles 200 --fps 20
```

录像写入忽略的 `examples/behavior/runs/videos/`，对应日志写入
`examples/behavior/runs/logs/`。该流程不会修改 `third_party/BEHAVIOR-1K/`。

## Planner 通信接口

`examples/behavior/heating_food_up/adapter.py` 将 BEHAVIOR 的 plain `raw_obs` 转成统一的
`planner_obs`；其 RGBD 均为 `H x W x 4 float32`，RGB 在 `[0, 1]`，depth 为 meter。`state` 的
固定 27 维顺序由 `STATE_LAYOUT` 定义。当前 `server` 使用 `MockPlanner` 返回 `(4, 23) float32`
小幅连续 action chunk，后续可直接替换为真实 planner。通信采用长期 WebSocket 连接和 MessagePack +
NumPy 二进制编码；`rollout.py` 是真实 BEHAVIOR 场景的同步有限录制入口，直接执行 planner 返回的
23 维 OmniGibson scene action。MockPlanner 只生成 torso、右臂和右夹爪的小幅动作，base 和左侧
控制维度为零。

## Planner 模块与第三方源码

核心算法保持在固定的 `src/planner/` 边界内，不再新增 `perception/` 或
`planning/` 顶层包：

```text
src/
├── protocol.py
├── serving/
└── planner/
    ├── __init__.py
    ├── base.py
    └── mock.py
```

各模块职责是：`base.py` 定义统一 `infer(obs) -> {"actions": actions}` 接口；
`mock.py` 提供当前 WebSocket 联调的平滑 MockPlanner。未来 AnyGrasp、候选排序、cuRobo
轨迹规划和 retreat planning 在真正实现后再加入 `src/planner/`，当前不保留空壳文件。
`__init__.py` 导出公共接口。WebSocket server 只依赖统一 planner 接口，不直接导入第三方实现。

后续真实规划的数据流保持为：

```text
WebSocket Server
      ↓ planner.infer(obs)
AnyGraspAdapter
      ↓ grasp candidates
GraspRanker
      ↓ selected grasp
CuRoboPlanner
      ↓ joint trajectory / action chunk
RetreatPlanner
      ↓ actions
```

第三方源码只放在 `third_party/`：

```text
third_party/BEHAVIOR-1K/  # simulation dependency
third_party/anygrasp/     # grasp perception dependency
third_party/curobo/       # motion planning dependency
```

AnyGrasp 和 cuRobo 的源码版本由 Git submodule commit 固定；不修改第三方目录内部源码，
也不让实验代码隐式跟随 `main`。完整克隆时使用：

```bash
git clone --recursive <repo>
git submodule update --init --recursive
```

需要手动补齐两个 submodule 时使用官方仓库：

```bash
git submodule add https://github.com/NYU-robot-learning/anygrasp.git third_party/anygrasp
git submodule add https://github.com/NVlabs/curobo.git third_party/curobo
```

## Repository rules

- External source repositories belong under `third_party/` and are Git submodules.
- Do not edit files below `third_party/BEHAVIOR-1K/`. Local integration work belongs
  in this repository outside that path.
- Do not commit downloaded datasets, decryption keys, environments, caches, or
      generated output. The dataset license also prohibits redistribution.
- Do not modify global Git, Pip, Pixi, OS, or driver configuration. The BEHAVIOR
      environment is the ignored `examples/behavior/.conda/` prefix.

## Current status

BEHAVIOR-1K v3.7.2 remains an unmodified submodule. The current installation path
uses the root `pixi run setup-behavior` task as a wrapper around the official Conda
flow; Isaac Sim 4.5 and the BEHAVIOR dependencies are installed into
`examples/behavior/.conda/`, outside the Pixi solver input.

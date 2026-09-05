# BEHAVIOR integration

这个目录保存 BEHAVIOR v3.7.2、OmniGibson 和 R1 Pro 仿真接入代码。运行环境由
官方 Conda 安装流程管理，固定在 `.conda/`；通用的 protocol / WebSocket / planner
代码通过根项目源码路径引入，不复制第三方源码。

## 安装

```bash
cd <repository-root>
pixi run setup-behavior
```

`setup-behavior` 只作为 Pixi 的统一入口，内部按 BEHAVIOR 官方顺序创建 Conda
prefix、安装官方指定的 numpy/setuptools 和 CUDA 12.4 PyTorch，再调用官方
`third_party/BEHAVIOR-1K/setup.sh --bddl --omnigibson` 安装 BDDL、OmniGibson 和
Isaac Sim。不会把 BEHAVIOR 依赖交给 Pixi 解析。

如果 `.conda/` 已存在且可用，脚本会直接退出；不会自动删除或重建。只有明确需要重装时，
才执行：

```bash
pixi run setup-behavior --force
```

运行 task 会通过 `conda run --no-capture-output -p .conda` 调用该环境，不需要手动
`conda activate`。

## 运行

先启动根项目 planner server：

```bash
cd /data6/xuchenfei/household
pixi install
pixi run server
```

再在本目录启动有限时长的 BEHAVIOR 录制和 planner 通信：

```bash
cd /data6/xuchenfei/household/examples/behavior
pixi run rollout --frames 200 --fps 20
```

这条命令通过 `conda run -p .conda` 使用官方 Conda 环境中的 Isaac Sim，同步执行每个规划周期：

```text
采集 raw_obs → BehaviorR1ProAdapter → 阻塞 WebSocket planner → 完整 action chunk → env.step
```

planner 返回 12 维 action chunk 后，本地执行适配器会将其映射到 OmniGibson 的 23 维场景
action（base 和左臂暂时保持零控制），BEHAVIOR 才逐步执行其中的 action；执行完成后才发送下一次
observation。`--frames` 表示 plan/execute 周期数。录像保存在 `runs/videos/`，BEHAVIOR
侧日志自动保存在 `runs/logs/rollout-<UTC>.log`，同时继续显示在终端。server 默认只
显示在 server 终端；如需保存 server 日志，可显式传入 `--log-file`。

其他入口：

```bash
cd <repository-root>/examples/behavior
pixi run demo
pixi run streaming-demo
```

## GPU 选择

OmniGibson 默认使用 GPU 0（同时用作渲染和物理）。这台机器是多卡共享，
如果 GPU 0 被其他任务占用，启动时会刷大量
`carb.cudainterop.plugin ... cudaErrorMemoryAllocation` 并在十几秒后无声退出。
先查空闲卡：

```bash
nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv
```

再用 OmniGibson 自己的 `OMNIGIBSON_GPU_ID` 指定物理 GPU。不要只设置
`CUDA_VISIBLE_DEVICES`：Isaac Sim 和 CUDA 的设备枚举可能不同，日志也会提示这会导致
不期望的行为或崩溃：

```bash
env -u CUDA_VISIBLE_DEVICES OMNIGIBSON_GPU_ID=1 pixi run rollout --frames 200 --fps 20
env -u CUDA_VISIBLE_DEVICES OMNIGIBSON_GPU_ID=1 pixi run episode-server
```

这里的 `1` 是机器上的物理 GPU 编号。若日志中显示 `--/physics/cudaDevice=1`，并且
GPU 表中 bus/UUID 对应第 1 卡，才表示确实选中了物理 GPU 1；即使 CUDA 侧显示
`cuda:0`，也可能只是可见设备后的逻辑编号。

## 常驻 episode server(多轮任务免冷启动)

`rollout` 每次运行都会重新启动 Isaac Sim 并重新加载整栋房子场景（冷启动约
3 分钟，其中约 2 分钟在 `og.Environment` 构建）。如果外层脚本/评测框架需要连续
跑多轮，把仿真端也变成常驻服务后，只有第一轮付完整冷启动，后续每轮只付一次
`env.reset()` + 任务重初始化：

```bash
# terminal 1:planner server（不变）
cd /data6/xuchenfei/household
pixi run server

# terminal 2:常驻仿真服务。启动约 3 分钟后打印 Environment ready；保持运行
cd /data6/xuchenfei/household/examples/behavior
pixi run episode-server

# terminal 3:每轮请求一个有限时长的 round（秒级启动，不拉起 Isaac Sim）
pixi run episode --frames 200 --fps 20
pixi run episode --frames 100 --output /path/to/round-2.mp4 --robot-posture untuck
```

要点：

- `episode-server` 默认监听 `ws://0.0.0.0:8100`，planner 仍连 `ws://127.0.0.1:8000`；
  可用 `--host/--port/--planner-uri` 调整。
- 场景、任务模板、渲染分辨率在 `episode-server` 启动时固定；每轮可改
  `--frames/--fps/--prompt/--robot-posture/--camera-view/--output`。
- 每轮结束自动回到该任务模板的初始状态：第一轮直接用刚加载的初始状态（不重复
  `env.reset()`），之后每轮先 `env.reset()` 再重新应用 `heating_food_up/config.json`
  的初始化（开冰箱、汉堡落位、机器人位姿）。
- 同一时刻只执行一轮，其余请求排队；planner 连接在 daemon 内常驻复用。
- 成功返回 `cycles/done/output/reset`，失败返回 `error`；客户端退出码反映成败，
  失败时删除半截录像。
- 录像默认写到 `runs/videos/episode-<UTC>.mp4`（可用 `BEHAVIOR_RUNS_PATH` 调整）。

## 路径约定

- BEHAVIOR Conda prefix：`.conda/`
- BEHAVIOR 数据：`data/omnigibson/`（Git 忽略）
- 录像与运行日志：`runs/`（Git 忽略）
- 上游源码：`../../third_party/BEHAVIOR-1K/`，不修改其中任何源码

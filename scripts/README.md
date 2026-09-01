# 脚本说明

此目录仅包含本工作区的辅助脚本；没有复制、移动或修改任何上游脚本。官方
BEHAVIOR-1K 源码始终位于 `../third_party/BEHAVIOR-1K/` 子模块。

```text
scripts/
├── env.sh                         # 共用环境变量：数据、Anaconda、源码与 GPU
├── bootstrap_anaconda.sh           # 安装锁定版本的 Anaconda
├── install_behavior.sh             # 调用上游安装器并下载许可数据
├── official_quickstart.sh          # 官方键盘控制示例的包装器
├── r1pro_behavior_demo.sh          # 官方 R1 Pro BEHAVIOR 示例的包装器
├── r1pro_record_demo.sh            # 无桌面录制 R1 Pro 示例为 MP4 的启动器
└── r1pro_heating_food_scene.sh     # 录制 heating_food_up 的初始化场景

src/
├── r1pro_record_demo.py            # r1pro_record_demo.sh 调用的本地录像逻辑
├── r1pro_task_scene_record.py      # 已保存任务实例的静态场景录像逻辑
└── sample_behavior_task_instance.py # 一次性采样并保存完整任务实例
```

## 日常使用

优先使用上游 Python 入口；先设置本工作区的数据路径并激活环境：

```bash
cd /data6/xuchenfei/household
source scripts/env.sh
conda activate behavior
```

| 目标 | 上游原始入口 | 本地可选包装器 |
| --- | --- | --- |
| 键盘控制机器人 | `python -m omnigibson.examples.robots.robot_control_example --quickstart` | `./scripts/official_quickstart.sh` |
| R1 Pro BEHAVIOR 任务 | `python -m omnigibson.examples.environments.behavior_env_demo` | `./scripts/r1pro_behavior_demo.sh` |
| 录制 R1 Pro 示例 | 无 | `./scripts/r1pro_record_demo.sh` |
| 有限无头验证 | 无；上游示例是交互式的 | 两个包装器均可加 `--smoke` |

包装器不会改动上游源码；它们只负责激活环境、设置本工作区数据路径，并将运行
输出按格式保存到忽略的 `runs/` 目录：MP4 位于 `runs/videos/`，日志位于
`runs/logs/`。

## 无桌面录像

在服务器上生成 MP4 是不依赖远程桌面或 WebRTC 的观看方式：

```bash
./scripts/r1pro_record_demo.sh
```

它复用上游 `r1pro_behavior.yaml`、预采样场景和官方示例中的相机位姿，默认运行
100 个随机动作、每 4 步保留一帧，写入
`runs/videos/r1pro-behavior-<UTC 时间>.mp4`；相应日志写入 `runs/logs/`。可按需控制
长度与画面大小，例如：

```bash
./scripts/r1pro_record_demo.sh --steps 40 --fps 10 --frame-stride 2 --width 640 --height 360
```

录像 Python 实现在 `src/r1pro_record_demo.py`；它是本地集成代码，不改动上游示例。
生成的视频和日志均被 Git 忽略。

## heating_food_up 场景视频

以下命令生成 `heating_food_up` 的初始化场景视频；MP4 保存至 `runs/videos/task_scene/`，
日志保存至 `runs/logs/task_scene/`：

```bash
./scripts/r1pro_heating_food_scene.sh
```

视频只展示已初始化的 R1 Pro 和任务场景；没有发送机器人动作，也不表示机器人完成了
任务。第三人称视频和原生相机视频来自同一初始化状态，不推进旧模板中可能不稳定的物理状态。

如需查看关节控制的可复现小幅随机抖动，运行：

```bash
./scripts/r1pro_heating_food_scene.sh --random-jitter --jitter-scale 0.04 --seed 20260901 --frames 120 --fps 20
```

该模式每帧执行 `env.step(action * 0.04)`：`action` 从 R1 Pro 的归一化动作空间中、以
`20260901` 为随机种子采样。它仅用于检查控制和相机，不是任务策略，也不代表完成任务。

| 文件 | 内容与质量 |
| --- | --- |
| `heating_food_up.mp4` | 第三人称，1280×720；RTX Real-Time 2.0（`RealTimePathTracing`）与 DLSS Quality。 |
| `heating_food_up-r1pro-native-cameras.mp4` | R1 Pro 原生相机横向拼接：左腕 RealSense → ZED → 右腕 RealSense；每路默认 480×480，成片为 1440×512（含标签栏）。 |

Python 实现位于 `src/r1pro_task_scene_record.py`，第三人称相机位置由 R1 Pro 和任务物体的位置计算；当前启动器使用已经验证的 `near_right` 机位，避免在服务器上逐个扫描候选机位造成长时间等待。需要自动评分时可给录制器传 `--camera-view auto`。录像采用 NVIDIA 推荐给机器人和合成数据工作流的 RTX Real-Time 2.0
（`RealTimePathTracing`）与 DLSS Quality。原生相机视频按 R1 Pro USD 的固定布局读取三个
明确的 Camera prim 相对路径：`left_realsense_link/Camera`、`zed_link/Camera`、
`right_realsense_link/Camera`，再拼接当前 `robot.prim_path` 的运行时前缀；为每个 prim
建立独立的 RGB Replicator render product，不改变 Camera prim 的位姿。`--camera-width` 和
`--camera-height` 只调整这些 render product 的分辨率。这样绕过 OmniGibson 1.5 只扫描
link 直接子节点的限制，录像内容与控制策略读取的原生相机坐标和朝向一致。录制器将 R1 Pro 初始关节姿态
设为官方任务采样器使用的 `untuck`；这不是任务动作，只是让腕部相机朝向工作区。

`heating_food_up` 首次采样后会保存完整 JSON 和本地 manifest 至
`data/omnigibson/local-task-instances/heating_food_up/`，之后只加载该 JSON，不再在线采样。
配置文件记录场景、固定随机种子与模型选择，manifest 记录配置和实例的 SHA-256；这些数据
受许可约束且被 Git 忽略。该任务在本服务器上可复现。

## 相关上游脚本

| 上游路径 | 作用 | 当前是否使用 |
| --- | --- | --- |
| `third_party/BEHAVIOR-1K/setup.sh` | 官方 Linux 安装器：创建 Conda 环境、安装 OmniGibson/BDDL、下载数据等 | 本地 `install_behavior.sh` 调用它 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/run_docker.sh` | 官方 Docker 运行入口 | 否；当前使用本机 Anaconda 安装 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/sbatch_example.sh` | 官方 Slurm/容器集群范例 | 否；当前服务器未按该容器方案配置 |
| `third_party/BEHAVIOR-1K/joylo/config_hostmachine.sh` | JoyLo 遥操作的主机配置 | 否；当前未安装 JoyLo |

其余上游 `.sh` 文件服务于 Docker 构建、数据资产流水线、学习任务或内部 Slurm
作业，不是当前 BEHAVIOR/R1 Pro 示例的启动入口。

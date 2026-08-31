# 脚本说明

此目录仅包含本工作区的辅助脚本；没有复制、移动或修改任何上游脚本。官方
BEHAVIOR-1K 源码始终位于 `../third_party/BEHAVIOR-1K/` 子模块。

```text
scripts/
├── env.sh                         # 共用环境变量：数据、Anaconda、源码与 GPU
├── bootstrap_anaconda.sh           # 安装锁定版本的 Anaconda
├── install_behavior.sh             # 调用上游安装器并下载许可数据
├── preflight.sh                    # 只读的服务器与 GPU 检查
├── official_quickstart.sh          # 官方键盘控制示例的包装器
├── r1pro_behavior_demo.sh          # 官方 R1 Pro BEHAVIOR 示例的包装器
├── r1pro_record_demo.sh            # 无桌面录制 R1 Pro 示例为 MP4 的启动器
└── r1pro_task_scene_videos.sh      # 批量录制 BEHAVIOR 任务初始化场景

src/
├── r1pro_record_demo.py            # r1pro_record_demo.sh 调用的本地录像逻辑
└── r1pro_task_scene_record.py      # r1pro_task_scene_videos.sh 调用的录像逻辑
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

## 批量任务场景视频

以下命令生成当前服务器可直接加载的 3 个任务实例的初始化场景视频：MP4 全部保存至
`runs/videos/task_scene/`，同名日志保存至 `runs/logs/task_scene/`：

```bash
./scripts/r1pro_task_scene_videos.sh
```

每段视频依次展示 R1 Pro、主要设施和任务物体区域；没有发送机器人动作，也不表示
机器人完成了任务。Python 实现位于 `src/r1pro_task_scene_record.py`。批处理固定为下列本机
已有的预采样实例，因而不会尝试不稳定的在线物体采样：

| 任务 | 场景 |
| --- | --- |
| `carrying_in_groceries` | `house_double_floor_lower` |
| `thawing_frozen_food` | `house_single_floor` |
| `canning_food` | `house_single_floor` |

其余最初列出的 8 个任务仍有定义文件和基础模型，但当前没有可与已安装版本直接配合的
本地任务实例；本脚本不会把它们伪装成可运行任务。

## 相关上游脚本

| 上游路径 | 作用 | 当前是否使用 |
| --- | --- | --- |
| `third_party/BEHAVIOR-1K/setup.sh` | 官方 Linux 安装器：创建 Conda 环境、安装 OmniGibson/BDDL、下载数据等 | 本地 `install_behavior.sh` 调用它 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/run_docker.sh` | 官方 Docker 运行入口 | 否；当前使用本机 Anaconda 安装 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/sbatch_example.sh` | 官方 Slurm/容器集群范例 | 否；当前服务器未按该容器方案配置 |
| `third_party/BEHAVIOR-1K/joylo/config_hostmachine.sh` | JoyLo 遥操作的主机配置 | 否；当前未安装 JoyLo |

其余上游 `.sh` 文件服务于 Docker 构建、数据资产流水线、学习任务或内部 Slurm
作业，不是当前 BEHAVIOR/R1 Pro 示例的启动入口。

# 脚本说明

此目录仅包含本工作区的辅助脚本；没有复制、移动或修改任何上游脚本。官方
BEHAVIOR-1K 源码始终位于 `../third_party/BEHAVIOR-1K/` 子模块。

```text
scripts/
├── env.sh                         # 共用环境变量：数据、Anaconda、源码与 GPU
├── setup/
│   ├── bootstrap_anaconda.sh       # 安装锁定版本的 Anaconda
│   └── install_behavior.sh         # 调用上游安装器并下载许可数据
├── run/
│   ├── official_quickstart.sh      # 官方键盘控制示例的包装器
│   └── r1pro_behavior_demo.sh      # 官方 R1 Pro BEHAVIOR 示例的包装器
└── tools/
    └── preflight.sh                # 只读的服务器与 GPU 检查
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
| 键盘控制机器人 | `python -m omnigibson.examples.robots.robot_control_example --quickstart` | `./scripts/run/official_quickstart.sh` |
| R1 Pro BEHAVIOR 任务 | `python -m omnigibson.examples.environments.behavior_env_demo` | `./scripts/run/r1pro_behavior_demo.sh` |
| 有限无头验证 | 无；上游示例是交互式的 | 两个包装器均可加 `--smoke` |

包装器不会改动上游源码；它们只负责激活环境、设置本工作区数据路径，并将运行
输出保存到忽略的 `runs/` 目录。

## 相关上游脚本

| 上游路径 | 作用 | 当前是否使用 |
| --- | --- | --- |
| `third_party/BEHAVIOR-1K/setup.sh` | 官方 Linux 安装器：创建 Conda 环境、安装 OmniGibson/BDDL、下载数据等 | 本地 `install_behavior.sh` 调用它 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/run_docker.sh` | 官方 Docker 运行入口 | 否；当前使用本机 Anaconda 安装 |
| `third_party/BEHAVIOR-1K/OmniGibson/docker/sbatch_example.sh` | 官方 Slurm/容器集群范例 | 否；当前服务器未按该容器方案配置 |
| `third_party/BEHAVIOR-1K/joylo/config_hostmachine.sh` | JoyLo 遥操作的主机配置 | 否；当前未安装 JoyLo |

其余上游 `.sh` 文件服务于 Docker 构建、数据资产流水线、学习任务或内部 Slurm
作业，不是当前 BEHAVIOR/R1 Pro 示例的启动入口。

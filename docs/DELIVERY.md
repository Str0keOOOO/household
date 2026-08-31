# 交付记录

## 完成状态

BEHAVIOR-1K 已在这个隔离的工作区中安装并验证。所选源码是特意选择的、与此
Ubuntu 20.04 主机兼容的最新发布版本：BEHAVIOR-1K `v3.7.2`，提交为
`88454bd04f75dc57c00ab1f1a00bcde1ff505950`，已注册为干净的 Git 子模块
`third_party/BEHAVIOR-1K`。未修改该子模块中的任何文件。

本地 `behavior` 环境包含 Python 3.10.21、Isaac Sim 4.5.0.0、
OmniGibson 3.7.2、BDDL 3.7.0 和 PyTorch 2.6.0+cu124。精确解析的版本固定项见
[`versions.lock`](../versions.lock)；完整的机器可读 Conda 快照位于被 Git 忽略的
运行时记录 `records/runtime/environment-20260831T053713Z.md`。

## 已获取资源

| 资源 | 结果 | 工作区位置 |
|---|---|---|
| 上游源码 | 固定的 Git 子模块，`v3.7.2` | `third_party/BEHAVIOR-1K` |
| Miniforge | `26.5.3-0`，已验证 SHA-256 | `.tools/miniforge3` |
| Python / Isaac Sim 环境 | 已成功安装（约 15 GB） | `envs/behavior` |
| BEHAVIOR 机器人资源 | 已安装；包括 R1Pro URDF/模型资源 | `data/omnigibson/omnigibson-robot-assets` |
| BEHAVIOR 资源 | 已成功安装 | `data/omnigibson/behavior-1k-assets` |
| 挑战任务实例 | 已成功安装 | `data/omnigibson/2025-challenge-task-instances` |

已授权数据包、解密密钥、环境、缓存、日志和输出均有意不纳入 Git 管理。测得的
最终工作区用量记录于 [`docs/RESOURCES.md`](RESOURCES.md)。

## 已运行示例

| 示例 | 实际调用 | 结果 | 证据 |
|---|---|---|---|
| 官方快速入门 | `OMNIGIBSON_GPU_ID=1 ./scripts/run_official_quickstart.sh --smoke` | 通过，退出状态为 0。该封装保留了上游的 Fetch/Rs_int 快速入门配置，但由于原始 CLI 为无限键盘遥操作，因此调用其有限的 100 步随机动作测试路径。 | `runs/official-quickstart-smoke-20260831T051152Z.log`；已记录场景导入和正常关闭。 |
| Galaxea R1 Pro 任务 | `OMNIGIBSON_GPU_ID=1 ./scripts/run_r1pro_demo.sh --smoke` | 通过，退出状态为 0。该封装调用上游 `behavior_env_demo` 的有限执行路径，选择缓存的活动，并执行一次 100 步随机动作迭代。 | `runs/r1pro-behavior-smoke-20260831T052546Z.log`；已记录场景导入和正常关闭。 |

R1Pro 运行使用未经修改的上游
`OmniGibson/omnigibson/configs/r1pro_behavior.yaml`，其中机器人为 `R1Pro`，
任务为 `BehaviorTask` / `picking_up_trash`。固定的上游发布版本并未标注单独的
“2026”硬件修订版；本次验证的是其随附的 Galaxea R1 Pro 仿真模型，而非尚未提供的
特定年份厂商模型。

## 已进行的本地改动

- 初始化了此顶层 Git 仓库、本地专用 Git 身份、忽略策略、版本锁定、隔离路径配置、
  安装脚本和运行记录。
- 添加了固定的 `third_party/BEHAVIOR-1K` Git 子模块；没有修补、重新格式化或提交
  第三方源码。
- 添加了分阶段的本地安装器。它会在已授权数据阶段前安装核心软件栈，因此传输失败后
  可以重新运行，而无需重建环境。在此 SOCKS 代理主机上，它仅在 `envs/behavior` 中
  添加 `httpx[socks]`。
- 为两个本地启动脚本添加了 `--smoke` 模式。它们调用上游源码支持的有限 `main()`
  执行路径，并避免修改上游示例。
- 已根据实际安装版本和测试结果更新 README、操作指南、源码/资源记录以及本文档。

## 服务器与运行时观察

- 主机：Ubuntu 20.04.4，内核 5.15.0-70，96 个逻辑 CPU，376 GiB RAM。
- GPU：8 × RTX A6000（每张 49,140 MiB），驱动 535.230.02。测试前 GPU 1 空闲，
  并确认其为活动渲染器和 PhysX GPU。
- 两次运行后，GPU 1 恢复至 15 MiB / 0% 利用率。最终可用 RAM 约为 252 GiB；
  文件系统可用空间约为 959 GiB。
- 首次启动 Isaac 耗时更长，原因是本地 `.omnigibson` 目录中进行了 RTX 着色器/PSO
  缓存编译。启动时还报告了无害的无头 GLFW 警告和其他 GPU 均被占用时的 P2P 探测
  警告；尽管存在这些警告，两个示例都成功完成。不要使用 `CUDA_VISIBLE_DEVICES`
  选择 Isaac/RTX Vulkan 设备；应按 [`OPERATIONS.md`](OPERATIONS.md) 中的说明使用
  `OMNIGIBSON_GPU_ID`。

## 再次运行指南

```bash
cd /data6/xuchenfei/household

# 验证本地前置条件，然后运行有限的、适用于服务器的示例。
./setup.sh preflight
OMNIGIBSON_GPU_ID=1 ./scripts/run_official_quickstart.sh --smoke
OMNIGIBSON_GPU_ID=1 ./scripts/run_r1pro_demo.sh --smoke
```

对于 GUI/远程显示会话，省略 `--smoke` 以调用原始上游交互式入口点。快速入门必须
用 Escape 停止；R1Pro 上游模块会询问是使用缓存对象采样还是在线对象采样。

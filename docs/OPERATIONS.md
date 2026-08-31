# 工作区操作说明

## 为什么选择 v3.7.2

本工作区运行在 Ubuntu 20.04.4 上。上游最新稳定版 BEHAVIOR-1K 为 v3.9.2，
但其当前安装指南要求 Ubuntu 22.04+，且其依赖的 Isaac Sim 5.1 官方仅支持
Ubuntu 22.04/24.04。为保证与本服务器兼容，选择了 BEHAVIOR-1K v3.7.2：它使用
官方支持 Ubuntu 20.04/22.04 的 Isaac Sim 4.5。该版本还包含所需 Galaxea R1 Pro
示例的 `R1Pro` 机器人配置。

这是基于兼容性的选择，而不是分叉：固定版本的子模块内保留未经修改的上游代码。

## 隔离存放位置

辅助脚本会将可重定向的配置和缓存位置指向本仓库。尤其是 Conda 环境与软件包、
Pip/Hugging Face/Torch 缓存、临时文件、OmniGibson 资源和 OmniGibson 应用数据，
都存放在 `/data6/xuchenfei/household` 下。不会修改全局 Git、Conda、Pip、shell、
操作系统或驱动配置。

脚本刻意不重新定义用户主目录。如果某个无法重定向的第三方组件尝试向主目录写入，
请先停止并检查，再继续操作。

## 安装顺序

```bash
cd /data6/xuchenfei/household
./setup.sh preflight
./setup.sh bootstrap
./setup.sh install --accept-licenses
```

最后一条命令执行上游的最小化安装：

```bash
./setup.sh --new-env --omnigibson --bddl --dataset \
  --accept-conda-tos --accept-nvidia-eula --accept-dataset-tos
```

该命令会创建隔离的 `behavior` 环境，并安装 BDDL、OmniGibson、Isaac Sim 4.5
及数据集资源。它有意省略了 `--joylo`、`--eval` 和 `--primitives`，因为所需的
冒烟测试不依赖这些组件。

本地封装脚本会将核心软件栈和受许可数据的下载拆分为独立的上游调用。这样一来，
数据传输失败后可续传，无需重建环境。如果主机提供 SOCKS 代理，脚本会在调用上游
数据下载器前，仅在 `envs/behavior` 内安装必需的 `httpx[socks]` 扩展；不会改动上游
检出内容。

## 许可确认

传入 `--accept-licenses` 即表示确认接受以下全部许可：

1. Conda 服务条款；
2. NVIDIA Isaac Sim 最终用户许可协议（EULA）；以及
3. BEHAVIOR 数据包最终用户许可协议（EULA）。

BEHAVIOR 数据许可将使用限制为非商业学术研究，要求在 OmniGibson 内使用，并禁止
再分发、提取、逆向工程，以及分发其解密密钥。请勿将资源加入 Git 或 Git LFS。

## 示例

```bash
# 用于服务器验证的有限步、无头、非交互式冒烟测试：
./scripts/run_official_quickstart.sh --smoke
./scripts/run_r1pro_demo.sh --smoke

# 原始上游交互式入口（需要 GUI 或远程显示）：
./scripts/run_official_quickstart.sh
./scripts/run_r1pro_demo.sh
```

第一个是上游的键盘遥操作快速入门，需要可用的 GUI 或远程显示。第二个调用上游
`behavior_env_demo`，其配置会在已填充的 BEHAVIOR 任务中实例化一个 R1Pro。两个脚本
默认使用预检选定的 GPU 1；如需覆盖此选择，请显式设置 `OMNIGIBSON_GPU_ID`。

`--smoke` 变体是对上游函数的封装，不是源码补丁。它们会在导入 OmniGibson 前设置
`OMNIGIBSON_HEADLESS=1`，并执行上游有限步数的 `short_exec` 路径。由于原始 CLI 是
无限循环的键盘遥操作，快速入门冒烟测试使用默认的 Fetch/Rs_int 配置，并执行 100 步
随机动作。R1Pro 冒烟测试选择已缓存的 BEHAVIOR 活动并执行一次 100 步迭代，以避开原有
的交互式选择和非确定性的在线对象采样。每次冒烟测试均设置 20 分钟安全超时，并在
`runs/` 下写入带时间戳的日志。

### 多 GPU 服务器说明

在本服务器上，已在 Isaac Sim 日志中验证 `OMNIGIBSON_GPU_ID=1` 同时被用作渲染器和
PhysX 设备。OmniGibson v3.7.2 已禁用多 GPU 模式。不过，Isaac/Omniverse 在进程启动时
仍可能探测每张物理 GPU；当其他用户的 GPU 已满时，可能出现非致命的 P2P
`cudaErrorMemoryAllocation` 消息。请不要在 Isaac Sim 中用 `CUDA_VISIBLE_DEVICES`
替代 `OMNIGIBSON_GPU_ID`：其 Vulkan 渲染器不会通过这种仅限 CUDA 的机制被选择。请让
OmniGibson 变量指向实际空闲的物理 GPU，并在启动前用 `nvidia-smi` 验证。

2026-08-31 的首次冷启动花费了数分钟在 `.omnigibson` 中编译 RTX 着色器/PSO 缓存；
后续启动明显更快。运行中观察到无头 GLFW、OmniHub、DLSS 低分辨率和一些上游弃用警告，
但均未妨碍两个示例完成。

## 后续更新

不要盲目使用 `git submodule update --remote`。请先重新进行兼容性检查、阅读上游发行说明，
再有意更新子模块、运行两个示例，并用已测试的修订版本和结果更新 `versions.lock`、
`docs/RESOURCES.md` 和 `docs/DELIVERY.md`。

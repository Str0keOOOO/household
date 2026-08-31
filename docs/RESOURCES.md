# 已下载和引用的资源

本文档区分可复现的源码与体积较大或受许可证限制的运行时资源。每次操作成功后，
请更新**状态**列。

| 资源 | 版本 / 标识 | 获取方式 | 位置 | Git 状态 | 状态 |
|---|---|---|---|---|---|
| BEHAVIOR-1K 源码 | `v3.7.2`，提交 `88454bd04f75dc57c00ab1f1a00bcde1ff505950` | Git 子模块 | `third_party/BEHAVIOR-1K` | 已跟踪的 Git 链接（gitlink） | 已完成 |
| Miniforge 引导安装 | `26.5.3-0`，SHA-256 `14db468222ad564658656f769506056209b6dc375f5e7dfd31eb5ebbf08fa529` | 固定版本的 GitHub 发布安装程序 + SHA-256 校验 | `.tools/miniforge3`，安装程序位于 `.downloads` | 已忽略的二进制文件 | 已完成 |
| Conda `behavior` 环境 | Python `3.10.21`，Conda `26.5.3` | 上游安装脚本 | `envs/behavior`（约 15 GB） | 已忽略 | 已完成 |
| Isaac Sim | 软件包 `4.5.0.0` | NVIDIA Python 软件包索引，通过上游安装 | 本地 Conda 环境 | 已忽略 / EULA | 已完成 |
| OmniGibson / BDDL | `3.7.2` / `3.7.0` 可编辑安装 | 通过上游安装使用固定子模块 | 本地 Conda 环境 | 已忽略的运行时元数据 | 已完成 |
| CUDA PyTorch | `2.6.0+cu124`（含 torchvision `0.21.0+cu124`） | 通过上游安装使用官方 PyTorch wheel 索引 | 本地 Conda 环境 | 已忽略 | 已完成 |
| HTTPX SOCKS 支持 | `socksio 1.0.0` | PyPI，仅因本主机使用 SOCKS 代理 | 本地 Conda 环境 | 已忽略 | 已完成 |
| BEHAVIOR 机器人资源 | `omnigibson-robot-assets`，包括 `models/r1pro` | Hugging Face，通过上游安装 | `data/omnigibson/omnigibson-robot-assets` | 已忽略 / 受许可证限制 | 已完成 |
| BEHAVIOR 场景和对象资源 | `behavior-1k-assets-3.7.2rc1` | Hugging Face，通过上游安装 | `data/omnigibson/behavior-1k-assets` | 已忽略 / 受许可证限制 | 已完成 |
| 任务实例 | `2025-challenge-task-instances` | Hugging Face，通过上游安装 | `data/omnigibson/2025-challenge-task-instances` | 已忽略 / 受许可证限制 | 已完成 |

上游安装程序可能会解析传递性 Python 依赖，包括固定版本的 VCS 依赖。这些是
隔离环境内的包管理器依赖，而不是由用户维护的源码检出；安装后，
`scripts/capture_versions.sh` 会记录其解析出的版本。

## 已安装占用空间与传输说明

两次冒烟测试完成后测得：`data/` 约为 36 GB，`envs/` 为 15 GB，软件包/缓存
目录约为 2.7 GB，OmniGibson 的运行时缓存约为 8.9 GB。文件系统保留约 959 GB
可用空间。25 GB 的压缩 BEHAVIOR 资源传输使用 Hugging Face Xet，并遇到了可重试的
SOCKS/TLS EOF 消息；本地包装脚本将缺失的 `httpx[socks]` 支持安装到
`envs/behavior`，随后上游下载器成功完成。Git 未跟踪任何数据、密钥、环境或缓存。

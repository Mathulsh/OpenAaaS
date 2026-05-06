<p align="center">
  <img src="./assets/logo.png" width="360" alt="OpenAaaS Logo">
</p>

<p align="center"><strong>OpenAaaS — Open Us to the Agentic World</strong></p>

<p align="center">
  <a href="https://www.open-aaas.com">官网</a> ·
  <a href="./server/README.md">server 文档</a> ·
  <a href="./agent-core/README.md">agent-core 文档</a> ·
  <a href="#使用">使用指南</a> ·
  <a href="./client-extension/README.md">客户端插件</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-1.85%2B-orange?logo=rust" alt="Rust">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-590%2B-brightgreen" alt="Tests">
</p>

---

**OpenAaaS 是连接 AI 智能体与现实科研设施的桥梁。**

AI 的瓶颈不在模型，而在数据与能力的可及性。实验数据锁在电脑和机房、专家模型分散各处、工具链无法互通。

OpenAaaS把这些孤岛连成网络。任何 Agent——无论是 Claude、pi、Kimi 还是自研系统——都可以通过它调用远程的实验仪器、计算集群和专用分析工具。

## 架构

```
客户端 Agent (pi / kimi / 自研 Agent)
    │
    │ HTTP API
    ▼
OpenAaaS Server — 调度中心 (Rust + SQLite)
    │
    │ 短轮询
    ▼
Agent Core — 执行节点 (Docker 容器隔离执行)
```

| 层级 | 组件 | 职责 |
|------|------|------|
| 客户端 Agent | pi mono / Kimi Cli / Codex / Open Code / 自研 Agent | 理解任务、调用远程服务、整合结果 |
| OpenAaaS 网络 | Server — 科研调度中心 (Rust + SQLite) | 任务调度、队列管理、认证授权、文件中转 |
| 远程 Agent | agent-core — 实验室执行节点 + Docker | 向 Server 注册、短轮询获取任务、隔离执行、上报结果 |

## 设计思路

| 原则 | 说明 | 效果 |
|------|------|------|
| Rust + 单二进制 | `cargo build --release` 得到一个可执行文件 | 零依赖部署，复制即用 |
| SQLite 嵌入式 | 数据库随进程启动，无单独服务 | 零运维，单节点足够 |
| Docker 隔离 | 每个任务独立容器，workspace 挂载 | 安全可控，环境可复现 |
| Agent 自管轮询（反向拉取） | Server 只存队列，Agent 自行拉取 | 不需要公网 IP，实验室节点单向出站即可接入 |

## 特性

- **🔧 零配置启动** — `open-aaas-server run` 首次启动自动生成 `config.toml`、SQLite 数据库、密钥。无需手动配置，开箱即用。

- **🐳 每个实验任务独立沙箱，结果可复现** — 每个任务在独立容器中运行，通过 workspace 挂载实现输入输出。环境隔离，结果可追溯、可复现。

- **💾 单二进制零运维** — SQLite 数据库 + 本地文件存储，无需 Redis/MySQL。单节点即可部署，适合实验室边缘节点。

- **🔌 Agent 零学习成本接入，自描述 API 自动暴露服务文档** — 无需认证，返回完整 API 文档和使用说明。Agent 无需插件即可理解并调用全部科研服务。

- **⚖️ 反向连接，不需要公网 IP** — Agent 自行控制并发和任务认领，Server 只做轻量队列管理。实验室节点只需要单向出站即可接入，无需开放端口或 SSH。

- **🧩 Agent 按需获取仪器文档，避免上下文溢出** — 初次查询返回轻量摘要，再按需返回详细用法。类似 SKILL.md 的渐进式披露设计，保护 Agent 的上下文窗口。

## 使用

公共服务器：**<https://api.open-aaas.com>**

我们在公共服务器中提供了三项试用的科研服务：

- IDM-Alpha 科研文献挖掘系统
- 六元高熵合金描述符数据库
- 扶摇多专家研讨系统

可以让 Agent 连接公共服务器使用

### 快速开始

**场景一：使用公共服务器**

无需自建基础设施，直接配置你的 Agent 连接到公共服务器，即可调用社区共享的科研服务。适合个人研究者快速接入。

### 用 pi / kimi 插件

在对话中直接说：

> "帮我设置 OpenAaaS 的服务器地址为 <https://api.open-aaas.com>，然后提交一个数据分析任务"

客户端 Agent 自动完成注册、服务发现、任务提交和结果获取。

### 用通用 Agent 框架

如果你的 Agent 没有 OpenAaaS 插件，让 Agent 直接访问 <https://api.open-aaas.com>

- 无需认证，返回完整 API 文档和使用说明
- Agent 读取后即可自动完成注册、服务发现、任务提交

**场景二：部署在实验室服务器，连接仪器设备**

在机房或实验室的本地服务器上启动 OpenAaaS，将仪器控制脚本、专用分析软件注册为服务。课题组内的任何 Agent——pi、Kimi、Claude 或自研系统——都能通过统一入口查询仪器状态、提交分析任务、获取实验数据。

### 本地部署

**部署 Server（调度中心）**：

```bash
cd server
cargo build --release
./target/release/open-aaas-server run
```

首次启动自动生成 `config.toml`和 SQLite 数据库。

**部署 Agent Core（执行节点）**：

```bash
cd agent-core
cargo build --release
./target/release/agent-core init
./target/release/agent-core register --token <registration_token> --name my-agent
./target/release/agent-core run
```

`registration_token` 需要先在 Server 上创建 Service 获取。Admin 可使用 Server 日志中的 API Key 调用 `POST /api/v1/services/` 创建。

Agent 执行器镜像需要提前构建（在 agent-core 目录下）：

```bash
cd executor-example && docker build -t open-aaas-executor:latest .
```

详见 [agent-core/README.md](./agent-core/README.md)

## 项目结构

```
OpenAaaS/
├── server/           # 调度中心 (Rust) — 任务调度、队列、鉴权、文件中转
├── agent-core/       # 执行节点 (Rust) — 注册、轮询、Docker 隔离执行
├── dash/             # 调试与管理员工具 (Python/Streamlit)
└── client-extension/ # 客户端扩展 — pi 插件、kimi 插件
```

## 环境要求

- **Rust 1.85+** — 编译 server 和 agent-core
- **Docker** — Agent 任务隔离执行
- **Python 3.10+**（可选）— 运行 dash 管理工具

## 科研愿景

OpenAaaS 的愿景是让每个实验室的能力成为可组合的智能体服务。一台电镜、一个模拟脚本、一段实验数据——不再是孤立的工具，而是 Agentic Science 网络中的标准节点。当仪器能力可以被任意 Agent 发现、调用和组合，科研的边界将从单个实验室扩展到全球协作的智能体网络。

## 开源许可

MIT License © IDM Explorer Lab

<img src="./assets/idm-logo.png" width="200" alt="IDM Explorer Lab">

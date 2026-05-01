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
  <img src="https://img.shields.io/badge/tests-passing-brightgreen" alt="Tests">
</p>

---

> **OpenAaaS 将任何 Agent 转化为可通过 HTTP API 远程调用的服务，通过 Docker 容器隔离安全执行。**
>
> AI 的瓶颈不在模型，而在数据与能力的可及性。实验数据锁在机房、专家模型分散各处、工具链无法互通——OpenAaaS 把这些孤岛连成网络。

## 它能做什么

> 🔬 **科研数据调用**
>
> 你的实验数据库和专用分析工具运行在机房服务器上，Agent 在本地写一句"帮我查一下这个样品的 XRD 数据并做物相分析"，任务自动分发到远程节点，数据和结果直接返回。

> 🏢 **企业内部**
>
> 财务团队的 AI 分析工具、HR 的简历筛选 Agent、运维的日志诊断脚本——各自为政。OpenAaaS 让它们成为统一网络中的服务，任何有权限的 Agent 都可以调用。

> 🔧 **能力共享**
>
> 你写了一个代码审查 Agent，部署在服务器上并向 OpenAaaS Server 注册。朋友想借用？把 server 地址告诉他，他用 Claude 或自研 Agent 直接连上就能调用。

## 架构

```
客户端 Agent (pi / kimi / 自研 Agent)
    │
    │ HTTP API
    ▼
OpenAaaS Server (Rust + SQLite)
    │
    │ 短轮询
    ▼
Agent Core (Docker 容器隔离执行)
```

| 层级 | 组件 | 职责 |
|------|------|------|
| 客户端 Agent | pi mono / Kimi Cli / Codex / Open Code / 自研 Agent | 理解任务、调用远程服务、整合结果 |
| OpenAaaS 网络 | Server (Rust + SQLite) | 任务调度、队列管理、认证授权、文件中转 |
| 远程 Agent | agent-core + Docker | 向 Server 注册、短轮询获取任务、隔离执行、上报结果 |

## 设计思路

| 原则 | 说明 | 效果 |
|------|------|------|
| Rust + 单二进制 | `cargo build --release` 得到一个可执行文件 | 零依赖部署，复制即用 |
| SQLite 嵌入式 | 数据库随进程启动，无单独服务 | 零运维，单节点足够 |
| Docker 隔离 | 每个任务独立容器，workspace 挂载 | 安全可控，环境可复现 |
| Agent 自管轮询 | Server 只存队列，Agent 自行拉取 | 极简可靠，无单点瓶颈 |

## 特性

- **🔧 零配置启动** — `open-aaas-server run` 首次启动自动生成 `config.toml`、SQLite 数据库、密钥。无需手动配置，开箱即用。

- **🐳 Docker 安全隔离** — 每个任务在独立容器中运行，通过 workspace 挂载实现输入输出。环境可复现，安全可控。

- **💾 嵌入式优先** — SQLite 数据库 + 本地文件存储，无需 Redis/MySQL。单二进制即可部署，零运维开销。

- **🔌 自描述 API** — 无需认证，返回完整 API 文档和使用说明。Agent 无需插件即可理解并使用全部服务。

- **⚖️ 自管负载** — Agent 自行控制并发和任务认领，Server 只做轻量队列管理。极简可靠，无单点瓶颈。

- **🧩 渐进式披露** — 初次查询返回轻量摘要，再按需返回详细用法。类似SKILL.md的渐进式披露设计。

## 使用

公共服务器：**<https://api.open-aaas.com>**

### 用 pi / kimi 插件

在对话中直接说：

> "帮我设置 OpenAaaS 的服务器地址为 <https://api.open-aaas.com>，然后提交一个数据分析任务"

客户端 Agent 自动完成注册、服务发现、任务提交和结果获取。

### 用通用 Agent 框架

如果你的 Agent 没有 OpenAaaS 插件，直接访问 <https://api.open-aaas.com>

- 无需认证，返回完整 API 文档和使用说明
- Agent 读取后即可自动完成注册、服务发现、任务提交

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

`registration_token` 需要先在 Server 上创建 Service 获取。Admin 可使用 Server 日志中的 API Key 调用 `POST /api/v1/services` 创建。

Agent 执行器镜像需要提前构建（在 agent-core 目录下）：

```bash
cd executor-example && docker build -t open-aaas-executor:latest .
```

详见 [agent-core/README.md](./agent-core/README.md)

## 项目结构

```
OpenAaaS/
├── server/           # HTTP 服务端 (Rust) — 任务调度、队列、鉴权、文件中转
├── agent-core/       # Agent 调度器 (Rust) — 注册、轮询、Docker 隔离执行
├── dash/             # 调试与管理员工具 (Python/Streamlit)
└── client-extension/ # 客户端扩展 — pi 插件、kimi 插件
```

## 环境要求

- **Rust 1.85+** — 编译 server 和 agent-core
- **Docker** — Agent 任务隔离执行
- **Python 3.10+**（可选）— 运行 dash 管理工具

## 开源许可

MIT License © IDM Explorer Lab

<img src="./assets/idm-logo.png" width="200" alt="IDM Explorer Lab">

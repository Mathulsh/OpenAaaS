# OpenAaaS Dashboard

> **⚠️ 定位说明**：这是一个面向开发者和系统管理员的**调试与管理员控制工具**，用于监控和管理 OpenAaaS 的任务与系统状态。**它不是 OpenAaaS 的用户界面 / 主界面（Main UI）**。

A Streamlit-based web UI for debugging, monitoring and administering OpenAaaS tasks.

## Features

- 📊 **任务概览与调试**：以卡片布局查看所有任务，查看任务详情（输入/输出/文件等），支持取消任务
- 🔧 **管理员视图**：查看所有用户任务，按用户筛选任务
- 🔄 **自动刷新**：实时更新，支持可配置刷新间隔
- 🔍 **状态过滤**：按状态筛选任务（All/Pending/Running/Completed/Failed/Cancelled/Cancelling）
- ⚙️ **灵活配置**：支持 CLI 参数、环境变量和配置文件

## Installation

### Using `uv` (recommended)

```bash
uv tool install open-aaas-dashboard
```

### Using `pip`

```bash
pip install open-aaas-dashboard
```

### Development Install

```bash
cd OpenAaaS/dash
pip install -e .
```

## Usage

### Command Line

```bash
# With command line arguments
aaas-dashboard --server-url http://localhost:8080 --api-key ak_xxx

# With environment variables
export OAAS_SERVER_URL=http://localhost:8080
export OAAS_API_KEY=ak_xxx
aaas-dashboard
```

### Configuration Priority

Configuration is loaded in the following priority (highest first):

1. **Command line arguments**: `--server-url`, `--api-key`
2. **Environment variables**: `OAAS_SERVER_URL`, `OAAS_API_KEY`
3. **Config file**: `~/.config/aaas-dashboard/config.toml`

### Config File Format

Create `~/.config/aaas-dashboard/config.toml`:

```toml
server_url = "http://localhost:8080"
api_key = "ak_xxx"
```

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the dashboard
streamlit run src/aaas_dashboard/app.py
```

## License

MIT License

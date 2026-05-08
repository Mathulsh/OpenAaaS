# OpenAaaS MCP Adapter

OpenAaaS 的 MCP（Model Context Protocol）适配器，让任何支持 MCP 的 AI 客户端（Claude Desktop、Cursor、Cline 等）都能连接 OpenAaaS Server。

## 功能特性

- 基于 [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) 构建，Transport 为 `stdio`
- 支持多服务器配置管理
- 14 个核心 Tool，覆盖 OpenAaaS 完整客户端能力
- 文件上传/下载支持，含路径遍历防护与 zip 炸弹防护
- 配置文件原子写入，中文错误提示

## 安装

```bash
# 从源码安装
pip install -e .

# 或直接使用
openaaas-mcp-adapter
```

## 客户端配置

### Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）或对应平台配置：

```json
{
  "mcpServers": {
    "openaaas": {
      "command": "openaaas-mcp-adapter"
    }
  }
}
```

### Cursor

在 Cursor 设置中的 MCP 配置添加：

```json
{
  "mcpServers": {
    "openaaas": {
      "command": "openaaas-mcp-adapter"
    }
  }
}
```

## 标准使用流程

```
1. set_server_url  → 设置服务端地址（默认 http://localhost:8080）
2. register         → 注册获取 api_key（仅需一次）
3. list_services    → 获取轻量服务列表，浏览并筛选候选服务
4. get_service_usage → 对目标服务获取详细 usage（能力范围、调用规范等）
5. submit_task      → 提交任务（可附带文件）
6. get_task         → 查询任务状态和最终结果
7. list_files       → 列出结果文件
8. download_result  → 下载结果文件（zip 自动解压）
```

## Tools 列表

| Tool | 说明 |
|------|------|
| `discover` | 发现服务端 API 信息 |
| `set_server_url` | 设置/更新服务器地址 |
| `register` | 注册客户端，获取 api_key |
| `update_profile` | 修改用户名 |
| `list_services` | 获取可用 Agent 服务列表 |
| `get_service_usage` | 获取指定服务的详细用法 |
| `submit_task` | 提交任务（支持文件上传） |
| `get_task` | 查询任务状态和结果 |
| `cancel_task` | 取消执行中的任务 |
| `list_files` | 列出任务结果文件 |
| `download_result` | 下载结果文件（支持 zip 解压） |
| `list_servers` | 列出已配置服务器 |
| `set_default_server` | 切换默认服务器 |
| `remove_server` | 删除服务器配置 |

## 配置文件

位置：`~/.openaaas-mcp-adapter/config.json`

```json
{
  "servers": {
    "default": {
      "server_url": "https://api.open-aaas.com",
      "api_key": "ak_client_xxx",
      "client_id": "xxx",
      "name": "alice"
    }
  },
  "default_server": "default"
}
```

## 安全特性

- **路径遍历防护**：文件上传仅限当前工作目录下；zip 解压逐文件验证路径
- **zip 炸弹防护**：最大压缩比 500、解压后总大小 100MB、最大文件数 1000、单文件最大 50MB
- **配置文件原子写入**：使用临时文件 + replace 保证配置不损坏
- **符号链接拒绝**：zip 中的符号链接被直接拒绝解压

## 开发

```bash
# 安装依赖
uv add "mcp>=1.0.0" "httpx>=0.27.0"

# 运行
uv run python -m openaaas_mcp_adapter
```

## 许可证

MIT

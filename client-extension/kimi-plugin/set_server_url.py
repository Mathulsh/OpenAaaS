#!/usr/bin/env python3
"""
OpenAaaS 插件 - 设置/添加服务器配置
管理多服务器配置，支持添加新服务器或更新现有服务器
"""

import json
import sys
import os

from utils import load_config, save_config


def set_server(server_name, server_url, api_key="", client_id="", set_as_default=False):
    """
    设置/更新服务器配置

    Args:
        server_name: 服务器别名
        server_url: 服务端地址
        api_key: API 密钥（可选）
        client_id: 客户端 ID（可选）
        set_as_default: 是否设为默认服务器
    """
    config = load_config()
    servers = config.setdefault("servers", {})

    # 检查是否有其他别名已注册到同一服务器地址
    target_url = server_url.rstrip("/")
    for alias, srv in servers.items():
        if alias == server_name:
            continue
        other_url = srv.get("server_url", "").rstrip("/")
        if other_url == target_url and srv.get("api_key"):
            return {
                "error": (
                    f"该服务器地址已被其他别名注册过。\n"
                    f"服务器别名: {alias}\n"
                    f"服务器地址: {srv.get('server_url', '')}\n\n"
                    f"如需使用此别名，请先使用 remove_server 工具删除已有配置。"
                )
            }

    if server_name not in servers:
        servers[server_name] = {}

    servers[server_name]["server_url"] = target_url
    if api_key:
        servers[server_name]["api_key"] = api_key
    if client_id:
        servers[server_name]["client_id"] = client_id

    if set_as_default:
        config["default_server"] = server_name

    if "default_server" not in config or not config["default_server"]:
        config["default_server"] = server_name

    if not save_config(config):
        return {"error": "保存配置失败，请检查磁盘空间或文件权限"}

    return {
        "content": f"服务器 '{server_name}' 配置已保存: {server_url}",
        "data": {
            "server_name": server_name,
            "server_url": server_url,
            "is_default": config["default_server"] == server_name
        }
    }


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}

        server_name = params.get("server_name", "default").strip()
        server_url = params.get("server_url", "").strip()

        if not server_url:
            print(json.dumps({"error": "缺少必填参数: server_url"}, ensure_ascii=False))
            sys.exit(1)

        if not server_name:
            print(json.dumps({"error": "server_name 不能为空"}, ensure_ascii=False))
            sys.exit(1)

        api_key = params.get("api_key", "")
        client_id = params.get("client_id", "")
        set_as_default = params.get("set_as_default", False)

        result = set_server(server_name, server_url, api_key, client_id, set_as_default)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"参数 JSON 解析错误: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"执行错误: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()

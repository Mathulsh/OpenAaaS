#!/usr/bin/env python3
"""
OpenAaaS 插件 - 列出所有服务器配置
查看当前配置的多服务器列表及默认服务器
"""

import json
import sys
import os

from utils import load_config


def list_servers():
    """列出所有已配置的服务器"""
    config = load_config()
    servers = config.get("servers", {})
    default_name = config.get("default_server", "default")

    server_list = []
    for name, conf in servers.items():
        server_list.append({
            "name": name,
            "server_url": conf.get("server_url", ""),
            "has_api_key": bool(conf.get("api_key", "")),
            "client_id": conf.get("client_id", ""),
            "is_default": name == default_name
        })

    return {
        "content": f"共 {len(server_list)} 个服务器配置，当前默认: {default_name}",
        "data": {
            "total": len(server_list),
            "default_server": default_name,
            "servers": server_list
        }
    }


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        result = list_servers()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"执行错误: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()

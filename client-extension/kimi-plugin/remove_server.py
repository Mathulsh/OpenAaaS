#!/usr/bin/env python3
"""
OpenAaaS 插件 - 移除服务器配置
删除指定服务器的配置信息
"""

import json
import sys
import os

from utils import load_config, save_config


def remove_server(server_name):
    """
    移除指定服务器配置

    Args:
        server_name: 要移除的服务器别名
    """
    config = load_config()
    servers = config.get("servers", {})

    if server_name not in servers:
        return {"error": f"服务器 '{server_name}' 不存在"}

    del servers[server_name]

    # 如果删除的是默认服务器，重置默认
    if config.get("default_server") == server_name:
        if servers:
            config["default_server"] = list(servers.keys())[0]
        else:
            # 删除最后一个服务器后，清理相关字段
            if "default_server" in config:
                del config["default_server"]
            if "server_url" in config:
                del config["server_url"]
            if "api_key" in config:
                del config["api_key"]
            if "client_id" in config:
                del config["client_id"]

    if not save_config(config):
        return {"error": "保存配置失败，请检查磁盘空间或文件权限"}
    return {
        "content": f"服务器 '{server_name}' 已移除",
        "data": {
            "removed": server_name,
            "new_default": config.get("default_server", None)
        }
    }


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}

        server_name = params.get("server_name", "").strip()
        if not server_name:
            print(json.dumps({"error": "缺少必填参数: server_name"}, ensure_ascii=False))
            sys.exit(1)

        result = remove_server(server_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if "error" in result:
            sys.exit(1)

    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"参数 JSON 解析错误: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"执行错误: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()

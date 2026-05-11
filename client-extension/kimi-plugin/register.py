#!/usr/bin/env python3
"""
OpenAaaS 插件 - 注册客户端
调用 POST /client/auth/register 注册并获取 api_key
"""

import json
import sys
import os

from utils import load_config, save_config, safe_request


def register(server_url, name):
    """
    调用注册接口获取 api_key
    
    Args:
        server_url: 服务端基础地址
        name: 客户端名称
    """
    if not server_url:
        return {"error": "缺少服务端地址，请先使用 set_server_url 设置服务器地址"}

    if not name or not name.strip():
        return {"error": "缺少必填参数: name 或 name 不能为空"}

    config = load_config()
    active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
    if active_conf.get("api_key"):
        return {
            "error": "当前默认服务器已注册（存在 API Key），请勿重复注册。如需重新注册，请先使用 remove_server 工具移除当前配置，或切换到其他服务器后再注册。如需向其他服务器注册，请先使用 set_server_url 添加服务器。"
        }

    server_url = server_url.strip().rstrip("/")

    # 检查其他 alias 是否已用相同 URL 注册过
    default_alias = config.get("default_server", "default")
    for alias, conf in config.get("servers", {}).items():
        if alias == default_alias:
            continue
        if not isinstance(conf, dict):
            continue
        if (conf.get("server_url") or "").rstrip("/") == server_url and conf.get("api_key"):
            return {
                "error": (
                    f"该服务器地址已被其他别名注册过。\n"
                    f"服务器别名: {alias}\n"
                    f"服务器地址: {conf.get('server_url') or server_url}\n"
                    f"客户端 ID: {conf.get('client_id', 'unknown')}\n"
                    f"用户名: {conf.get('name', 'unknown')}\n\n"
                    f"如需使用其他别名，请先使用 remove_server 工具删除已有配置。"
                )
            }

    url = f"{server_url}/api/v1/client/auth/register"
    
    payload = {
        "name": name
    }
    
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json"
    }

    success, result, status = safe_request(
        url,
        headers=headers,
        data=data,
        method="POST",
        timeout=30,
    )

    if not success:
        if status == 401:
            return {"error": f"认证失败 (401): {result}"}
        elif status == 403:
            return {"error": f"权限不足 (403): 无权注册"}
        elif status is not None:
            return {"error": f"注册失败 (HTTP {status}): {result}"}
        else:
            return {"error": result}

    # 提取 api_key 并保存到配置文件
    api_key = result.get("api_key") or result.get("token")
    client_id = result.get("client_id") or result.get("id")

    if api_key:
        config = load_config()
        default_name = config.get("default_server", "default")
        servers = config.setdefault("servers", {})
        if default_name not in servers:
            servers[default_name] = {}
        servers[default_name]["api_key"] = api_key
        servers[default_name]["client_id"] = client_id
        if name:
            servers[default_name]["name"] = name
        servers[default_name]["server_url"] = server_url
        if not save_config(config):
            return {"error": "注册成功但保存配置失败，请检查磁盘空间或文件权限"}
        saved = True
    else:
        saved = False

    return {
        "content": f"注册成功！客户端 ID: {client_id}。API Key 已{'自动保存' if saved else '返回，请手动保存'}到 config.json",
        "data": {
            "client_id": client_id,
            "api_key": api_key,
            "saved_to_config": saved
        }
    }


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        # 从 stdin 读取 JSON 参数
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}
        
        # 获取参数
        config = load_config()
        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url") or config.get("server_url") or "https://api.open-aaas.com"
        if not server_url:
            print(json.dumps({"error": "缺少服务端地址，请先使用 set_server_url 设置服务器地址"}, ensure_ascii=False))
            sys.exit(1)
        name = params.get("name", "")
        if not name or not name.strip():
            print(json.dumps({"error": "缺少必填参数: name 或 name 不能为空"}, ensure_ascii=False))
            sys.exit(1)
        
        # 执行注册
        result = register(server_url, name)
        
        # 输出 JSON 结果
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

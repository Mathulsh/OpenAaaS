#!/usr/bin/env python3
"""
OpenAaaS 插件 - 修改客户端用户名
调用 PUT /client/profile 更新已注册客户端的名称
"""

import json
import sys
import os
import urllib.request
import urllib.error
import re
import unicodedata

from utils import load_config, save_config


def update_profile(server_url, api_key, name):
    """
    调用更新用户名接口
    
    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        name: 新用户名
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}
    
    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/profile"
    
    payload = {
        "name": name
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            # 提取更新后的用户信息
            client_id = result.get("client_id") or result.get("id")
            updated_name = result.get("name") or name
            
            # 更新配置文件中的用户名
            config = load_config()
            if "error" not in config:
                default_name = config.get("default_server", "default")
                servers = config.setdefault("servers", {})
                if default_name not in servers:
                    servers[default_name] = {}
                servers[default_name]["name"] = updated_name
                if not save_config(config):
                    return {"error": "更新成功但保存配置失败，请检查磁盘空间或文件权限"}
                saved = True
            else:
                saved = False
            
            return {
                "content": f"用户名更新成功！新用户名: {updated_name}",
                "data": {
                    "client_id": client_id,
                    "name": updated_name,
                    "saved_to_config": saved
                }
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get("error") or error_data.get("message") or error_body
        except:
            error_msg = error_body or e.reason
        
        if e.code == 401:
            return {"error": f"认证失败 (401): API Key 无效，请检查 config.json 中的 api_key 是否正确"}
        elif e.code == 403:
            return {"error": f"权限不足 (403): 无权更新用户名"}
        elif e.code == 409:
            return {"error": f"用户名已存在 (409): 该用户名已被其他用户使用，请选择其他名称"}
        return {"error": f"更新失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}，请检查服务端地址是否正确"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析错误: {str(e)}"}
    except Exception as e:
        return {"error": f"更新失败: {str(e)}"}


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        # 从 stdin 读取 JSON 参数
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}
        
        # 获取参数
        name = params.get("name", "").strip()
        
        if not name:
            print(json.dumps({"error": "参数错误: name 不能为空"}, ensure_ascii=False))
            sys.exit(1)
        
        if len(name) > 64:
            print(json.dumps({"error": "参数错误: name 长度不能超过64字符"}, ensure_ascii=False))
            sys.exit(1)
        
        # 校验特殊字符
        if re.search(r'[\x00-\x1f\x7f\x80-\x9f/\\<>|&;$]', name):
            print(json.dumps({"error": "参数错误: name 包含非法特殊字符"}, ensure_ascii=False))
            sys.exit(1)
        
        for c in name:
            if unicodedata.category(c).startswith('C'):
                print(json.dumps({"error": "参数错误: name 包含非法 Unicode 控制字符"}, ensure_ascii=False))
                sys.exit(1)
        
        # 加载配置
        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)
        
        # 检查 servers 是否为空或默认服务器是否有效
        servers = config.get("servers", {})
        default_server = config.get("default_server", "default")
        if not servers or default_server not in servers:
            print(json.dumps({"error": "未配置有效服务器，请先使用 set_server_url 添加服务器"}, ensure_ascii=False))
            sys.exit(1)
        
        active_conf = config.get("servers", {}).get(default_server, {})
        server_url = active_conf.get("server_url") or config.get("server_url") or "https://api.open-aaas.com"
        api_key = active_conf.get("api_key", config.get("api_key", ""))
        
        # 执行更新
        result = update_profile(server_url, api_key, name)
        
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

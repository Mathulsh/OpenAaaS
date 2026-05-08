#!/usr/bin/env python3
"""
OpenAaaS 插件 - 列出可用服务
调用 GET /client/services 获取服务列表
"""

import json
import sys
import os
import urllib.request
import urllib.error

from utils import load_config


def list_services(server_url, api_key):
    """
    调用服务列表接口
    
    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}
    
    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/services"
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            # 处理返回结果（可能是列表或对象）
            services = result if isinstance(result, list) else result.get("services", [])
            
            # 格式化服务列表
            formatted_services = []
            for svc in services:
                formatted_services.append({
                    "id": svc.get("id"),
                    "name": svc.get("name"),
                    "description": svc.get("description"),
                    "usage": svc.get("usage", ""),
                    "agent_status": svc.get("agent_status", "unknown"),
                    "access_type": svc.get("access_type", "unknown"),
                    "has_permission": svc.get("has_permission", False),
                    "registration_status": svc.get("registration_status", "unknown")
                })
            
            return {
                "content": f"找到 {len(formatted_services)} 个可用服务",
                "data": {
                    "total": len(formatted_services),
                    "services": formatted_services
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
            return {"error": f"权限不足 (403): 无权访问服务列表"}
        return {"error": f"请求失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}，请检查服务端地址是否正确"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析错误: {str(e)}"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        # 从 stdin 读取 JSON 参数（本工具不需要参数）
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}
        
        # 加载配置
        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)
        
        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url", config.get("server_url", "https://api.open-aaas.com"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))
        
        # 执行查询
        result = list_services(server_url, api_key)
        
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

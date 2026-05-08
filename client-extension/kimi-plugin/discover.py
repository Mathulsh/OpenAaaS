#!/usr/bin/env python3
"""
OpenAaaS 插件 - 发现服务端 API 信息
调用 GET /api/v1/discovery 获取服务端支持的 API 信息
"""

import json
import sys
import os

from utils import load_config, safe_request


def discover(server_url):
    """
    调用服务端 discovery 接口获取 API 信息
    
    Args:
        server_url: 服务端基础地址
    """
    # 确保 URL 格式正确
    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/discovery"
    
    success, result, status_code = safe_request(url, method="GET")
    
    if not success:
        if status_code == 403:
            return {"error": "权限不足 (403): 无权访问该服务端"}
        if status_code:
            return {"error": f"HTTP 错误 {status_code}: {result}"}
        return {"error": result}
    
    version = result.get("version", "unknown") if isinstance(result, dict) else "unknown"
    endpoints = result.get("endpoints", []) if isinstance(result, dict) else []
    services = result.get("services", []) if isinstance(result, dict) else []
    
    content = f"成功获取服务端 API 信息，服务端版本: {version}"
    if endpoints:
        content += f"\n\n支持的端点 ({len(endpoints)} 个):"
        for ep in endpoints:
            content += f"\n  - {ep}"
    if services:
        content += f"\n\n可用服务 ({len(services)} 个):"
        for svc in services:
            content += f"\n  - {svc.get('name', 'unknown')} ({svc.get('id', 'unknown')})"
    
    return {
        "content": content,
        "data": result
    }


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        # 从 stdin 读取 JSON 参数
        input_data = sys.stdin.read()
        params = json.loads(input_data) if input_data else {}
        
        # 获取参数（使用 .get() 提供默认值）
        config = load_config()
        server_name = params.get("server_name", "")
        active_conf = config.get("servers", {}).get(server_name or config.get("default_server", "default"), {})
        server_url = params.get("server_url", active_conf.get("server_url", config.get("server_url", "https://api.open-aaas.com")))
        
        # 执行发现
        result = discover(server_url)
        
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

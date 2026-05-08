#!/usr/bin/env python3
"""
OpenAaaS 插件 - 取消任务
调用 POST /client/tasks/{id}/cancel 取消指定任务
"""

import json
import sys
import os
import urllib.request
import urllib.error

from utils import load_config


def cancel_task(server_url, api_key, task_id):
    """
    取消任务
    
    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        task_id: 任务 ID
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}
    
    if not task_id:
        return {"error": "缺少任务 ID"}
    
    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/tasks/{task_id}/cancel"
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            status = result.get("status", "unknown")
            
            # 根据状态构造提示
            if status == "cancelled":
                content = f"✅ 任务已取消\n任务 ID: {task_id}\n状态: 已取消"
            elif status == "cancelling":
                content = f"⏳ 任务正在取消中\n任务 ID: {task_id}\n状态: 取消中（Agent 将收到取消信号）"
            else:
                content = f"任务状态: {status}\n任务 ID: {task_id}"
            
            return {
                "content": content,
                "data": {
                    "task_id": task_id,
                    "status": status,
                    "full_response": result
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
            return {"error": f"认证失败 (401): API Key 无效"}
        elif e.code == 403:
            return {"error": f"权限不足 (403): 只能取消自己创建的任务"}
        elif e.code == 404:
            return {"error": f"任务不存在 (404): 请检查 task_id 是否正确"}
        elif e.code == 400:
            return {"error": f"无法取消 (400): {error_msg}"}
        return {"error": f"取消失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}，请检查服务端地址是否正确"}
    except Exception as e:
        return {"error": f"取消失败: {str(e)}"}


def main():
    """主函数：从 stdin 读取参数并执行"""
    try:
        # 从 stdin 读取 JSON 参数
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"error": "缺少参数"}, ensure_ascii=False))
            sys.exit(1)
        
        params = json.loads(input_data)
        
        # 验证必填参数
        task_id = params.get("task_id")
        if not task_id:
            print(json.dumps({"error": "缺少必填参数: task_id"}, ensure_ascii=False))
            sys.exit(1)
        
        # 加载配置
        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)
        
        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url", config.get("server_url", "https://api.open-aaas.com"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))
        
        # 执行取消
        result = cancel_task(server_url, api_key, task_id)
        
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

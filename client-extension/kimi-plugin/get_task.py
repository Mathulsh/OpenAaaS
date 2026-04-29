#!/usr/bin/env python3
"""
OpenAaaS 插件 - 查询任务状态
调用 GET /client/tasks/{id} 获取任务详情
"""

import json
import sys
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

from utils import load_config


def get_task(server_url, api_key, task_id):
    """
    查询任务状态
    
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
    url = f"{server_url}/api/v1/client/tasks/{task_id}"
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            task_id = result.get("id") or result.get("task_id")
            status = result.get("status", "unknown")
            service_id = result.get("service_id", "")
            task_prompt = result.get("task_prompt", "")
            output_prompt = result.get("output_prompt", "")
            result_data = result.get("result", {})
            created_at = result.get("created_at", "")
            updated_at = result.get("updated_at", "")
            completed_at = result.get("completed_at", "")
            started_at = result.get("started_at", "")
            
            # 构建状态说明
            status_desc = {
                "pending": "等待中",
                "accepted": "已接受",
                "running": "执行中",
                "completed": "已完成",
                "failed": "失败",
                "cancelled": "已取消"
            }.get(status, status)
            
            # 计算运行时长
            duration_str = ""
            start_time = started_at or created_at  # 用 started_at 优先，否则用 created_at
            
            if start_time:
                # 解析时间（处理带 Z 和带 +00:00 的格式）
                start_time = start_time.replace("Z", "+00:00")
                started = datetime.fromisoformat(start_time)
                
                # 确保时间是带时区的
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                
                if status == "running":
                    # 获取当前 UTC 时间
                    now = datetime.now(timezone.utc)
                    duration = now - started
                elif completed_at:
                    # 解析完成时间
                    completed_str = completed_at.replace("Z", "+00:00")
                    completed = datetime.fromisoformat(completed_str)
                    if completed.tzinfo is None:
                        completed = completed.replace(tzinfo=timezone.utc)
                    duration = completed - started
                else:
                    duration = None
                
                if duration:
                    total_seconds = int(duration.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    
                    if hours > 0:
                        duration_str = f"{hours}小时{minutes}分钟{seconds}秒"
                    elif minutes > 0:
                        duration_str = f"{minutes}分钟{seconds}秒"
                    else:
                        duration_str = f"{seconds}秒"
            
            content = f"任务状态: {status_desc}\n任务 ID: {task_id}"
            
            if status == "completed":
                content += "\n\n✅ 任务已完成！可以使用 download_result 工具下载结果文件。"
                if result_data:
                    content += f"\n\n执行结果摘要:"
                    if isinstance(result_data, dict):
                        if "summary" in result_data:
                            content += f"\n{result_data['summary']}"
                        elif "output" in result_data:
                            content += f"\n{result_data['output'][:500]}..."
            elif status == "failed":
                content += "\n\n❌ 任务执行失败"
                if result_data and isinstance(result_data, dict):
                    error_msg = result_data.get("error") or result_data.get("message")
                    if error_msg:
                        content += f"\n错误信息: {error_msg}"
            elif status in ["pending", "accepted", "running"]:
                content += f"\n\n⏳ 任务正在执行中，请稍后再次查询..."
            
            if duration_str:
                content += f"\n⏱️ 运行时长: {duration_str}"
            
            return {
                "content": content,
                "data": {
                    "task_id": task_id,
                    "status": status,
                    "service_id": service_id,
                    "task_prompt": task_prompt,
                    "output_prompt": output_prompt,
                    "result": result_data,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "completed_at": completed_at,
                    "started_at": started_at,
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
            return {"error": f"认证失败 (401): API Key 无效，请检查 config.json 中的 api_key 是否正确"}
        elif e.code == 403:
            return {"error": f"权限不足 (403): 无权访问该任务"}
        elif e.code == 404:
            return {"error": f"任务不存在 (404): 请检查 task_id 是否正确"}
        return {"error": f"查询失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}，请检查服务端地址是否正确"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析错误: {str(e)}"}
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}


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
        server_url = active_conf.get("server_url", config.get("server_url", "http://localhost:8080"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))
        
        # 执行查询
        result = get_task(server_url, api_key, task_id)
        
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

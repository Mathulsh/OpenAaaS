#!/usr/bin/env python3
"""
OpenAaaS 插件 - 列出任务文件
调用 GET /api/v1/client/files/list/{task_id} 获取文件列表
"""

import json
import sys
import os
import urllib.request
import urllib.error

from utils import load_config


def list_files(server_url, api_key, task_id):
    """
    获取任务文件列表

    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        task_id: 任务 ID
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}

    if not task_id:
        return {"error": "缺少 task_id"}

    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/files/list/{task_id}"

    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            files = result if isinstance(result, list) else result.get("files", [])

            formatted = []
            for f in files:
                formatted.append({
                    "file_id": f.get("id") or f.get("file_id"),
                    "filename": f.get("filename", ""),
                    "size": f.get("size", 0),
                    "created_at": f.get("created_at", "")
                })

            return {
                "content": f"任务 {task_id} 共有 {len(formatted)} 个文件",
                "data": {
                    "task_id": task_id,
                    "files": formatted
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
            return {"error": f"权限不足 (403): 无权查看该任务文件"}
        elif e.code == 404:
            return {"error": f"任务不存在 (404): 请检查 task_id 是否正确"}
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
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"error": "缺少参数"}, ensure_ascii=False))
            sys.exit(1)

        params = json.loads(input_data)
        task_id = params.get("task_id", "").strip()
        if not task_id:
            print(json.dumps({"error": "缺少必填参数: task_id"}, ensure_ascii=False))
            sys.exit(1)

        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)

        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url", config.get("server_url", "http://localhost:8080"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))

        result = list_files(server_url, api_key, task_id)
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

#!/usr/bin/env python3
"""
OpenAaaS 插件 - 提交任务
调用 POST /client/tasks 提交任务，支持文件上传
"""

import json
import sys
import os
import urllib.request
import urllib.error
import mimetypes
import uuid

from utils import load_config


def build_multipart_request(url, fields, files, headers):
    """
    构建 multipart/form-data 请求
    
    Args:
        url: 请求地址
        fields: 表单字段字典
        files: 文件列表 [(field_name, file_path), ...]
        headers: 请求头字典
    """
    boundary = uuid.uuid4().hex
    
    # 构建请求体
    body_parts = []
    
    # 添加表单字段
    for field_name, field_value in fields.items():
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode())
        body_parts.append(f"{field_value}\r\n".encode())
    
    # 添加文件
    for field_name, file_path in files:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        
        body_parts.append(f"--{boundary}\r\n".encode())
        safe_filename = filename.replace('"', '\\"')
        body_parts.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{safe_filename}"\r\n'.encode())
        body_parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
        
        with open(file_path, "rb") as f:
            body_parts.append(f.read())
        body_parts.append(b"\r\n")
    
    # 结束边界
    body_parts.append(f"--{boundary}--\r\n".encode())
    
    # 合并请求体
    body = b"".join(body_parts)
    
    # 设置请求头
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    headers["Content-Length"] = str(len(body))
    
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return req


def submit_task(server_url, api_key, service_id, task_prompt, output_prompt, input_files):
    """
    提交任务
    
    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        service_id: 目标服务 ID
        task_prompt: 任务描述
        output_prompt: 输出格式要求
        input_files: 输入文件路径列表（可选）
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}
    
    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/tasks"
    
    # 准备表单字段
    fields = {
        "service_id": service_id,
        "task_prompt": task_prompt
    }
    if output_prompt:
        fields["output_prompt"] = output_prompt
    
    # 准备文件列表
    files = []
    if input_files and isinstance(input_files, list):
        for file_path in input_files:
            files.append(("files", file_path))
    
    # 准备请求头
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # 构建 multipart 请求
        req = build_multipart_request(url, fields, files, headers)
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            task_id = result.get("id") or result.get("task_id")
            status = result.get("status", "unknown")
            
            return {
                "content": f"任务提交成功！任务 ID: {task_id}，状态: {status}\n\n⚠️ 重要提示：任务执行可能需要数分钟到数小时不等，请勿轮询查询。请等待一段时间后使用 get_task 工具查询结果。",
                "data": {
                    "task_id": task_id,
                    "status": status,
                    "service_id": service_id,
                    "created_at": result.get("created_at")
                }
            }
            
    except FileNotFoundError as e:
        return {"error": f"文件上传失败: {str(e)}"}
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
            return {"error": f"权限不足 (403): 无权提交该服务的任务"}
        elif e.code == 404:
            return {"error": f"服务不存在 (404): 请检查 service_id 是否正确，可通过 list_services 获取可用服务列表"}
        return {"error": f"提交失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}，请检查服务端地址是否正确"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析错误: {str(e)}"}
    except Exception as e:
        return {"error": f"提交失败: {str(e)}"}


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
        service_id = params.get("service_id")
        task_prompt = params.get("task_prompt")
        output_prompt = params.get("output_prompt", "")
        
        if not service_id:
            print(json.dumps({"error": "缺少必填参数: service_id"}, ensure_ascii=False))
            sys.exit(1)
        if not task_prompt:
            print(json.dumps({"error": "缺少必填参数: task_prompt"}, ensure_ascii=False))
            sys.exit(1)
        
        # 加载配置
        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)
        
        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url", config.get("server_url", "http://localhost:8080"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))
        
        # 获取可选参数
        input_files = params.get("input_files", [])
        
        # 执行任务提交
        result = submit_task(server_url, api_key, service_id, task_prompt, 
                           output_prompt, input_files)
        
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

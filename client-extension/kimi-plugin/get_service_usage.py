#!/usr/bin/env python3
"""
OpenAaaS 插件 - 获取服务用法说明
调用 GET /api/v1/client/services/{service_id}/usage
"""

import json
import sys
import os
import urllib.request
import urllib.error

from utils import load_config


def get_service_usage(server_url, api_key, service_id):
    """
    获取服务用法说明

    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        service_id: 服务 ID
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}

    if not service_id:
        return {"error": "缺少 service_id"}

    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/services/{service_id}/usage"

    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return {
                "content": f"成功获取服务 {service_id} 的用法说明",
                "data": result
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
            return {"error": f"权限不足 (403): 无权查看该服务用法"}
        elif e.code == 404:
            return {"error": f"服务不存在 (404): 请检查 service_id 是否正确"}
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
        service_id = params.get("service_id", "").strip()
        if not service_id:
            print(json.dumps({"error": "缺少必填参数: service_id"}, ensure_ascii=False))
            sys.exit(1)

        config = load_config()
        if "error" in config:
            print(json.dumps(config, ensure_ascii=False))
            sys.exit(1)

        active_conf = config.get("servers", {}).get(config.get("default_server", "default"), {})
        server_url = active_conf.get("server_url", config.get("server_url", "http://localhost:8080"))
        api_key = active_conf.get("api_key", config.get("api_key", ""))

        result = get_service_usage(server_url, api_key, service_id)
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

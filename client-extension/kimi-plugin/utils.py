#!/usr/bin/env python3
"""
OpenAaaS 插件 - 公共工具模块
提供配置管理、HTTP 请求等通用功能
"""

import json
import os
import sys
import urllib.request
import urllib.error


def load_config():
    """加载配置文件（支持多服务器格式并兼容旧格式，迁移自动持久化）"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    migrated = False
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                return {
                    "error": f"config.json 格式错误: 期望 JSON 对象，实际为 {type(config).__name__}",
                    "server_url": "http://localhost:8080",
                    "api_key": "",
                    "client_id": "",
                    "servers": {
                        "default": {
                            "server_url": "http://localhost:8080",
                            "api_key": "",
                            "client_id": ""
                        }
                    },
                    "default_server": "default"
                }
    except Exception as e:
        return {
            "error": f"无法读取 config.json: {str(e)}",
            "server_url": "http://localhost:8080",
            "api_key": "",
            "client_id": "",
            "servers": {
                "default": {
                    "server_url": "http://localhost:8080",
                    "api_key": "",
                    "client_id": ""
                }
            },
            "default_server": "default"
        }

    # 兼容旧格式：单服务器配置
    if "servers" not in config and "server_url" in config:
        config = {
            "server_url": config.get("server_url", "http://localhost:8080"),
            "api_key": config.get("api_key", ""),
            "client_id": config.get("client_id", ""),
            "servers": {
                "default": {
                    "server_url": config.get("server_url", "http://localhost:8080"),
                    "api_key": config.get("api_key", ""),
                    "client_id": config.get("client_id", "")
                }
            },
            "default_server": config.get("default_server", "default")
        }
        migrated = True

    # 持久化迁移后的配置
    if migrated:
        if not save_config(config):
            print("警告: 配置迁移后保存失败，请检查磁盘空间或文件权限", file=sys.stderr)

    return config


def save_config(config):
    """保存配置到文件，失败时返回 False"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def safe_request(url, headers=None, data=None, method="GET", timeout=30):
    """
    发送 HTTP 请求并安全处理响应

    Args:
        url: 请求 URL
        headers: 请求头字典
        data: 请求体字节数据
        method: HTTP 方法
        timeout: 超时时间

    Returns:
        (success, result_or_error, status_code)
        - success: bool
        - result_or_error: 解析后的 JSON/dict 或错误信息字符串
        - status_code: HTTP 状态码或 None
    """
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            result = json.loads(body)
            return True, result, response.getcode()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get("error") or error_data.get("message") or error_body
        except Exception:
            error_msg = error_body or e.reason
        return False, error_msg, e.code
    except urllib.error.URLError as e:
        return False, f"连接失败: {e.reason}，请检查服务端地址是否正确", None
    except json.JSONDecodeError as e:
        return False, f"JSON 解析错误: {str(e)}", None
    except Exception as e:
        return False, f"请求失败: {str(e)}", None

#!/usr/bin/env python3
"""
测试辅助函数模块
提供统一的 mock 创建工具函数
"""

import json
from io import BytesIO
from unittest.mock import MagicMock


def create_mock_response(status_code=200, json_data=None, text_data=None):
    """
    创建统一的 mock HTTP 响应
    
    Args:
        status_code: HTTP 状态码，默认 200
        json_data: 要作为 JSON 返回的数据，与 text_data 互斥
        text_data: 要作为纯文本返回的数据，与 json_data 互斥
    
    Returns:
        MagicMock: 配置好的 mock 响应对象
    """
    mock_response = MagicMock()
    mock_response.getcode.return_value = status_code
    if json_data is not None:
        mock_response.read.return_value = json.dumps(json_data).encode("utf-8")
    elif text_data is not None:
        mock_response.read.return_value = text_data.encode("utf-8")
    return mock_response


def create_mock_http_error(status_code, error_body):
    """
    创建 mock HTTP 错误
    
    Args:
        status_code: HTTP 错误状态码
        error_body: 错误响应体（字符串）
    
    Returns:
        urllib.error.HTTPError: 配置好的 HTTP 错误对象
    """
    import urllib.error
    return urllib.error.HTTPError(
        url="http://localhost:8080/api/v1/test",
        code=status_code,
        msg="Error",
        hdrs={},
        fp=BytesIO(error_body.encode("utf-8"))
    )


def create_mock_urlopen_context_manager(mock_response):
    """
    创建 mock urlopen 的上下文管理器返回值
    
    Args:
        mock_response: mock 响应对象
    
    Returns:
        MagicMock: 配置好的 mock urlopen 对象
    """
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value = mock_response
    return mock_urlopen

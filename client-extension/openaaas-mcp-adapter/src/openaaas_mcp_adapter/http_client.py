"""HTTP 客户端：基于 httpx 的安全请求与错误处理"""

import json
from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0
UPLOAD_TIMEOUT = 60.0
DOWNLOAD_TIMEOUT = 60.0


class OpenAaaSError(Exception):
    """OpenAaaS 业务异常"""

    pass


def _extract_error_message(response: httpx.Response) -> str:
    """从响应体中提取错误信息"""
    text = response.text or response.reason_phrase
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("error") or data.get("message") or text)
    except json.JSONDecodeError:
        pass
    return text


def _map_exception(exc: Exception, url: str) -> OpenAaaSError:
    """将网络异常映射为中文业务异常"""
    msg = str(exc)
    if isinstance(exc, httpx.ConnectError):
        return OpenAaaSError("连接失败: 无法连接到服务端，请检查 server_url 是否正确")
    if isinstance(exc, httpx.TimeoutException):
        return OpenAaaSError("请求超时: 服务端响应时间过长，请稍后重试")
    if isinstance(exc, httpx.NetworkError):
        return OpenAaaSError("网络错误: 无法连接到服务端，请检查网络或 server_url")
    if isinstance(exc, httpx.InvalidURL):
        return OpenAaaSError("服务端地址格式错误: 请检查 server_url 配置")
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        error_msg = _extract_error_message(exc.response)
        if status == 401:
            return OpenAaaSError(
                "认证失败 (401): API Key 无效，请检查 config.json 中的 api_key 是否正确"
            )
        if status == 403:
            return OpenAaaSError("权限不足 (403): 无法访问该资源")
        if status == 404:
            return OpenAaaSError("资源不存在 (404): 请检查参数是否正确")
        if status == 409:
            return OpenAaaSError(f"冲突 (409): {error_msg}")
        if status == 400:
            return OpenAaaSError(f"请求参数错误 (400): {error_msg}")
        return OpenAaaSError(f"请求失败 (HTTP {status}): {error_msg}")
    return OpenAaaSError(f"请求失败: {msg}")


def safe_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    timeout: float | None = None,
    max_redirects: int = 3,
) -> Any:
    """
    发送 HTTP 请求并安全处理响应（手动处理 3xx 重定向，保持原 HTTP 方法）

    Args:
        method: HTTP 方法 (GET/POST/PUT/DELETE)
        url: 请求 URL
        headers: 请求头
        data: JSON 请求体（会被序列化为 JSON）
        files: 文件列表，格式 [(field_name, (filename, content, mime_type)), ...]
        timeout: 超时秒数
        max_redirects: 最大重定向次数

    Returns:
        解析后的 JSON 对象

    Raises:
        OpenAaaSError: 所有网络或 HTTP 错误以中文抛出
    """
    headers = headers or {}
    timeout_val = timeout or DEFAULT_TIMEOUT
    current_url = url
    remaining_redirects = max_redirects
    original_host = httpx.URL(url).host

    try:
        with httpx.Client(timeout=timeout_val, follow_redirects=False) as client:
            while remaining_redirects >= 0:
                req_headers = dict(headers)
                current_host = httpx.URL(current_url).host
                if current_host != original_host:
                    req_headers.pop("Authorization", None)

                if files is not None:
                    # multipart upload: data for form fields, files for uploads
                    form_data = {k: str(v) for k, v in (data or {}).items()}
                    response = client.request(
                        method, current_url, headers=req_headers, data=form_data, files=files
                    )
                elif data:
                    if "Content-Type" not in req_headers:
                        req_headers = {**req_headers, "Content-Type": "application/json"}
                    response = client.request(
                        method, current_url, headers=req_headers, json=data
                    )
                else:
                    response = client.request(method, current_url, headers=req_headers)

                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    if location:
                        if remaining_redirects > 0:
                            current_url = str(httpx.URL(location, base=current_url))
                            remaining_redirects -= 1
                            continue
                        raise OpenAaaSError("请求被多次重定向，请直接使用 HTTPS URL")

                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return {}
                return response.json()

    except httpx.HTTPStatusError as e:
        raise _map_exception(e, current_url)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.InvalidURL) as e:
        raise _map_exception(e, current_url)
    except json.JSONDecodeError as e:
        raise OpenAaaSError(f"响应 JSON 解析错误: {e}")
    except OpenAaaSError:
        raise
    except Exception as e:
        raise OpenAaaSError(f"请求失败: {e}")

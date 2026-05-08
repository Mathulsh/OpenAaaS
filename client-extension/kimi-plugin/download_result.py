#!/usr/bin/env python3
"""
OpenAaaS 插件 - 下载任务结果
调用 GET /client/files/list/{task_id} 获取文件列表
然后下载 zip 结果文件
"""

import json
import re
import sys
import os
import urllib.request
import urllib.error
import zipfile
import shutil

from utils import load_config


# zip 炸弹防护常量
MAX_ZIP_RATIO = 500          # 最大压缩比
MAX_TOTAL_SIZE = 100 * 1024 * 1024   # 100MB
MAX_FILE_COUNT = 1000        # 最大文件数
MAX_SINGLE_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _zipinfo_is_symlink(info):
    """兼容不同 Python 版本的 ZipInfo 符号链接检测"""
    if hasattr(info, "is_symlink"):
        return info.is_symlink()
    # Fallback: Unix symlink upper nibble of external_attr is 0xA
    return info.create_system == 3 and (info.external_attr >> 28) == 0xA


def safe_extract_zip(zip_path, extract_dir):
    """
    安全解压 zip 文件到指定目录（含 zip 炸弹防护）

    Args:
        zip_path: zip 文件路径
        extract_dir: 解压目标目录

    Returns:
        成功返回解压目录路径，失败返回 {"error": "错误信息"}
    """
    try:
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            file_count = len(zf.infolist())
            if file_count > MAX_FILE_COUNT:
                return {"error": f"zip 文件包含过多文件 ({file_count} > {MAX_FILE_COUNT})，可能存在 zip 炸弹风险"}

            total_size = 0
            for info in zf.infolist():
                total_size += info.file_size
                if info.file_size > MAX_SINGLE_FILE_SIZE:
                    return {"error": f"zip 文件包含过大文件: {info.filename} ({info.file_size} bytes)"}

            if total_size > MAX_TOTAL_SIZE:
                return {"error": f"zip 文件解压后总大小过大 ({total_size} bytes > {MAX_TOTAL_SIZE} bytes)"}

            zip_size = os.path.getsize(zip_path)
            if zip_size > 0 and total_size / zip_size > MAX_ZIP_RATIO:
                return {"error": f"zip 文件压缩比异常 ({total_size / zip_size:.1f} > {MAX_ZIP_RATIO})，可能存在 zip 炸弹风险"}

            # 逐文件解压，每次解压后重新验证路径（防止符号链接攻击）
            real_extract_dir = os.path.realpath(extract_dir)
            for info in zf.infolist():
                if _zipinfo_is_symlink(info):
                    return {"error": f"zip 文件包含符号链接: {info.filename}，已拒绝解压"}

                # 预检查路径
                extracted_path = os.path.join(extract_dir, info.filename)
                real_extracted_path = os.path.realpath(extracted_path)
                if not real_extracted_path.startswith(real_extract_dir + os.sep):
                    return {"error": f"zip 文件包含非法路径: {info.filename}"}

                zf.extract(info, extract_dir)

                # 解压后再次验证（符号链接创建后 realpath 会跟随）
                real_extracted_path = os.path.realpath(extracted_path)
                if not real_extracted_path.startswith(real_extract_dir + os.sep):
                    # 删除已创建的危险文件或目录
                    shutil.rmtree(extracted_path, ignore_errors=True)
                    return {"error": f"zip 文件包含路径穿越: {info.filename}"}

        return extract_dir
    except Exception as e:
        return {"error": f"解压失败: {str(e)}"}


def get_file_list(server_url, api_key, task_id):
    """
    获取任务文件列表
    
    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        task_id: 任务 ID
    
    Returns:
        文件列表或错误字典
    """
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
            return files
            
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
            return {"error": f"权限不足 (403): 无权访问该任务"}
        elif e.code == 404:
            return {"error": f"任务不存在 (404): 请检查 task_id 是否正确"}
        return {"error": f"获取文件列表失败 (HTTP {e.code}): {error_msg}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}"}
    except Exception as e:
        return {"error": f"获取文件列表失败: {str(e)}"}


def get_download_dir(task_id):
    """获取下载目录：项目目录下的 .OpenAaaS/downloads/{task_id}"""
    sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', task_id)
    if sanitized in (".", "..", ""):
        sanitized = "_"
    cwd = os.getcwd()
    return os.path.join(cwd, ".OpenAaaS", "downloads", sanitized)


def download_file(server_url, api_key, file_id, save_path):
    """
    下载单个文件

    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        file_id: 文件 ID
        save_path: 保存路径
    """
    save_dir = os.path.dirname(save_path)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)

    server_url = server_url.rstrip("/")
    url = f"{server_url}/api/v1/client/files/{file_id}/download"

    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

            # 检查内容是否是 JSON 错误（通过 Content-Type 头判断）
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                try:
                    error_data = json.loads(content.decode('utf-8'))
                    error_msg = error_data.get('error') or error_data.get('message') or '未知错误'
                    return {"error": f"下载失败: {error_msg}"}
                except:
                    pass

            with open(save_path, "wb") as f:
                f.write(content)

            return save_path

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get('error') or error_data.get('message') or e.reason
        except:
            error_msg = error_body or e.reason
        
        if e.code == 401:
            return {"error": f"认证失败 (401): API Key 无效"}
        elif e.code == 403:
            return {"error": f"权限不足 (403): 无权访问该文件"}
        return {"error": f"HTTP {e.code}: {error_msg}"}
    except Exception as e:
        return {"error": str(e)}


def download_result(server_url, api_key, task_id, file_id=None, download_all=False):
    """
    下载任务结果

    Args:
        server_url: 服务端基础地址
        api_key: API 密钥
        task_id: 任务 ID
        file_id: 指定下载的文件 ID（可选）
        download_all: 是否下载所有文件（可选）
    """
    if not api_key:
        return {"error": "缺少 API Key，请先运行 register 进行注册"}

    if not task_id:
        return {"error": "缺少任务 ID"}

    download_dir = get_download_dir(task_id)

    # 获取文件列表
    files_result = get_file_list(server_url, api_key, task_id)

    if isinstance(files_result, dict) and "error" in files_result:
        return files_result

    files = files_result

    if not files:
        return {"error": f"任务 {task_id} 没有可下载的结果文件"}

    # 如果指定了 file_id，下载该文件
    if file_id:
        target_file = None
        for f in files:
            if (f.get("id") or f.get("file_id")) == file_id:
                target_file = f
                break
        if not target_file:
            return {"error": f"未找到 file_id 为 {file_id} 的文件"}
        files_to_download = [target_file]
    # 如果 download_all，下载所有文件
    elif download_all:
        files_to_download = files
    else:
        # 默认下载第一个 zip 文件，如果没有 zip 则下载第一个文件
        zip_files = [f for f in files if f.get("filename", "").endswith(".zip")]
        files_to_download = [zip_files[0]] if zip_files else [files[0]]

    downloaded = []
    errors = []
    extracted_dirs = []

    for target_file in files_to_download:
        fid = target_file.get("id") or target_file.get("file_id")
        filename = target_file.get("filename", f"{fid}.zip")

        if not fid:
            errors.append("文件信息不完整，无法下载")
            continue

        # 修复路径遍历漏洞：使用 os.path.basename 过滤
        basename = os.path.basename(filename)
        if basename in (".", ".."):
            errors.append(f"非法文件名: {filename}")
            continue
        save_path = os.path.join(download_dir, basename)
        result = download_file(server_url, api_key, fid, save_path)

        if isinstance(result, dict) and "error" in result:
            errors.append(f"{filename}: {result['error']}")
            continue

        downloaded.append({"filename": filename, "path": result})

        # 如果是 zip 文件，自动解压
        if filename.endswith(".zip"):
            extract_dir = os.path.join(download_dir, os.path.splitext(filename)[0])
            extract_result = safe_extract_zip(result, extract_dir)
            if isinstance(extract_result, dict) and "error" in extract_result:
                errors.append(f"{filename} 解压失败: {extract_result['error']}")
            else:
                extracted_dirs.append(extract_dir)
                # 解压成功后删除原 zip
                try:
                    os.remove(result)
                except:
                    pass

    if not downloaded:
        return {"error": f"所有文件下载失败: {'; '.join(errors)}"}

    content = f"结果下载完成！\n任务 ID: {task_id}\n下载目录: {download_dir}\n成功下载: {len(downloaded)} 个文件"
    if extracted_dirs:
        content += f"\n自动解压目录: {len(extracted_dirs)} 个"
        for d in extracted_dirs:
            try:
                files_in_dir = os.listdir(d)
                content += f"\n  - {d}: {', '.join(files_in_dir)}"
            except:
                content += f"\n  - {d}"
    if errors:
        content += f"\n失败项 ({len(errors)} 个):"
        for err in errors:
            content += f"\n  - {err}"

    return {
        "content": content,
        "data": {
            "task_id": task_id,
            "download_dir": download_dir,
            "downloaded": downloaded,
            "extracted_dirs": extracted_dirs,
            "errors": errors
        }
    }


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
        if not task_id or task_id in (".", ".."):
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

        # 获取可选参数
        file_id = params.get("file_id", "")
        download_all = params.get("download_all", False)

        # 执行下载
        result = download_result(server_url, api_key, task_id, file_id=file_id, download_all=download_all)
        
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

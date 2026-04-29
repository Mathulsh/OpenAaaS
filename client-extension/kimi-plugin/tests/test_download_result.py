#!/usr/bin/env python3
"""
Tests for download_result.py - 下载任务结果模块
"""

import json
import sys
import os
import unittest
import tempfile
import zipfile
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import download_result


class TestSafeExtractZip(unittest.TestCase):
    """测试 safe_extract_zip 函数"""

    def setUp(self):
        """创建临时目录用于测试"""
        self.test_dir = tempfile.mkdtemp()
        self.zip_path = os.path.join(self.test_dir, "test.zip")
        self.extract_dir = os.path.join(self.test_dir, "extracted")

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_test_zip(self, files_content):
        """辅助方法：创建测试 zip 文件"""
        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            for filename, content in files_content.items():
                zf.writestr(filename, content)

    def test_extract_zip_success(self):
        """测试正常解压成功"""
        self.create_test_zip({"file1.txt": "content1", "file2.txt": "content2"})

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertEqual(result, self.extract_dir)
        self.assertTrue(os.path.exists(os.path.join(self.extract_dir, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.extract_dir, "file2.txt")))
        with open(os.path.join(self.extract_dir, "file1.txt")) as f:
            self.assertEqual(f.read(), "content1")

    def test_extract_zip_existing_dir(self):
        """测试目标目录已存在时的处理"""
        os.makedirs(self.extract_dir)
        with open(os.path.join(self.extract_dir, "old_file.txt"), "w") as f:
            f.write("old content")

        self.create_test_zip({"new_file.txt": "new content"})

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertEqual(result, self.extract_dir)
        self.assertTrue(os.path.exists(os.path.join(self.extract_dir, "new_file.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.extract_dir, "old_file.txt")))

    def test_extract_zip_invalid_file(self):
        """测试无效的 zip 文件"""
        with open(self.zip_path, "w") as f:
            f.write("not a zip file")

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertIn("error", result)
        self.assertIn("解压失败", result["error"])

    def test_extract_zip_nonexistent_file(self):
        """测试不存在的 zip 文件"""
        result = download_result.safe_extract_zip("/nonexistent/file.zip", self.extract_dir)

        self.assertIn("error", result)

    def test_extract_zip_path_traversal(self):
        """测试 zip 路径穿越防护"""
        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            zf.writestr("../escape.txt", "bad content")

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertIn("error", result)
        self.assertIn("非法路径", result["error"])

    def test_extract_zip_symlink(self):
        """测试 zip 符号链接拒绝"""
        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            info = zipfile.ZipInfo("link.txt")
            info.create_system = 3  # Unix
            info.external_attr = (0xA << 28) | 0o777  # symlink
            zf.writestr(info, "target.txt")

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertIn("error", result)
        self.assertIn("符号链接", result["error"])

    def test_extract_zip_too_many_files(self):
        """测试 zip 文件数量超限防护"""
        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            for i in range(download_result.MAX_FILE_COUNT + 1):
                zf.writestr(f"file{i}.txt", "x")

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        self.assertIn("error", result)
        self.assertIn("文件包含过多文件", result["error"])

    def test_extract_zip_ratio_bomb(self):
        """测试 zip 炸弹压缩比防护"""
        # 创建一个高压缩比文件：大量重复字符
        with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.txt", "A" * (1024 * 1024 * 10))  # 10MB 的 A

        result = download_result.safe_extract_zip(self.zip_path, self.extract_dir)

        # 10MB 的 A 压缩后通常只有几 KB，压缩比会远超 100
        self.assertIn("error", result)
        self.assertIn("zip 炸弹", result["error"])


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080", "api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = download_result.load_config()
        self.assertEqual(config["api_key"], "test-key")
        self.assertIn("servers", config)

    @patch("builtins.open", side_effect=Exception("Read error"))
    def test_load_config_error(self, mock_file):
        """测试加载配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = download_result.load_config()
        self.assertIn("error", config)


class TestGetFileList(unittest.TestCase):
    """测试 get_file_list 函数"""

    @patch("urllib.request.urlopen")
    def test_get_file_list_success(self, mock_urlopen):
        """测试正常获取文件列表"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {"id": "file-1", "filename": "result.zip"},
            {"id": "file-2", "filename": "data.txt"}
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = download_result.get_file_list("http://localhost:8080", "test-key", "task-123")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "file-1")

    @patch("urllib.request.urlopen")
    def test_get_file_list_object_format(self, mock_urlopen):
        """测试返回对象格式（包含 files 字段）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "files": [
                {"id": "file-1", "filename": "result.zip"}
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = download_result.get_file_list("http://localhost:8080", "test-key", "task-123")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("urllib.request.urlopen")
    def test_get_file_list_http_error(self, mock_urlopen):
        """测试 HTTP 错误"""
        error_body = b'{"error": "Task not found"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/files/list/task-123",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error

        result = download_result.get_file_list("http://localhost:8080", "test-key", "task-123")

        self.assertIn("error", result)
        self.assertIn("404", result["error"])

    @patch("urllib.request.urlopen")
    def test_get_file_list_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = download_result.get_file_list("http://localhost:8080", "test-key", "task-123")

        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])


class TestDownloadFile(unittest.TestCase):
    """测试 download_file 函数"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.save_path = os.path.join(self.test_dir, "downloaded.zip")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("urllib.request.urlopen")
    def test_download_file_success(self, mock_urlopen):
        """测试正常下载文件"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"file content"
        mock_response.headers = {
            "Content-Disposition": 'attachment; filename="original.zip"',
            "Content-Type": "application/zip"
        }
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = download_result.download_file(
            "http://localhost:8080",
            "test-key",
            "file-123",
            self.save_path
        )

        self.assertEqual(result, self.save_path)
        self.assertTrue(os.path.exists(self.save_path))
        with open(self.save_path, "rb") as f:
            self.assertEqual(f.read(), b"file content")

    @patch("urllib.request.urlopen")
    def test_download_file_creates_parent_dir(self, mock_urlopen):
        """测试保存路径的父目录不存在时自动创建"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"content"
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        nested_path = os.path.join(self.test_dir, "nested", "file.zip")
        result = download_result.download_file(
            "http://localhost:8080",
            "test-key",
            "file-123",
            nested_path
        )

        self.assertEqual(result, nested_path)
        self.assertTrue(os.path.exists(nested_path))

    @patch("urllib.request.urlopen")
    def test_download_file_uses_save_path_directly(self, mock_urlopen):
        """测试 save_path 被直接用作保存路径"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"content"
        mock_response.headers = {}  # 没有 Content-Disposition
        mock_urlopen.return_value.__enter__.return_value = mock_response

        save_path = os.path.join(self.test_dir, "my_custom_name.zip")
        result = download_result.download_file(
            "http://localhost:8080",
            "test-key",
            "file-abc",
            save_path
        )

        self.assertEqual(result, save_path)
        self.assertTrue(os.path.exists(save_path))

    @patch("urllib.request.urlopen")
    def test_download_file_json_error(self, mock_urlopen):
        """测试下载内容为 JSON 错误时"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error": "File not ready"}'
        mock_response.headers = {
            "Content-Type": "application/json"
        }
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = download_result.download_file(
            "http://localhost:8080",
            "test-key",
            "file-123",
            self.save_path
        )

        self.assertIn("error", result)
        self.assertIn("File not ready", result["error"])

    @patch("urllib.request.urlopen")
    def test_download_file_http_error(self, mock_urlopen):
        """测试 HTTP 错误"""
        error_body = b'{"error": "Access denied"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/files/file-123/download",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error

        result = download_result.download_file(
            "http://localhost:8080",
            "test-key",
            "file-123",
            self.save_path
        )

        self.assertIn("error", result)
        self.assertIn("403", result["error"])


class TestGetDownloadDir(unittest.TestCase):
    """测试 get_download_dir 函数"""

    def test_get_download_dir(self):
        """测试下载目录构造"""
        result = download_result.get_download_dir("task-abc")
        self.assertIn(".OpenAaaS", result)
        self.assertIn("downloads", result)
        self.assertIn("task-abc", result)

    def test_get_download_dir_sanitizes_task_id(self):
        """测试 task_id 路径遍历消毒"""
        result = download_result.get_download_dir("../../../etc")
        # 确保没有路径分隔符后的 .. 导致目录遍历
        self.assertNotIn("../", result)
        self.assertNotIn("..\\", result)
        self.assertIn(".._.._.._etc", result)

    def test_get_download_dir_rejects_dot(self):
        """测试 task_id 为 . 时返回安全目录"""
        result = download_result.get_download_dir(".")
        self.assertTrue(result.endswith(os.sep + "_"))

    def test_get_download_dir_rejects_dotdot(self):
        """测试 task_id 为 .. 时返回安全目录"""
        result = download_result.get_download_dir("..")
        self.assertTrue(result.endswith(os.sep + "_"))


class TestDownloadResult(unittest.TestCase):
    """测试 download_result 函数"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("download_result.get_download_dir")
    @patch("download_result.safe_extract_zip")
    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_success(self, mock_get_list, mock_download, mock_extract, mock_get_dir):
        """测试正常下载并解压成功"""
        mock_get_dir.return_value = self.test_dir
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "result.zip"}
        ]

        zip_path = os.path.join(self.test_dir, "result.zip")
        with open(zip_path, "w") as f:
            f.write("zip content")
        mock_download.return_value = zip_path

        extract_dir = os.path.join(self.test_dir, "result")
        os.makedirs(extract_dir, exist_ok=True)
        with open(os.path.join(extract_dir, "result.txt"), "w") as f:
            f.write("extracted content")
        mock_extract.return_value = extract_dir

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["task_id"], "task-123")

    @patch("download_result.get_file_list")
    def test_download_result_no_files(self, mock_get_list):
        """测试无结果文件"""
        mock_get_list.return_value = []

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("没有可下载的结果文件", result["error"])

    @patch("download_result.get_file_list")
    def test_download_result_get_list_error(self, mock_get_list):
        """测试获取文件列表失败"""
        mock_get_list.return_value = {"error": "Task not found"}

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("Task not found", result["error"])

    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_download_failed(self, mock_get_list, mock_download):
        """测试下载失败"""
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "result.zip"}
        ]
        mock_download.return_value = {"error": "Download failed"}

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("所有文件下载失败", result["error"])

    @patch("download_result.safe_extract_zip")
    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_extract_failed(self, mock_get_list, mock_download, mock_extract):
        """测试解压失败"""
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "result.zip"}
        ]

        zip_path = os.path.join(self.test_dir, "result.zip")
        with open(zip_path, "w") as f:
            f.write("content")
        mock_download.return_value = zip_path

        mock_extract.return_value = {"error": "Corrupt zip file"}

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        # 下载成功但解压失败，返回 content 而非 error
        self.assertIn("content", result)
        self.assertIn("解压失败", result["content"])
        self.assertEqual(len(result["data"]["errors"]), 1)

    def test_download_result_missing_api_key(self):
        """测试缺少 API Key"""
        result = download_result.download_result(
            "http://localhost:8080",
            "",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])

    def test_download_result_missing_task_id(self):
        """测试缺少任务 ID"""
        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            ""
        )

        self.assertIn("error", result)
        self.assertIn("缺少任务 ID", result["error"])

    @patch("download_result.get_download_dir")
    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_with_file_id(self, mock_get_list, mock_download, mock_get_dir):
        """测试指定 file_id 下载"""
        mock_get_dir.return_value = self.test_dir
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "a.zip"},
            {"id": "file-2", "filename": "b.txt"}
        ]
        mock_download.return_value = os.path.join(self.test_dir, "b.txt")

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123",
            file_id="file-2"
        )

        self.assertIn("content", result)
        self.assertEqual(len(result["data"]["downloaded"]), 1)

    @patch("download_result.get_download_dir")
    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_download_all(self, mock_get_list, mock_download, mock_get_dir):
        """测试 download_all 下载所有文件"""
        mock_get_dir.return_value = self.test_dir
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "a.zip"},
            {"id": "file-2", "filename": "b.txt"}
        ]
        mock_download.return_value = os.path.join(self.test_dir, "b.txt")

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123",
            download_all=True
        )

        self.assertIn("content", result)
        self.assertEqual(len(result["data"]["downloaded"]), 2)

    @patch("download_result.get_download_dir")
    @patch("download_result.download_file")
    @patch("download_result.get_file_list")
    def test_download_result_path_traversal_filename(self, mock_get_list, mock_download, mock_get_dir):
        """测试文件名路径遍历防护（os.path.basename）"""
        mock_get_dir.return_value = self.test_dir
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "../../../etc/passwd"}
        ]
        mock_download.return_value = os.path.join(self.test_dir, "passwd")

        download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        # 验证 download_file 被传入 basename 过滤后的路径
        call_args = mock_download.call_args
        save_path_arg = call_args[0][3]
        self.assertTrue(save_path_arg.endswith("passwd"))
        self.assertNotIn("..", save_path_arg)

    @patch("download_result.get_file_list")
    def test_download_result_rejects_dot_filename(self, mock_get_list):
        """测试服务端返回文件名 . 时拒绝下载"""
        mock_get_list.return_value = [
            {"id": "file-1", "filename": "."}
        ]

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("非法文件名", result["error"])

    @patch("download_result.get_file_list")
    def test_download_result_rejects_dotdot_filename(self, mock_get_list):
        """测试服务端返回文件名 .. 时拒绝下载"""
        mock_get_list.return_value = [
            {"id": "file-1", "filename": ".."}
        ]

        result = download_result.download_result(
            "http://localhost:8080",
            "test-key",
            "task-123"
        )

        self.assertIn("error", result)
        self.assertIn("非法文件名", result["error"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    def test_main_missing_task_id(self):
        """测试缺少 task_id 参数"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    download_result.main()

            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("task_id", output["error"])

    def test_main_empty_input(self):
        """测试空输入"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('')):
                with self.assertRaises(SystemExit) as cm:
                    download_result.main()

            self.assertEqual(cm.exception.code, 1)

    def test_main_task_id_dot(self):
        """测试 task_id 为 . 时拒绝"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{"task_id": "."}')):
                with self.assertRaises(SystemExit) as cm:
                    download_result.main()

            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("task_id", output["error"])

    def test_main_task_id_dotdot(self):
        """测试 task_id 为 .. 时拒绝"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{"task_id": ".."}')):
                with self.assertRaises(SystemExit) as cm:
                    download_result.main()

            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("task_id", output["error"])


if __name__ == "__main__":
    unittest.main()

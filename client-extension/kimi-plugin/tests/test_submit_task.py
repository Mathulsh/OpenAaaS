#!/usr/bin/env python3
"""
Tests for submit_task.py - 提交任务模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import submit_task


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = submit_task.load_config()
        self.assertEqual(config["api_key"], "test-key")
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_config_error(self, mock_file):
        """测试加载配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = submit_task.load_config()
        self.assertIn("error", config)


class TestBuildMultipartRequest(unittest.TestCase):
    """测试 build_multipart_request 函数"""
    
    @patch("os.path.exists")
    @patch("mimetypes.guess_type")
    @patch("builtins.open", mock_open(read_data=b"file content"))
    def test_build_multipart_without_files(self, mock_guess_type, mock_exists):
        """测试不带文件的 multipart 构建"""
        url = "http://localhost:8080/api/v1/client/tasks"
        fields = {"service_id": "svc-1", "task_prompt": "test task"}
        files = []
        headers = {"Authorization": "Bearer test-key"}
        
        req = submit_task.build_multipart_request(url, fields, files, headers)
        
        self.assertEqual(req.full_url, url)
        self.assertIn("multipart/form-data", req.headers["Content-type"])
        self.assertIn("boundary", req.headers["Content-type"])
        self.assertEqual(req.headers["Authorization"], "Bearer test-key")
    
    @patch("os.path.exists")
    @patch("mimetypes.guess_type")
    @patch("builtins.open", mock_open(read_data=b"file content"))
    def test_build_multipart_with_files(self, mock_guess_type, mock_exists):
        """测试带文件的 multipart 构建"""
        mock_exists.return_value = True
        mock_guess_type.return_value = ("text/plain", None)

        url = "http://localhost:8080/api/v1/client/tasks"
        fields = {"service_id": "svc-1", "task_prompt": "test task"}
        files = [("files", "/path/to/test.txt")]
        headers = {"Authorization": "Bearer test-key"}

        req = submit_task.build_multipart_request(url, fields, files, headers)

        body = req.data
        self.assertIn(b"--", body)
        self.assertIn(b'Content-Disposition: form-data; name="files"; filename="test.txt"', body)
        self.assertIn(b"file content", body)

    @patch("os.path.exists")
    @patch("mimetypes.guess_type")
    @patch("builtins.open", mock_open(read_data=b"file content"))
    def test_build_multipart_escapes_quotes_in_filename(self, mock_guess_type, mock_exists):
        """测试文件名中包含双引号时正确转义"""
        mock_exists.return_value = True
        mock_guess_type.return_value = ("text/plain", None)

        url = "http://localhost:8080/api/v1/client/tasks"
        fields = {"service_id": "svc-1"}
        files = [("files", '/path/to/test"evil.txt')]
        headers = {}

        req = submit_task.build_multipart_request(url, fields, files, headers)

        body = req.data
        self.assertIn(b'Content-Disposition: form-data; name="files"; filename="test\\"evil.txt"', body)
    
    @patch("os.path.exists")
    def test_build_multipart_file_not_found(self, mock_exists):
        """测试文件不存在错误"""
        mock_exists.return_value = False
        
        url = "http://localhost:8080/api/v1/client/tasks"
        fields = {"service_id": "svc-1"}
        files = [("files", "/nonexistent/file.txt")]
        headers = {}
        
        with self.assertRaises(FileNotFoundError):
            submit_task.build_multipart_request(url, fields, files, headers)
    
    @patch("os.path.exists")
    @patch("mimetypes.guess_type")
    @patch("builtins.open", mock_open(read_data=b"content1"))
    def test_build_multipart_multiple_files(self, mock_guess_type, mock_exists):
        """测试多个文件上传"""
        mock_exists.return_value = True
        mock_guess_type.return_value = ("application/octet-stream", None)
        
        url = "http://localhost:8080/api/v1/client/tasks"
        fields = {"service_id": "svc-1"}
        files = [("files", "/path/file1.txt"), ("files", "/path/file2.txt")]
        headers = {}
        
        req = submit_task.build_multipart_request(url, fields, files, headers)
        body = req.data
        
        # 应该有两个文件的 boundary
        boundary_count = body.count(b"--")
        self.assertGreaterEqual(boundary_count, 4)  # 开始、每个文件、结束


class TestSubmitTask(unittest.TestCase):
    """测试 submit_task 函数"""
    
    @patch("urllib.request.urlopen")
    def test_submit_without_files(self, mock_urlopen):
        """测试正常提交（无文件）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-123",
            "status": "pending"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "test-api-key",
            "svc-1",
            "test prompt",
            "output format",
            []
        )
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["task_id"], "task-123")
        self.assertEqual(result["data"]["status"], "pending")
    
    @patch("urllib.request.urlopen")
    @patch("submit_task.build_multipart_request")
    def test_submit_with_files(self, mock_build, mock_urlopen):
        """测试带文件上传"""
        mock_request = MagicMock()
        mock_build.return_value = mock_request
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-456",
            "status": "accepted"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"file data")):
                with patch("mimetypes.guess_type", return_value=("text/plain", None)):
                    result = submit_task.submit_task(
                        "http://localhost:8080",
                        "test-api-key",
                        "svc-1",
                        "test prompt",
                        "output format",
                        ["/path/to/file.txt"]
                    )
        
        self.assertEqual(result["data"]["task_id"], "task-456")
        mock_build.assert_called_once()
    
    @patch("submit_task.build_multipart_request")
    def test_submit_file_not_found(self, mock_build):
        """测试文件不存在错误"""
        mock_build.side_effect = FileNotFoundError("文件不存在: /nonexistent.txt")
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "test-api-key",
            "svc-1",
            "test prompt",
            "output format",
            ["/nonexistent.txt"]
        )
        
        self.assertIn("error", result)
        self.assertIn("文件上传失败", result["error"])
    
    def test_submit_missing_api_key(self):
        """测试缺少 API Key"""
        result = submit_task.submit_task(
            "http://localhost:8080",
            "",
            "svc-1",
            "test prompt",
            "output format",
            []
        )
        
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_submit_auth_failure_401(self, mock_urlopen):
        """测试认证失败（401）"""
        error_body = b'{"error": "Invalid API key"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "invalid-key",
            "svc-1",
            "test prompt",
            "output format",
            []
        )
        
        self.assertIn("error", result)
        self.assertIn("认证失败 (401)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_submit_service_not_found_404(self, mock_urlopen):
        """测试服务不存在（404）"""
        error_body = b'{"error": "Service not found"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "valid-key",
            "invalid-svc",
            "test prompt",
            "output format",
            []
        )
        
        self.assertIn("error", result)
        self.assertIn("服务不存在 (404)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_submit_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "test-key",
            "svc-1",
            "test prompt",
            "output format",
            []
        )
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
    
    @patch("submit_task.build_multipart_request")
    @patch("urllib.request.urlopen")
    def test_submit_does_not_send_session_id(self, mock_urlopen, mock_build):
        """测试插件提交时不暴露 session_id 字段"""
        mock_request = MagicMock()
        mock_build.return_value = mock_request
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-789",
            "session_id": "server-internal-session",
            "status": "pending"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = submit_task.submit_task(
            "http://localhost:8080",
            "test-api-key",
            "svc-1",
            "test prompt",
            "output format",
            []
        )
        
        self.assertEqual(result["data"]["task_id"], "task-789")
        self.assertNotIn("session_id", result["data"])
        fields = mock_build.call_args.args[1]
        self.assertNotIn("session_id", fields)


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    def test_main_missing_output_prompt_allows_empty(self):
        """测试 output_prompt 为可选参数"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO(json.dumps({
                "service_id": "svc-1",
                "task_prompt": "test task"
            }))):
                with patch("submit_task.submit_task") as mock_submit:
                    mock_submit.return_value = {
                        "content": "任务提交成功！",
                        "data": {"task_id": "task-123", "status": "pending"}
                    }
                    with patch("submit_task.load_config") as mock_load:
                        mock_load.return_value = {
                            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": "test-key"}},
                            "default_server": "default"
                        }
                        submit_task.main()
            
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("content", output)
    
    def test_main_empty_input(self):
        """测试空输入"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('')):
                with self.assertRaises(SystemExit) as cm:
                    submit_task.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("缺少参数", output["error"])


if __name__ == "__main__":
    unittest.main()

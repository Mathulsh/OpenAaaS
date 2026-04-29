#!/usr/bin/env python3
"""
Tests for cancel_task.py - 取消任务模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cancel_task


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = cancel_task.load_config()
        self.assertEqual(config["api_key"], "test-key")
    
    @patch("builtins.open", side_effect=Exception("Read error"))
    def test_load_config_error(self, mock_file):
        """测试加载配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = cancel_task.load_config()
        self.assertIn("error", config)


class TestCancelTask(unittest.TestCase):
    """测试 cancel_task 函数"""
    
    @patch("urllib.request.urlopen")
    def test_cancel_success_cancelled(self, mock_urlopen):
        """测试正常取消成功（已取消状态）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "cancelled",
            "task_id": "task-123"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = cancel_task.cancel_task("http://localhost:8080", "test-api-key", "task-123")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["task_id"], "task-123")
        self.assertEqual(result["data"]["status"], "cancelled")
        self.assertIn("已取消", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_success_cancelling(self, mock_urlopen):
        """测试取消成功（取消中状态）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "cancelling",
            "task_id": "task-456"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = cancel_task.cancel_task("http://localhost:8080", "test-api-key", "task-456")
        
        self.assertEqual(result["data"]["status"], "cancelling")
        self.assertIn("正在取消中", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_other_status(self, mock_urlopen):
        """测试其他状态返回"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "completed"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = cancel_task.cancel_task("http://localhost:8080", "test-api-key", "task-789")
        
        self.assertEqual(result["data"]["status"], "completed")
    
    def test_cancel_missing_api_key(self):
        """测试缺少 API Key"""
        result = cancel_task.cancel_task("http://localhost:8080", "", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])
    
    def test_cancel_missing_task_id(self):
        """测试缺少任务 ID"""
        result = cancel_task.cancel_task("http://localhost:8080", "test-key", "")
        
        self.assertIn("error", result)
        self.assertIn("缺少任务 ID", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_auth_failure_401(self, mock_urlopen):
        """测试认证失败（401）"""
        error_body = b'{"error": "Invalid API key"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123/cancel",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = cancel_task.cancel_task("http://localhost:8080", "invalid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("认证失败 (401)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_forbidden_403(self, mock_urlopen):
        """测试权限不足（403）"""
        error_body = b'{"error": "Cannot cancel task of another client"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123/cancel",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = cancel_task.cancel_task("http://localhost:8080", "valid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("权限不足 (403)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_not_found_404(self, mock_urlopen):
        """测试任务不存在（404）"""
        error_body = b'{"error": "Task not found"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123/cancel",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = cancel_task.cancel_task("http://localhost:8080", "valid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("任务不存在 (404)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_bad_request_400(self, mock_urlopen):
        """测试无法取消（400）"""
        error_body = b'{"error": "Task already completed"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123/cancel",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = cancel_task.cancel_task("http://localhost:8080", "valid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("无法取消 (400)", result["error"])
        self.assertIn("Task already completed", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_other_http_error(self, mock_urlopen):
        """测试其他 HTTP 错误"""
        error_body = b'{"error": "Internal error"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123/cancel",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = cancel_task.cancel_task("http://localhost:8080", "valid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("HTTP 500", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        result = cancel_task.cancel_task("http://localhost:8080", "test-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_cancel_authorization_header(self, mock_urlopen):
        """测试 Authorization 请求头正确设置"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "cancelled"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        cancel_task.cancel_task("http://localhost:8080", "my-api-key", "task-123")
        
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        self.assertEqual(request.headers["Authorization"], "Bearer my-api-key")


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    def test_main_missing_task_id(self):
        """测试缺少 task_id 参数"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    cancel_task.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("task_id", output["error"])
    
    def test_main_empty_input(self):
        """测试空输入"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('')):
                with self.assertRaises(SystemExit) as cm:
                    cancel_task.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("缺少参数", output["error"])


if __name__ == "__main__":
    unittest.main()

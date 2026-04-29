#!/usr/bin/env python3
"""
Tests for get_task.py - 查询任务模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import get_task


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = get_task.load_config()
        self.assertEqual(config["api_key"], "test-key")
    
    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_load_config_error(self, mock_file):
        """测试加载配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = get_task.load_config()
        self.assertIn("error", config)


class TestGetTask(unittest.TestCase):
    """测试 get_task 函数"""
    
    @patch("urllib.request.urlopen")
    def test_get_task_success_completed(self, mock_urlopen):
        """测试正常查询已完成任务"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-123",
            "status": "completed",
            "service_id": "svc-1",
            "task_prompt": "test prompt",
            "output_prompt": "output format",
            "result": {"summary": "Task completed successfully"},
            "created_at": "2024-01-01T00:00:00Z",
            "started_at": "2024-01-01T00:00:01Z",
            "completed_at": "2024-01-01T00:00:05Z"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-api-key", "task-123")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["task_id"], "task-123")
        self.assertEqual(result["data"]["status"], "completed")
        self.assertIn("已完成", result["content"])
        self.assertIn("运行时长", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_running(self, mock_urlopen):
        """测试查询运行中任务"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-456",
            "status": "running",
            "service_id": "svc-1",
            "created_at": "2024-01-01T00:00:00Z",
            "started_at": "2024-01-01T00:00:01Z"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-api-key", "task-456")
        
        self.assertEqual(result["data"]["status"], "running")
        self.assertIn("执行中", result["content"])
        self.assertIn("运行时长", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_failed(self, mock_urlopen):
        """测试查询失败任务"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-789",
            "status": "failed",
            "service_id": "svc-1",
            "result": {"error": "Something went wrong"},
            "created_at": "2024-01-01T00:00:00Z"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-api-key", "task-789")
        
        self.assertEqual(result["data"]["status"], "failed")
        self.assertIn("失败", result["content"])
        self.assertIn("Something went wrong", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_pending(self, mock_urlopen):
        """测试查询等待中任务"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-000",
            "status": "pending",
            "service_id": "svc-1",
            "created_at": "2024-01-01T00:00:00Z"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-api-key", "task-000")
        
        self.assertEqual(result["data"]["status"], "pending")
        self.assertIn("等待中", result["content"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_with_task_id_field(self, mock_urlopen):
        """测试使用 task_id 字段而非 id"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "task_id": "task-abc",
            "status": "completed"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-api-key", "task-abc")
        
        self.assertEqual(result["data"]["task_id"], "task-abc")
    
    def test_get_task_missing_api_key(self):
        """测试缺少 API Key"""
        result = get_task.get_task("http://localhost:8080", "", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])
    
    def test_get_task_missing_task_id(self):
        """测试缺少任务 ID"""
        result = get_task.get_task("http://localhost:8080", "test-key", "")
        
        self.assertIn("error", result)
        self.assertIn("缺少任务 ID", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_auth_failure_401(self, mock_urlopen):
        """测试认证失败（401）"""
        error_body = b'{"error": "Invalid API key"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = get_task.get_task("http://localhost:8080", "invalid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("认证失败 (401)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_not_found_404(self, mock_urlopen):
        """测试任务不存在（404）"""
        error_body = b'{"error": "Task not found"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/tasks/task-123",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = get_task.get_task("http://localhost:8080", "valid-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("任务不存在 (404)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection timeout")
        
        result = get_task.get_task("http://localhost:8080", "test-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_json_parse_error(self, mock_urlopen):
        """测试 JSON 解析错误"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-key", "task-123")
        
        self.assertIn("error", result)
        self.assertIn("JSON 解析错误", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_get_task_unknown_status(self, mock_urlopen):
        """测试未知状态"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "task-xyz",
            "status": "unknown_status",
            "created_at": "2024-01-01T00:00:00Z"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_task.get_task("http://localhost:8080", "test-key", "task-xyz")
        
        self.assertIn("unknown_status", result["content"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    def test_main_missing_task_id(self):
        """测试缺少 task_id 参数"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    get_task.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("task_id", output["error"])
    
    def test_main_empty_input(self):
        """测试空输入"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('')):
                with self.assertRaises(SystemExit) as cm:
                    get_task.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)


if __name__ == "__main__":
    unittest.main()

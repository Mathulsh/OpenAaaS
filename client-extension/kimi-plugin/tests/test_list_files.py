#!/usr/bin/env python3
"""
Tests for list_files.py - 列出任务文件模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import list_files


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080", "api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = list_files.load_config()
        self.assertEqual(config["api_key"], "test-key")
        self.assertIn("servers", config)


class TestListFiles(unittest.TestCase):
    """测试 list_files 函数"""

    @patch("urllib.request.urlopen")
    def test_list_files_success(self, mock_urlopen):
        """测试正常获取文件列表"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {"id": "file-1", "filename": "result.zip", "size": 1024, "created_at": "2024-01-01T00:00:00Z"},
            {"id": "file-2", "filename": "data.txt", "size": 512, "created_at": "2024-01-01T00:00:01Z"}
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = list_files.list_files("http://localhost:8080", "test-key", "task-123")
        self.assertIn("content", result)
        self.assertEqual(len(result["data"]["files"]), 2)
        self.assertEqual(result["data"]["files"][0]["file_id"], "file-1")
        self.assertEqual(result["data"]["files"][0]["size"], 1024)

    @patch("urllib.request.urlopen")
    def test_list_files_object_format(self, mock_urlopen):
        """测试返回对象格式"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "files": [{"id": "file-1", "filename": "a.zip"}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = list_files.list_files("http://localhost:8080", "test-key", "task-123")
        self.assertEqual(len(result["data"]["files"]), 1)

    def test_list_files_missing_api_key(self):
        """测试缺少 API Key"""
        result = list_files.list_files("http://localhost:8080", "", "task-123")
        self.assertIn("error", result)

    def test_list_files_missing_task_id(self):
        """测试缺少 task_id"""
        result = list_files.list_files("http://localhost:8080", "test-key", "")
        self.assertIn("error", result)

    @patch("urllib.request.urlopen")
    def test_list_files_404(self, mock_urlopen):
        """测试任务不存在"""
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/files/list/task-123",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(b'{"error": "Task not found"}')
        )
        mock_urlopen.side_effect = error
        result = list_files.list_files("http://localhost:8080", "test-key", "task-123")
        self.assertIn("404", result["error"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("list_files.list_files")
    @patch("list_files.load_config")
    def test_main_success(self, mock_load, mock_list):
        """测试 main 函数成功执行"""
        mock_load.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": "test-key"}},
            "default_server": "default"
        }
        mock_list.return_value = {"content": "成功", "data": {"files": []}}
        old_stdin = sys.stdin
        sys.stdin = StringIO(json.dumps({"task_id": "task-123"}))
        try:
            list_files.main()
            mock_list.assert_called_once()
        finally:
            sys.stdin = old_stdin

    def test_main_missing_task_id(self):
        """测试缺少 task_id"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    list_files.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)


if __name__ == "__main__":
    unittest.main()

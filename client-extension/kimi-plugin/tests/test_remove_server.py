#!/usr/bin/env python3
"""
Tests for remove_server.py - 移除服务器配置模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import remove_server


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = remove_server.load_config()
        self.assertIn("servers", config)


class TestRemoveServer(unittest.TestCase):
    """测试 remove_server 函数"""

    @patch("remove_server.save_config")
    @patch("remove_server.load_config")
    def test_remove_existing(self, mock_load, mock_save):
        """测试移除存在的服务器"""
        mock_load.return_value = {
            "servers": {"default": {}, "prod": {}},
            "default_server": "prod"
        }
        result = remove_server.remove_server("default")
        self.assertIn("content", result)
        self.assertEqual(result["data"]["removed"], "default")
        self.assertEqual(result["data"]["new_default"], "prod")

    @patch("remove_server.save_config")
    @patch("remove_server.load_config")
    def test_remove_default(self, mock_load, mock_save):
        """测试移除默认服务器后自动切换"""
        mock_load.return_value = {
            "servers": {"default": {}, "prod": {}},
            "default_server": "default"
        }
        result = remove_server.remove_server("default")
        self.assertEqual(result["data"]["new_default"], "prod")

    @patch("remove_server.save_config")
    @patch("remove_server.load_config")
    def test_remove_last_server(self, mock_load, mock_save):
        """测试移除最后一个服务器"""
        mock_load.return_value = {
            "servers": {"default": {}},
            "default_server": "default"
        }
        result = remove_server.remove_server("default")
        self.assertIsNone(result["data"]["new_default"])

    @patch("remove_server.load_config")
    def test_remove_nonexistent(self, mock_load):
        """测试移除不存在的服务器"""
        mock_load.return_value = {
            "servers": {"default": {}},
            "default_server": "default"
        }
        result = remove_server.remove_server("prod")
        self.assertIn("error", result)


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("remove_server.remove_server")
    def test_main_success(self, mock_remove):
        """测试 main 函数成功执行"""
        mock_remove.return_value = {"content": "已移除", "data": {"removed": "default"}}
        old_stdin = sys.stdin
        sys.stdin = StringIO(json.dumps({"server_name": "default"}))
        try:
            remove_server.main()
            mock_remove.assert_called_once_with("default")
        finally:
            sys.stdin = old_stdin

    def test_main_missing_server_name(self):
        """测试缺少 server_name"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    remove_server.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)


if __name__ == "__main__":
    unittest.main()

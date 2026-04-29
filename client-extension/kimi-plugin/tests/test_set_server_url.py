#!/usr/bin/env python3
"""
Tests for set_server_url.py - 设置服务器配置模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import set_server_url


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = set_server_url.load_config()
        self.assertEqual(config["server_url"], "http://test.com:8080")
        self.assertIn("servers", config)

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_config_not_found(self, mock_file):
        """测试配置文件不存在时使用默认值"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = set_server_url.load_config()
        self.assertEqual(config["default_server"], "default")
        self.assertIn("servers", config)


class TestSetServer(unittest.TestCase):
    """测试 set_server 函数"""

    @patch("set_server_url.save_config")
    @patch("set_server_url.load_config")
    def test_set_new_server(self, mock_load, mock_save):
        """测试添加新服务器"""
        mock_load.return_value = {
            "servers": {},
            "default_server": ""
        }
        result = set_server_url.set_server("prod", "http://prod.com:8080")
        self.assertIn("content", result)
        self.assertTrue(result["data"]["is_default"])
        mock_save.assert_called_once()

    @patch("set_server_url.save_config")
    @patch("set_server_url.load_config")
    def test_update_existing_server(self, mock_load, mock_save):
        """测试更新现有服务器"""
        mock_load.return_value = {
            "servers": {
                "default": {"server_url": "http://old.com:8080", "api_key": "old-key"}
            },
            "default_server": "default"
        }
        result = set_server_url.set_server("default", "http://new.com:8080")
        self.assertEqual(result["data"]["server_url"], "http://new.com:8080")

    @patch("set_server_url.save_config")
    @patch("set_server_url.load_config")
    def test_set_as_default(self, mock_load, mock_save):
        """测试设为默认服务器"""
        mock_load.return_value = {
            "servers": {"default": {}},
            "default_server": "default"
        }
        result = set_server_url.set_server("prod", "http://prod.com:8080", set_as_default=True)
        self.assertTrue(result["data"]["is_default"])

    @patch("set_server_url.save_config")
    @patch("set_server_url.load_config")
    def test_set_with_api_key(self, mock_load, mock_save):
        """测试设置时包含 api_key"""
        mock_load.return_value = {
            "servers": {},
            "default_server": ""
        }
        result = set_server_url.set_server("default", "http://localhost:8080", api_key="test-key", client_id="client-1")
        self.assertIn("content", result)


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("set_server_url.set_server")
    def test_main_success(self, mock_set):
        """测试 main 函数成功执行"""
        mock_set.return_value = {
            "content": "服务器配置已保存",
            "data": {"server_name": "default", "is_default": True}
        }
        old_stdin = sys.stdin
        sys.stdin = StringIO(json.dumps({"server_url": "http://localhost:8080"}))
        try:
            set_server_url.main()
            mock_set.assert_called_once()
        finally:
            sys.stdin = old_stdin

    def test_main_missing_server_url(self):
        """测试缺少 server_url"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    set_server_url.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)


if __name__ == "__main__":
    unittest.main()

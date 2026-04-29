#!/usr/bin/env python3
"""
Tests for list_servers.py - 列出服务器配置模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import list_servers


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = list_servers.load_config()
        self.assertIn("servers", config)


class TestListServers(unittest.TestCase):
    """测试 list_servers 函数"""

    @patch("list_servers.load_config")
    def test_list_servers_empty(self, mock_load):
        """测试空服务器列表"""
        mock_load.return_value = {"servers": {}, "default_server": ""}
        result = list_servers.list_servers()
        self.assertEqual(result["data"]["total"], 0)
        self.assertEqual(len(result["data"]["servers"]), 0)

    @patch("list_servers.load_config")
    def test_list_servers_with_data(self, mock_load):
        """测试有数据的服务器列表"""
        mock_load.return_value = {
            "servers": {
                "default": {"server_url": "http://localhost:8080", "api_key": "key1", "client_id": "c1"},
                "prod": {"server_url": "http://prod.com:8080", "api_key": "", "client_id": ""}
            },
            "default_server": "default"
        }
        result = list_servers.list_servers()
        self.assertEqual(len(result["data"]["servers"]), 2)
        default_server = [s for s in result["data"]["servers"] if s["is_default"]][0]
        self.assertEqual(default_server["name"], "default")
        self.assertTrue(default_server["has_api_key"])
        prod_server = [s for s in result["data"]["servers"] if s["name"] == "prod"][0]
        self.assertFalse(prod_server["has_api_key"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("list_servers.list_servers")
    def test_main_success(self, mock_list):
        """测试 main 函数成功执行"""
        mock_list.return_value = {
            "content": "共 1 个服务器配置",
            "data": {"default_server": "default", "servers": []}
        }
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            list_servers.main()
            output = json.loads(sys.stdout.getvalue())
            self.assertIn("content", output)
        finally:
            sys.stdout = old_stdout


if __name__ == "__main__":
    unittest.main()

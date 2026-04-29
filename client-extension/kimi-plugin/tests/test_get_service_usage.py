#!/usr/bin/env python3
"""
Tests for get_service_usage.py - 获取服务用法模块
""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import get_service_usage


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""

    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080", "api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置（旧格式兼容）"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = get_service_usage.load_config()
        self.assertEqual(config["api_key"], "test-key")
        self.assertIn("servers", config)


class TestGetServiceUsage(unittest.TestCase):
    """测试 get_service_usage 函数"""

    @patch("urllib.request.urlopen")
    def test_get_usage_success(self, mock_urlopen):
        """测试正常获取用法"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "service_id": "svc-1",
            "quota": 100,
            "used": 50
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = get_service_usage.get_service_usage("http://localhost:8080", "test-key", "svc-1")
        self.assertIn("content", result)
        self.assertIn("data", result)

    def test_get_usage_missing_api_key(self):
        """测试缺少 API Key"""
        result = get_service_usage.get_service_usage("http://localhost:8080", "", "svc-1")
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])

    def test_get_usage_missing_service_id(self):
        """测试缺少 service_id"""
        result = get_service_usage.get_service_usage("http://localhost:8080", "test-key", "")
        self.assertIn("error", result)
        self.assertIn("service_id", result["error"])

    @patch("urllib.request.urlopen")
    def test_get_usage_404(self, mock_urlopen):
        """测试服务不存在"""
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/services/svc-1/usage",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(b'{"error": "Service not found"}')
        )
        mock_urlopen.side_effect = error
        result = get_service_usage.get_service_usage("http://localhost:8080", "test-key", "svc-1")
        self.assertIn("404", result["error"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("get_service_usage.get_service_usage")
    @patch("get_service_usage.load_config")
    def test_main_success(self, mock_load, mock_get):
        """测试 main 函数成功执行"""
        mock_load.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": "test-key"}},
            "default_server": "default"
        }
        mock_get.return_value = {"content": "成功", "data": {}}
        old_stdin = sys.stdin
        sys.stdin = StringIO(json.dumps({"service_id": "svc-1"}))
        try:
            get_service_usage.main()
            mock_get.assert_called_once()
        finally:
            sys.stdin = old_stdin

    def test_main_missing_service_id(self):
        """测试缺少 service_id"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{}')):
                with self.assertRaises(SystemExit) as cm:
                    get_service_usage.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)


if __name__ == "__main__":
    unittest.main()

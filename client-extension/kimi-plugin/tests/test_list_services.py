#!/usr/bin/env python3
"""
Tests for list_services.py - 列出服务模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import list_services


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = list_services.load_config()
        self.assertEqual(config["api_key"], "test-key")
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_config_not_found(self, mock_file):
        """测试配置文件不存在"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = list_services.load_config()
        self.assertIn("error", config)


class TestListServices(unittest.TestCase):
    """测试 list_services 函数"""
    
    @patch("urllib.request.urlopen")
    def test_list_services_success_list_format(self, mock_urlopen):
        """测试正常调用返回列表格式"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {
                "id": "svc-1",
                "name": "Service 1",
                "description": "Test service 1",
                "usage": "How to use",
                "agent_status": "online"
            },
            {
                "id": "svc-2",
                "name": "Service 2",
                "description": "Test service 2"
            }
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = list_services.list_services("http://localhost:8080", "test-api-key")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["total"], 2)
        self.assertEqual(len(result["data"]["services"]), 2)
        self.assertEqual(result["data"]["services"][0]["id"], "svc-1")
        self.assertEqual(result["data"]["services"][1].get("agent_status"), "unknown")
    
    @patch("urllib.request.urlopen")
    def test_list_services_success_object_format(self, mock_urlopen):
        """测试正常调用返回对象格式（包含 services 字段）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "services": [
                {"id": "svc-1", "name": "Service 1"},
                {"id": "svc-2", "name": "Service 2"}
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = list_services.list_services("http://localhost:8080", "test-api-key")
        
        self.assertEqual(result["data"]["total"], 2)
        self.assertEqual(result["data"]["services"][0]["id"], "svc-1")
    
    def test_list_services_missing_api_key(self):
        """测试缺少 API Key"""
        result = list_services.list_services("http://localhost:8080", "")
        
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_list_services_auth_failure_401(self, mock_urlopen):
        """测试认证失败（401）"""
        error_body = b'{"error": "Invalid API key"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/services",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = list_services.list_services("http://localhost:8080", "invalid-key")
        
        self.assertIn("error", result)
        self.assertIn("认证失败 (401)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_list_services_not_found_404(self, mock_urlopen):
        """测试资源不存在（404）"""
        error_body = b'{"error": "Not found"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/services",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = list_services.list_services("http://localhost:8080", "valid-key")
        
        self.assertIn("error", result)
        self.assertIn("404", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_list_services_empty_list(self, mock_urlopen):
        """测试返回空服务列表"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = list_services.list_services("http://localhost:8080", "test-api-key")
        
        self.assertEqual(result["data"]["total"], 0)
        self.assertEqual(len(result["data"]["services"]), 0)
    
    @patch("urllib.request.urlopen")
    def test_list_services_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection timeout")
        
        result = list_services.list_services("http://localhost:8080", "test-api-key")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_list_services_json_parse_error(self, mock_urlopen):
        """测试 JSON 解析错误"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = list_services.list_services("http://localhost:8080", "test-api-key")
        
        self.assertIn("error", result)
        self.assertIn("JSON 解析错误", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_list_services_authorization_header(self, mock_urlopen):
        """测试 Authorization 请求头正确设置"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        list_services.list_services("http://localhost:8080", "my-api-key")
        
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        self.assertEqual(request.headers["Authorization"], "Bearer my-api-key")


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    @patch("list_services.list_services")
    @patch("list_services.load_config")
    def test_main_success(self, mock_load, mock_list):
        """测试 main 函数成功执行"""
        mock_load.return_value = {
            "server_url": "http://localhost:8080",
            "api_key": "test-key"
        }
        mock_list.return_value = {
            "content": "找到 2 个可用服务",
            "data": {
                "total": 2,
                "services": [
                    {"id": "svc-1", "name": "Service 1"},
                    {"id": "svc-2", "name": "Service 2"}
                ]
            }
        }
        
        # 模拟 stdin 输入（空输入）
        import sys
        from io import StringIO
        
        old_stdin = sys.stdin
        sys.stdin = StringIO('{}')
        
        try:
            list_services.main()
            mock_list.assert_called_once()
        finally:
            sys.stdin = old_stdin
    
    @patch("list_services.load_config")
    def test_main_config_error(self, mock_load):
        """测试 main 函数配置加载错误"""
        mock_load.return_value = {"error": "无法读取 config.json"}
        
        import sys
        from io import StringIO
        
        old_stdin = sys.stdin
        sys.stdin = StringIO('{}')
        
        try:
            with self.assertRaises(SystemExit) as cm:
                list_services.main()
            self.assertEqual(cm.exception.code, 1)
        finally:
            sys.stdin = old_stdin


if __name__ == "__main__":
    unittest.main()

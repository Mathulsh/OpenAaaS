#!/usr/bin/env python3
"""
Tests for register.py - 客户端注册模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import register


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = register.load_config()
        self.assertEqual(config["server_url"], "http://test.com:8080")
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_config_not_found(self, mock_file):
        """测试配置文件不存在时使用默认值"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = register.load_config()
        self.assertEqual(config["server_url"], "http://localhost:8080")


class TestSaveConfig(unittest.TestCase):
    """测试 save_config 函数"""
    
    @patch("builtins.open", mock_open())
    @patch("json.dump")
    @patch("os.path.join")
    def test_save_config_success(self, mock_join, mock_json_dump):
        """测试正常保存配置"""
        mock_join.return_value = "/fake/config.json"
        result = register.save_config({"api_key": "test123"})
        self.assertTrue(result)
    
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_save_config_failure(self, mock_file):
        """测试保存配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            result = register.save_config({"api_key": "test123"})
        self.assertFalse(result)


class TestRegister(unittest.TestCase):
    """测试 register 函数"""

    def test_register_empty_server_url(self):
        """测试空 server_url 拒绝注册"""
        result = register.register("", "test-client")

        self.assertIn("error", result)
        self.assertIn("缺少服务端地址", result["error"])

    @patch("register.load_config")
    def test_register_duplicate(self, mock_load_config):
        """测试重复注册提示"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": "existing-key"}},
            "default_server": "default"
        }

        result = register.register("http://localhost:8080", "test-client")

        self.assertIn("error", result)
        self.assertIn("set_server_url", result["error"])

    @patch("register.save_config")
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_success(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试正常注册成功"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        # mock_urlopen 对应 urllib.request.urlopen (最内层)
        # mock_load_config 对应 register.load_config (中间层)
        # mock_save_config 对应 register.save_config (最外层)
        mock_load_config.return_value = {"server_url": "http://localhost:8080"}
        mock_save_config.return_value = True
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "api_key": "test-api-key-123",
            "client_id": "client-456",
            "name": "test-client"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["client_id"], "client-456")
        self.assertEqual(result["data"]["api_key"], "test-api-key-123")
        self.assertTrue(result["data"]["saved_to_config"])
        mock_save_config.assert_called_once()
    
    @patch("register.save_config")
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_success_token_field(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试注册成功但使用 token 字段而非 api_key"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        mock_load_config.return_value = {"server_url": "http://localhost:8080"}
        mock_save_config.return_value = True
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "token": "test-token-789",
            "id": "client-999"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertEqual(result["data"]["api_key"], "test-token-789")
        self.assertEqual(result["data"]["client_id"], "client-999")
    
    @patch("register.save_config")
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_no_api_key(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试注册成功但没有返回 api_key"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        mock_load_config.return_value = {"server_url": "http://localhost:8080"}
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "client_id": "client-456"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIsNone(result["data"]["api_key"])
        self.assertFalse(result["data"]["saved_to_config"])
        mock_save_config.assert_not_called()
    
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_username_exists(self, mock_urlopen, mock_load_config):
        """测试用户名已存在（409 错误）"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        error_body = b'{"error": "Client name already exists"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/auth/register",
            code=409,
            msg="Conflict",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = register.register("http://localhost:8080", "existing-client")
        
        self.assertIn("error", result)
        self.assertIn("409", result["error"])
    
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_http_error_with_json(self, mock_urlopen, mock_load_config):
        """测试 HTTP 错误返回 JSON 错误信息"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        error_body = b'{"message": "Invalid request data"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/auth/register",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIn("error", result)
        self.assertIn("Invalid request data", result["error"])
    
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_http_error_plain_text(self, mock_urlopen, mock_load_config):
        """测试 HTTP 错误返回纯文本错误信息"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        error_body = b'Server Error'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/auth/register",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIn("error", result)
        self.assertIn("Server Error", result["error"])
    
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_network_error(self, mock_urlopen, mock_load_config):
        """测试网络错误"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
        self.assertIn("Network unreachable", result["error"])
    
    def test_register_empty_name(self):
        """测试空名称返回错误"""
        result = register.register("http://localhost:8080", "")
        
        self.assertIn("error", result)
        self.assertIn("缺少必填参数", result["error"])
    
    @patch("register.load_config")
    @patch("urllib.request.urlopen")
    def test_register_json_parse_error(self, mock_urlopen, mock_load_config):
        """测试 JSON 解析错误"""
        mock_load_config.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = register.register("http://localhost:8080", "test-client")
        
        self.assertIn("error", result)
        self.assertIn("JSON 解析错误", result["error"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""

    @patch("register.register")
    @patch("register.save_config")
    @patch("register.load_config")
    def test_main_with_name(self, mock_load, mock_save, mock_register):
        """测试 main 函数带 name 参数"""
        mock_load.return_value = {
            "servers": {"default": {"server_url": "http://localhost:8080", "api_key": ""}},
            "default_server": "default"
        }
        mock_register.return_value = {
            "client_id": "test-id",
            "api_key": "test-key",
            "name": "test-client"
        }

        # 模拟 stdin 输入
        import sys
        from io import StringIO

        test_input = json.dumps({"name": "test-client"})
        old_stdin = sys.stdin
        sys.stdin = StringIO(test_input)

        try:
            register.main()
            mock_register.assert_called_once()
        finally:
            sys.stdin = old_stdin


if __name__ == "__main__":
    unittest.main()

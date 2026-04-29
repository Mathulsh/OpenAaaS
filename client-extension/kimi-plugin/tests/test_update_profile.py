#!/usr/bin/env python3
"""
Tests for update_profile.py - 修改用户名模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO, BytesIO
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_profile


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"api_key": "test-key"}'))
    def test_load_config_success(self):
        """测试正常加载配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = update_profile.load_config()
        self.assertEqual(config["api_key"], "test-key")
    
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_load_config_error(self, mock_file):
        """测试加载配置失败返回错误信息"""
        with patch("os.path.join", return_value="/fake/config.json"):
            config = update_profile.load_config()
        self.assertIn("error", config)


class TestSaveConfig(unittest.TestCase):
    """测试 save_config 函数"""
    
    @patch("builtins.open", mock_open())
    @patch("json.dump")
    def test_save_config_success(self, mock_json_dump):
        """测试正常保存配置"""
        with patch("os.path.join", return_value="/fake/config.json"):
            result = update_profile.save_config({"name": "new-name"})
        self.assertTrue(result)
    
    @patch("builtins.open", side_effect=IOError("Disk full"))
    def test_save_config_failure(self, mock_file):
        """测试保存配置失败"""
        with patch("os.path.join", return_value="/fake/config.json"):
            result = update_profile.save_config({"name": "new-name"})
        self.assertFalse(result)


class TestUpdateProfile(unittest.TestCase):
    """测试 update_profile 函数"""
    
    @patch("update_profile.save_config")
    @patch("update_profile.load_config")
    @patch("urllib.request.urlopen")
    def test_update_success(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试正常更新用户名成功"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        # mock_urlopen 对应 urllib.request.urlopen (最内层)
        # mock_load_config 对应 update_profile.load_config (中间层)
        # mock_save_config 对应 update_profile.save_config (最外层)
        mock_load_config.return_value = {"api_key": "test-key"}
        mock_save_config.return_value = True
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "client_id": "client-123",
            "name": "new-username"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = update_profile.update_profile("http://localhost:8080", "test-key", "new-username")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["name"], "new-username")
        self.assertEqual(result["data"]["client_id"], "client-123")
        self.assertTrue(result["data"]["saved_to_config"])
        mock_save_config.assert_called_once()
    
    @patch("update_profile.save_config")
    @patch("update_profile.load_config")
    @patch("urllib.request.urlopen")
    def test_update_with_id_field(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试更新成功使用 id 字段而非 client_id"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        mock_load_config.return_value = {"api_key": "test-key"}
        mock_save_config.return_value = True
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "client-999",
            "name": "updated-name"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = update_profile.update_profile("http://localhost:8080", "test-key", "updated-name")
        
        self.assertEqual(result["data"]["client_id"], "client-999")
    
    def test_update_missing_api_key(self):
        """测试缺少 API Key"""
        result = update_profile.update_profile("http://localhost:8080", "", "new-name")
        
        self.assertIn("error", result)
        self.assertIn("缺少 API Key", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_update_auth_failure_401(self, mock_urlopen):
        """测试认证失败（401）"""
        error_body = b'{"error": "Unauthorized"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/profile",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = update_profile.update_profile("http://localhost:8080", "invalid-key", "new-name")
        
        self.assertIn("error", result)
        self.assertIn("认证失败 (401)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_update_username_exists_409(self, mock_urlopen):
        """测试用户名已存在（409）"""
        error_body = b'{"error": "Name already taken"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/profile",
            code=409,
            msg="Conflict",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = update_profile.update_profile("http://localhost:8080", "valid-key", "taken-name")
        
        self.assertIn("error", result)
        self.assertIn("用户名已存在 (409)", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_update_other_http_error(self, mock_urlopen):
        """测试其他 HTTP 错误"""
        error_body = b'{"message": "Server error"}'
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/client/profile",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(error_body)
        )
        mock_urlopen.side_effect = error
        
        result = update_profile.update_profile("http://localhost:8080", "valid-key", "new-name")
        
        self.assertIn("error", result)
        self.assertIn("HTTP 500", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_update_network_error(self, mock_urlopen):
        """测试网络错误"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        result = update_profile.update_profile("http://localhost:8080", "valid-key", "new-name")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
    
    @patch("urllib.request.urlopen")
    def test_update_json_parse_error(self, mock_urlopen):
        """测试 JSON 解析错误"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = update_profile.update_profile("http://localhost:8080", "valid-key", "new-name")
        
        self.assertIn("error", result)
        self.assertIn("JSON 解析错误", result["error"])
    
    @patch("update_profile.save_config")
    @patch("update_profile.load_config")
    @patch("urllib.request.urlopen")
    def test_update_save_config_failure(self, mock_urlopen, mock_load_config, mock_save_config):
        """测试更新成功但加载配置失败（导致无法保存）"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        # 设置 load_config 返回一个包含 error 的配置对象（模拟读取失败）
        mock_load_config.return_value = {"error": "无法读取 config.json", "api_key": "test-key"}
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "client_id": "client-123",
            "name": "new-name"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = update_profile.update_profile("http://localhost:8080", "test-key", "new-name")
        
        # 由于 load_config 返回 error，save_config 不应被调用
        mock_save_config.assert_not_called()
        # 检查 saved_to_config 为 False
        self.assertFalse(result["data"]["saved_to_config"])


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    def test_main_empty_name(self):
        """测试空用户名"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('{"name": ""}')):
                with self.assertRaises(SystemExit) as cm:
                    update_profile.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("name 不能为空", output["error"])
    
    def test_main_name_too_long(self):
        """测试用户名过长"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            long_name = "a" * 65
            with patch("sys.stdin", StringIO(json.dumps({"name": long_name}))):
                with self.assertRaises(SystemExit) as cm:
                    update_profile.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("长度不能超过64字符", output["error"])

    def test_main_invalid_characters(self):
        """测试用户名包含非法特殊字符"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO(json.dumps({"name": "test/name"}))):
                with self.assertRaises(SystemExit) as cm:
                    update_profile.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("非法特殊字符", output["error"])

    def test_main_unicode_control_char(self):
        """测试用户名包含 Unicode 控制字符"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO(json.dumps({"name": "test\u200bname"}))):
                with self.assertRaises(SystemExit) as cm:
                    update_profile.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("Unicode 控制字符", output["error"])

    @patch("update_profile.load_config")
    def test_main_no_valid_server(self, mock_load_config):
        """测试没有有效服务器配置"""
        mock_load_config.return_value = {
            "servers": {},
            "default_server": "default"
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO(json.dumps({"name": "test"}))):
                with self.assertRaises(SystemExit) as cm:
                    update_profile.main()
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("set_server_url", output["error"])


if __name__ == "__main__":
    unittest.main()

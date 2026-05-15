#!/usr/bin/env python3
"""
Tests for discover.py - 服务端发现模块
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
from io import StringIO
import urllib.error

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加当前目录到路径以导入 helpers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover
from helpers import create_mock_response, create_mock_http_error


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数"""
    
    @patch("builtins.open", mock_open(read_data='{"server_url": "http://test.com:8080"}'))
    @patch("os.path.join")
    def test_load_config_success(self, mock_join):
        """测试正常加载配置"""
        # 注意：mock_open 直接传入装饰器，不作为参数
        # mock_join 对应 os.path.join
        mock_join.return_value = "/fake/config.json"
        config = discover.load_config()
        self.assertEqual(config["server_url"], "http://test.com:8080")
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    @patch("os.path.join")
    def test_load_config_not_found(self, mock_join, mock_file):
        """测试配置文件不存在时使用默认值"""
        # 注意：装饰器从内到外应用，参数顺序从外到内
        # mock_join 对应 os.path.join (内层)
        # mock_file 对应 builtins.open (外层)
        mock_join.return_value = "/fake/config.json"
        config = discover.load_config()
        self.assertEqual(config["server_url"], "https://api.open-aaas.com")


class TestDiscover(unittest.TestCase):
    """测试 discover 函数"""
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_success(self, mock_urlopen):
        """测试正常发现成功"""
        mock_response = create_mock_response(200, json_data={
            "version": "1.0.0",
            "endpoints": ["/api/v1/discovery"]
        })
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("content", result)
        self.assertIn("data", result)
        self.assertEqual(result["data"]["version"], "1.0.0")
        self.assertIn("1.0.0", result["content"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_no_version(self, mock_urlopen):
        """测试返回结果中没有 version 字段"""
        mock_response = create_mock_response(200, json_data={
            "endpoints": ["/api/v1/discovery"]
        })
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("unknown", result["content"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_url_trailing_slash(self, mock_urlopen):
        """测试 URL 末尾带斜杠的处理"""
        mock_response = create_mock_response(200, json_data={"version": "1.0.0"})
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = discover.discover("http://localhost:8080/")
        
        # 验证尾斜杠被正确移除，请求发送到正确的 URL
        call_args = mock_urlopen.call_args
        req = call_args[0][0]  # 第一个位置参数是 Request 对象
        self.assertEqual(req.full_url, "http://localhost:8080/api/v1/discovery")
        self.assertIn("content", result)
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_connection_refused(self, mock_urlopen):
        """测试连接失败处理"""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)
        self.assertIn("连接失败", result["error"])
        self.assertIn("Connection refused", result["error"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_http_403(self, mock_urlopen):
        """测试 HTTP 403 错误处理"""
        mock_urlopen.side_effect = create_mock_http_error(403, "Forbidden")
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)
        self.assertIn("权限不足 (403)", result["error"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_http_404(self, mock_urlopen):
        """测试 HTTP 404 错误处理"""
        mock_urlopen.side_effect = create_mock_http_error(404, "Not Found")
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)
        self.assertIn("HTTP 错误 404", result["error"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_http_500(self, mock_urlopen):
        """测试 HTTP 500 错误处理"""
        mock_urlopen.side_effect = create_mock_http_error(500, "Internal Server Error")
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)
        self.assertIn("HTTP 错误 500", result["error"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_json_parse_error(self, mock_urlopen):
        """测试 JSON 解析错误处理"""
        mock_response = create_mock_response(200, text_data="invalid json {")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)
        self.assertIn("JSON 解析错误", result["error"])
    
    @patch("utils._no_redirect_opener.open")
    def test_discover_timeout(self, mock_urlopen):
        """测试超时错误处理"""
        mock_urlopen.side_effect = TimeoutError("Request timed out")
        
        result = discover.discover("http://localhost:8080")
        
        self.assertIn("error", result)


class TestMain(unittest.TestCase):
    """测试 main 函数"""
    
    def test_main_invalid_json(self):
        """测试主函数处理无效 JSON 输入"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stdin", StringIO('invalid json')):
                with self.assertRaises(SystemExit) as cm:
                    discover.main()
            
            self.assertEqual(cm.exception.code, 1)
            output = json.loads(mock_stdout.getvalue())
            self.assertIn("error", output)
            self.assertIn("JSON 解析错误", output["error"])


if __name__ == "__main__":
    unittest.main()

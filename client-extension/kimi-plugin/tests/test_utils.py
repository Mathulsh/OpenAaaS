#!/usr/bin/env python3
"""
Tests for utils.py - 配置管理与 HTTP 请求工具
"""

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

import utils


class TestLoadConfig:
    """测试 load_config 函数"""

    def test_load_config_success(self, tmp_path, monkeypatch):
        """测试正常加载配置"""
        config_file = tmp_path / "config.json"
        config_data = {
            "server_url": "http://test.com:8080",
            "api_key": "test_key",
            "servers": {
                "default": {
                    "server_url": "http://test.com:8080",
                    "api_key": "test_key",
                    "client_id": "",
                }
            },
            "default_server": "default",
        }
        config_file.write_text(json.dumps(config_data), encoding="utf-8")
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = utils.load_config()
        assert config["server_url"] == "http://test.com:8080"
        assert config["api_key"] == "test_key"

    def test_load_config_file_not_found(self, tmp_path, monkeypatch):
        """测试文件不存在时返回默认值"""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = utils.load_config()
        assert config["server_url"] == "https://api.open-aaas.com"
        assert config["api_key"] == ""
        assert "error" in config
        assert "无法读取 config.json" in config["error"]

    def test_load_config_invalid_format(self, tmp_path, monkeypatch):
        """测试配置不是字典时返回默认值"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = utils.load_config()
        assert config["server_url"] == "https://api.open-aaas.com"
        assert "error" in config
        assert "格式错误" in config["error"]

    def test_load_config_old_format_migration(self, tmp_path, monkeypatch):
        """测试旧格式自动迁移"""
        config_file = tmp_path / "config.json"
        old_config = {
            "server_url": "http://old.com:8080",
            "api_key": "old_key",
            "client_id": "old_client",
        }
        config_file.write_text(json.dumps(old_config), encoding="utf-8")
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = utils.load_config()
        assert config["servers"]["default"]["server_url"] == "http://old.com:8080"
        assert config["servers"]["default"]["api_key"] == "old_key"
        assert config["default_server"] == "default"

    def test_load_config_json_decode_error(self, tmp_path, monkeypatch):
        """测试 JSON 解析错误"""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = utils.load_config()
        assert config["server_url"] == "https://api.open-aaas.com"
        assert "error" in config


class TestSaveConfig:
    """测试 save_config 函数"""

    def test_save_config_success(self, tmp_path, monkeypatch):
        """测试正常保存配置"""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr(utils, "__file__", str(config_file))

        config = {"server_url": "http://test.com"}
        result = utils.save_config(config)
        assert result is True
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["server_url"] == "http://test.com"

    def test_save_config_failure(self, tmp_path, monkeypatch):
        """测试保存失败返回 False"""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr(utils, "__file__", str(config_file))

        # 模拟无写入权限目录
        monkeypatch.setattr(utils.os.path, "join", lambda *args: "/dev/null/config.json")
        config = {"server_url": "http://test.com"}
        result = utils.save_config(config)
        assert result is False


class TestSafeRequest:
    """测试 safe_request 函数"""

    def _make_mock_response(self, status_code, body_bytes):
        mock_response = MagicMock()
        mock_response.getcode.return_value = status_code
        mock_response.read.return_value = body_bytes
        mock_response.headers = {}
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        return mock_response

    def test_get_success(self, monkeypatch):
        """测试 GET 请求成功"""
        mock_response = self._make_mock_response(
            200, json.dumps({"data": "ok"}).encode("utf-8")
        )
        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, data, status = utils.safe_request("http://example.com/api")
        assert success is True
        assert data == {"data": "ok"}
        assert status == 200

    def test_post_success(self, monkeypatch):
        """测试 POST 请求成功"""
        mock_response = self._make_mock_response(
            201, json.dumps({"id": "123"}).encode("utf-8")
        )
        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, data, status = utils.safe_request(
            "http://example.com/api",
            data=b'{"key":"value"}',
            method="POST",
        )
        assert success is True
        assert data == {"id": "123"}
        assert status == 201

    def test_http_4xx_error(self, monkeypatch):
        """测试 HTTP 4xx 错误"""
        error = urllib.error.HTTPError(
            url="http://example.com/api",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(json.dumps({"error": "not found"}).encode("utf-8")),
        )
        mock_opener = MagicMock()
        mock_opener.open.side_effect = error
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, msg, status = utils.safe_request("http://example.com/api")
        assert success is False
        assert msg == "not found"
        assert status == 404

    def test_http_5xx_error(self, monkeypatch):
        """测试 HTTP 5xx 错误"""
        error = urllib.error.HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Error",
            hdrs={},
            fp=BytesIO(b"server error"),
        )
        mock_opener = MagicMock()
        mock_opener.open.side_effect = error
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, msg, status = utils.safe_request("http://example.com/api")
        assert success is False
        assert "server error" in msg
        assert status == 500

    def test_redirect_handling(self, monkeypatch):
        """测试重定向处理"""
        redirect_response = self._make_mock_response(302, b"")
        redirect_response.headers = {"Location": "http://example.com/new"}

        final_response = self._make_mock_response(
            200, json.dumps({"result": "ok"}).encode("utf-8")
        )
        final_response.headers = {}

        mock_opener = MagicMock()
        mock_opener.open.side_effect = [redirect_response, final_response]
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, data, status = utils.safe_request("http://example.com/api")
        assert success is True
        assert data == {"result": "ok"}
        assert status == 200

    def test_redirect_exceeded(self, monkeypatch):
        """测试重定向次数超限"""
        redirect_response = self._make_mock_response(302, b"")
        redirect_response.headers = {"Location": "http://example.com/new"}

        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = redirect_response
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, msg, status = utils.safe_request(
            "http://example.com/api", max_redirects=1
        )
        assert success is False
        assert "重定向" in msg
        assert status == 302

    def test_json_parse_error(self, monkeypatch):
        """测试 JSON 解析错误"""
        mock_response = self._make_mock_response(200, b"not json")
        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, msg, status = utils.safe_request("http://example.com/api")
        assert success is False
        assert "JSON 解析错误" in msg
        assert status is None

    def test_network_error(self, monkeypatch):
        """测试网络错误"""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("Connection refused")
        monkeypatch.setattr(utils, "_no_redirect_opener", mock_opener)

        success, msg, status = utils.safe_request("http://example.com/api")
        assert success is False
        assert "连接失败" in msg
        assert status is None

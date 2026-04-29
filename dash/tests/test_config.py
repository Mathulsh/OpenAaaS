"""Tests for configuration module."""

import os
from pathlib import Path

import pytest
import toml

from aaas_dashboard.config import Config, get_config, DEFAULT_CONFIG_FILE


class TestConfigDefaults:
    """Test configuration default values."""

    def test_config_defaults(self):
        """Test that Config has correct default values."""
        config = Config()
        
        assert config.server_url == "http://localhost:8080"
        assert config.api_key is None
        assert config.refresh_interval == 5


class TestConfigFromFile:
    """Test loading configuration from file."""

    def test_config_from_file(self, temp_config_file):
        """Test loading configuration from config file."""
        config = Config.from_config_file(temp_config_file)
        
        assert config.server_url == "http://config-file-server:9000"
        assert config.refresh_interval == 10
        assert config.api_key is None

    def test_config_from_file_with_api_key(self, temp_config_with_api_key):
        """Test loading configuration with API key from separate file."""
        config = Config.from_config_file(temp_config_with_api_key)
        
        assert config.server_url == "http://config-file-server:9000"
        assert config.refresh_interval == 10
        assert config.api_key == "ak_from_file_123"

    def test_config_from_nonexistent_file(self, tmp_path):
        """Test loading from non-existent file returns defaults."""
        nonexistent = tmp_path / "nonexistent.toml"
        config = Config.from_config_file(nonexistent)
        
        assert config.server_url == "http://localhost:8080"
        assert config.refresh_interval == 5
        assert config.api_key is None

    def test_config_from_invalid_file(self, tmp_path):
        """Test loading from invalid file returns defaults."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text("not valid toml [[[")
        
        config = Config.from_config_file(invalid_file)
        
        assert config.server_url == "http://localhost:8080"
        assert config.refresh_interval == 5


class TestConfigFromEnv:
    """Test loading configuration from environment variables."""

    def test_config_from_env(self, clean_env):
        """Test loading configuration from environment variables."""
        os.environ["OAAS_SERVER_URL"] = "http://env-server:8000"
        os.environ["OAAS_API_KEY"] = "ak_env_key"
        os.environ["OAAS_REFRESH_INTERVAL"] = "15"
        
        config = Config.load()
        
        assert config.server_url == "http://env-server:8000"
        assert config.api_key == "ak_env_key"
        assert config.refresh_interval == 15

    def test_config_partial_env(self, clean_env):
        """Test that partial environment variables are loaded."""
        os.environ["OAAS_SERVER_URL"] = "http://partial-env:8000"
        # OAAS_API_KEY and OAAS_REFRESH_INTERVAL not set
        
        config = Config.load()
        
        assert config.server_url == "http://partial-env:8000"
        assert config.api_key is None
        assert config.refresh_interval == 5  # default


class TestConfigPriority:
    """Test configuration loading priority."""

    def test_config_priority_defaults_only(self):
        """Test that defaults are used when nothing else is set."""
        config = Config.load()
        
        assert config.server_url == "http://localhost:8080"
        assert config.api_key is None
        assert config.refresh_interval == 5

    def test_config_priority_file_over_defaults(self, temp_config_file):
        """Test that file values override defaults."""
        config = Config.load(config_path=temp_config_file)
        
        assert config.server_url == "http://config-file-server:9000"
        assert config.refresh_interval == 10

    def test_config_priority_env_over_file(self, temp_config_file, clean_env):
        """Test that environment variables override file values."""
        os.environ["OAAS_SERVER_URL"] = "http://env-server:8000"
        os.environ["OAAS_API_KEY"] = "ak_env_key"
        
        config = Config.load(config_path=temp_config_file)
        
        assert config.server_url == "http://env-server:8000"
        assert config.api_key == "ak_env_key"
        assert config.refresh_interval == 10  # from file

    def test_config_priority_cli_over_env(self, clean_env):
        """Test that CLI arguments override environment variables."""
        os.environ["OAAS_SERVER_URL"] = "http://env-server:8000"
        os.environ["OAAS_API_KEY"] = "ak_env_key"
        
        config = Config.load(
            server_url="http://cli-server:7000",
            api_key="ak_cli_key"
        )
        
        assert config.server_url == "http://cli-server:7000"
        assert config.api_key == "ak_cli_key"

    def test_config_priority_full_chain(self, temp_config_file, clean_env):
        """Test full priority chain: CLI > ENV > File > Defaults."""
        # Set environment variables
        os.environ["OAAS_SERVER_URL"] = "http://env-server:8000"
        os.environ["OAAS_API_KEY"] = "ak_env_key"
        os.environ["OAAS_REFRESH_INTERVAL"] = "20"
        
        # Load with CLI override for server_url
        config = Config.load(
            server_url="http://cli-server:7000",
            config_path=temp_config_file
        )
        
        # CLI overrides ENV for server_url
        assert config.server_url == "http://cli-server:7000"
        # ENV overrides File for api_key
        assert config.api_key == "ak_env_key"
        # ENV overrides File for refresh_interval
        assert config.refresh_interval == 20


class TestConfigSave:
    """Test saving configuration to file."""

    def test_save_to_file(self, tmp_path):
        """Test saving configuration to file."""
        config = Config(
            server_url="http://saved-server:8080",
            api_key="ak_saved_key",
            refresh_interval=30
        )
        
        config_file = tmp_path / "test_config.toml"
        config.save_to_file(config_file)
        
        # Verify file was created
        assert config_file.exists()
        
        # Verify content (API key should NOT be in config file)
        saved_data = toml.load(config_file)
        assert saved_data["server_url"] == "http://saved-server:8080"
        assert saved_data["refresh_interval"] == 30
        assert "api_key" not in saved_data
        
        # Verify API key is in separate file
        api_key_file = config_file.parent / ".api_key"
        assert api_key_file.exists()
        assert api_key_file.read_text().strip() == "ak_saved_key"


class TestGetConfig:
    """Test the get_config convenience function."""

    def test_get_config_with_string_path(self, temp_config_file):
        """Test get_config with string path."""
        config = get_config(config_path=str(temp_config_file))
        
        assert config.server_url == "http://config-file-server:9000"

    def test_get_config_with_no_path(self):
        """Test get_config without path uses defaults."""
        config = get_config()
        
        assert config.server_url == "http://localhost:8080"

    def test_get_config_with_overrides(self, temp_config_file):
        """Test get_config with command line overrides."""
        config = get_config(
            server_url="http://override:7000",
            config_path=str(temp_config_file)
        )
        
        assert config.server_url == "http://override:7000"

"""Configuration management for OpenAaaS Dashboard."""

import os
from pathlib import Path
from typing import Optional

import toml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "aaas-dashboard"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"


class Config(BaseSettings):
    """Configuration for OpenAaaS Dashboard.
    
    Configuration priority (highest to lowest):
    1. Command line arguments
    2. Environment variables (OAAS_SERVER_URL, OAAS_API_KEY)
    3. Config file (~/.config/aaas-dashboard/config.toml)
    """
    
    model_config = SettingsConfigDict(
        env_prefix="OAAS_",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    server_url: str = Field(
        default="http://localhost:8080",
        description="OpenAaaS server URL",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication",
    )
    refresh_interval: int = Field(
        default=5,
        description="Auto-refresh interval in seconds",
    )
    
    @classmethod
    def from_config_file(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from config file.
        
        Args:
            config_path: Path to config file. Defaults to ~/.config/aaas-dashboard/config.toml
            
        Returns:
            Config instance with values from file
        """
        if config_path is None:
            config_path = DEFAULT_CONFIG_FILE
            
        if not config_path.exists():
            return cls()
            
        try:
            config_data = toml.load(config_path)
            # Map config file keys to model fields
            mapping = {
                "server_url": config_data.get("server_url"),
                "refresh_interval": config_data.get("refresh_interval"),
            }
            # Filter out None values
            mapping = {k: v for k, v in mapping.items() if v is not None}
            
            # 从单独文件读取 API Key（如果存在）
            api_key_file = config_path.parent / ".api_key"
            if api_key_file.exists():
                mapping["api_key"] = api_key_file.read_text().strip()
            
            return cls(**mapping)
        except Exception:
            return cls()
    
    @classmethod
    def load(
        cls,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> "Config":
        """Load configuration with priority resolution.
        
        Priority (highest to lowest):
        1. Command line arguments (server_url, api_key)
        2. Environment variables
        3. Config file
        4. Default values
        
        Args:
            server_url: Server URL from command line
            api_key: API key from command line
            config_path: Path to config file
            
        Returns:
            Config instance with resolved values
        """
        # Start with config file
        config = cls.from_config_file(config_path)
        
        # 2. 检查环境变量并覆盖
        if "OAAS_SERVER_URL" in os.environ:
            config.server_url = os.environ["OAAS_SERVER_URL"]
        if "OAAS_API_KEY" in os.environ:
            config.api_key = os.environ["OAAS_API_KEY"]
        if "OAAS_REFRESH_INTERVAL" in os.environ:
            config.refresh_interval = int(os.environ["OAAS_REFRESH_INTERVAL"])
        
        # Override with command line arguments (highest priority)
        if server_url is not None:
            config.server_url = server_url
        if api_key is not None:
            config.api_key = api_key
            
        return config
    
    def ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def save_to_file(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to file with secure permissions."""
        if config_path is None:
            config_path = DEFAULT_CONFIG_FILE
            
        self.ensure_config_dir()
        
        # 分离敏感数据：API Key 不存入配置文件
        config_data = {
            "server_url": self.server_url,
            "refresh_interval": self.refresh_interval,
        }
        
        with open(config_path, "w") as f:
            toml.dump(config_data, f)
        
        # 设置严格文件权限 (Unix/Linux/macOS)
        import stat
        config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        
        # API Key 单独存储（如果存在）
        if self.api_key:
            api_key_file = config_path.parent / ".api_key"
            api_key_file.write_text(self.api_key)
            api_key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        else:
            api_key_file = config_path.parent / ".api_key"
            if api_key_file.exists():
                api_key_file.unlink()


def get_config(
    server_url: Optional[str] = None,
    api_key: Optional[str] = None,
    config_path: Optional[str] = None,
) -> Config:
    """Get configuration with priority resolution.
    
    This is a convenience function for loading configuration.
    
    Args:
        server_url: Server URL from command line
        api_key: API key from command line
        config_path: Path to config file as string
        
    Returns:
        Config instance with resolved values
    """
    path = Path(config_path) if config_path else None
    return Config.load(server_url, api_key, path)

"""Shared fixtures for tests."""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import responses

from aaas_dashboard.client import OaaSClient, MockOaaSClient, TaskStatus, Task
from aaas_dashboard.config import Config, DEFAULT_CONFIG_FILE


@pytest.fixture
def mock_server_url():
    """Return a mock server URL."""
    return "http://localhost:8080"


@pytest.fixture
def mock_api_key():
    """Return a mock API key."""
    return "ak_test_key_12345"


@pytest.fixture
def client(mock_server_url, mock_api_key):
    """Create a real OaaSClient instance for testing."""
    return OaaSClient(server_url=mock_server_url, api_key=mock_api_key)


@pytest.fixture
def mock_client():
    """Create a MockOaaSClient instance for testing."""
    return MockOaaSClient()


@pytest.fixture
def sample_task_data():
    """Return sample task data for creating Task objects."""
    return {
        "id": "task-test-001",
        "service_id": "code-agent",
        "status": "running",
        "session_id": "session-001",
        "retry_count": 0,
        "created_at": "2024-01-15T10:30:00Z",
        "assigned_at": "2024-01-15T10:30:05Z",
        "started_at": "2024-01-15T10:30:10Z",
        "input": {
            "task_prompt": "Test task prompt",
            "output_prompt": "Test output format",
        },
        "output": None,
        "error_message": None,
    }


@pytest.fixture
def sample_completed_task_data():
    """Return sample completed task data."""
    return {
        "id": "task-test-002",
        "service_id": "data-agent",
        "status": "completed",
        "session_id": "session-002",
        "retry_count": 0,
        "created_at": "2024-01-15T09:00:00Z",
        "assigned_at": "2024-01-15T09:00:05Z",
        "started_at": "2024-01-15T09:00:10Z",
        "completed_at": "2024-01-15T09:05:30Z",
        "input": {
            "task_prompt": "This is a very long task prompt that should be truncated in the name property " * 3,
        },
        "output": {"result": "Task completed successfully"},
        "error_message": None,
    }


@pytest.fixture
def sample_failed_task_data():
    """Return sample failed task data."""
    return {
        "id": "task-test-003",
        "service_id": "analysis-agent",
        "status": "failed",
        "session_id": "session-003",
        "retry_count": 1,
        "created_at": "2024-01-15T08:00:00Z",
        "assigned_at": "2024-01-15T08:00:05Z",
        "started_at": "2024-01-15T08:00:10Z",
        "completed_at": "2024-01-15T08:02:00Z",
        "input": {"task_prompt": "Analysis task"},
        "output": None,
        "error_message": "Connection timeout",
    }


@pytest.fixture
def activated_responses():
    """Activate responses mock for HTTP requests."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clean environment variables before each test."""
    # Store original values
    env_vars = ["OAAS_SERVER_URL", "OAAS_API_KEY", "OAAS_REFRESH_INTERVAL"]
    original = {var: os.environ.get(var) for var in env_vars}
    
    # Clear environment variables
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]
    
    # Prevent reading user's actual config file
    monkeypatch.setattr(
        "aaas_dashboard.config.DEFAULT_CONFIG_FILE",
        Path("/nonexistent/aaas-dashboard/config.toml")
    )
    
    yield
    
    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "aaas-dashboard"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file."""
    config_file = temp_config_dir / "config.toml"
    config_content = """
server_url = "http://config-file-server:9000"
refresh_interval = 10
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def temp_config_with_api_key(temp_config_dir):
    """Create a temporary config file with separate API key file."""
    config_file = temp_config_dir / "config.toml"
    config_content = """
server_url = "http://config-file-server:9000"
refresh_interval = 10
"""
    config_file.write_text(config_content)
    
    # Create API key file
    api_key_file = temp_config_dir / ".api_key"
    api_key_file.write_text("ak_from_file_123")
    
    return config_file

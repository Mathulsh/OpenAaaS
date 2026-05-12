"""Tests for components module."""

from unittest.mock import MagicMock, patch

import pytest

from aaas_dashboard.components import (
    get_or_create_client,
    init_session_state,
    render_sidebar,
    sync_sidebar_state,
    sync_sidebar_state_for_page,
)
from aaas_dashboard.config import Config


class MockSessionState:
    """Mock that supports both attribute and dict-style access."""

    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "_data":
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def mock_st():
    """Mock streamlit module."""
    with patch("aaas_dashboard.components.st") as mock:
        mock.session_state = MockSessionState()
        yield mock


class TestInitSessionState:
    """Tests for init_session_state."""

    def test_initializes_all_keys(self, mock_st):
        init_session_state()
        assert mock_st.session_state.config is None
        assert mock_st.session_state.client is None
        assert mock_st.session_state.use_mock is False
        assert mock_st.session_state.sidebar_server_url == ""
        assert mock_st.session_state.sidebar_api_key == ""
        assert mock_st.session_state.sidebar_refresh_interval == 5
        assert mock_st.session_state.sidebar_page_id is None

    def test_does_not_overwrite_existing(self, mock_st):
        mock_st.session_state["config"] = "existing"
        init_session_state()
        assert mock_st.session_state.config == "existing"


class TestSyncSidebarState:
    """Tests for sync_sidebar_state."""

    def test_syncs_values(self, mock_st):
        config = Config(server_url="http://test.com", api_key="ak_test", refresh_interval=10)
        sync_sidebar_state(config)
        assert mock_st.session_state.sidebar_server_url == "http://test.com"
        assert mock_st.session_state.sidebar_api_key == "ak_test"
        assert mock_st.session_state.sidebar_refresh_interval == 10


class TestSyncSidebarStateForPage:
    """Tests for sync_sidebar_state_for_page."""

    def test_syncs_when_page_changes(self, mock_st):
        mock_st.session_state["sidebar_page_id"] = "old_page"
        config = Config(server_url="http://test.com", api_key="ak_test", refresh_interval=10)
        sync_sidebar_state_for_page(config, "new_page")
        assert mock_st.session_state.sidebar_page_id == "new_page"
        assert mock_st.session_state.sidebar_server_url == "http://test.com"

    def test_does_not_sync_same_page(self, mock_st):
        mock_st.session_state["sidebar_page_id"] = "same_page"
        mock_st.session_state["sidebar_server_url"] = "existing"
        config = Config(server_url="http://test.com")
        sync_sidebar_state_for_page(config, "same_page")
        assert mock_st.session_state.sidebar_server_url == "existing"


class TestRenderSidebar:
    """Tests for render_sidebar."""

    def test_returns_config(self, mock_st):
        init_session_state()
        mock_st.button.return_value = False
        mock_st.text_input.side_effect = ["http://test.com", "ak_test"]
        mock_st.number_input.return_value = 10
        config = Config(server_url="http://old.com")
        result_config, auto_refresh = render_sidebar(config)
        assert result_config.server_url == "http://test.com"
        assert result_config.api_key == "ak_test"
        assert result_config.refresh_interval == 10

    def test_mock_toggle(self, mock_st):
        init_session_state()
        mock_st.button.return_value = False
        mock_st.text_input.side_effect = ["http://test.com", "ak_test"]
        mock_st.number_input.return_value = 5
        mock_st.toggle.return_value = True
        config = Config()
        render_sidebar(config)
        assert mock_st.session_state.use_mock is True


class TestGetOrCreateClient:
    """Tests for get_or_create_client."""

    def test_creates_new_client(self, mock_st):
        init_session_state()
        mock_st.session_state["client"] = None
        config = Config(server_url="http://test.com", api_key="ak_test")
        with patch("aaas_dashboard.components.OaaSClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            client = get_or_create_client(config)
        mock_client_cls.assert_called_once_with(server_url="http://test.com", api_key="ak_test")
        assert client is not None

    def test_returns_existing_client(self, mock_st):
        existing = MagicMock()
        mock_st.session_state["client"] = existing
        config = Config(server_url="http://test.com")
        client = get_or_create_client(config)
        assert client is existing

    def test_creates_mock_client(self, mock_st):
        mock_st.session_state["client"] = None
        mock_st.session_state["use_mock"] = True
        config = Config()
        with patch("aaas_dashboard.components.MockOaaSClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = get_or_create_client(config)
        mock_cls.assert_called_once()
        assert client is not None

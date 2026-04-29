"""Shared Streamlit components for OpenAaaS Dashboard."""

import os

import streamlit as st

from aaas_dashboard.client import OaaSClient, MockOaaSClient
from aaas_dashboard.config import Config, get_config


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "config" not in st.session_state:
        st.session_state.config = None
    if "client" not in st.session_state:
        st.session_state.client = None
    if "use_mock" not in st.session_state:
        st.session_state.use_mock = False
    if "sidebar_server_url" not in st.session_state:
        st.session_state.sidebar_server_url = ""
    if "sidebar_api_key" not in st.session_state:
        st.session_state.sidebar_api_key = ""
    if "sidebar_refresh_interval" not in st.session_state:
        st.session_state.sidebar_refresh_interval = 5
    if "sidebar_page_id" not in st.session_state:
        st.session_state.sidebar_page_id = None


def sync_sidebar_state(config: Config) -> None:
    """Sync persisted config values into sidebar widget state."""
    st.session_state.sidebar_server_url = config.server_url
    st.session_state.sidebar_api_key = config.api_key or ""
    st.session_state.sidebar_refresh_interval = config.refresh_interval


def sync_sidebar_state_for_page(config: Config, page_id: str) -> None:
    """Sync sidebar widget state when entering a different page."""
    if st.session_state.sidebar_page_id != page_id:
        sync_sidebar_state(config)
        st.session_state.sidebar_page_id = page_id


def render_sidebar(config: Config) -> tuple[Config, bool]:
    """Render sidebar with configuration inputs.

    Args:
        config: Current configuration

    Returns:
        Updated configuration and auto_refresh toggle value
    """
    with st.sidebar:
        st.title("⚙️ Configuration")

        # Connection settings
        st.subheader("Server Connection")
        server_url = st.text_input(
            "Server URL",
            key="sidebar_server_url",
            placeholder="http://localhost:8080",
            help="OpenAaaS server URL",
        )

        api_key = st.text_input(
            "API Key",
            key="sidebar_api_key",
            type="password",
            placeholder="ak_xxx",
            help="API key for authentication",
        )

        # Mock mode toggle
        use_mock = st.toggle(
            "Use Mock Data",
            value=st.session_state.use_mock,
            help="Use mock data for testing without a real server",
        )
        st.session_state.use_mock = use_mock

        st.divider()

        # Refresh settings
        st.subheader("Refresh Settings")
        refresh_interval = st.number_input(
            "Auto-refresh interval (seconds)",
            min_value=1,
            max_value=300,
            key="sidebar_refresh_interval",
            help="How often to refresh the task list",
        )

        auto_refresh = st.toggle(
            "Auto-refresh",
            value=True,  # 默认开启
            help="Automatically refresh task list every few seconds",
        )

        st.divider()

        # Save config button
        if st.button("💾 Save Config", use_container_width=True):
            new_config = Config(
                server_url=server_url,
                api_key=api_key if api_key else None,
                refresh_interval=refresh_interval,
            )
            new_config.save_to_file()
            os.environ["OAAS_SERVER_URL"] = new_config.server_url
            os.environ["OAAS_REFRESH_INTERVAL"] = str(new_config.refresh_interval)
            if new_config.api_key:
                os.environ["OAAS_API_KEY"] = new_config.api_key
            else:
                os.environ.pop("OAAS_API_KEY", None)
            st.session_state.config = new_config
            st.session_state.client = None
            st.success("Configuration saved!")

        st.divider()

        # Manual refresh button
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

        # About
        st.markdown("---")
        st.markdown("**OpenAaaS Dashboard** v0.1.0")
        st.markdown("[Documentation](https://github.com/Wolido/OpenAaaS/dash)")

    return Config(
        server_url=server_url,
        api_key=api_key if api_key else None,
        refresh_interval=refresh_interval,
    ), auto_refresh


def get_or_create_client(config: Config) -> OaaSClient:
    """Get or create the API client based on current config.

    Args:
        config: Current configuration

    Returns:
        Initialized OaaSClient or MockOaaSClient
    """
    if st.session_state.client is None:
        if st.session_state.use_mock:
            st.session_state.client = MockOaaSClient()
        else:
            st.session_state.client = OaaSClient(
                server_url=config.server_url,
                api_key=config.api_key,
            )
    return st.session_state.client

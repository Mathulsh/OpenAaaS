"""OpenAaaS Dashboard - A Streamlit-based web UI for monitoring tasks."""

__version__ = "0.1.0"
__author__ = "IDM Explorer Lab"

from .config import Config
from .client import OaaSClient

__all__ = ["Config", "OaaSClient"]

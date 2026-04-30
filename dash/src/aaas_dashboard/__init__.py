"""OpenAaaS Dashboard - A Streamlit-based web UI for monitoring tasks."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("open-aaas-dashboard")
except PackageNotFoundError:
    __version__ = "unknown"

__author__ = "IDM Explorer Lab"

from .config import Config
from .client import OaaSClient

__all__ = ["Config", "OaaSClient"]

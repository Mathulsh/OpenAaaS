"""Entry point for aaas-dashboard command."""

import argparse
import os
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="aaas-dashboard",
        description="OpenAaaS Dashboard - A Streamlit-based web UI for monitoring tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration Priority (highest to lowest):
  1. Command line arguments (--server, --api-key)
  2. Environment variables (OAAS_SERVER_URL, OAAS_API_KEY)
  3. Config file (~/.config/aaas-dashboard/config.toml)

Environment Variables:
  OAAS_SERVER_URL     OpenAaaS server URL
  OAAS_API_KEY        API key for authentication
  OAAS_REFRESH_INTERVAL   Auto-refresh interval in seconds (default: 5)

Examples:
  aaas-dashboard --server http://localhost:8080 --api-key ak_xxx
  aaas-dashboard --server http://api.example.com
  OAAS_SERVER_URL=http://localhost:8080 aaas-dashboard
        """,
    )
    
    parser.add_argument(
        "--server",
        "-s",
        type=str,
        default=None,
        help="OpenAaaS server URL (default: http://localhost:8080)",
    )
    
    parser.add_argument(
        "--api-key",
        "-k",
        type=str,
        default=None,
        help="API key for authentication",
    )
    
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to config file (default: ~/.config/aaas-dashboard/config.toml)",
    )
    
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8501,
        help="Port to run the Streamlit server on (default: 8501)",
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the Streamlit server to (default: localhost)",
    )
    
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s 0.1.0",
    )
    
    return parser


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # 确保 src 目录在 PYTHONPATH 中供子进程使用
    src_dir = Path(__file__).parent.parent
    src_path = str(src_dir)
    
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    if src_path not in current_pythonpath:
        os.environ["PYTHONPATH"] = f"{src_path}{os.pathsep}{current_pythonpath}" if current_pythonpath else src_path
    
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    parser = create_parser()
    args = parser.parse_args()
    
    # Import here to avoid slow startup when just showing help
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print("Error: streamlit is not installed. Please install it with:")
        print("  pip install streamlit")
        return 1
    
    # Load configuration to merge with args
    from aaas_dashboard.config import get_config
    
    config_path = Path(args.config) if args.config else None
    config = get_config(
        server_url=args.server,
        api_key=args.api_key,
        config_path=str(config_path) if config_path else None,
    )
    
    # Get the path to app.py
    app_path = Path(__file__).parent / "app.py"
    
    # Build streamlit arguments
    st_args = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port", str(args.port),
        "--server.address", args.host,
        "--browser.gatherUsageStats", "false",
    ]
    
    # Store config in environment for the app to pick up
    os.environ["OAAS_SERVER_URL"] = config.server_url
    if config.api_key:
        os.environ["OAAS_API_KEY"] = config.api_key
    os.environ["OAAS_REFRESH_INTERVAL"] = str(config.refresh_interval)
    
    # Run streamlit
    sys.argv = st_args
    try:
        stcli.main()
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

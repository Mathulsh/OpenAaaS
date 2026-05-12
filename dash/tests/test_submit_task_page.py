"""Tests for 01_Submit_Task page."""

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _extract_functions_from_module(file_path, function_names):
    """Extract specific function definitions from a Python source file."""
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    extracted = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            extracted.append(node)

    # Create a new module with only imports and the extracted functions
    new_body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            new_body.append(node)
    new_body.extend(extracted)

    new_tree = ast.Module(body=new_body, type_ignores=[])
    code = compile(new_tree, file_path.name, "exec")
    namespace = {"__name__": "test_module"}
    exec(code, namespace)
    return namespace


# Extract only the pure functions we need to test
_page_path = Path(__file__).parent.parent / "src" / "aaas_dashboard" / "pages" / "01_Submit_Task.py"
_namespace = _extract_functions_from_module(
    _page_path,
    {"format_datetime", "format_duration", "inject_page_styles", "render_stat_tile"}
)
format_datetime = _namespace["format_datetime"]
format_duration = _namespace["format_duration"]
inject_page_styles = _namespace["inject_page_styles"]
render_stat_tile = _namespace["render_stat_tile"]


class TestFormatDatetime:
    """Tests for format_datetime."""

    def test_none_returns_dash(self):
        assert format_datetime(None) == "-"

    def test_formats_correctly(self):
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert format_datetime(dt) == "2024-01-15 10:30:00"


class TestFormatDuration:
    """Tests for format_duration."""

    def test_none_start_returns_dash(self):
        assert format_duration(None, None) == "-"

    def test_no_end_uses_now(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_duration(start, None)
        assert result != "-"
        assert "h" in result or "m" in result or "s" in result

    def test_hours_minutes_seconds(self):
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 5, 3, tzinfo=timezone.utc)
        assert format_duration(start, end) == "2h 5m 3s"

    def test_minutes_seconds(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 5, 3, tzinfo=timezone.utc)
        assert format_duration(start, end) == "5m 3s"

    def test_seconds_only(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 7, tzinfo=timezone.utc)
        assert format_duration(start, end) == "7s"

    def test_naive_start_with_aware_end(self):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
        assert format_duration(start, end) == "5s"


class TestInjectPageStyles:
    """Tests for inject_page_styles."""

    def test_contains_key_css_classes(self):
        mock_st = MagicMock()
        _namespace["st"] = mock_st
        inject_page_styles()
        call_args = mock_st.markdown.call_args[0][0]
        assert "submit-hero" in call_args
        assert "stat-tile" in call_args
        assert "status-pill" in call_args
        assert "meta-card" in call_args


class TestRenderStatTile:
    """Tests for render_stat_tile."""

    def test_calls_st_markdown(self):
        mock_st = MagicMock()
        _namespace["st"] = mock_st
        render_stat_tile("Label", 42, "hint text")
        mock_st.markdown.assert_called_once()
        call_args = mock_st.markdown.call_args[0][0]
        assert "Label" in call_args
        assert "42" in call_args
        assert "hint text" in call_args

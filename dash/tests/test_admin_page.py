"""Tests for 02_Admin page.

Note: 02_Admin.py contains only Streamlit UI code with no user-defined
pure functions. These tests verify the module structure and key elements.
"""

import ast
from pathlib import Path

import pytest


class TestAdminPageStructure:
    """Tests for 02_Admin.py structure."""

    def _load_module(self):
        page_path = (
            Path(__file__).parent.parent
            / "src"
            / "aaas_dashboard"
            / "pages"
            / "02_Admin.py"
        )
        source = page_path.read_text(encoding="utf-8")
        return ast.parse(source)

    def test_module_exists(self):
        page_path = (
            Path(__file__).parent.parent
            / "src"
            / "aaas_dashboard"
            / "pages"
            / "02_Admin.py"
        )
        assert page_path.exists()

    def test_contains_streamlit_import(self):
        tree = self._load_module()
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) and any(alias.name == "streamlit" for alias in node.names)
        ]
        assert len(imports) > 0

    def test_contains_service_management_section(self):
        tree = self._load_module()
        source = ast.unparse(tree)
        assert "Service Management" in source
        assert "All Services" in source

    def test_contains_user_management_section(self):
        tree = self._load_module()
        source = ast.unparse(tree)
        assert "User Management" in source
        assert "All Users" in source

    def test_contains_permission_management_section(self):
        tree = self._load_module()
        source = ast.unparse(tree)
        assert "Permission Management" in source
        assert "Grant Permission" in source

    def test_no_user_defined_functions(self):
        """Verify the page has no user-defined pure functions (it's all UI code)."""
        tree = self._load_module()
        funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert len(funcs) == 0

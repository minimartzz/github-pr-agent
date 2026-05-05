"""
Unit Test for MCP Server
========================
Tests:
- test_imports: Check if all imports were successful

"""

import json
from unittest.mock import MagicMock, patch

import pytest

# Import implemented functions
try:
    from server import analyse_file_changes, get_pr_templates, mcp, suggest_template

    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    IMPORTS_SUCCESSFUL = False
    IMPORT_ERROR = str(e)


class TestImplementation:
    """Test that the required functions are implemented"""

    def test_imports(self):
        """Test taht all required functions can be imported"""
        assert IMPORTS_SUCCESSFUL, (
            "Failed to import required functions: Failed to"
            f" import required functions: {
                IMPORT_ERROR if not IMPORTS_SUCCESSFUL else ''
            }"
        )
        assert mcp is not None, "FastMCP server instance not found"
        assert callable(analyse_file_changes), (
            "analyse_file_changes should be a callable function"
        )
        assert callable(get_pr_templates), (
            "get_pr_templates should be a callable function"
        )
        assert callable(suggest_template), (
            "suggest_template should be a callable function"
        )


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Imports failed")
class TestAnalyseFileChanges:
    """Test the analyse_file_changes tool"""

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")

            result = await analyse_file_changes()

            assert isinstance(result, str), "Should return a string"
            # Should be valid JSON
            data = json.loads(result)

            is_implemented = not (
                "error" in data and "Not implemented" in str(data.get("error", ""))
            )
            if is_implemented:
                assert any(
                    key in data for key in ["files_changed", "files", "changes", "diff"]
                ), "Result should included file change information"
            else:
                assert isinstance(data, dict), "Should return a JSON object"


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Imports failed")
class TestGetPRTemplates:
    """Test the get_pr_templates_tool."""

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        "Test that get_pr_templates returns a JSON string"
        result = await get_pr_templates()

        assert isinstance(result, str), "Templates should be a string"
        data = json.loads(result)

        # Check if function was implemented and has the right return type
        is_implemented = not ("error" in data and isinstance(data, dict))
        if is_implemented:
            assert isinstance(data, list), "Templates should return a JSON array"
        else:
            assert isinstance(data, dict), "Templates not implemented"

    @pytest.mark.asyncio
    async def test_returns_templates(self):
        """Test taht templates are returned"""
        result = await get_pr_templates()
        templates = json.loads(result)

        is_implemented = not ("error" in templates and isinstance(templates, dict))
        if is_implemented:
            assert len(templates) >= 1, "Should have at least 1 template"

            for temp in templates:
                assert isinstance(temp, dict), "Every template should be a dictionary"
                assert any(key in temp for key in ["filename", "name", "type", "id"]), (
                    "Templates should have an identifier"
                )
        else:
            assert isinstance(templates, dict), "Should return structured error"
            " for starter code"


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Imports failed")
class TestSuggestTemplate:
    """Test the suggest_template tool"""

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        """Test that suggest_template returns a JSON string"""
        result = await suggest_template(
            "Fixed a bug in the authentication system", "bug"
        )

        assert isinstance(result, str), "Suggested template should be a string"
        data = json.loads(result)

        assert isinstance(data, dict), "JSON loaded template should be a dictionary"

    @pytest.mark.asyncio
    async def test_suggestion_structure(self):
        """Test that suggestion has expected structure"""
        result = await suggest_template(
            "Added new feature for user management", "feature"
        )
        suggestion = json.loads(result)

        is_implemented = not (
            "error" in suggestion
            and "Not implemented" in str(suggestion.get("error", ""))
        )
        if is_implemented:
            assert any(
                key in suggestion
                for key in ["template", "recommended_template", "suggestion"]
            ), "Should include a template recommendation"
        else:
            assert isinstance(suggestion, dict), "Should return structured error for"
            " starter code"


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Imports failed")
class TestToolRegistration:
    """Test that tools are properly registered with FastMCP"""

    def test_tools_have_decorators(self):
        """Test that tool functions are decorated with @mcp.tool()"""
        # FastMCP, decorated functions have certain attributes. This checks that
        # these functions exist and are callable
        assert hasattr(analyse_file_changes, "__name__"), (
            "analyse_file_changes should be a proper function"
        )
        assert hasattr(get_pr_templates, "__name__"), (
            "get_pr_templates should be a proper function"
        )
        assert hasattr(suggest_template, "__name__"), (
            "suggest_template should be a proper function"
        )


if __name__ == "__main__":
    if not IMPORTS_SUCCESSFUL:
        print(f"❌ Cannot run tests - imports failed: {IMPORT_ERROR}")
        print("\nMake sure you've:")
        print("1. Implemented all three tool functions")
        print("2. Decorated them with @mcp.tool()")
        print("3. Installed dependencies with: uv sync")
        exit(1)

    pytest.main([__file__, "-v"])

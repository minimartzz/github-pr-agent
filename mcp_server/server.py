"""
MCP Server
==========
Implement tools for analysing git changes and suggesting PR templates

Components:
- analyse_file_changes - Provides the git diff between the main and working branch
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialise FastMCP server
mcp = FastMCP("pr-agent")

# PR template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"

CHANGE_TYPE_MAPPER = {
    "bug": "bug.md",
    "doc": "docs.md",
    "feature": "feature.md",
    "performance": "performance.md",
    "optimization": "performance.md",
    "cleanup": "refactor.md",
    "refactor": "refactor.md",
    "security": "security.md",
    "test": "test.md",
}
FILE_TO_TYPE = {v: k for k, v in CHANGE_TYPE_MAPPER.items()}


# ========================================
# TOOLS
# ========================================
@mcp.tool()
async def analyse_file_changes(
    base_branch: str = "main",
    include_diff: bool = True,
    max_diff_lines: int = 500,
    working_dir: Optional[str] = None,
) -> str:
    """
    Get the full diff and list of changed files in the current git repository

    Args:
        base_branch (str, optional): Base branch to compare against. Defaults to "main".
        include_diff (bool, optional): Include the full diff content. Defaults to True.
        max_diff_lines (int, optional): Maximum number of diff lines to incldue.
            Defaults to 500.
        working_dir (Optional[str], optional): Directory to run fit commands from.
            Defaults to None.

    Returns:
        str: JSON dump of git diff information
    """
    try:
        if working_dir is None:
            # Get Claudes working directory
            context = mcp.get_context()
            root_result = await context.session.list_roots()
            working_dir = root_result.roots[0].uri.path

        cwd = working_dir if working_dir else os.getcwd()

        # Get git diff from subprocesses
        command = ["git", "diff", f"{base_branch}...HEAD"]
        result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)

        if result.returncode == 0:
            git_diff = result.stdout
        else:
            return json.dumps({"error": "No changes found in current repo"})

        # Truncate lines
        if len(git_diff) > max_diff_lines:
            lines = git_diff.split("\n")
            trunc_lines = lines[:max_diff_lines]
            trunc_diff = "\n".join(trunc_lines)
            trunc_diff += f"\n Truncated diff lines {len(trunc_diff)} / {len(git_diff)}"
            git_diff = trunc_diff

        # Get git diff stats
        stats_command = ["git", "diff", "--stat", f"{base_branch}...HEAD"]
        stats_result = subprocess.run(
            stats_command, capture_output=True, text=True, cwd=cwd
        )

        # Get list of changed files
        files_command = ["git", "diff", "--name-status", f"{base_branch}...HEAD"]
        files_result = subprocess.run(
            files_command, capture_output=True, text=True, check=True, cwd=cwd
        )

        # Get commit message
        commit_command = ["git", "log", "--oneline", f"{base_branch}...HEAD"]
        commit_result = subprocess.run(
            commit_command, capture_output=True, text=True, cwd=cwd
        )

        out = {
            "stats": stats_result.stdout,
            "total_lines": len(trunc_lines),
            "diff": git_diff if include_diff else "Use include_diff=True to see diff",
            "files_changed": files_result.stdout,
            "commit_message": commit_result.stdout,
        }

        return json.dumps(out)

    except subprocess.CalledProcessError as e:
        return json.dumps({"error": f"Git error: {e.stderr}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """
    Get a list of all available PR templates in the template folder

    Returns:
        str: JSON dump of list of available templates
    """
    files = os.listdir(TEMPLATES_DIR)
    templates = [
        {
            "filename": name,
            "type": FILE_TO_TYPE[name],
            "content": (TEMPLATES_DIR / name).read_text(),
        }
        for name in files
    ]

    return json.dumps(templates)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    templates = await get_pr_templates()
    templates = json.loads(templates)

    # Get the corresponding template based on change type
    selected_template = next(
        (t for t in templates if t["type"] == change_type), templates[0]
    )

    return json.dumps(
        {
            "recommended_template": selected_template,
            "reasoning": f"Based on your analysis of '{changes_summary}', this appears"
            f" to be a {change_type} change.",
            "template_content": selected_template["content"],
            "usage_hint": "Cluade can help you fill out a PR template based on the"
            " changes in your code",
        }
    )


if __name__ == "__main__":
    mcp.run()

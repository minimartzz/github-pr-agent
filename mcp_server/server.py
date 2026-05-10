"""
MCP Server
==========
Implement tools and prompts for analysing git changes and suggesting PR templates

Tools:
- analyse_file_changes - Provides the git diff between the main and working branch
- get_pr_templates - Retrieve a list of PR templates from "templates" folder
- suggest_template - Suggests which template to be used based on analysis
- get_recent_action_events - Loads the most recent X events from Github Actions
- get_workflow_status - Groups commits and returns their status'

Prompts:
- analyse_ci_results
- create_deployment_summary
- generate_pr_status_reports
- troubleshoot_workflow_failures
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialise FastMCP server
mcp = FastMCP("pr-agent")

# PR template directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

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

# Webhook events
EVENTS_FILE = Path(__file__).parent.parent / "github_events.json"


# ========================================
# TOOLS
# ========================================


# -------------------- PR TEMPLATE TOOLS --------------------
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
            try:
                # Get Claudes working directory
                context = mcp.get_context()
                root_result = await context.session.list_roots()
                working_dir = root_result.roots[0].uri.path
            except Exception:
                working_dir = os.getcwd()

        cwd = working_dir or os.getcwd()

        # Get git diff from subprocesses
        command = ["git", "diff", f"{base_branch}...HEAD"]
        result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)

        if result.returncode == 0:
            git_diff = result.stdout
        else:
            return json.dumps({"error": "No changes found in current repo"})

        # Truncate lines
        lines = git_diff.split("\n")
        if len(lines) > max_diff_lines:
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
            "total_lines": len(lines),
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
    try:
        files = os.listdir(TEMPLATES_DIR)
        templates = []
        for name in files:
            if name not in FILE_TO_TYPE:
                continue
            templates.append(
                {
                    "filename": name,
                    "type": FILE_TO_TYPE[name],
                    "content": (TEMPLATES_DIR / name).read_text(),
                }
            )

        return json.dumps(templates)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """
    Suggests which PR template to be used

    Args:
        changes_summary (str): Description of the proposed changes from your analysis
        change_type (str): Recommended type of change you've identified
            (bug, feature, docs, refactor, etc.)

    Returns:
        str: _description_
    """
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
            "usage_hint": "Claude can help you fill out a PR template based on the"
            " changes in your code",
        }
    )


# -------------------- GITHUB ACTIONS TOOLS --------------------
@mcp.tool()
async def get_recent_actions_events(limit: int = 10) -> str:
    """
    Get the most recent Github Action events received via webhook.

    Args:
        limit (int, optional): Maximum number of recent events to retrieve.
            Defaults to 10.

    Returns:
        str: List of most recent events
    """
    try:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, "r") as f:
                events = json.load(f)

            # Limit to latest 10 entries
            events = events[-limit:]
            return json.dumps(events, indent=2)
        else:
            return json.dumps({"events": []})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_workflow_status(workflow_name: Optional[str] = None) -> str:
    """
    Get the current status of each events commit.

    Args:
        workflow_name (Optional[str], optional): Filter by workflow name.
            Defaults to None.

    Returns:
        str: List of most recent workflows status'
    """
    try:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, "r") as f:
                events = json.load(f)

            # Filter for workflow_run events
            events = [e for e in events if e["event_type"] == "workflow_run"]

            # Filter on workflow_name if exists
            if workflow_name:
                events = [e for e in events if e["workflow_run"] == workflow_name]

            if not events:
                return json.dumps({"message": "No Github Actions events created yet"})

            # Get the latest event for each commit
            status = {}
            for event in events:
                commit = event["commit_sha"]
                curr_ts = datetime.fromisoformat(event["timestamp"])
                if commit not in status or curr_ts > datetime.fromisoformat(
                    status[commit]["timestamp"]
                ):
                    status[commit] = {
                        "name": event.get("workflow_run", ""),
                        "status": event.get("workflow_status"),
                        "updated_at": event.get("timestamp", ""),
                        "branch": event.get("branch", ""),
                        "html_url": event.get("workflow_url", ""),
                    }

            return json.dumps(list(status.values()), indent=2)

        else:
            return json.dumps({"message": "No Github Actions events created yet"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ========================================
# PROMPTS
# ========================================
@mcp.prompt()
async def analyse_ci_results():
    """Analyse the recent CI/CD results captured by Github Actions"""
    return """Please analyse the recent CI/CD results from Github Actions:

1. First, call get_recent_actions() to fetch the latest CI/CD events
2. Then call get_workflow_status() to summarise the current workflow states
3. Identify any failures or issues that need attention
4. Provide actionable next steps based on the results

Format your response as:
## CI/CD Status Summary
- **Overall Health**: [Good/Warning/Critical]
- **Failed Workflows**: [List any failures with links]
- **Successful Workflows**: [List recent successes]
- **Recommendations**: [Specific actions to take]
- **Trends**: [Any patterns you notice]"""


@mcp.prompt()
async def create_deployment_summary():
    """Generate a summary of all recent deployments"""
    return """Provide a summary of the recent CI/CD results of deployment actions

1. First call get_recent_actions() to get CI/CD events
2. Use get_workflow_status() to get the workflows status
3. Gather all deployment related information if present

Format the response as
## Deployment Summary
- **Status**: [✅ Success / ❌ Failed / ⏳ In Progress]
- **Branch**: Which branch did the deployment occur on
- **Commit**: What was the commit hash for this deployment
- **Duration**: How long did it take to deploy (if available)
- **Issues**: Where there any existing issues (if available)
- **Key Changes**: What were the changes in this deployment (if available)

Keep the information brief for quick reading in the team."""


@mcp.prompt()
async def generate_pr_status_report():
    """Provide a comprehensive report of all Pull Requests including CI/CD results"""
    return """Generate a report of all Pull Requests:

1. Use analyze_file_changes() to understand what changed
2. Use get_workflow_status() to check CI/CD status
3. Use suggest_template() to recommend the appropriate PR template
4. Combine all information into a cohesive report

Create a detailed report with:

## 📋 PR Status Report

### 📝 Code Changes
- **Files Modified**: [Count by type - .py, .js, etc.]
- **Change Type**: [Feature/Bug/Refactor/etc.]
- **Impact Assessment**: [High/Medium/Low with reasoning]
- **Key Changes**: [Bullet points of main modifications]

### 🔄 CI/CD Status
- **All Checks**: [✅ Passing / ❌ Failing / ⏳ Running]
- **Test Results**: [Pass rate, failed tests if any]
- **Build Status**: [Success/Failed with details]
- **Code Quality**: [Linting, coverage if available]

### 📌 Recommendations
- **PR Template**: [Suggested template and why]
- **Next Steps**: [What needs to happen before merge]
- **Reviewers**: [Suggested reviewers based on files changed]

### ⚠️ Risks & Considerations
- [Any deployment risks]
- [Breaking changes]
- [Dependencies affected]"""


@mcp.prompt()
async def troubleshoot_workflow_failure():
    """Help troubleshoot a failing GitHub Actions workflow."""
    return """Help troubleshoot failing GitHub Actions workflows:

1. Use get_recent_actions_events() to find recent failures
2. Use get_workflow_status() to see which workflows are failing
3. Analyze the failure patterns and timing
4. Provide systematic troubleshooting steps

Structure your response as:

## 🔧 Workflow Troubleshooting Guide

### ❌ Failed Workflow Details
- **Workflow Name**: [Name of failing workflow]
- **Failure Type**: [Test/Build/Deploy/Lint]
- **First Failed**: [When did it start failing]
- **Failure Rate**: [Intermittent or consistent]

### 🔍 Diagnostic Information
- **Error Patterns**: [Common error messages or symptoms]
- **Recent Changes**: [What changed before failures started]
- **Dependencies**: [External services or resources involved]

### 💡 Possible Causes (ordered by likelihood)
1. **[Most Likely]**: [Description and why]
2. **[Likely]**: [Description and why]
3. **[Possible]**: [Description and why]

### ✅ Suggested Fixes
**Immediate Actions:**
- [ ] [Quick fix to try first]
- [ ] [Second quick fix]

**Investigation Steps:**
- [ ] [How to gather more info]
- [ ] [Logs or data to check]

**Long-term Solutions:**
- [ ] [Preventive measure]
- [ ] [Process improvement]

### 📚 Resources
- [Relevant documentation links]
- [Similar issues or solutions]"""


if __name__ == "__main__":
    mcp.run()

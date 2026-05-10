```bash
# Enable local webhook server
uv run python github-actions-integration/webhook_server.py

# Expose using ngrok
ngrok https 8080

# Claude mcp commands
## To add agent
claude mcp add pr-agent -- uv --directory "D:\Repos\github_pr_agent\mcp_server" run server.py
## To list agents
claude mcp list
## Remove the agent
claude mcp remove github-pr-agent
```

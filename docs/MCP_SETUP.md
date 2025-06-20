# MCP (Model Context Protocol) Setup for Ollama Code

## Overview

Ollama Code supports MCP (Model Context Protocol) servers, allowing you to extend its capabilities with external tools and services.

## Configuration

MCP servers are configured via `mcp_servers.json` which can be placed in:
1. `.ollama-code/mcp_servers.json` in your current project directory
2. `~/.ollama/ollama-code/mcp_servers.json` for global configuration

## Example Configuration

```json
{
  "servers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      },
      "description": "GitHub API access via MCP",
      "enabled": true
    },
    "filesystem": {
      "type": "stdio", 
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"],
      "description": "File system access via MCP",
      "enabled": false
    }
  }
}
```

## Setting up GitHub MCP Server

1. **Install Node.js** (required for npx)
   ```bash
   # Check if Node.js is installed
   node --version
   ```

2. **Get a GitHub Personal Access Token**
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Create a new token with appropriate permissions
   - Set it as an environment variable:
     ```bash
     export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here
     ```

3. **Enable the GitHub server** in `mcp_servers.json`:
   ```json
   {
     "servers": {
       "github": {
         "enabled": true
         // ... rest of config
       }
     }
   }
   ```

4. **Run ollama-code**
   ```bash
   ollama-code
   ```
   
   You should see:
   ```
   🔌 Loading MCP servers from .ollama-code/mcp_servers.json
     Connecting to github...
     ✅ Connected to github
   ```

5. **Check available tools**
   Use the `/tools` command to see what MCP tools are available:
   ```
   /tools
   ```

## Available MCP Servers

Official MCP servers from the Model Context Protocol team:

- **GitHub** (`@modelcontextprotocol/server-github`) - GitHub API access
- **Filesystem** (`@modelcontextprotocol/server-filesystem`) - Controlled file system access
- **PostgreSQL** (`@modelcontextprotocol/server-postgres`) - Database access
- **Slack** (`@modelcontextprotocol/server-slack`) - Slack integration
- **Memory** (`@modelcontextprotocol/server-memory`) - Persistent memory storage
- **Puppeteer** (`@modelcontextprotocol/server-puppeteer`) - Web automation
- **Brave Search** (`@modelcontextprotocol/server-brave-search`) - Web search

## Troubleshooting

1. **Node.js not found**: Install Node.js from https://nodejs.org/
2. **Connection failed**: Check your internet connection and firewall settings
3. **Authentication errors**: Verify your tokens/credentials are correct
4. **No tools showing**: Use `/tools` command after connection is established

## Security Notes

- MCP servers run as separate processes with their own permissions
- Only enable servers you trust
- Be careful with filesystem access paths
- Keep your tokens and credentials secure (use environment variables)
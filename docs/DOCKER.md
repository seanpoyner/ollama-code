# Running Ollama Code in Docker

This guide explains how to run ollama-code in a Docker container for testing and development.

## Docker Desktop Users

If you're using Docker Desktop, we have a simplified setup:

### Windows:
```batch
run-docker-desktop.bat
```

### Mac/Linux:
```bash
./run-docker-desktop.sh
```

Then:
1. Open Docker Desktop → Containers
2. Click on `ollama-code-desktop`
3. Click the `Terminal` tab
4. Run:
   ```bash
   ollama serve &
   ollama pull llama3.2:3b
   cd /workspace
   ollama-code
   ```

## Quick Start (Docker CLI)

1. **Build the Docker image:**
   ```bash
   docker build -t ollama-code:latest .
   ```

2. **Run with docker-compose (recommended):**
   ```bash
   docker-compose up -d
   docker-compose exec ollama-code bash
   ```

3. **Or run with docker directly:**
   ```bash
   docker run -it --rm \
     --name ollama-code-test \
     --network host \
     -v $(pwd)/workspace:/home/ollama/workspace \
     -e GITHUB_PERSONAL_ACCESS_TOKEN=your_token \
     ollama-code:latest
   ```

## Inside the Container

Once inside the container:

1. **Install and start Ollama:**
   ```bash
   # Ollama is auto-installed on container start
   # Start the Ollama server
   ollama serve &
   
   # Pull a model
   ollama pull qwen2.5-coder:7b
   ```

2. **Run ollama-code:**
   ```bash
   # Go to workspace
   cd /workspace
   
   # Run ollama-code
   ollama-code
   ```

## Features Included

- **Python 3.11** with virtual environment
- **Node.js & npm** for MCP servers
- **Git** for version control
- **All ollama-code dependencies** including ChromaDB, Docker SDK, FastMCP
- **Editors** (nano, vim) for testing file operations
- **Ollama** auto-installation script

## Directory Structure

```
/home/ollama/
├── ollama-code/        # The ollama-code repository
│   └── venv/          # Python virtual environment
├── workspace/          # Your working directory (mounted)
├── .ollama/           # Ollama configuration and models
└── install-ollama.sh  # Ollama installation script
```

## Environment Variables

- `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)
- `GITHUB_PERSONAL_ACCESS_TOKEN`: For GitHub MCP server
- `PYTHONUNBUFFERED`: Set to 1 for immediate output

## Volumes

The docker-compose.yml defines several volumes:

- `./workspace`: Mounted to `/home/ollama/workspace` for persistent work
- `ollama-models`: Stores Ollama models
- `ollama-config`: Stores ollama-code configuration
- `.ollama-code`: Stores conversation history and project settings

## Using MCP Servers

1. **Set your GitHub token:**
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here
   ```

2. **Enable MCP servers in the config:**
   The `.ollama-code/mcp_servers.json` is already configured

3. **Run ollama-code and check tools:**
   ```bash
   ollama-code
   /tools  # List available MCP tools
   ```

## Testing Different Scenarios

### Test Basic Code Execution
```bash
cd /workspace
ollama-code
# Type: Write a Python script that lists all files in the current directory
```

### Test Web Development
```bash
cd /workspace
ollama-code
# Type: Create a simple web chat interface using HTML, CSS, and JavaScript
```

### Test MCP Integration
```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=your_token
ollama-code
/tools
# Type: Search GitHub for repositories about ollama
```

### Test Project Initialization
```bash
cd /workspace
mkdir my-project && cd my-project
ollama-code
/init This is a FastAPI project for a todo list application
```

## Troubleshooting

### Ollama Connection Issues
```bash
# Check if Ollama is running
ps aux | grep ollama

# Restart Ollama
pkill ollama
ollama serve &

# Test Ollama
curl http://localhost:11434/api/tags
```

### Permission Issues
The container runs as the `ollama` user. All files in `/workspace` should be accessible.

### MCP Server Issues
```bash
# Check Node.js
node --version
npm --version

# Test MCP server manually
npx -y @modelcontextprotocol/server-github
```

## Development Workflow

1. Make changes to ollama-code on your host
2. Rebuild the Docker image: `docker-compose build`
3. Restart the container: `docker-compose restart`
4. Test your changes inside the container

## Resource Limits

The docker-compose.yml sets resource limits:
- CPU: 4 cores max, 2 cores reserved
- Memory: 8GB max, 4GB reserved

Adjust these based on your system capabilities.
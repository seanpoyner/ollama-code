#!/bin/bash
# Test script for Docker environment

echo "🧪 Testing Ollama Code Docker Environment"
echo "========================================"
echo ""

# Function to check command
check_command() {
    if command -v $1 &> /dev/null; then
        echo "✅ $1 is installed: $(command -v $1)"
        if [ "$2" = "version" ]; then
            $1 --version 2>/dev/null || $1 -v 2>/dev/null || echo "   Version check not available"
        fi
    else
        echo "❌ $1 is NOT installed"
        return 1
    fi
}

# Function to check Python package
check_python_package() {
    if python3 -c "import $1" 2>/dev/null; then
        echo "✅ Python package '$1' is installed"
    else
        echo "❌ Python package '$1' is NOT installed"
        return 1
    fi
}

echo "1. System Commands:"
echo "-------------------"
check_command python3 version
check_command pip version
check_command git version
check_command node version
check_command npm version
check_command ollama version

echo ""
echo "2. Python Environment:"
echo "---------------------"
echo "Python location: $(which python3)"
echo "Pip location: $(which pip)"
echo "Virtual env: ${VIRTUAL_ENV:-Not activated}"

echo ""
echo "3. Python Packages:"
echo "------------------"
check_python_package ollama
check_python_package rich
check_python_package chromadb
check_python_package docker
check_python_package fastmcp
check_python_package yaml

echo ""
echo "4. Ollama Code:"
echo "--------------"
if command -v ollama-code &> /dev/null; then
    echo "✅ ollama-code is installed: $(command -v ollama-code)"
else
    echo "❌ ollama-code is NOT in PATH"
fi

echo ""
echo "5. Directory Structure:"
echo "----------------------"
echo "Current directory: $(pwd)"
echo "Home directory: $HOME"
echo ""
echo "Directory tree:"
tree -L 2 $HOME 2>/dev/null || ls -la $HOME

echo ""
echo "6. Ollama Server:"
echo "----------------"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama server is running"
    echo "   Models available:"
    curl -s http://localhost:11434/api/tags | jq -r '.models[].name' 2>/dev/null | sed 's/^/   - /'
else
    echo "⚠️  Ollama server is not running"
    echo "   Start it with: ollama serve &"
fi

echo ""
echo "7. MCP Configuration:"
echo "--------------------"
if [ -f "$HOME/workspace/.ollama-code/mcp_servers.json" ]; then
    echo "✅ MCP config found at: $HOME/workspace/.ollama-code/mcp_servers.json"
    echo "   Configured servers:"
    jq -r '.servers | keys[]' "$HOME/workspace/.ollama-code/mcp_servers.json" 2>/dev/null | sed 's/^/   - /'
else
    echo "⚠️  No MCP config found"
fi

echo ""
echo "8. Environment Variables:"
echo "------------------------"
echo "OLLAMA_HOST: ${OLLAMA_HOST:-Not set}"
echo "GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_PERSONAL_ACCESS_TOKEN:+[SET]}"
echo "PATH: $PATH"

echo ""
echo "========================================"
echo "Test complete!"
echo ""
echo "To start using ollama-code:"
echo "  1. ollama serve &"
echo "  2. ollama pull qwen2.5-coder:7b"
echo "  3. cd /workspace"
echo "  4. ollama-code"
echo ""
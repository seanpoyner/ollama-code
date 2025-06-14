# Ollama Code

A powerful coding assistant powered by Ollama models with code execution capabilities.

## Features

- 🤖 Interactive AI coding assistant with thought loop processing
- 🐍 Python code execution in sandboxed environment
- 📄 Automatic file creation from code blocks
- 🌐 Web GUI creation support
- 💭 Real-time thinking indicators
- ⚡ ESC key cancellation support
- 📚 Project context awareness (OLLAMA.md)
- 🔄 Conversation history with --resume
- 🧠 Automatic task decomposition for complex requests
- 📋 Internal task management for systematic completion
- 🚀 Auto-continue mode for hands-free operation
- 🔧 Extensible with MCP tools

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ollama-code.git
cd ollama-code

# Install in development mode
pip install -e .

# Or install with optional dependencies
pip install -e ".[docker,mcp]"
```

## Usage

```bash
# Start Ollama server
ollama serve

# Run Ollama Code
ollama-code

# Resume previous conversation
ollama-code --resume
```

## Commands

### Project Management
- `/init [context]` - Analyze codebase and create OLLAMA.md
- `/init --force` - Overwrite existing OLLAMA.md

### Task Management
- `/tasks` - Show current task progress
- `/auto` - Toggle auto-continue mode

### Other Commands
- `/tools` - Show available MCP tools
- `/prompts` - List available code prompts
- `/prompt <name>` - Load a specific prompt
- `/help` - Show all commands
- `quit` - Exit the program

## Creating Web Applications

When asked to create a web GUI, Ollama Code will automatically generate HTML, CSS, and JavaScript files:

```
Create a web gui that can connect to local ollama model
```

## Configuration

- `messages.json` - User interface messages
- `prompts.yaml` - System prompts and templates
- `OLLAMA.md` - Project-specific context (created with `/init`)
- `.ollama-code/` - Additional project configuration

## License

MIT
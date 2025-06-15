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

### Basic Usage

```bash
# Start Ollama server
ollama serve

# Run Ollama Code in interactive mode
ollama-code

# Resume previous conversation
ollama-code --resume
```

### Command-Line Options

```bash
# Execute a single prompt
ollama-code -p "Create a Python web scraper"

# Initialize project with context
ollama-code --init "FastAPI project for e-commerce"

# Use a specific model
ollama-code --model qwen2.5-coder:7b

# Enable auto-mode and quick analysis
ollama-code --auto --quick

# Execute with auto-approval and verbose output
ollama-code -p "Create a README file" --auto-approve --verbose

# List available models
ollama-code --list-models
```

### Full Options

```
-p, --prompt TEXT         Execute a single prompt and exit
--init [CONTEXT]          Initialize project with OLLAMA.md
--resume                  Resume the previous conversation
-m, --model TEXT          Specify the Ollama model to use
--auto                    Enable auto-continue mode for tasks
--quick                   Enable quick analysis mode (30s limit)
--no-quick                Disable quick analysis mode
-v, --verbose             Enable verbose logging
-q, --quiet               Minimize output
--no-color                Disable colored output
--auto-approve            Auto-approve all file writes and commands
--force                   Force overwrite existing files
--temperature T           Set model temperature (0.0-2.0)
--max-tokens N            Maximum tokens for model response
--timeout SECONDS         Timeout for model responses (default: 120s)
--list-models             List available Ollama models
--version                 Show version information
--help                    Show help message
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
# Ollama Code Architecture

## Project Structure

```
ollama-code/
├── ollama-code.py          # Legacy entry point (backward compatibility)
├── ollama-code             # New CLI entry point
├── setup.py                # Package installation
├── README.md               # Project documentation
├── ARCHITECTURE.md         # This file
├── messages.json           # UI messages configuration
├── prompts.yaml            # Prompts and templates
├── OLLAMA.md              # Project context (created by /init)
│
└── ollama_code/           # Main package
    ├── __init__.py
    ├── main.py            # Main application entry (198 lines)
    │
    ├── core/              # Core functionality
    │   ├── __init__.py
    │   ├── agent.py       # OllamaCodeAgent class (336 lines)
    │   ├── sandbox.py     # Code execution sandbox (138 lines)
    │   └── file_ops.py    # File operations & extraction (165 lines)
    │
    ├── integrations/      # External integrations
    │   ├── __init__.py
    │   └── mcp.py         # FastMCP integration (116 lines)
    │
    └── utils/             # Utility modules
        ├── __init__.py
        ├── config.py      # Configuration loading (68 lines)
        ├── logging.py     # Logging setup (30 lines)
        ├── messages.py    # Message management (86 lines)
        └── ui.py          # UI utilities (110 lines)
```

## Module Breakdown

### Core Modules

- **agent.py** (336 lines): Main agent logic, chat interface, init command
- **sandbox.py** (138 lines): Safe Python code execution (Docker/subprocess)
- **file_ops.py** (165 lines): File creation, reading, and code extraction

### Integration Modules

- **mcp.py** (116 lines): MCP server connections and tool management

### Utility Modules

- **config.py** (68 lines): Load prompts.yaml, OLLAMA.md, .ollama-code
- **logging.py** (30 lines): Logging configuration
- **messages.py** (86 lines): Load and format messages from messages.json
- **ui.py** (110 lines): UI helpers, thinking status, ESC handling

### Main Entry

- **main.py** (198 lines): Application setup, model selection, command handling

## Benefits of Modular Structure

1. **Maintainability**: Each module has a single responsibility
2. **Testability**: Modules can be tested independently
3. **Extensibility**: Easy to add new features without touching core logic
4. **Reusability**: Modules can be imported and used separately
5. **Clarity**: Clear separation of concerns

## Total Lines

- Original: 1168 lines in one file
- Modular: ~1249 lines across 13 files
- Largest module: 336 lines (agent.py)
- Average module: ~96 lines
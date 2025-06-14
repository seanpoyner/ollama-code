# OLLAMA.md

This file provides guidance to Ollama Code Agent when working with code in this repository.

## Overview

This repository contains the Ollama Code Agent - a Python CLI tool for interacting with Ollama models with code execution capabilities.

## Key Commands

- Build: Not applicable (Python script)
- Run: `python ollama-code.py` or use the PowerShell function `ollama-code`
- Test: No tests currently implemented
- Dependencies: Install with `pip install ollama rich requests pyyaml`

## Architecture

### Main Components

1. **ollama-code.py**: Main script containing:
   - `OllamaCodeAgent`: Core agent class that handles conversations and code execution
   - `CodeSandbox`: Handles safe code execution (subprocess or Docker)
   - `FastMCPIntegration`: Optional MCP server integration
   - Message loading system from `messages.json`
   - Prompt system from `prompts.yaml`

2. **Configuration Files**:
   - `messages.json`: All user-facing messages with Rich markup
   - `prompts.yaml`: System prompts and model configurations
   - `CLAUDE.md`: Documentation for Claude Code (this tool's inspiration)

### Code Execution Flow

1. User input is processed in the main loop
2. Commands starting with `/` are handled specially (e.g., `/help`, `/prompts`)
3. Regular messages are sent to the Ollama model with the system prompt
4. Python code blocks in responses are automatically extracted and executed
5. Execution results are displayed and added to the conversation context

### Important Conventions

- All file operations use UTF-8 encoding
- Logging goes to `~/.ollama/logs/ollama-code.log`
- The script must be run from its directory or messages.json won't load
- Code execution defaults to subprocess mode for safety

## Development Guidelines

When modifying this codebase:

1. Maintain the existing message system - add new messages to `messages.json`
2. Follow the existing error handling patterns with try/except blocks
3. Use the logger for debugging information, not console.print
4. Test with multiple Ollama models to ensure compatibility
5. Keep the code execution sandboxed and safe

## Tips for Ollama Code Agent

- When users ask for help with code, provide executable Python examples
- Use the code execution feature to demonstrate solutions
- Be aware of the current working directory when dealing with file operations
- Remember that each code block executes in isolation
- When creating web applications or multi-file projects:
  - Use ```html blocks for HTML files
  - Use ```css blocks for CSS files
  - Use ```javascript blocks for JavaScript files
  - Use ```json blocks for JSON files
  - Add filename comments (e.g., <!-- File: index.html -->) to specify filenames
  - Files are automatically created from code blocks
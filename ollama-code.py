#! /usr/bin/env python

"""
ollama-code.py

Ollama Code Interface:
- Requires: ollama, rich, requests
- Run with: python ollama-code.py
- Ensure Ollama server is running on localhost:11434
"""

import ollama
import subprocess
import tempfile
import os
import json
import asyncio
import re
import sys
import logging
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt

console = Console()

# Setup logging first, before any imports that might fail
def setup_logging():
    """Setup logging to file only"""
    log_dir = Path.home() / '.ollama' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Only log to file, not console
    file_handler = logging.FileHandler(log_dir / 'ollama-code.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Only add handler if not already present
    if not logger.handlers:
        logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("ollama").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger

logger = setup_logging()

# Check for Docker availability
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.info("Docker package not available - using subprocess mode for code execution")

# FastMCP imports (optional advanced feature)
try:
    # Try different possible imports for FastMCP
    try:
        from fastmcp import FastMCPClient
    except ImportError:
        from fastmcp.client import FastMCPClient
    
    try:
        from fastmcp.server import MCPServer
    except ImportError:
        MCPServer = None
        
    MCP_AVAILABLE = True
    logger.info("FastMCP available for MCP server integration")
except ImportError:
    MCP_AVAILABLE = False
    logger.info("FastMCP not available - this is optional for advanced MCP server integration")

class CodeSandbox:
    def __init__(self):
        self.docker_client = None
        # Disable Docker by default for better reliability
        self.use_docker = False
        
        if DOCKER_AVAILABLE and self.use_docker:
            try:
                self.docker_client = docker.from_env()
                console.print("🐳 [green]Docker connected[/green]")
            except:
                console.print("⚠️ [yellow]Docker not available, using subprocess mode[/yellow]")
        else:
            console.print("⚙️ [blue]Using subprocess mode for code execution[/blue]")
    
    def execute_python(self, code, timeout=30):
        """Execute Python code safely"""
        if self.docker_client and self.use_docker:
            return self._execute_docker_python(code, timeout)
        else:
            return self._execute_subprocess_python(code, timeout)
    
    def _execute_docker_python(self, code, timeout):
        """Execute Python in Docker container"""
        try:
            # Create a temporary file to avoid shell escaping issues
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Copy file to container and execute
            container = self.docker_client.containers.run(
                'python:3.11-slim',
                f'python /tmp/script.py',
                volumes={temp_file: {'bind': '/tmp/script.py', 'mode': 'ro'}},
                remove=True,
                stdout=True,
                stderr=True,
                mem_limit='512m',
                network_disabled=False,
                detach=False
            )
            
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
            
            return {
                'success': True,
                'output': container.decode('utf-8') if isinstance(container, bytes) else str(container),
                'error': None
            }
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_file)
            except:
                pass
                
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }
    
    def _execute_subprocess_python(self, code, timeout):
        """Execute Python using subprocess"""
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name
            
            # Use a try-except for timeout parameter compatibility
            try:
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tempfile.gettempdir()
                )
            except TypeError:
                # Fallback for older Python versions without timeout
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    cwd=tempfile.gettempdir()
                )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': None,
                'error': 'Code execution timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }
        finally:
            # Clean up temp file
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass

class FastMCPIntegration:
    def __init__(self):
        self.clients = {}
        self.available_tools = {}
        self.connected_servers = {}
        
    async def connect_server(self, server_name, server_config):
        """Connect to an MCP server using FastMCP"""
        if not MCP_AVAILABLE:
            console.print("❌ [red]FastMCP not available[/red]")
            return False
            
        try:
            if server_config['type'] == 'stdio':
                client = FastMCPClient()
                await client.connect_stdio(
                    command=server_config['command'],
                    args=server_config.get('args', []),
                    env=server_config.get('env', {})
                )
            elif server_config['type'] == 'websocket':
                client = FastMCPClient()
                await client.connect_websocket(server_config['url'])
            else:
                console.print(f"❌ [red]Unsupported server type: {server_config['type']}[/red]")
                return False
            
            self.clients[server_name] = client
            self.connected_servers[server_name] = server_config
            
            # Get available tools from this server
            tools = await client.list_tools()
            for tool in tools:
                tool_key = f"{server_name}.{tool.name}"
                self.available_tools[tool_key] = {
                    'server': server_name,
                    'tool': tool,
                    'client': client
                }
            
            console.print(f"✅ [green]Connected to {server_name} ({len(tools)} tools available)[/green]")
            return True
            
        except Exception as e:
            console.print(f"❌ [red]Failed to connect to {server_name}: {e}[/red]")
            return False
    
    async def call_tool(self, tool_key, **kwargs):
        """Call an MCP tool"""
        if tool_key not in self.available_tools:
            return f"Tool {tool_key} not found"
        
        tool_info = self.available_tools[tool_key]
        client = tool_info['client']
        tool = tool_info['tool']
        
        try:
            result = await client.call_tool(tool.name, kwargs)
            return result
        except Exception as e:
            return f"Error calling {tool_key}: {e}"
    
    def get_available_tools(self):
        """Get list of all available MCP tools"""
        return list(self.available_tools.keys())
    
    def get_tool_info(self, tool_key):
        """Get detailed info about a specific tool"""
        if tool_key in self.available_tools:
            tool_info = self.available_tools[tool_key]
            return {
                'name': tool_info['tool'].name,
                'description': tool_info['tool'].description,
                'server': tool_info['server'],
                'parameters': tool_info['tool'].inputSchema
            }
        return None
    
    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.clients.clear()
        self.available_tools.clear()
        self.connected_servers.clear()

class OllamaCodeAgent:
    def __init__(self, model_name):
        self.model = model_name
        self.sandbox = CodeSandbox()
        self.mcp = FastMCPIntegration()
        self.conversation = []
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self):
        return '''You are a helpful coding assistant with the ability to write and execute code.

IMPORTANT CODE EXECUTION RULES:
- When you write Python code in ```python blocks, it will be automatically executed
- DO NOT call execute_python() from within your code blocks - this function doesn't exist in the execution context
- Just write the Python code directly in code blocks and it will run
- Each code block runs in its own isolated environment

Available capabilities:
- Write Python code in ```python blocks (automatically executed)
- create_file(filename, content): Create files
- read_file(filename): Read files  
- list_files(directory): List files in directory

When asked to write code:
1. Think through the solution step by step
2. Write clean, well-commented code in ```python blocks
3. The code will automatically execute and show results
4. Don't try to call execute_python() or other functions from within the code

Example correct usage:
```python
print("Hello, World!")
```

Example INCORRECT usage:
```python
code = "print('Hello')"
execute_python(code)  # DON'T DO THIS - execute_python doesn't exist in code context
```

You can help with:
- Writing and debugging Python scripts
- Data analysis and visualization
- File operations
- Web scraping
- API interactions
- And much more!'''

    async def connect_mcp_servers(self):
        """Connect to common MCP servers"""
        if not MCP_AVAILABLE:
            logger.info("MCP not available, skipping server connections")
            return
            
        # Example server configurations (commented out by default)
        servers = {
            # 'filesystem': {
            #     'type': 'stdio',
            #     'command': 'uvx',
            #     'args': ['mcp-server-filesystem', '--', '/tmp'],
            #     'description': 'File system operations'
            # }
        }
        
        if servers:
            console.print("🔌 [cyan]Connecting to MCP servers...[/cyan]")
            for server_name, config in servers.items():
                try:
                    await self.mcp.connect_server(server_name, config)
                except Exception as e:
                    console.print(f"⚠️ [yellow]Could not connect to {server_name}: {e}[/yellow]")
    
    def show_mcp_tools(self):
        """Display available MCP tools"""
        tools = self.mcp.get_available_tools()
        
        if not tools:
            console.print("🔧 [cyan]MCP Tools:[/cyan] None configured")
            console.print("💡 [dim]MCP (Model Context Protocol) allows integration with external tools[/dim]")
            console.print("📖 [dim]See logs for configuration details[/dim]")
            return
        
        tools_table = Table(title="🔧 Available MCP Tools", style="cyan")
        tools_table.add_column("Tool", style="bold yellow")
        tools_table.add_column("Server", style="blue")
        tools_table.add_column("Description", style="white")
        
        for tool_key in tools:
            info = self.mcp.get_tool_info(tool_key)
            if info:
                tools_table.add_row(
                    info['name'],
                    info['server'],
                    info['description'][:60] + "..." if len(info['description']) > 60 else info['description']
                )
        
        console.print(tools_table)
    
    def execute_python(self, code):
        """Tool for executing Python code"""
        console.print(Panel(
            Syntax(code, "python", theme="monokai", line_numbers=True),
            title="🐍 Executing Python Code",
            border_style="blue"
        ))
        
        logger.info(f"Executing Python code: {code[:100]}...")
        result = self.sandbox.execute_python(code)
        
        if result['success']:
            if result['output']:
                console.print(Panel(
                    result['output'],
                    title="✅ Output",
                    border_style="green"
                ))
                logger.info("Code execution successful with output")
                return f"Code executed successfully. Output:\n{result['output']}"
            else:
                console.print("✅ [green]Code executed successfully (no output)[/green]")
                logger.info("Code execution successful (no output)")
                return "Code executed successfully (no output)"
        else:
            console.print(Panel(
                result['error'],
                title="❌ Error",
                border_style="red"
            ))
            logger.error(f"Code execution failed: {result['error']}")
            return f"Code execution failed: {result['error']}"
    
    def create_file(self, filename, content):
        """Tool for creating files"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            console.print(f"📝 [green]Created file: {filename}[/green]")
            return f"File {filename} created successfully"
        except Exception as e:
            return f"Failed to create file: {e}"
    
    def read_file(self, filename):
        """Tool for reading files"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            console.print(Panel(
                Syntax(content, self._get_lexer_from_filename(filename), theme="monokai"),
                title=f"📖 {filename}",
                border_style="cyan"
            ))
            return content
        except Exception as e:
            return f"Failed to read file: {e}"
    
    def list_files(self, directory="."):
        """Tool for listing files"""
        try:
            files = list(Path(directory).iterdir())
            file_list = "\n".join([f.name for f in files])
            console.print(Panel(file_list, title=f"📁 Files in {directory}", border_style="yellow"))
            return file_list
        except Exception as e:
            return f"Failed to list files: {e}"
    
    def _get_lexer_from_filename(self, filename):
        """Get lexer name from filename for syntax highlighting"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript', 
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.md': 'markdown',
            '.txt': 'text'
        }
        ext = Path(filename).suffix.lower()
        return ext_map.get(ext, 'text')
    
    def _extract_function_calls(self, text):
        """Extract function calls from AI response"""
        calls = []
        
        # Extract Python code blocks
        code_pattern = r'```python\n(.*?)\n```'
        code_matches = re.findall(code_pattern, text, re.DOTALL)
        for code in code_matches:
            calls.append(('execute_python', code.strip()))
        
        return calls
    
    async def chat(self, user_input):
        """Main chat interface with tool execution"""
        # Add user message
        self.conversation.append({'role': 'user', 'content': user_input})
        
        # Prepare messages with system prompt  
        messages = [{'role': 'system', 'content': self.system_prompt}]
        messages.extend(self.conversation)
        
        # Get AI response
        response = ""
        try:
            with console.status("🤔 [yellow]AI is thinking...[/yellow]", spinner="dots"):
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                for chunk in stream:
                    response += chunk['message']['content']
        except Exception as e:
            console.print(f"❌ [red]Error communicating with Ollama: {e}[/red]")
            console.print("Make sure Ollama is running: ollama serve")
            return "Error: Could not connect to Ollama"
        
        # Display AI response first
        console.print(Panel(response, title="🤖 AI Assistant", border_style="green"))
        
        # Extract and execute function calls
        function_calls = self._extract_function_calls(response)
        
        execution_results = []
        for call in function_calls:
            try:
                if call[0] == 'execute_python':
                    result = self.execute_python(call[1])
                    execution_results.append(result)
            except Exception as e:
                console.print(f"❌ [red]Error executing {call[0]}: {e}[/red]")
                execution_results.append(f"Error executing {call[0]}: {e}")
        
        # Add results to response for conversation context
        if execution_results:
            response += "\n\nExecution Results:\n" + "\n".join(execution_results)
        
        # Add AI response to conversation
        self.conversation.append({'role': 'assistant', 'content': response})
        
        return response

async def main():
    console.print(Panel(
        Text("🤖 OLLAMA CODE AGENT 🤖", justify="center"),
        style="bold blue"
    ))
    
    # Check if Ollama is running
    try:
        models = ollama.list()
        console.print("✅ [green]Ollama server is running[/green]")
        logger.info(f"Connected to Ollama, found {len(models.models)} models")
        
    except Exception as e:
        console.print("❌ [red]Cannot connect to Ollama server[/red]")
        console.print(f"Error: {e}")
        console.print("Please start Ollama: ollama serve")
        logger.error(f"Failed to connect to Ollama: {e}")
        return
    
    # Extract model names properly
    try:
        available_models = []
        for model in models.models:
            # Extract the model name from the Model object
            model_name = model.model if hasattr(model, 'model') else str(model)
            available_models.append(model_name)
            
        if not available_models:
            console.print("❌ [red]No models available. Please pull a model first.[/red]")
            console.print("Example: ollama pull qwen2.5-coder:7b")
            return
            
    except Exception as e:
        console.print(f"❌ [red]Error parsing model list: {e}[/red]")
        logger.error(f"Error parsing models: {e}")
        return
    
    # Display available models and let user choose
    console.print("\n📋 [cyan]Available Models:[/cyan]")
    models_table = Table(style="cyan")
    models_table.add_column("Index", style="bold yellow")
    models_table.add_column("Model", style="white")
    
    for i, model in enumerate(available_models, 1):
        models_table.add_row(str(i), model)
    
    console.print(models_table)
    
    # Let user select model
    while True:
        try:
            choice = Prompt.ask(
                "\n🎯 Select a model by number (or press Enter for default)", 
                default="1"
            )
            
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(available_models):
                    model_name = available_models[index]
                    break
                else:
                    console.print("❌ [red]Invalid selection. Please try again.[/red]")
            else:
                console.print("❌ [red]Please enter a number.[/red]")
                
        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
            return
    
    console.print(f"🤖 [cyan]Using model: {model_name}[/cyan]")
    logger.info(f"Selected model: {model_name}")
    
    # Initialize agent
    agent = OllamaCodeAgent(model_name)
    
    # Connect to MCP servers
    await agent.connect_mcp_servers()
    
    console.print("🚀 [green]Code agent ready![/green]")
    console.print("💡 [dim]Try: 'Write Python code to analyze a CSV file'[/dim]")
    console.print("🔧 [dim]Type '/tools' to see available tools[/dim]")
    console.print("🚪 [dim]Type 'quit' or 'exit' to leave[/dim]\n")
    
    while True:
        try:
            user_input = input("\n💭 You: ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input.lower() == '/tools':
                agent.show_mcp_tools()
                continue
            elif user_input.lower() == '/help':
                console.print(Panel("""
Available commands:
- /tools  - Show available MCP tools
- /help   - Show this help
- quit    - Exit the program

Just type your request in natural language!
Examples:
- "Write a Python script to scrape a website"
- "Create a data visualization from CSV"
- "Help me debug this code"
                """, title="Help", border_style="blue"))
                continue
            
            if not user_input.strip():
                continue
            
            logger.info(f"User query: {user_input}")
            await agent.chat(user_input)
            
        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ [red]Unexpected error: {e}[/red]")
            logger.error(f"Unexpected error: {e}")
    
    # Cleanup
    await agent.mcp.disconnect_all()
    console.print("📝 [dim]Logs saved to ~/.ollama/logs/ollama-code.log[/dim]")

if __name__ == "__main__":
    asyncio.run(main())
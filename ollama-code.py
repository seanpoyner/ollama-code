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
import yaml
import threading
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner

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

# Global messages dictionary
MESSAGES = {}

def remove_comments(obj):
    """Recursively remove comment keys from a dictionary"""
    if isinstance(obj, dict):
        return {k: remove_comments(v) for k, v in obj.items() if not k.startswith("//")}
    elif isinstance(obj, list):
        return [remove_comments(item) for item in obj]
    else:
        return obj

def load_messages():
    """Load messages from messages.json file"""
    try:
        # Use absolute path resolution
        script_path = Path(os.path.abspath(__file__))
        messages_file = script_path.parent / "messages.json"
        
        if messages_file.exists():
            with open(messages_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Recursively remove comment keys
                cleaned_data = remove_comments(data)
                return cleaned_data
        else:
            logger.error(f"messages.json not found at {messages_file}")
            return {}
    except Exception as e:
        logger.error(f"Could not load messages.json: {e}")
        return {}

# Load messages immediately after defining the function
MESSAGES = load_messages()

def get_message(path, **kwargs):
    """Get a message from the messages dictionary with formatting"""
    # If messages aren't loaded, try loading them now
    global MESSAGES
    if not MESSAGES:
        MESSAGES = load_messages()
    
    keys = path.split('.')
    msg = MESSAGES
    
    # Navigate through the dictionary
    for i, key in enumerate(keys):
        if isinstance(msg, dict) and key in msg:
            msg = msg[key]
        else:
            # If we can't find the key, return the path itself
            return path
    
    # Extract text from the message
    if isinstance(msg, dict):
        # If it has a 'text' key, use that
        if 'text' in msg:
            text = msg['text']
        else:
            # Otherwise, return the path as fallback
            text = path
    else:
        # If it's a string or other type, use it directly
        text = str(msg)
    
    # Format with any provided kwargs
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            # If formatting fails, return the unformatted text
            pass
    
    return text

def load_prompts():
    """Load prompts from prompts.yaml file"""
    try:
        # Use absolute path resolution
        script_path = Path(os.path.abspath(__file__))
        prompts_file = script_path.parent / "prompts.yaml"
        if prompts_file.exists():
            with open(prompts_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            logger.info("prompts.yaml not found, using defaults")
            return None
    except Exception as e:
        logger.error(f"Could not load prompts.yaml: {e}")
        return None

def load_ollama_md():
    """Load OLLAMA.md from the current working directory"""
    try:
        # Look for OLLAMA.md in current directory
        ollama_md_path = Path.cwd() / "OLLAMA.md"
        if ollama_md_path.exists():
            with open(ollama_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"Loaded OLLAMA.md from {ollama_md_path}")
                return content
        else:
            logger.info("No OLLAMA.md found in current directory")
            return None
    except Exception as e:
        logger.error(f"Could not load OLLAMA.md: {e}")
        return None

def load_ollama_code_config():
    """Load additional configuration from .ollama-code directory"""
    try:
        config_dir = Path.cwd() / ".ollama-code"
        config = {}
        
        if config_dir.exists() and config_dir.is_dir():
            # Load any .md files in the directory
            for md_file in config_dir.glob("*.md"):
                with open(md_file, 'r', encoding='utf-8') as f:
                    config[md_file.stem] = f.read()
                    logger.info(f"Loaded {md_file.name} from .ollama-code")
            
            # Load any .yaml files for additional prompts
            for yaml_file in config_dir.glob("*.yaml"):
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config[yaml_file.stem] = yaml.safe_load(f)
                    logger.info(f"Loaded {yaml_file.name} from .ollama-code")
        
        return config if config else None
    except Exception as e:
        logger.error(f"Could not load .ollama-code config: {e}")
        return None

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
                console.print(get_message('connection.docker_connected'))
            except:
                console.print(get_message('connection.docker_not_available'))
        else:
            console.print(get_message('connection.subprocess_mode'))
    
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
            console.print(get_message('mcp.not_available'))
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
                console.print(get_message('mcp.unsupported_type', server_type=server_config['type']))
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
            
            console.print(get_message('mcp.connected', server_name=server_name, tool_count=len(tools)))
            return True
            
        except Exception as e:
            console.print(get_message('mcp.connection_failed', server_name=server_name, error=e))
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
    def __init__(self, model_name, prompts_data=None, ollama_md=None, ollama_config=None):
        self.model = model_name
        self.sandbox = CodeSandbox()
        self.mcp = FastMCPIntegration()
        self.conversation = []
        self.prompts_data = prompts_data
        self.ollama_md = ollama_md
        self.ollama_config = ollama_config
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self):
        # Try to load from prompts.yaml first
        if self.prompts_data and 'code' in self.prompts_data:
            base_prompt = self.prompts_data['code'].get('default_system', 'You are a helpful coding assistant.')
            execution_rules = self.prompts_data['code'].get('execution_rules', '')
        else:
            base_prompt = 'You are a helpful coding assistant with the ability to write and execute code.'
            execution_rules = ''
        
        full_prompt = base_prompt + execution_rules
        
        # Add OLLAMA.md content if available
        if self.ollama_md:
            full_prompt += "\n\n## Project-Specific Context (from OLLAMA.md)\n\n"
            full_prompt += self.ollama_md
            full_prompt += "\n\nPlease follow the guidelines and conventions described above when working with this codebase."
        
        # Add any additional config from .ollama-code directory
        if self.ollama_config:
            for filename, content in self.ollama_config.items():
                if isinstance(content, str):  # Markdown files
                    full_prompt += f"\n\n## Additional Context: {filename}\n\n{content}"
        
        return full_prompt

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
            console.print(get_message('mcp.connecting'))
            for server_name, config in servers.items():
                try:
                    await self.mcp.connect_server(server_name, config)
                except Exception as e:
                    console.print(get_message('mcp.connection_warning', server_name=server_name, error=e))
    
    def show_mcp_tools(self):
        """Display available MCP tools"""
        tools = self.mcp.get_available_tools()
        
        if not tools:
            console.print(get_message('mcp.no_tools'))
            console.print(get_message('mcp.info'))
            console.print(get_message('mcp.see_logs'))
            return
        
        tools_table = Table(title=get_message('mcp.available_tools_header'), style="cyan")
        tools_table.add_column(get_message('table_headers.tools.tool'), style="bold yellow")
        tools_table.add_column(get_message('table_headers.tools.server'), style="blue")
        tools_table.add_column(get_message('table_headers.tools.description'), style="white")
        
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
            title=get_message('code_execution.code_panel_title'),
            border_style="blue"
        ))
        
        logger.info(f"Executing Python code: {code[:100]}...")
        result = self.sandbox.execute_python(code)
        
        if result['success']:
            if result['output']:
                console.print(Panel(
                    result['output'],
                    title=get_message('code_execution.success_with_output.panel_title.text'),
                    border_style="green"
                ))
                logger.info("Code execution successful with output")
                return f"Code executed successfully. Output:\n{result['output']}"
            else:
                console.print(get_message('code_execution.success_no_output'))
                logger.info("Code execution successful (no output)")
                return "Code executed successfully (no output)"
        else:
            console.print(Panel(
                result['error'],
                title=get_message('code_execution.error.panel_title.text'),
                border_style="red"
            ))
            logger.error(f"Code execution failed: {result['error']}")
            return f"Code execution failed: {result['error']}"
    
    def create_file(self, filename, content):
        """Tool for creating files"""
        try:
            # Create directory if it doesn't exist
            file_path = Path(filename)
            if file_path.parent != Path('.'):
                file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            console.print(get_message('file_operations.created', filename=filename))
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
                title=get_message('file_operations.read_panel_title', filename=filename),
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
            console.print(Panel(file_list, title=get_message('file_operations.list_panel_title', directory=directory), border_style="yellow"))
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
    
    def _detect_thinking_status(self, response):
        """Detect what the AI is currently doing based on response content"""
        response_lower = response.lower()
        
        # Check for various thinking patterns
        if '```python' in response:
            return "Writing Python code..."
        elif '```html' in response:
            return "Creating HTML structure..."
        elif '```css' in response:
            return "Styling with CSS..."
        elif '```javascript' in response or '```js' in response:
            return "Writing JavaScript..."
        elif 'analyzing' in response_lower or 'looking at' in response_lower:
            return "Analyzing the request..."
        elif 'creating' in response_lower or 'building' in response_lower:
            return "Building solution..."
        elif 'let me' in response_lower or "i'll" in response_lower:
            return "Planning approach..."
        elif 'first' in response_lower or 'step' in response_lower:
            return "Breaking down steps..."
        elif 'error' in response_lower or 'issue' in response_lower:
            return "Handling issues..."
        elif 'file:' in response_lower:
            return "Preparing files..."
        elif len(response) < 50:
            return "Starting response..."
        else:
            return "Processing..."
    
    def _extract_function_calls(self, text):
        """Extract function calls from AI response"""
        calls = []
        
        # Extract Python code blocks for execution
        code_pattern = r'```python\n(.*?)\n```'
        code_matches = re.findall(code_pattern, text, re.DOTALL)
        for code in code_matches:
            # Check if this is a file creation block
            if code.strip().startswith('# File:') or code.strip().startswith('# file:'):
                # Extract filename and content
                lines = code.strip().split('\n')
                if len(lines) > 1:
                    filename_line = lines[0]
                    filename_match = re.search(r'#\s*[Ff]ile:\s*(.+)', filename_line)
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        content = '\n'.join(lines[1:])
                        calls.append(('create_file', (filename, content)))
                        continue
            # Otherwise treat as executable Python code
            calls.append(('execute_python', code.strip()))
        
        # Extract HTML files
        html_pattern = r'```html\n(.*?)\n```'
        html_matches = re.findall(html_pattern, text, re.DOTALL)
        for i, html in enumerate(html_matches):
            # Check for filename comment
            if html.strip().startswith('<!-- File:') or html.strip().startswith('<!-- file:'):
                lines = html.strip().split('\n')
                if len(lines) > 1:
                    filename_match = re.search(r'<!--\s*[Ff]ile:\s*(.+?)\s*-->', lines[0])
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        content = '\n'.join(lines[1:])
                        calls.append(('create_file', (filename, content)))
                        continue
            # If no filename specified, generate one
            filename = f'index.html' if i == 0 else f'page{i+1}.html'
            calls.append(('create_file', (filename, html.strip())))
        
        # Extract CSS files
        css_pattern = r'```css\n(.*?)\n```'
        css_matches = re.findall(css_pattern, text, re.DOTALL)
        for i, css in enumerate(css_matches):
            # Check for filename comment
            if css.strip().startswith('/* File:') or css.strip().startswith('/* file:'):
                lines = css.strip().split('\n')
                if len(lines) > 1:
                    filename_match = re.search(r'/\*\s*[Ff]ile:\s*(.+?)\s*\*/', lines[0])
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        content = '\n'.join(lines[1:])
                        calls.append(('create_file', (filename, content)))
                        continue
            # If no filename specified, generate one
            filename = f'styles.css' if i == 0 else f'styles{i+1}.css'
            calls.append(('create_file', (filename, css.strip())))
        
        # Extract JavaScript files
        js_pattern = r'```(?:javascript|js)\n(.*?)\n```'
        js_matches = re.findall(js_pattern, text, re.DOTALL)
        for i, js in enumerate(js_matches):
            # Check for filename comment
            if js.strip().startswith('// File:') or js.strip().startswith('// file:'):
                lines = js.strip().split('\n')
                if len(lines) > 1:
                    filename_match = re.search(r'//\s*[Ff]ile:\s*(.+)', lines[0])
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        content = '\n'.join(lines[1:])
                        calls.append(('create_file', (filename, content)))
                        continue
            # If no filename specified, generate one
            filename = f'script.js' if i == 0 else f'script{i+1}.js'
            calls.append(('create_file', (filename, js.strip())))
        
        # Extract JSON files
        json_pattern = r'```json\n(.*?)\n```'
        json_matches = re.findall(json_pattern, text, re.DOTALL)
        for i, json_content in enumerate(json_matches):
            # Check for filename comment
            if json_content.strip().startswith('// File:') or json_content.strip().startswith('// file:'):
                lines = json_content.strip().split('\n')
                if len(lines) > 1:
                    filename_match = re.search(r'//\s*[Ff]ile:\s*(.+)', lines[0])
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        content = '\n'.join(lines[1:])
                        calls.append(('create_file', (filename, content)))
                        continue
            # Skip if it looks like it's just example data, not a file to create
            if len(json_matches) == 1 and i == 0 and not any(keyword in text.lower() for keyword in ['create', 'file', 'save']):
                continue
            filename = f'data.json' if i == 0 else f'data{i+1}.json'
            calls.append(('create_file', (filename, json_content.strip())))
        
        return calls
    
    async def chat(self, user_input):
        """Main chat interface with tool execution"""
        # Add user message
        self.conversation.append({'role': 'user', 'content': user_input})
        
        # Prepare messages with system prompt  
        messages = [{'role': 'system', 'content': self.system_prompt}]
        messages.extend(self.conversation)
        
        # Get AI response with thinking indicators
        response = ""
        cancelled = False
        thinking_steps = []
        
        # Set up cancellation handling
        cancel_event = threading.Event()
        
        def check_for_esc():
            """Check for ESC key press in a separate thread"""
            try:
                import msvcrt  # Windows
                while not cancel_event.is_set():
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\x1b':  # ESC key
                            cancel_event.set()
                            return
                    time.sleep(0.1)
            except ImportError:
                # Unix/Linux
                import termios, tty, select
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    while not cancel_event.is_set():
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.read(1)
                            if ord(key) == 27:  # ESC key
                                cancel_event.set()
                                return
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        
        # Start ESC monitoring thread
        esc_thread = threading.Thread(target=check_for_esc, daemon=True)
        esc_thread.start()
        
        try:
            with Live(console=console, refresh_per_second=4) as live:
                # Initial thinking status
                status_text = Text()
                status_text.append("🤔 ", style="bold yellow")
                status_text.append("AI is thinking...", style="yellow")
                status_text.append("\n💡 ", style="dim")
                status_text.append("Press ESC to cancel", style="dim italic")
                
                live.update(Panel(status_text, border_style="yellow", title="Processing"))
                
                # Stream the response
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                chunk_count = 0
                last_update = time.time()
                
                for chunk in stream:
                    if cancel_event.is_set():
                        cancelled = True
                        break
                    
                    chunk_content = chunk['message']['content']
                    response += chunk_content
                    chunk_count += 1
                    
                    # Update status periodically
                    if time.time() - last_update > 0.5:
                        # Detect what the AI is doing based on content
                        thinking_status = self._detect_thinking_status(response)
                        
                        status_text = Text()
                        status_text.append(f"🤔 ", style="bold yellow")
                        status_text.append(thinking_status, style="yellow")
                        status_text.append(f"\n📝 ", style="dim")
                        status_text.append(f"Received {chunk_count} chunks...", style="dim")
                        status_text.append("\n💡 ", style="dim")
                        status_text.append("Press ESC to cancel", style="dim italic")
                        
                        live.update(Panel(status_text, border_style="yellow", title="Processing"))
                        last_update = time.time()
                
        except Exception as e:
            console.print(get_message('errors.ollama_communication', error=e))
            console.print(get_message('errors.ollama_hint'))
            return "Error: Could not connect to Ollama"
        finally:
            # Stop the ESC monitoring thread
            cancel_event.set()
        
        if cancelled:
            console.print("❌ [red]Request cancelled by user[/red]")
            return "Request cancelled"
        
        # Display AI response first
        console.print(Panel(response, title=get_message('interface.ai_response_title'), border_style="green"))
        
        # Extract and execute function calls
        function_calls = self._extract_function_calls(response)
        
        if function_calls:
            console.print(f"\n🔧 [cyan]Found {len(function_calls)} actions to perform[/cyan]")
        
        execution_results = []
        for i, call in enumerate(function_calls, 1):
            try:
                if call[0] == 'execute_python':
                    console.print(f"\n⚡ [yellow]Action {i}/{len(function_calls)}:[/yellow] Executing Python code")
                    result = self.execute_python(call[1])
                    execution_results.append(result)
                elif call[0] == 'create_file':
                    filename, content = call[1]
                    console.print(f"\n📄 [yellow]Action {i}/{len(function_calls)}:[/yellow] Creating {filename}")
                    result = self.create_file(filename, content)
                    execution_results.append(result)
            except Exception as e:
                console.print(get_message('errors.execution_failed', function=call[0], error=e))
                execution_results.append(f"Error executing {call[0]}: {e}")
        
        # Add results to response for conversation context
        if execution_results:
            response += "\n\nExecution Results:\n" + "\n".join(execution_results)
        
        # Add AI response to conversation
        self.conversation.append({'role': 'assistant', 'content': response})
        
        return response
    
    async def init_project(self, force=False, user_context=""):
        """Analyze the current project and create OLLAMA.md"""
        # Check if OLLAMA.md already exists
        ollama_md_path = Path.cwd() / "OLLAMA.md"
        if ollama_md_path.exists() and not force:
            console.print(get_message('init.already_exists'))
            return
        
        console.print(get_message('init.analyzing'))
        
        # Analyze the codebase
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', 
                          '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
                          '.r', '.m', '.mm', '.pl', '.sh', '.bash', '.ps1', '.yaml', '.yml',
                          '.json', '.xml', '.html', '.css', '.scss', '.sass', '.vue', '.svelte'}
        
        # Find all code files
        all_files = []
        for ext in code_extensions:
            all_files.extend(Path.cwd().rglob(f'*{ext}'))
        
        # Exclude common directories
        excluded_dirs = {'node_modules', '.git', '__pycache__', 'dist', 'build', 
                        'target', 'out', '.next', '.nuxt', 'coverage', '.pytest_cache',
                        'venv', '.venv', 'env', '.env'}
        
        code_files = [f for f in all_files 
                     if not any(excluded in f.parts for excluded in excluded_dirs)]
        
        if code_files:
            console.print(get_message('init.analyzing_files', count=len(code_files)))
        elif not user_context:
            # Only return if no files AND no user context
            console.print(get_message('init.no_files'))
            return
        
        # Prepare analysis prompt
        file_list = "\n".join([f"- {f.relative_to(Path.cwd())}" for f in code_files[:50]])  # Limit to 50 files
        if len(code_files) > 50:
            file_list += f"\n... and {len(code_files) - 50} more files"
        
        # Read README if exists
        readme_content = ""
        for readme_name in ['README.md', 'readme.md', 'README.rst', 'README.txt']:
            readme_path = Path.cwd() / readme_name
            if readme_path.exists():
                with open(readme_path, 'r', encoding='utf-8') as f:
                    readme_content = f.read()[:2000]  # First 2000 chars
                break
        
        # Read package files if they exist
        package_info = ""
        package_files = ['package.json', 'requirements.txt', 'Cargo.toml', 'pom.xml', 
                        'build.gradle', 'pyproject.toml', 'setup.py', 'go.mod']
        for pkg_file in package_files:
            pkg_path = Path.cwd() / pkg_file
            if pkg_path.exists():
                with open(pkg_path, 'r', encoding='utf-8') as f:
                    package_info += f"\n\n{pkg_file}:\n{f.read()[:500]}"
        
        console.print(get_message('init.generating'))
        
        # Create the analysis prompt
        if code_files:
            analysis_prompt = f"""Please analyze this codebase and create an OLLAMA.md file that will help you understand the project when working with it in the future.

{f"User-provided context about this project: {user_context}" if user_context else ""}

Project structure:
{file_list}

{f"README content:\n{readme_content}" if readme_content else "No README found"}

{f"Package files:{package_info}" if package_info else "No package files found"}

Create a comprehensive OLLAMA.md that includes:
1. Project overview
2. Key commands (build, test, run)
3. Architecture and main components
4. Important conventions and patterns
5. Development guidelines

{f"Make sure to incorporate this context: '{user_context}'" if user_context else ""}

Format it as a proper markdown file that starts with:
# OLLAMA.md

This file provides guidance to Ollama Code Agent when working with code in this repository.

Make it specific to this project, not generic."""
        else:
            # Empty directory - use user context to create OLLAMA.md
            analysis_prompt = f"""Create an OLLAMA.md file for a new project based on this description: {user_context}

This is a new/empty project directory. Based on the user's description, create an OLLAMA.md that will help guide development.

Include:
1. Project overview based on the description
2. Suggested project structure
3. Recommended technologies and frameworks
4. Key commands that will be needed (build, test, run)
5. Development guidelines and best practices

Format it as a proper markdown file that starts with:
# OLLAMA.md

This file provides guidance to Ollama Code Agent when working with code in this repository.

Make it specific to what the user described."""
        
        # Get AI to analyze and create OLLAMA.md
        response = await self.chat(analysis_prompt)
        
        # Extract the OLLAMA.md content from the response
        # Look for content between ```markdown and ``` or just use the whole response
        import re
        md_match = re.search(r'```(?:markdown|md)?\n(.*?)\n```', response, re.DOTALL)
        if md_match:
            ollama_md_content = md_match.group(1)
        else:
            # Use the whole response if no code block found
            ollama_md_content = response
        
        # Write OLLAMA.md
        with open(ollama_md_path, 'w', encoding='utf-8') as f:
            f.write(ollama_md_content)
        
        console.print(get_message('init.success'))
        logger.info(f"Created OLLAMA.md in {Path.cwd()}")

async def main():
    console.print(Panel(
        Text(get_message('app.title'), justify="center"),
        style="bold blue"
    ))
    
    # Load prompts
    prompts_data = load_prompts()
    
    # Load OLLAMA.md and .ollama-code config
    ollama_md = load_ollama_md()
    ollama_config = load_ollama_code_config()
    
    # Show status if project config was loaded
    if ollama_md:
        console.print("📚 [green]Loaded project context from OLLAMA.md[/green]")
    if ollama_config:
        console.print(f"📁 [green]Loaded {len(ollama_config)} additional config files from .ollama-code[/green]")
    
    # Check if Ollama is running
    try:
        models = ollama.list()
        console.print(get_message('connection.ollama_connected'))
        logger.info(f"Connected to Ollama, found {len(models.models)} models")
        
    except Exception as e:
        console.print(get_message('connection.ollama_not_connected'))
        console.print(f"Error: {e}")  # Keep raw error for debugging
        console.print(get_message('connection.ollama_start_hint'))
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
            console.print(get_message('models.no_models'))
            console.print(get_message('models.model_pull_example'))
            return
            
    except Exception as e:
        console.print(get_message('errors.parsing_models', error=e))
        logger.error(f"Error parsing models: {e}")
        return
    
    # Display available models and let user choose
    console.print(get_message('models.available_models_header'))
    models_table = Table(style="cyan")
    models_table.add_column(get_message('table_headers.models.index'), style="bold yellow")
    models_table.add_column(get_message('table_headers.models.model'), style="white")
    
    for i, model in enumerate(available_models, 1):
        models_table.add_row(str(i), model)
    
    console.print(models_table)
    
    # Let user select model
    while True:
        try:
            choice = Prompt.ask(
                get_message('models.model_selection_prompt'), 
                default="1"
            )
            
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(available_models):
                    model_name = available_models[index]
                    break
                else:
                    console.print(get_message('models.invalid_selection'))
            else:
                console.print(get_message('models.enter_number'))
                
        except KeyboardInterrupt:
            console.print("\n" + get_message('app.goodbye'))
            return
    
    console.print(get_message('models.model_selected', model_name=model_name))
    logger.info(f"Selected model: {model_name}")
    
    # Initialize agent with prompts data, OLLAMA.md, and config
    agent = OllamaCodeAgent(model_name, prompts_data, ollama_md, ollama_config)
    
    # Connect to MCP servers
    await agent.connect_mcp_servers()
    
    console.print(get_message('interface.ready'))
    if not ollama_md:  # Only show init hint if no OLLAMA.md exists
        console.print(get_message('interface.init_hint'))
    console.print(get_message('interface.example_hint'))
    console.print(get_message('interface.tools_hint'))
    console.print(get_message('interface.exit_hint') + "\n")
    
    while True:
        try:
            user_input = input(get_message('interface.user_prompt'))
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input.lower() == '/tools':
                agent.show_mcp_tools()
                continue
            elif user_input.lower() == '/help':
                console.print(Panel(
                    get_message('help.panel_content'),
                    title=get_message('help.panel_title'),
                    border_style="blue"
                ))
                continue
            elif user_input.lower().startswith('/init'):
                # Parse the init command
                parts = user_input.split(maxsplit=1)
                force = '--force' in user_input
                
                # Extract user context if provided
                user_context = ""
                if len(parts) > 1:
                    # Remove --force flag if present and get the context
                    context_part = parts[1].replace('--force', '').strip()
                    if context_part:
                        user_context = context_part
                
                await agent.init_project(force=force, user_context=user_context)
                continue
            elif user_input.lower() == '/prompts':
                if prompts_data and 'code' in prompts_data:
                    prompts_table = Table(title=get_message('prompts.available_prompts_header'), style="cyan")
                    prompts_table.add_column(get_message('table_headers.prompts.name'), style="bold yellow")
                    prompts_table.add_column(get_message('table_headers.prompts.description'), style="white")
                    
                    for key, value in prompts_data['code'].items():
                        if key != 'default_system' and isinstance(value, dict):
                            desc = value.get('system', '')[:60] + "..." if len(value.get('system', '')) > 60 else value.get('system', '')
                            prompts_table.add_row(key, desc)
                    
                    console.print(prompts_table)
                else:
                    console.print(get_message('prompts.no_prompts'))
                continue
            elif user_input.startswith('/prompt '):
                prompt_name = user_input.split()[1] if len(user_input.split()) > 1 else ''
                if prompt_name and prompts_data and 'code' in prompts_data and prompt_name in prompts_data['code']:
                    prompt_config = prompts_data['code'][prompt_name]
                    agent.system_prompt = prompt_config.get('system', agent.system_prompt)
                    console.print(get_message('prompts.prompt_loaded', prompt_name=prompt_name))
                else:
                    console.print(get_message('prompts.prompt_not_found', prompt_name=prompt_name))
                continue
            
            if not user_input.strip():
                continue
            
            logger.info(f"User query: {user_input}")
            await agent.chat(user_input)
            
        except KeyboardInterrupt:
            console.print("\n" + get_message('app.goodbye'))
            break
        except Exception as e:
            console.print(get_message('errors.unexpected', error=e))
            logger.error(f"Unexpected error: {e}")
    
    # Cleanup
    await agent.mcp.disconnect_all()
    console.print(get_message('app.logs_saved'))

if __name__ == "__main__":
    asyncio.run(main())
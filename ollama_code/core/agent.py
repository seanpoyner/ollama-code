"""Main Ollama Code Agent implementation"""

import ollama
import time
import logging
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

from ..core.sandbox import CodeSandbox
from ..core.file_ops import create_file, read_file, list_files
from ..core.thought_loop import ThoughtLoop
from ..core.todos import TodoManager, TodoStatus, TodoPriority
from ..core.task_validator import TaskValidator, ValidationResult
from ..core.doc_integration import DocumentationAssistant
from ..integrations.mcp import FastMCPIntegration
from ..utils.messages import get_message
from ..utils.ui import detect_thinking_status, setup_esc_handler, display_code_execution, display_execution_result

logger = logging.getLogger(__name__)
console = Console()


class OllamaCodeAgent:
    def __init__(self, model_name, prompts_data=None, ollama_md=None, ollama_config=None, todo_manager=None, ollama_client=None):
        self.model = model_name
        self.ollama_client = ollama_client or ollama.Client()
        self.mcp = FastMCPIntegration()
        self.conversation = []
        self.prompts_data = prompts_data
        self.ollama_md = ollama_md
        self.ollama_config = ollama_config
        self.todo_manager = todo_manager or TodoManager()
        self.auto_mode = False  # Auto-continue tasks
        self.auto_approve_writes = False  # Auto-approve file writes
        self.quick_analysis_mode = True  # Limit analysis task depth
        self.analysis_timeout = 30  # Seconds for analysis tasks
        self.system_prompt = self._build_system_prompt()
        self.task_validator = TaskValidator()  # Initialize task validator
        self.files_created_in_task = []  # Track files created during current task
        self.doc_assistant = DocumentationAssistant()  # Initialize documentation assistant
        self.thought_loop = ThoughtLoop(self.todo_manager, model_name=model_name, doc_assistant=self.doc_assistant)
        self.last_compaction_size = 0  # Track when we last compacted
        # Initialize sandbox with confirmation callbacks
        self.sandbox = CodeSandbox(
            write_confirmation_callback=self._confirm_file_write,
            doc_request_callback=self._handle_doc_request
        )
        self.sandbox.bash_confirmation_callback = self._confirm_bash_command
        # Add documentation tools
        self.doc_assistant.add_documentation_tools(self)
    
    def _build_system_prompt(self):
        # Try to load from prompts.yaml first
        if self.prompts_data and 'code' in self.prompts_data:
            base_prompt = self.prompts_data['code'].get('default_system', 'You are a helpful coding assistant.')
            execution_rules = self.prompts_data['code'].get('execution_rules', '')
        else:
            base_prompt = 'You are a helpful coding assistant with the ability to write and execute code.'
            execution_rules = ''
        
        full_prompt = base_prompt + execution_rules
        
        # Add CRITICAL file operation reminder
        full_prompt += "\n\n## 🚨 CRITICAL: File Operation Rules\n"
        full_prompt += "When working with files:\n"
        full_prompt += "1. Check if file exists: os.path.exists() or read_file()\n"
        full_prompt += "2. For NEW files: use write_file()\n"
        full_prompt += "3. For EXISTING files: use edit_file() for small changes\n"
        full_prompt += "4. Use ```python code blocks for ALL file operations\n"
        full_prompt += "5. Use cd() to change directories PERSISTENTLY\n\n"
        full_prompt += "Examples:\n"
        full_prompt += "```python\n"
        full_prompt += '# Change directory (persists for all subsequent operations):\n'
        full_prompt += 'cd("project-name")\n\n'
        full_prompt += '# Create new file:\n'
        full_prompt += 'write_file("app.js", """console.log("Hello");""")\n\n'
        full_prompt += '# Edit existing file:\n'
        full_prompt += 'edit_file("server.js", "Hello World", "Welcome!")\n'
        full_prompt += "```\n\n"
        full_prompt += "IMPORTANT: Always use cd() instead of bash('cd ...') to change directories!\n\n"
        
        # Add documentation tools info
        full_prompt += "## Documentation Tools Available\n"
        full_prompt += "You have access to the following documentation tools:\n"
        full_prompt += "- search_docs(query, source_type=None): Search for documentation and get relevant context\n"
        full_prompt += "- get_api_info(service, endpoint=None): Get API endpoint information\n"
        full_prompt += "- remember_solution(title, description, code, language, tags): Remember successful solutions\n"
        full_prompt += "\nUse these tools to get accurate information and prevent hallucination.\n"
        
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
    
    def _confirm_file_write(self, filename, content, exists=False):
        """Confirm file write with user"""
        # Track files created for validation
        self.files_created_in_task.append(filename)
        
        if self.auto_approve_writes:
            return True, None
        
        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.prompt import Prompt
        from pathlib import Path
        
        # Determine syntax highlighting based on file extension
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.md': 'markdown',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.sh': 'bash',
            '.bash': 'bash',
            '.txt': 'text'
        }
        
        file_ext = Path(filename).suffix.lower()
        syntax = ext_map.get(file_ext, 'text')
        
        # Show file preview with appropriate message
        if exists:
            console.print(f"\n⚠️  {get_message('file_operations.overwrite_request', filename=filename)}")
        else:
            console.print(f"\n{get_message('file_operations.write_request', filename=filename)}")
        
        # Truncate content if too long
        preview_content = content
        truncated = False
        if len(content.split('\n')) > 50:
            lines = content.split('\n')
            preview_content = '\n'.join(lines[:50])
            truncated = True
        elif len(content) > 2000:
            preview_content = content[:2000]
            truncated = True
        
        # Display content
        console.print(Panel(
            Syntax(preview_content, syntax, theme="monokai", line_numbers=True),
            title=f"📄 {filename}",
            border_style="yellow"
        ))
        
        if truncated:
            console.print("[dim]... content truncated for preview ...[/dim]")
        
        # Show options
        console.print("\n[dim]Options: [green]y[/green]es | [red]n[/red]o | [yellow]a[/yellow]ll (auto-approve for session)[/dim]")
        
        # Ask for confirmation
        while True:
            logger.info(f"Prompting user for file write confirmation: {filename}")
            choice = Prompt.ask(
                "[cyan]Approve this file write?[/cyan]",
                choices=["y", "yes", "n", "no", "a", "all"],
                default="y"
            )
            logger.info(f"User choice for {filename}: {choice}")
            
            choice = choice.lower()
            
            if choice in ["y", "yes"]:
                return True, None
            elif choice in ["a", "all"]:
                self.auto_approve_writes = True
                console.print("[green]✓ Auto-approving all file writes for this session[/green]")
                return True, None
            elif choice in ["n", "no"]:
                # Ask for feedback
                feedback = Prompt.ask(
                    "[yellow]What should be done differently?[/yellow]",
                    default="skip this file"
                )
                return False, feedback
            
            console.print("[red]Please enter: y/yes, n/no, or a/all[/red]")

    async def connect_mcp_servers(self):
        """Connect to configured MCP servers"""
        import json
        import os
        from pathlib import Path
        
        # Check for MCP configuration file
        mcp_config_paths = [
            Path.cwd() / '.ollama-code' / 'mcp_servers.json',
            Path.home() / '.ollama' / 'ollama-code' / 'mcp_servers.json'
        ]
        
        config_loaded = False
        for config_path in mcp_config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        
                    if 'servers' in config:
                        console.print(f"\n🔌 [cyan]Loading MCP servers from {config_path.relative_to(Path.home())}[/cyan]")
                        
                        for server_name, server_config in config['servers'].items():
                            if server_config.get('enabled', False):
                                # Substitute environment variables
                                if 'env' in server_config:
                                    for key, value in server_config['env'].items():
                                        if value.startswith('${') and value.endswith('}'):
                                            env_var = value[2:-1]
                                            server_config['env'][key] = os.environ.get(env_var, '')
                                
                                console.print(f"  Connecting to {server_name}...")
                                success = await self.mcp.connect_server(server_name, server_config)
                                if success:
                                    console.print(f"  ✅ [green]Connected to {server_name}[/green]")
                                else:
                                    console.print(f"  ❌ [red]Failed to connect to {server_name}[/red]")
                        
                        config_loaded = True
                        break
                        
                except Exception as e:
                    logger.error(f"Error loading MCP config from {config_path}: {e}")
        
        if not config_loaded:
            logger.info("No MCP server configuration found")
    
    def compact_conversation(self):
        """Compact the conversation history to reduce tokens"""
        if len(self.conversation) < 10:
            return "Conversation too short to compact"
        
        # Keep system messages and last few exchanges
        compacted = []
        
        # Keep all system messages
        for msg in self.conversation:
            if msg['role'] == 'system':
                compacted.append(msg)
        
        # Generate summary of older messages
        older_messages = []
        for msg in self.conversation[:-6]:  # All but last 6 messages
            if msg['role'] != 'system':
                role = "User" if msg['role'] == 'user' else "Assistant"
                # Truncate long messages
                content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
                older_messages.append(f"{role}: {content}")
        
        if older_messages:
            summary = "Previous conversation summary:\n" + "\n".join(older_messages[:10])
            compacted.append({
                'role': 'system',
                'content': f"[Conversation compacted. {len(older_messages)} older messages summarized]\n{summary}"
            })
        
        # Keep last 6 messages intact
        for msg in self.conversation[-6:]:
            if msg['role'] != 'system':
                compacted.append(msg)
        
        old_count = len(self.conversation)
        self.conversation = compacted
        new_count = len(self.conversation)
        
        return f"Compacted conversation from {old_count} to {new_count} messages"
    
    def show_mcp_tools(self):
        """Display available MCP tools"""
        from rich.table import Table
        
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
        display_code_execution(code)
        logger.info(f"Executing Python code: {code[:100]}...")
        
        # Inject documentation tools into the code
        injected_code = self._inject_documentation_tools(code)
        
        result = self.sandbox.execute_python(injected_code)
        
        # Only display result if there's output or error
        if result['output'] or result['error']:
            display_execution_result(result)
        
        if result['success']:
            if result['output']:
                logger.info("Code execution successful with output")
                return f"Code executed successfully. Output:\n{result['output']}"
            else:
                logger.info("Code execution successful (no output)")
                return "Code executed successfully (no output)"
        else:
            logger.error(f"Code execution failed: {result['error']}")
            return f"Code execution failed: {result['error']}"
    
    def write_file(self, filename, content):
        """Tool for writing files"""
        result = create_file(filename, content)
        return result
    
    def read_file_tool(self, filename):
        """Tool for reading files"""
        result = read_file(filename)
        return result
    
    def list_files_tool(self, directory="."):
        """Tool for listing files"""
        result = list_files(directory)
        return result
    
    def bash(self, command):
        """Tool for executing bash/shell commands"""
        # Confirm with user first
        if not self._confirm_bash_command(command):
            return "Command cancelled by user"
        
        from ..utils.environment import get_environment_detector
        
        # Use environment detector for proper shell execution
        env_detector = get_environment_detector()
        result = env_detector.execute_command(command, timeout=30)
        
        if result['success']:
            return result['output'] if result['output'] else "Command executed successfully (no output)"
        else:
            return f"Command failed: {result['error']}\n{result['output']}"
    
    def _confirm_bash_command(self, command):
        """Confirm bash command execution with user"""
        if self.auto_approve_writes:  # Reuse the same flag for now
            return True
        
        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.prompt import Prompt
        
        # Show command preview
        console.print(f"\n{get_message('bash_operations.command_request')}")
        
        # Determine if this is a potentially dangerous command
        dangerous_patterns = [
            'rm -rf', 'rm -r', 'del /f', 'format', 'fdisk',
            'dd if=', 'mkfs', '> /dev/', 'sudo rm',
            ':(){:|:', 'fork bomb'
        ]
        
        is_dangerous = any(pattern in command.lower() for pattern in dangerous_patterns)
        
        # Display command with appropriate styling
        panel_style = "red" if is_dangerous else "yellow"
        console.print(Panel(
            Syntax(command, "bash", theme="monokai"),
            title="🖥️ Command to Execute",
            border_style=panel_style
        ))
        
        if is_dangerous:
            console.print(get_message('bash_operations.command_warning'))
        
        # Show working directory
        import os
        console.print(f"[dim]Working directory: {os.getcwd()}[/dim]")
        
        # Show options
        console.print("\n[dim]Options: [green]y[/green]es | [red]n[/red]o | [yellow]a[/yellow]ll (auto-approve for session)[/dim]")
        
        # Ask for confirmation
        while True:
            logger.info(f"Prompting user for bash command confirmation: {command}")
            choice = Prompt.ask(
                "[cyan]Execute this command?[/cyan]",
                choices=["y", "yes", "n", "no", "a", "all"],
                default="n" if is_dangerous else "y"
            )
            logger.info(f"User choice for command: {choice}")
            
            choice = choice.lower()
            
            if choice in ["y", "yes"]:
                return True
            elif choice in ["a", "all"]:
                self.auto_approve_writes = True
                console.print(get_message('bash_operations.command_auto_approved'))
                return True
            elif choice in ["n", "no"]:
                return False
            
            console.print("[red]Please enter: y/yes, n/no, or a/all[/red]")
    
    def _handle_doc_request(self, request):
        """Handle documentation requests from sandboxed code"""
        action = request.get('action')
        
        try:
            if action == 'search_docs':
                query = request.get('query', '')
                source_type = request.get('source_type')
                logger.info(f"Processing search_docs request: {query}")
                result = self.doc_assistant.get_documentation_context(query, source_type)
                return result
            
            elif action == 'get_api_info':
                service = request.get('service', '')
                endpoint = request.get('endpoint')
                logger.info(f"Processing get_api_info request: {service}, {endpoint}")
                # Use the knowledge base directly
                endpoints = self.doc_assistant.knowledge_base.get_api_endpoints(service)
                if endpoint:
                    endpoints = [e for e in endpoints if endpoint in e['endpoint']]
                
                if not endpoints:
                    return f"No API information found for {service}"
                
                result = []
                for ep in endpoints:
                    result.append(f"## {ep['method']} {ep['endpoint']}")
                    if ep.get('parameters'):
                        result.append("**Parameters:**")
                        import json
                        result.append(f"```json\n{json.dumps(ep['parameters'], indent=2)}\n```")
                    if ep.get('examples'):
                        result.append("**Examples:**")
                        for ex in ep['examples']:
                            result.append(f"```\n{ex}\n```")
                
                return "\n".join(result)
            
            elif action == 'remember_solution':
                title = request.get('title', '')
                description = request.get('description', '')
                code = request.get('code', '')
                language = request.get('language', 'python')
                tags = request.get('tags', [])
                
                logger.info(f"Processing remember_solution request: {title}")
                self.doc_assistant.knowledge_base.add_code_pattern(
                    name=title,
                    description=description,
                    pattern=code,
                    language=language,
                    use_cases=tags,
                    examples=[]
                )
                return f"Solution remembered: {title}"
            
            else:
                logger.warning(f"Unknown documentation request action: {action}")
                return f"Unknown documentation action: {action}"
                
        except Exception as e:
            logger.error(f"Error handling documentation request: {e}")
            return f"Error processing documentation request: {str(e)}"

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count (4 chars per token average)"""
        return len(text) // 4
    
    def _check_and_compact_if_needed(self, max_context_tokens: int = None):
        """Auto-compact conversation if approaching token limit"""
        # Model-specific context limits (approximate)
        model_limits = {
            'llama3': 8192,
            'llama3.1': 131072,  # 128k context
            'llama3.2': 131072,  # 128k context
            'qwen2.5': 32768,    # 32k context
            'qwen2.5-coder': 32768,
            'mistral': 8192,
            'mixtral': 32768,
            'deepseek-coder': 16384,
            'codellama': 16384,
            'phi3': 4096,
            'gemma2': 8192,
            'command-r': 131072,  # 128k context
        }
        
        # Determine limit based on model
        if max_context_tokens is None:
            # Try to match model name to get limit
            model_lower = self.model.lower()
            for model_prefix, limit in model_limits.items():
                if model_prefix in model_lower:
                    max_context_tokens = limit
                    break
            else:
                # Default to conservative 8k if model unknown
                max_context_tokens = 8192
        
        # Estimate current conversation size
        total_chars = len(self.system_prompt)
        for msg in self.conversation:
            total_chars += len(msg['content'])
        
        estimated_tokens = self._estimate_tokens(str(total_chars))
        
        # Compact if over 75% of limit and grew significantly since last compaction
        if estimated_tokens > (max_context_tokens * 0.75):
            # Only compact if conversation grew by at least 25% since last compaction
            if self.last_compaction_size == 0 or estimated_tokens > self.last_compaction_size * 1.25:
                logger.info(f"Auto-compacting conversation: ~{estimated_tokens} tokens approaching {max_context_tokens} limit for model {self.model}")
                result = self.compact_conversation()
                console.print(f"\n♻️ [dim][Auto-compaction: {result}][/dim]\n")
                self.last_compaction_size = self._estimate_tokens(str(sum(len(msg['content']) for msg in self.conversation)))
                return True
        return False

    async def chat(self, user_input, enable_esc_cancel=True, auto_continue=False, skip_function_extraction=False, skip_task_breakdown=False, is_task_execution=False, max_tokens=None):
        """Main chat interface with tool execution"""
        # Check if this needs task decomposition (unless explicitly skipped)
        if skip_task_breakdown or is_task_execution:
            tasks, task_response = [], ""
        else:
            tasks, task_response = self.thought_loop.process_request(user_input)
        
        if tasks and task_response and not is_task_execution:
            # Display task breakdown
            console.print(Panel(task_response, title="📋 Task Planning", border_style="cyan"))
            
            # Display the todo list to show all tasks
            console.print("\n📝 [cyan]Task List Created:[/cyan]")
            self.todo_manager.display_todos()
            
            # IMPORTANT: Return immediately after creating tasks
            # Don't let the AI continue working on tasks in this call
            console.print(f"\n🚀 [cyan]Tasks created! Starting execution...[/cyan]")
            
            # Execute tasks in separate calls
            await self._execute_tasks_sequentially(enable_esc_cancel)
            return "Task execution completed. Control returned to user."
        
        # Add hint for file creation requests
        if any(keyword in user_input.lower() for keyword in ['create', 'write', 'generate']) and \
           any(keyword in user_input.lower() for keyword in ['readme', 'license', 'dockerfile', '.md', '.txt', 'file']):
            user_input += "\n\n[System: Remember to use the write_file() function to create files. Example: write_file('README.md', '# Content here'). The user will be asked to approve file writes before they are created.]"
        
        # Add user message
        self.conversation.append({'role': 'user', 'content': user_input})
        
        # Auto-compact if needed (before sending to LLM)
        self._check_and_compact_if_needed()
        
        # Prepare messages with system prompt  
        messages = [{'role': 'system', 'content': self.system_prompt}]
        messages.extend(self.conversation)
        
        # Get AI response with thinking indicators
        response = ""
        cancelled = False
        
        # Set up cancellation handling
        cancel_event = setup_esc_handler() if enable_esc_cancel else None
        
        try:
            with Live(console=console, refresh_per_second=4) as live:
                # Initial thinking status
                status_text = Text()
                status_text.append("🤔 ", style="bold yellow")
                status_text.append("AI is thinking...", style="yellow")
                if enable_esc_cancel:
                    status_text.append("\n💡 ", style="dim")
                    status_text.append("Press ESC to cancel", style="dim italic")
                
                live.update(Panel(status_text, border_style="yellow", title="Processing"))
                
                # Stream the response
                chat_options = {
                    'model': self.model,
                    'messages': messages,
                    'stream': True
                }
                
                # Add options for response length control if specified
                if max_tokens:
                    chat_options['options'] = {
                        'num_predict': max_tokens,
                        'temperature': 0.3  # Lower temperature for more focused responses
                    }
                elif is_task_execution and self._is_analysis_task(user_input):
                    # For analysis tasks, use shorter responses to prevent truncation
                    chat_options['options'] = {
                        'num_predict': 500 if self.quick_analysis_mode else 800,  # Much shorter to avoid truncation
                        'temperature': 0.3,
                        'top_p': 0.8,  # More focused responses
                        'stop': ['```\n\n```', '\n\n##', '\n\nStep']  # Stop at natural breaks
                    }
                
                stream = self.ollama_client.chat(**chat_options)
                
                chunk_count = 0
                last_update = time.time()
                
                for chunk in stream:
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        break
                    
                    chunk_content = chunk['message']['content']
                    response += chunk_content
                    chunk_count += 1
                    
                    # Update status periodically
                    if time.time() - last_update > 0.5:
                        # Detect what the AI is doing based on content
                        thinking_status = detect_thinking_status(response)
                        
                        status_text = Text()
                        status_text.append(f"🤔 ", style="bold yellow")
                        status_text.append(thinking_status, style="yellow")
                        status_text.append(f"\n📝 ", style="dim")
                        status_text.append(f"Received {chunk_count} chunks...", style="dim")
                        if enable_esc_cancel:
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
            if cancel_event:
                cancel_event.set()
        
        if cancelled:
            console.print("❌ [red]Request cancelled by user[/red]")
            return "Request cancelled"
        
        # Display AI response first
        console.print(Panel(response, title=get_message('interface.ai_response_title'), border_style="green"))
        
        # Extract and execute Python code blocks (unless skipped)
        execution_results = []
        if not skip_function_extraction:
            # Simple extraction - just find Python code blocks
            import re
            code_pattern = r'```python\s*(.*?)\n```'
            code_matches = re.findall(code_pattern, response, re.DOTALL)
            
            if code_matches:
                console.print(f"\n🔧 [cyan]Found {len(code_matches)} code blocks to execute[/cyan]")
                # Log extracted code for debugging
                for idx, code_block in enumerate(code_matches, 1):
                    logger.debug(f"Code block {idx}: {code_block[:100]}...")
            
            for i, code in enumerate(code_matches, 1):
                try:
                    console.print(f"\n⚡ [yellow]Executing code block {i}/{len(code_matches)}[/yellow]")
                    # Check if this code block contains write_file
                    if 'write_file' in code:
                        logger.info(f"Code block {i} contains write_file call")
                    result = self.execute_python(code)
                    execution_results.append(result)
                    
                    # Check if there was a file write cancellation with feedback
                    if "File write cancelled:" in result and "skip this file" not in result:
                        # Extract the feedback and add it to the conversation
                        feedback_start = result.find("File write cancelled:") + len("File write cancelled:")
                        feedback = result[feedback_start:].strip()
                        if feedback:
                            # Add feedback as a system message for the next response
                            self.conversation.append({
                                'role': 'system', 
                                'content': f"User cancelled file write with feedback: {feedback}"
                            })
                            # Trigger a follow-up response
                            console.print(f"\n💭 [dim]Processing user feedback: {feedback}[/dim]")
                            follow_up = await self.chat(
                                "Please address the user's feedback about the file write.",
                                enable_esc_cancel=enable_esc_cancel,
                                skip_function_extraction=False
                            )
                            # Remove the temporary system message
                            self.conversation.pop()
                            
                except Exception as e:
                    console.print(get_message('errors.execution_failed', function='execute_python', error=e))
                    execution_results.append(f"Error executing code: {e}")
        
        # Add results to response for conversation context
        if execution_results:
            response += "\n\nExecution Results:\n" + "\n".join(execution_results)
        
        # Add AI response to conversation
        self.conversation.append({'role': 'assistant', 'content': response})
        
        # Don't auto-continue if we're in task execution mode
        # Task continuation is handled by _execute_tasks_sequentially
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
        
        # Add documentation and content file extensions
        doc_extensions = {'.md', '.txt', '.rst', '.adoc', '.tex', '.docx', '.doc', 
                         '.pdf', '.rtf', '.odt'}
        
        # Find all code and documentation files
        all_files = []
        for ext in code_extensions.union(doc_extensions):
            all_files.extend(Path.cwd().rglob(f'*{ext}'))
        
        # Exclude common directories
        excluded_dirs = {'node_modules', '.git', '__pycache__', 'dist', 'build', 
                        'target', 'out', '.next', '.nuxt', 'coverage', '.pytest_cache',
                        'venv', '.venv', 'env', '.env', '.ollama-code'}
        
        # Separate code files and doc files
        filtered_files = [f for f in all_files 
                         if not any(excluded in f.parts for excluded in excluded_dirs)]
        
        code_files = [f for f in filtered_files if f.suffix in code_extensions]
        doc_files = [f for f in filtered_files if f.suffix in doc_extensions]
        
        total_files = len(code_files) + len(doc_files)
        if total_files > 0:
            console.print(get_message('init.analyzing_files', count=total_files))
            if doc_files:
                console.print(f"📄 [dim]Found {len(doc_files)} documentation files[/dim]")
        elif not user_context:
            # Only return if no files AND no user context
            console.print(get_message('init.no_files'))
            return
        
        # Prepare analysis prompt
        all_project_files = code_files + doc_files
        file_list = "\n".join([f"- {f.relative_to(Path.cwd())}" for f in all_project_files[:50]])  # Limit to 50 files
        if len(all_project_files) > 50:
            file_list += f"\n... and {len(all_project_files) - 50} more files"
        
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
        
        # Read key documentation files (besides README)
        doc_content = ""
        important_docs = ['CONTRIBUTING.md', 'ARCHITECTURE.md', 'API.md', 'DESIGN.md', 
                         'CHANGELOG.md', 'TODO.md', 'NOTES.md']
        for doc_name in important_docs:
            doc_path = Path.cwd() / doc_name
            if doc_path.exists():
                with open(doc_path, 'r', encoding='utf-8') as f:
                    doc_content += f"\n\n{doc_name}:\n{f.read()[:1000]}"
        
        # Read a sample of other documentation files
        other_docs_sample = ""
        other_doc_files = [f for f in doc_files if f.name not in important_docs + ['README.md', 'readme.md']]
        for doc_file in other_doc_files[:5]:  # Sample up to 5 other doc files
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content_preview = f.read()[:500]
                    other_docs_sample += f"\n\n{doc_file.relative_to(Path.cwd())}:\n{content_preview}\n..."
            except Exception as e:
                logger.warning(f"Could not read {doc_file}: {e}")
        
        # Read key source files (entry points, main files, etc.)
        key_source_content = ""
        key_file_patterns = ['main.py', 'app.py', 'index.js', 'index.ts', 'main.js', 'main.ts',
                           'server.py', 'server.js', '__init__.py', 'setup.py', 'cli.py',
                           'api.py', 'routes.py', 'App.js', 'App.tsx', 'index.html']
        
        found_key_files = []
        for pattern in key_file_patterns:
            for f in code_files:
                if f.name == pattern and f not in found_key_files:
                    found_key_files.append(f)
                    if len(found_key_files) >= 5:  # Limit to 5 key files
                        break
            if len(found_key_files) >= 5:
                break
        
        for key_file in found_key_files:
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    content = f.read()[:1000]  # First 1000 chars
                    key_source_content += f"\n\n{key_file.relative_to(Path.cwd())}:\n{content}\n..."
            except Exception as e:
                logger.warning(f"Could not read {key_file}: {e}")
        
        console.print(get_message('init.generating'))
        
        # Show what we're sending to the AI
        console.print(f"📊 [dim]Found {len(code_files) if code_files else 0} code files to analyze[/dim]")
        if doc_files:
            console.print(f"📚 [dim]Found {len(doc_files)} documentation files to analyze[/dim]")
        if readme_content:
            console.print(f"📖 [dim]Found README file[/dim]")
        if package_info:
            console.print(f"📦 [dim]Found package configuration files[/dim]")
        if doc_content:
            console.print(f"📝 [dim]Found additional documentation files[/dim]")
        if key_source_content:
            console.print(f"🔍 [dim]Reading {len(found_key_files)} key source files[/dim]")
        if user_context:
            console.print(f"💡 [dim]Using context: {user_context[:60]}{'...' if len(user_context) > 60 else ''}[/dim]")
        
        console.print(f"\n🤖 [yellow]Sending analysis request to {self.model}...[/yellow]")
        console.print(f"⏳ [dim]This may take a moment for large codebases[/dim]")
        
        # Use templates from prompts.yaml
        templates_available = self.prompts_data and 'templates' in self.prompts_data
        
        if not templates_available:
            console.print("⚠️ [yellow]Warning: prompts.yaml templates not available. Using basic prompt.[/yellow]")
            logger.warning("prompts.yaml templates not available for init command")
            # Create a basic prompt without templates
            project_name = Path.cwd().name
            if code_files:
                analysis_prompt = f"Please analyze this '{project_name}' project and create an OLLAMA.md file. Project has {len(code_files)} files. User context: {user_context}. IMPORTANT: Do NOT call this 'OLLAMA codebase' - use the actual project name '{project_name}'."
            else:
                analysis_prompt = f"Create an OLLAMA.md file for a new project named '{project_name}': {user_context}"
        else:
            templates = self.prompts_data['templates']
            
            if code_files and 'init_project_with_files' in templates:
                # Get project name from directory
                project_name = Path.cwd().name
                
                # Prepare template variables
                user_context_section = f"User-provided context about this project: {user_context}" if user_context else ""
                readme_section = f"README content:\n{readme_content}" if readme_content else "No README found"
                package_section = f"Package files:{package_info}" if package_info else "No package files found"
                doc_section = f"Documentation files:{doc_content}{other_docs_sample}" if (doc_content or other_docs_sample) else "No additional documentation found"
                source_section = f"Key source files:{key_source_content}" if key_source_content else "No key source files sampled"
                user_context_reminder = f"Make sure to incorporate this context: '{user_context}'" if user_context else ""
                
                analysis_prompt = templates['init_project_with_files'].format(
                    project_name=project_name,
                    user_context_section=user_context_section,
                    file_list=file_list,
                    readme_section=readme_section,
                    package_section=package_section,
                    doc_section=doc_section,
                    source_section=source_section,
                    user_context_reminder=user_context_reminder
                )
            elif not code_files and 'init_project_empty' in templates:
                # Get project name from directory
                project_name = Path.cwd().name
                
                analysis_prompt = templates['init_project_empty'].format(
                    project_name=project_name,
                    user_context=user_context
                )
            else:
                console.print("⚠️ [yellow]Warning: Required template not found in prompts.yaml[/yellow]")
                # Create a basic prompt
                project_name = Path.cwd().name
                if code_files:
                    analysis_prompt = f"Please analyze this '{project_name}' project and create an OLLAMA.md file. Project has {len(code_files)} files. User context: {user_context}. IMPORTANT: Do NOT call this 'OLLAMA codebase' - use the actual project name '{project_name}'."
                else:
                    analysis_prompt = f"Create an OLLAMA.md file for a new project named '{project_name}': {user_context}"
        
        # Get AI to analyze and create OLLAMA.md (disable ESC cancel and task breakdown for init, but ENABLE function extraction)
        console.print("🤖 [dim]Sending analysis request to {}...[/dim]".format(self.model))
        console.print("⏳ [dim]This may take a moment for large codebases[/dim]")
        
        response = await self.chat(analysis_prompt, enable_esc_cancel=False, skip_function_extraction=False, skip_task_breakdown=True)
        
        # Wait a moment to ensure file write completes
        import time
        time.sleep(0.5)
        
        # Check if OLLAMA.md was created
        ollama_md_path = Path.cwd() / "OLLAMA.md"
        if not ollama_md_path.exists():
            console.print("⚠️ [yellow]OLLAMA.md was not created. The AI response may not have executed properly.[/yellow]")
            logger.warning("OLLAMA.md creation failed - file not found after AI response")
        import json
        
        # Create .ollama-code directory and settings.local.json
        ollama_code_dir = Path.cwd() / '.ollama-code'
        ollama_code_dir.mkdir(exist_ok=True)
        
        settings_path = ollama_code_dir / 'settings.local.json'
        if not settings_path.exists():
            # Create default settings
            default_settings = {
                "model": self.model,
                "temperature": 0.7,
                "max_tokens": 4096,
                "project_type": "development_testing",
                "auto_continue": False
            }
            
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=2)
            
            console.print(f"📁 [green]Created {settings_path.relative_to(Path.cwd())}[/green]")
        
        # Only show success if OLLAMA.md was actually created
        if ollama_md_path.exists():
            console.print(get_message('init.success'))
            logger.info(f"Created OLLAMA.md in {Path.cwd()}")
        else:
            console.print("❌ [red]Failed to create OLLAMA.md[/red]")
            console.print("💡 [dim]Try running the command again or check the logs for errors[/dim]")
    
    async def _execute_tasks_sequentially(self, enable_esc_cancel=True):
        """Execute tasks one by one in separate AI calls"""
        import asyncio
        import os
        
        cancelled_all = False
        
        # Store initial working directory
        initial_cwd = os.getcwd()
        
        # Track project directory if created
        project_dir = None
        
        while self.thought_loop.should_continue_tasks() and not cancelled_all:
            # Get the next task context
            next_task_context = self.thought_loop.get_next_task_context()
            if not next_task_context:
                break
            
            # Check if this task creates a project directory
            if "create" in next_task_context.lower() and "project directory" in next_task_context.lower():
                # Extract directory name from task
                import re
                # Look for quoted directory name
                match = re.search(r'["\']([^"\'\/]+)["\']', next_task_context)
                if match:
                    potential_dir = match.group(1)
                    # Common project directory patterns
                    if "web" in potential_dir or "app" in potential_dir or "project" in potential_dir:
                        project_dir = potential_dir
                        logger.info(f"Detected project directory: {project_dir}")
            
            # If we have a project directory and we're creating files, ensure we're in it
            if project_dir and any(word in next_task_context.lower() for word in ["implement", "create", "frontend", "backend", "file"]):
                target_dir = os.path.join(initial_cwd, project_dir)
                if os.path.exists(target_dir) and os.getcwd() != target_dir:
                    os.chdir(target_dir)
                    logger.info(f"Changed working directory to: {target_dir}")
            
            # Clear conversation history to prevent AI from seeing previous tasks
            # Keep only the system prompt
            self.conversation = []
            
            # Reset files created tracker for this task
            self.files_created_in_task = []
            
            # Add focused system message for this specific task
            focused_system_prompt = (
                "You are working on a SINGLE SPECIFIC TASK. "
                "Complete ONLY the task given to you. "
                "Do NOT work on any other tasks. "
                "Do NOT reference or think about other tasks. "
                "Focus entirely on the current task."
            )
            
            self.conversation.append({
                'role': 'system',
                'content': focused_system_prompt
            })
            
            # Add timeout for long-running tasks
            # Use shorter timeout for analysis tasks
            is_analysis = self._is_analysis_task(next_task_context)
            timeout_seconds = self.analysis_timeout if is_analysis else 120  # 30s for analysis, 2 min for others
            
            try:
                # Execute this single task with timeout
                result = await asyncio.wait_for(
                    self.chat(
                        next_task_context, 
                        enable_esc_cancel=enable_esc_cancel,
                        auto_continue=False,  # Don't auto-continue within the task
                        skip_function_extraction=False,
                        skip_task_breakdown=True,  # Don't decompose the task further
                        is_task_execution=True  # Flag to indicate we're executing a task
                    ),
                    timeout=timeout_seconds
                )
                
                # Check if we're working with subtasks
                if self.thought_loop.current_subtasks:
                    # Try to validate and advance subtask
                    if self.thought_loop.mark_subtask_complete(result):
                        # All subtasks complete - mark main task complete
                        self.thought_loop.mark_current_task_complete(result)
                    # Continue with next subtask or task
                    continue
                
                # Check if task was cancelled by user
                if "Request cancelled" in result:
                    console.print("\n❌ [red]Task cancelled by user[/red]")
                    # Ask if they want to stop all tasks
                    from rich.prompt import Prompt
                    choice = Prompt.ask(
                        "\n[yellow]Stop all remaining tasks?[/yellow]",
                        choices=["y", "yes", "n", "no"],
                        default="y"
                    )
                    if choice.lower() in ["y", "yes"]:
                        cancelled_all = True
                        console.print("[red]Stopping all task execution.[/red]")
                        break
                    else:
                        console.print("[green]Continuing with next task...[/green]")
                
                # Check if task was aborted due to file write timeout
                elif "Timeout waiting for confirmation" in result:
                    console.print("\n❌ [red]Task aborted: User did not respond to file write confirmation[/red]")
                    console.print("[yellow]Stopping task execution. You can continue with /tasks command.[/yellow]")
                    break
                    
            except asyncio.TimeoutError:
                console.print(f"\n⏱️ [yellow]Task timed out after {timeout_seconds} seconds[/yellow]")
                console.print("[dim]Moving to next task...[/dim]")
            
            # Mark the current task as complete only if not cancelled
            if not cancelled_all and result and "Request cancelled" not in result:
                in_progress_tasks = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
                if in_progress_tasks:
                    # Check if this is a sub-task execution
                    if hasattr(self.thought_loop, 'current_subtask_manager') and self.thought_loop.current_subtask_manager:
                        subtask_mgr = self.thought_loop.current_subtask_manager
                        current_subtask = subtask_mgr.get_next_subtask()
                        
                        if current_subtask:
                            # Mark sub-task complete and check for more
                            subtask_mgr.mark_current_complete()
                            console.print(f"\n✅ [dim]Sub-task completed: {current_subtask.description}[/dim]")
                            
                            # Check if there are more sub-tasks
                            next_subtask = subtask_mgr.get_next_subtask()
                            if next_subtask:
                                # Continue with next sub-task
                                console.print(f"\n🔄 [dim]Next sub-task: {next_subtask.description}[/dim]")
                                continue  # Don't mark main task complete yet
                            else:
                                # All sub-tasks done
                                console.print(f"\n✅ [green]All sub-tasks completed![/green]")
                                self.thought_loop.current_subtask_manager = None
                    
                    # Extract task summary from result
                    task_summary = self._extract_task_summary(result)
                    
                    # Validate task completion using TaskValidator
                    current_task = in_progress_tasks[0]
                    validation_result, validation_feedback = self.task_validator.validate_task_completion(
                        current_task.content, 
                        result, 
                        self.files_created_in_task
                    )
                    
                    # Handle validation results
                    if validation_result == ValidationResult.NEEDS_RETRY:
                        console.print(f"\n⚠️ [yellow]Task validation failed: {validation_feedback}[/yellow]")
                        
                        # Implement retry logic - max 3 attempts
                        retry_count = getattr(current_task, 'retry_count', 0)
                        if retry_count < 3:
                            console.print(f"\n🔄 [cyan]Retrying task (attempt {retry_count + 2}/3)...[/cyan]")
                            
                            # Generate retry context
                            retry_context = self.task_validator.generate_retry_context(
                                current_task.content,
                                validation_feedback,
                                retry_count + 1
                            )
                            
                            # Update task retry count
                            current_task.retry_count = retry_count + 1
                            
                            # Reset conversation and add retry context
                            self.conversation = []
                            self.conversation.append({
                                'role': 'system',
                                'content': retry_context
                            })
                            
                            # Reset the task to pending so it will be retried
                            self.todo_manager.update_todo(current_task.id, status=TodoStatus.PENDING.value)
                            
                            # Continue to retry the task
                            continue
                        else:
                            console.print("\n❌ [red]Task failed after 3 attempts[/red]")
                            task_summary = f"Task failed validation: {validation_feedback}"
                            self.thought_loop.mark_current_task_complete(task_summary)
                    elif validation_result == ValidationResult.FAILED:
                        console.print(f"\n❌ [red]Task failed: {validation_feedback}[/red]")
                        task_summary = f"Task failed: {validation_feedback}"
                        self.thought_loop.mark_current_task_complete(task_summary)
                    else:
                        # Validation passed
                        console.print("\n✅ [green]Task validation passed[/green]")
                        self.thought_loop.mark_current_task_complete(task_summary)
            
            # Show progress
            console.print(f"\n{self.thought_loop.get_progress_summary()}")
            
            # Display updated todo list
            pending_tasks = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
            if pending_tasks and not cancelled_all:
                console.print("\n📊 [cyan]Task Progress:[/cyan]")
                self.todo_manager.display_todos()
                console.print(f"\n🔄 [cyan]Moving to next task...[/cyan]")
        
        # Show appropriate message based on how execution ended
        if cancelled_all:
            console.print("\n" + "=" * 50)
            console.print("\n⛔ [red]Task execution stopped by user[/red]")
            completed_tasks = self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
            pending_tasks = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
            in_progress_tasks = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
            console.print(f"\n📊 Status: {len(completed_tasks)} completed, {len(in_progress_tasks)} in progress, {len(pending_tasks)} pending")
            console.print("\n💡 [yellow]Use /tasks to see remaining tasks or start a new request[/yellow]")
            console.print("=" * 50 + "\n")
        else:
            # Show completion message when all tasks are done
            completed_tasks = self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
            total_tasks = len(self.todo_manager.todos)
            
            if not self.thought_loop.should_continue_tasks() and completed_tasks:
                console.print("\n" + "=" * 50)
                console.print("\n🎉 [bold green]All tasks completed![/bold green]")
                console.print(f"\n✅ Completed {len(completed_tasks)} out of {total_tasks} tasks")
                console.print("\n📝 Task Summary:")
                for task in completed_tasks:
                    console.print(f"   ✓ {task.content}")
                
                # Clear todos after completion
                self.todo_manager.clear()
                console.print("\n🧹 [dim]Todo list cleared[/dim]")
                
                # Clear task validator's partial progress tracking
                self.task_validator.partial_progress.clear()
                
                console.print("\n💬 [cyan]Ready for your next command![/cyan]")
                console.print("=" * 50 + "\n")
    
    def _is_analysis_task(self, input_text: str) -> bool:
        """Check if the current task is an analysis/information gathering task"""
        # Use the expanded list from task validator for consistency
        return self.task_validator._is_analysis_task(input_text.lower())
    
    def _extract_task_summary(self, result: str) -> str:
        """Extract a summary of what was accomplished from the AI response"""
        # Look for common summary patterns
        import re
        
        # Try to find explicit summaries
        summary_patterns = [
            r'summary[:\s]+(.+?)(?:\n\n|$)',
            r'accomplished[:\s]+(.+?)(?:\n\n|$)',
            r'created[:\s]+(.+?)(?:\n\n|$)',
            r'implemented[:\s]+(.+?)(?:\n\n|$)',
            r'results?[:\s]+(.+?)(?:\n\n|$)'
        ]
        
        for pattern in summary_patterns:
            match = re.search(pattern, result, re.IGNORECASE | re.DOTALL)
            if match:
                summary = match.group(1).strip()
                # Limit length
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                return summary
        
        # Look for files created
        file_pattern = r'write_file\(["\']([^"\']*)'
        created_files = re.findall(file_pattern, result)
        
        if created_files:
            return f"Created files: {', '.join(set(created_files[:5]))}"
        
        # Look for key findings from analysis
        if "=== " in result:  # Our analysis output format
            findings = []
            for line in result.split('\n'):
                if "API endpoint" in line or "model" in line.lower():
                    findings.append(line.strip())
            if findings:
                return " | ".join(findings[:3])
        
        # Extract execution output
        if "print(" in result:
            # Find printed output
            output_match = re.search(r'print\([^)]+\).*?\n(.+?)(?:\n|$)', result, re.DOTALL)
            if output_match:
                output = output_match.group(1).strip()
                return output[:200] + "..." if len(output) > 200 else output
        
        # Default: extract first meaningful line
        lines = result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.startswith('#') and not line.startswith('```'):
                return line[:200] + "..." if len(line) > 200 else line
        
        return "Task executed"
    
    def _inject_documentation_tools(self, code):
        """Inject documentation tools into Python code before execution"""
        # Create wrapper functions that call back to the agent's methods
        doc_tools_code = '''
# Documentation tools injected by agent
def search_docs(query, source_type=None):
    """Search documentation and get relevant context"""
    # This will be replaced with actual implementation
    return f"Documentation search for '{query}' (source_type={source_type})"

def get_api_info(service, endpoint=None):
    """Get API endpoint information"""
    # This will be replaced with actual implementation
    return f"API info for {service} endpoint {endpoint}"

def remember_solution(title, description, code, language='python', tags=None):
    """Remember a successful solution for future use"""
    # This will be replaced with actual implementation
    return f"Solution '{title}' remembered"

# Override the placeholders in the sandbox
import sys
sys.modules[__name__].search_docs = search_docs
sys.modules[__name__].get_api_info = get_api_info
sys.modules[__name__].remember_solution = remember_solution

'''
        
        # If we have a doc_assistant, create actual implementations
        if hasattr(self, 'doc_assistant') and self.doc_assistant:
            doc_tools_code = f'''
# Documentation tools injected by agent
import json

# Create a temporary file for communication with the agent
import tempfile
doc_comm_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
DOC_COMM_FILE = doc_comm_file.name
doc_comm_file.close()

def search_docs(query, source_type=None):
    """Search documentation and get relevant context"""
    request = {{
        'action': 'search_docs',
        'query': query,
        'source_type': source_type
    }}
    
    with open(DOC_COMM_FILE, 'w', encoding='utf-8') as f:
        json.dump(request, f)
    
    # Signal that we need documentation
    print("###DOCUMENTATION_REQUEST###", flush=True)
    print(f"Searching docs for: {{query}}", flush=True)
    
    # Wait for response
    import time
    for _ in range(100):  # Wait up to 10 seconds
        try:
            with open(DOC_COMM_FILE, 'r', encoding='utf-8') as f:
                response = json.load(f)
                if 'result' in response:
                    return response['result']
        except:
            pass
        time.sleep(0.1)
    
    return "Documentation search timed out"

def get_api_info(service, endpoint=None):
    """Get API endpoint information"""
    request = {{
        'action': 'get_api_info',
        'service': service,
        'endpoint': endpoint
    }}
    
    with open(DOC_COMM_FILE, 'w', encoding='utf-8') as f:
        json.dump(request, f)
    
    print("###DOCUMENTATION_REQUEST###", flush=True)
    print(f"Getting API info for: {{service}}", flush=True)
    
    # Wait for response
    import time
    for _ in range(100):
        try:
            with open(DOC_COMM_FILE, 'r', encoding='utf-8') as f:
                response = json.load(f)
                if 'result' in response:
                    return response['result']
        except:
            pass
        time.sleep(0.1)
    
    return "API info request timed out"

def remember_solution(title, description, code, language='python', tags=None):
    """Remember a successful solution for future use"""
    request = {{
        'action': 'remember_solution',
        'title': title,
        'description': description,
        'code': code,
        'language': language,
        'tags': tags or []
    }}
    
    with open(DOC_COMM_FILE, 'w', encoding='utf-8') as f:
        json.dump(request, f)
    
    print("###DOCUMENTATION_REQUEST###", flush=True)
    print(f"Remembering solution: {{title}}", flush=True)
    
    # Wait for response
    import time
    for _ in range(100):
        try:
            with open(DOC_COMM_FILE, 'r', encoding='utf-8') as f:
                response = json.load(f)
                if 'result' in response:
                    return response['result']
        except:
            pass
        time.sleep(0.1)
    
    return "Remember solution request timed out"

# Override the placeholders in the sandbox
import sys
sys.modules[__name__].search_docs = search_docs
sys.modules[__name__].get_api_info = get_api_info
sys.modules[__name__].remember_solution = remember_solution

'''
        
        # Prepend the documentation tools to the user's code
        return doc_tools_code + "\n\n" + code
    
    # Note: _needs_validation and _validate_task_completion methods removed
    # Now using comprehensive TaskValidator class for all validation
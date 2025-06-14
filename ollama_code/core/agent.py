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
from ..core.file_ops import create_file, read_file, list_files, extract_function_calls
from ..core.thought_loop import ThoughtLoop
from ..core.todos import TodoManager
from ..integrations.mcp import FastMCPIntegration
from ..utils.messages import get_message
from ..utils.ui import detect_thinking_status, setup_esc_handler, display_code_execution, display_execution_result

logger = logging.getLogger(__name__)
console = Console()


class OllamaCodeAgent:
    def __init__(self, model_name, prompts_data=None, ollama_md=None, ollama_config=None, todo_manager=None):
        self.model = model_name
        self.sandbox = CodeSandbox()
        self.mcp = FastMCPIntegration()
        self.conversation = []
        self.prompts_data = prompts_data
        self.ollama_md = ollama_md
        self.ollama_config = ollama_config
        self.todo_manager = todo_manager or TodoManager()
        self.thought_loop = ThoughtLoop(self.todo_manager)
        self.auto_mode = False  # Auto-continue tasks
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
        # Implementation moved to MCP module
        logger.info("MCP server connections would be initialized here")
    
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
        result = self.sandbox.execute_python(code)
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

    async def chat(self, user_input, enable_esc_cancel=True, auto_continue=False):
        """Main chat interface with tool execution"""
        # Check if this needs task decomposition
        tasks, task_response = self.thought_loop.process_request(user_input)
        
        if tasks and task_response:
            # Display task breakdown
            console.print(Panel(task_response, title="📋 Task Planning", border_style="cyan"))
            
            # Add system message about task breakdown
            user_input = f"{user_input}\n\n[System: I've broken this down into {len(tasks)} tasks. Please work through them systematically.]"
        
        # Add user message
        self.conversation.append({'role': 'user', 'content': user_input})
        
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
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
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
        
        # Extract and execute function calls
        function_calls = extract_function_calls(response)
        
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
                    result = create_file(filename, content)
                    execution_results.append(result)
            except Exception as e:
                console.print(get_message('errors.execution_failed', function=call[0], error=e))
                execution_results.append(f"Error executing {call[0]}: {e}")
        
        # Add results to response for conversation context
        if execution_results:
            response += "\n\nExecution Results:\n" + "\n".join(execution_results)
        
        # Add AI response to conversation
        self.conversation.append({'role': 'assistant', 'content': response})
        
        # Check if we should continue with next task
        if (auto_continue or self.auto_mode) and self.thought_loop.should_continue_tasks():
            # Mark current task as complete if there was one
            self.thought_loop.mark_current_task_complete()
            
            # Get next task
            next_context = self.thought_loop.get_next_task_context()
            if next_context:
                console.print(f"\n{self.thought_loop.get_progress_summary()}")
                console.print(f"\n🔄 [cyan]Continuing with next task...[/cyan]")
                # Recursively continue with next task
                await self.chat(next_context, enable_esc_cancel=enable_esc_cancel, auto_continue=True)
        
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
        
        # Show what we're sending to the AI
        console.print(f"📊 [dim]Found {len(code_files) if code_files else 0} code files to analyze[/dim]")
        if readme_content:
            console.print(f"📖 [dim]Found README file[/dim]")
        if package_info:
            console.print(f"📦 [dim]Found package configuration files[/dim]")
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
            if code_files:
                analysis_prompt = f"Please analyze this codebase and create an OLLAMA.md file. Project has {len(code_files)} files. User context: {user_context}"
            else:
                analysis_prompt = f"Create an OLLAMA.md file for a new project: {user_context}"
        else:
            templates = self.prompts_data['templates']
            
            if code_files and 'init_project_with_files' in templates:
                # Prepare template variables
                user_context_section = f"User-provided context about this project: {user_context}" if user_context else ""
                readme_section = f"README content:\n{readme_content}" if readme_content else "No README found"
                package_section = f"Package files:{package_info}" if package_info else "No package files found"
                user_context_reminder = f"Make sure to incorporate this context: '{user_context}'" if user_context else ""
                
                analysis_prompt = templates['init_project_with_files'].format(
                    user_context_section=user_context_section,
                    file_list=file_list,
                    readme_section=readme_section,
                    package_section=package_section,
                    user_context_reminder=user_context_reminder
                )
            elif not code_files and 'init_project_empty' in templates:
                analysis_prompt = templates['init_project_empty'].format(
                    user_context=user_context
                )
            else:
                console.print("⚠️ [yellow]Warning: Required template not found in prompts.yaml[/yellow]")
                # Create a basic prompt
                if code_files:
                    analysis_prompt = f"Please analyze this codebase and create an OLLAMA.md file. Project has {len(code_files)} files. User context: {user_context}"
                else:
                    analysis_prompt = f"Create an OLLAMA.md file for a new project: {user_context}"
        
        # Get AI to analyze and create OLLAMA.md (disable ESC cancel for init)
        response = await self.chat(analysis_prompt, enable_esc_cancel=False)
        
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
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
from ..integrations.mcp import FastMCPIntegration
from ..utils.messages import get_message
from ..utils.ui import detect_thinking_status, setup_esc_handler, display_code_execution, display_execution_result

logger = logging.getLogger(__name__)
console = Console()


class OllamaCodeAgent:
    def __init__(self, model_name, prompts_data=None, ollama_md=None, ollama_config=None, todo_manager=None):
        self.model = model_name
        self.mcp = FastMCPIntegration()
        self.conversation = []
        self.prompts_data = prompts_data
        self.ollama_md = ollama_md
        self.ollama_config = ollama_config
        self.todo_manager = todo_manager or TodoManager()
        self.thought_loop = ThoughtLoop(self.todo_manager)
        self.auto_mode = False  # Auto-continue tasks
        self.auto_approve_writes = False  # Auto-approve file writes
        self.system_prompt = self._build_system_prompt()
        # Initialize sandbox with confirmation callbacks
        self.sandbox = CodeSandbox(write_confirmation_callback=self._confirm_file_write)
        self.sandbox.bash_confirmation_callback = self._confirm_bash_command
    
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
    
    def _confirm_file_write(self, filename, content):
        """Confirm file write with user"""
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
        
        # Show file preview
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
            choice = Prompt.ask(
                "[cyan]Approve this file write?[/cyan]",
                choices=["y", "yes", "n", "no", "a", "all"],
                default="y"
            )
            
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
            choice = Prompt.ask(
                "[cyan]Execute this command?[/cyan]",
                choices=["y", "yes", "n", "no", "a", "all"],
                default="n" if is_dangerous else "y"
            )
            
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

    async def chat(self, user_input, enable_esc_cancel=True, auto_continue=False, skip_function_extraction=False, skip_task_breakdown=False, is_task_execution=False):
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
            return "Tasks completed"
        
        # Add hint for file creation requests
        if any(keyword in user_input.lower() for keyword in ['create', 'write', 'generate']) and \
           any(keyword in user_input.lower() for keyword in ['readme', 'license', 'dockerfile', '.md', '.txt', 'file']):
            user_input += "\n\n[System: Remember to use the write_file() function to create files. Example: write_file('README.md', '# Content here'). The user will be asked to approve file writes before they are created.]"
        
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
        
        # Extract and execute Python code blocks (unless skipped)
        execution_results = []
        if not skip_function_extraction:
            # Simple extraction - just find Python code blocks
            import re
            code_pattern = r'```python\n(.*?)\n```'
            code_matches = re.findall(code_pattern, response, re.DOTALL)
            
            if code_matches:
                console.print(f"\n🔧 [cyan]Found {len(code_matches)} code blocks to execute[/cyan]")
            
            for i, code in enumerate(code_matches, 1):
                try:
                    console.print(f"\n⚡ [yellow]Executing code block {i}/{len(code_matches)}[/yellow]")
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
        response = await self.chat(analysis_prompt, enable_esc_cancel=False, skip_function_extraction=False, skip_task_breakdown=True)
        
        # No need to extract content - the AI will use write_file() to create OLLAMA.md
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
            
            console.print(f"📁 [green]Created .ollama-code/settings.local.json[/green]")
        
        console.print(get_message('init.success'))
        logger.info(f"Created OLLAMA.md in {Path.cwd()}")
    
    async def _execute_tasks_sequentially(self, enable_esc_cancel=True):
        """Execute tasks one by one in separate AI calls"""
        while self.thought_loop.should_continue_tasks():
            # Get the next task context
            next_task_context = self.thought_loop.get_next_task_context()
            if not next_task_context:
                break
            
            # Clear conversation history to prevent AI from seeing previous tasks
            # Keep only the system prompt
            self.conversation = []
            
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
            
            # Execute this single task
            await self.chat(
                next_task_context, 
                enable_esc_cancel=enable_esc_cancel,
                auto_continue=False,  # Don't auto-continue within the task
                skip_function_extraction=False,
                skip_task_breakdown=True,  # Don't decompose the task further
                is_task_execution=True  # Flag to indicate we're executing a task
            )
            
            # Mark the current task as complete
            in_progress_tasks = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
            if in_progress_tasks:
                self.thought_loop.mark_current_task_complete()
            
            # Show progress
            console.print(f"\n{self.thought_loop.get_progress_summary()}")
            
            # Display updated todo list
            pending_tasks = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
            if pending_tasks:
                console.print("\n📊 [cyan]Task Progress:[/cyan]")
                self.todo_manager.display_todos()
                console.print(f"\n🔄 [cyan]Moving to next task...[/cyan]")
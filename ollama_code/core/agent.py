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
from ..core.todos import TodoManager
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
        console.print(f"\n📝 [bold yellow]File Write Request:[/bold yellow] {filename}")
        
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
        
        import subprocess
        import os
        
        try:
            # Use shell=True for proper command interpretation
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.getcwd()
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            if result.returncode != 0:
                return f"Command failed with exit code {result.returncode}:\n{output}"
            
            return output if output else "Command executed successfully (no output)"
            
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds"
        except Exception as e:
            return f"Error executing command: {e}"
    
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

    async def chat(self, user_input, enable_esc_cancel=True, auto_continue=False, skip_function_extraction=False):
        """Main chat interface with tool execution"""
        # Check if this needs task decomposition
        tasks, task_response = self.thought_loop.process_request(user_input)
        
        if tasks and task_response:
            # Display task breakdown
            console.print(Panel(task_response, title="📋 Task Planning", border_style="cyan"))
            
            # Add system message about task breakdown
            user_input = f"{user_input}\n\n[System: I've broken this down into {len(tasks)} tasks. Please work through them systematically.]"
        
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
                        'venv', '.venv', 'env', '.env', '.ollama-code'}
        
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
        
        # Get AI to analyze and create OLLAMA.md (disable ESC cancel and function extraction for init)
        response = await self.chat(analysis_prompt, enable_esc_cancel=False, skip_function_extraction=True)
        
        # Extract the OLLAMA.md content from the response
        # Look for content between ```markdown and ``` or just use the whole response
        import re
        import json
        
        # Try to find markdown code block - use a more robust approach
        # First try to find ```markdown or ```md blocks
        md_matches = list(re.finditer(r'```(?:markdown|md)?\n', response))
        ollama_md_content = response  # Default to whole response
        
        if md_matches:
            # Find the matching closing ``` for the first markdown block
            start_pos = md_matches[0].end()
            # Count nested code blocks to find the correct closing ```
            block_count = 1
            pos = start_pos
            while block_count > 0 and pos < len(response):
                if response[pos:pos+3] == '```':
                    # Check if this is opening or closing
                    # Look back to see if we're at start of line
                    line_start = response.rfind('\n', 0, pos) + 1
                    if line_start == pos or response[line_start:pos].strip() == '':
                        # This is a code fence at start of line
                        # Check if it's followed by a language identifier (opening) or newline (closing)
                        next_newline = response.find('\n', pos)
                        if next_newline == -1:
                            next_newline = len(response)
                        fence_content = response[pos+3:next_newline].strip()
                        if not fence_content or fence_content.isspace():
                            # Closing fence
                            block_count -= 1
                            if block_count == 0:
                                ollama_md_content = response[start_pos:pos].rstrip()
                                break
                        else:
                            # Opening fence
                            block_count += 1
                pos += 1
        
        # Write OLLAMA.md
        with open(ollama_md_path, 'w', encoding='utf-8') as f:
            f.write(ollama_md_content)
        
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
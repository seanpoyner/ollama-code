"""Thought loop processing with integrated todo management"""

import os
import re
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .todos import TodoManager, TodoStatus, TodoPriority
from .task_planner import AITaskPlanner
from .subtask_manager import SubTaskManager, SubTask, SubTaskType
from .task_decomposer import TaskDecomposer, ConcreteSubTask

console = Console()


class ThoughtLoop:
    """Manages the AI's thought process and task decomposition"""
    
    def __init__(self, todo_manager: TodoManager = None, model_name: str = None, doc_assistant=None):
        self.todo_manager = todo_manager or TodoManager()
        self.current_task_context = []
        self.thinking_steps = []
        self.model_name = model_name
        self.task_planner = AITaskPlanner(model_name) if model_name else None
        self.task_results = {}  # Store results from completed tasks
        self.current_subtask_manager = None  # Current sub-task manager
        self.doc_assistant = doc_assistant  # Documentation assistant
        self.task_attempts = {}  # Track retry attempts per task
        self.task_decomposer = TaskDecomposer()  # New task decomposer
        self.current_subtasks = []  # Current concrete subtasks
        self.current_subtask_index = 0
        self.current_todo_id = None  # Track which todo the subtasks belong to  # Index of current subtask
    
    def process_request(self, request: str) -> Tuple[List[Dict], str]:
        """
        Process a user request by breaking it down into tasks
        Returns: (tasks, initial_response)
        """
        # Analyze if this is a complex request that needs task breakdown
        if self._is_complex_request(request):
            if self.task_planner:
                # Get tasks and explanation from AI
                console.print("[dim]🤔 Analyzing request and planning tasks...[/dim]")
                tasks, explanation = self.task_planner.plan_tasks(request)
                if tasks and len(tasks) > 0:
                    self._add_tasks_to_todos(tasks)
                    initial_response = self._generate_task_response_with_explanation(tasks, explanation)
                    return tasks, initial_response
            
            # Fallback if AI planning fails
            tasks = self._decompose_request(request)
            self._add_tasks_to_todos(tasks)
            initial_response = self._generate_task_response(tasks)
            return tasks, initial_response
        else:
            # Simple request, no task breakdown needed
            return [], ""
    
    def _is_complex_request(self, request: str) -> bool:
        """Determine if a request needs task breakdown"""
        # Only truly complex multi-step operations
        complex_indicators = [
            r'build.*full.*application',
            r'create.*complete.*system',
            r'develop.*from.*scratch',
            r'implement.*entire.*project',
            r'setup.*ci.*cd.*pipeline',
            r'multiple.*steps.*required',
            r'step.*by.*step.*guide',
            r'full.*stack.*application'
        ]
        
        # Simple indicators that suggest it's NOT complex
        simple_indicators = [
            r'^what\s+is',
            r'^explain',
            r'^show\s+me',
            r'^tell\s+me',
            r'^list',
            r'^hello',
            r'^hi',
            r'^\s*$',
            r'^create\s+a\s+\w+\s+(directory|folder|file)',
            r'^make\s+a\s+\w+\s+(directory|folder|file)',
            r'^install',
            r'^run',
            r'^execute',
            r'^test'
        ]
        
        request_lower = request.lower()
        
        # Check if it's explicitly simple
        if any(re.match(pattern, request_lower) for pattern in simple_indicators):
            return False
        
        # Check if it contains complex patterns
        if any(re.search(pattern, request_lower) for pattern in complex_indicators):
            return True
        
        # Check word count - only very long requests
        words = request.split()
        if len(words) > 50:  # Increased threshold significantly
            return True
        
        # Check for multiple numbered steps or many bullet points
        if len(re.findall(r'(?:\n\d+\.|\n[-*])', request)) > 3:
            return True
        
        return False
    
    def _decompose_request(self, request: str) -> List[Dict]:
        """Break down a complex request into tasks using AI"""
        # This method is only called from the fallback path now
        # The main path uses the task planner directly in process_request
        
        # Create a truncated version for display, but preserve full context
        display_request = request if len(request) <= 100 else request[:97] + "..."
        
        # Fallback to simple task generation
        tasks = [
            {"name": f"Analyze requirements for: {display_request}", "priority": TodoPriority.HIGH},
            {"name": "Design the implementation approach", "priority": TodoPriority.HIGH},
            {"name": "Implement the main functionality", "priority": TodoPriority.HIGH},
            {"name": "Test and validate the implementation", "priority": TodoPriority.MEDIUM},
            {"name": "Document the solution", "priority": TodoPriority.LOW}
        ]
        
        return tasks
    
    def _add_tasks_to_todos(self, tasks: List[Dict]):
        """Add tasks to the todo manager"""
        for task in tasks:
            self.todo_manager.add_todo(
                content=task["name"],
                priority=task["priority"]
            )
    
    def _generate_task_response(self, tasks: List[Dict]) -> str:
        """Generate a response explaining the task breakdown"""
        response = "I'll help you with this step by step. Here's my approach:\n\n"
        
        for i, task in enumerate(tasks, 1):
            priority_emoji = {
                TodoPriority.HIGH: "🔴",
                TodoPriority.MEDIUM: "🟡",
                TodoPriority.LOW: "🟢"
            }
            emoji = priority_emoji.get(task["priority"], "⚪")
            response += f"{i}. {emoji} {task['name']}\n"
        
        response += "\nI'll work through these tasks one at a time."
        return response
    
    def _generate_task_response_with_explanation(self, tasks: List[Dict], explanation: str) -> str:
        """Generate a response with AI-provided explanation"""
        response = f"{explanation}\n\n"
        response += "Here's my task breakdown:\n\n"
        
        for i, task in enumerate(tasks, 1):
            priority_emoji = {
                TodoPriority.HIGH: "🔴",
                TodoPriority.MEDIUM: "🟡",
                TodoPriority.LOW: "🟢"
            }
            emoji = priority_emoji.get(task["priority"], "⚪")
            response += f"{i}. {emoji} {task['name']}\n"
        
        response += "\nI'll work through these tasks systematically."
        return response
    
    def get_next_task_context(self) -> Optional[str]:
        """Get context for the next task to work on"""
        # First check if we're already working on subtasks
        if self.current_subtasks and self.current_subtask_index < len(self.current_subtasks):
            # We're in the middle of executing subtasks, don't re-initialize
            current_subtask = self.current_subtasks[self.current_subtask_index]
            
            # Check dependencies
            can_execute = True
            if current_subtask.dependencies:
                for dep_id in current_subtask.dependencies:
                    dep_task = next((st for st in self.current_subtasks if st.id == dep_id), None)
                    if dep_task and not dep_task.completed:
                        can_execute = False
                        break
            
            if can_execute:
                context = f"\n🎯 [SUBTASK {self.current_subtask_index + 1}/{len(self.current_subtasks)}]\n"
                context += f"Task: {current_subtask.description}\n"
                context += f"Validation: {current_subtask.validation}\n\n"
                context += "EXECUTE ONLY THIS CODE:\n"
                context += "```python\n"
                context += current_subtask.action
                context += "\n```\n\n"
                context += "IMPORTANT: Execute ONLY the code above. Do not add anything else.\n"
                context += "The output will be validated against: " + current_subtask.validation + "\n"
                return context
        
        # Otherwise, get the next todo
        next_todo = self.todo_manager.get_next_todo()
        if next_todo:
            # Track task attempts
            if next_todo.id not in self.task_attempts:
                self.task_attempts[next_todo.id] = 0
            self.task_attempts[next_todo.id] += 1
            
            # Mark as in progress
            self.todo_manager.update_todo(next_todo.id, status=TodoStatus.IN_PROGRESS.value)
            
            # Display starting task message
            priority_colors = {
                TodoPriority.HIGH: "red",
                TodoPriority.MEDIUM: "yellow", 
                TodoPriority.LOW: "green"
            }
            color = priority_colors.get(next_todo.priority, "white")
            console.print(f"\n🚀 [cyan]Starting task:[/cyan] [{color}]{next_todo.content}[/{color}]")
            
            # Create concrete subtasks only if we don't already have them for this todo
            # This prevents recreating subtasks on each call
            if self.current_todo_id != next_todo.id or not self.current_subtasks:
                self.current_subtasks = self.task_decomposer.decompose_task(next_todo.content)
                self.current_subtask_index = 0
                self.current_todo_id = next_todo.id
                
                if self.current_subtasks:
                    console.print(f"\n🔧 [dim]Breaking down into {len(self.current_subtasks)} concrete sub-tasks:[/dim]")
                    for i, subtask in enumerate(self.current_subtasks):
                        console.print(f"   {i+1}. {subtask.description}")
            
            # Legacy subtask manager (keep for now)
            subtask_manager = SubTaskManager()
            subtasks = subtask_manager.create_subtasks_for_task(next_todo.content)
            if subtasks:
                self.current_subtask_manager = subtask_manager
            
            # Build context from previous completed tasks
            completed = self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
            pending = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
            
            # Include results from previous tasks
            previous_results = ""
            if completed:
                previous_results = "\n## Results from Previous Tasks:\n"
                for i, task in enumerate(completed, 1):
                    previous_results += f"\n### Task {i}: {task.content[:80]}...\n"
                    if task.id in self.task_results:
                        previous_results += f"{self.task_results[task.id]}\n"
                    else:
                        previous_results += "No specific results recorded.\n"
                previous_results += "\nUSE THESE RESULTS! Build on what was discovered and created in previous tasks!\n"
            
            # Get documentation context for this task
            doc_context = ""
            if hasattr(self, 'doc_assistant'):
                try:
                    # Search for relevant documentation
                    doc_context = self.doc_assistant.get_documentation_context(next_todo.content)
                    if doc_context:
                        doc_context = "\n## Relevant Documentation\n" + doc_context + "\n"
                except Exception as e:
                    console.print(f"[dim]Could not fetch documentation: {e}[/dim]")
            
            # Create focused context for this specific task
            context = f"Please complete the following task:\n\n{next_todo.content}\n\n"
            
            # Add critical project context reminder  
            if "project" in next_todo.content.lower() and "directory" in str(previous_results).lower():
                context += "🚨 PROJECT CONTEXT REMINDER:\n"
                context += "If working in a project directory, ensure all files are created with the correct paths.\n"
                context += "NEVER create files in the root directory when working on a project!\n\n"
            if doc_context:
                context += doc_context
            if previous_results:
                context += previous_results + "\n"
            
            context += "🚨 CRITICAL: STOP EXPLAINING, START DOING!\n\n"
            context += "You MUST execute Python code to create/modify files!\n"
            context += "DO NOT just describe what should be done!\n"
            context += "DO NOT show file contents without write_file() or edit_file()!\n\n"
            
            # Detect if this is a retry and analysis was already done
            is_retry = self.task_attempts.get(next_todo.id, 0) > 1
            has_previous_analysis = previous_results and any(indicator in previous_results.lower() 
                for indicator in ['files:', 'current files:', 'found', 'list_files()'])
            
            if is_retry and has_previous_analysis:
                context += "SKIP ANALYSIS - GO DIRECTLY TO IMPLEMENTATION:\n"
                context += "```python\n"
                context += "# Analysis already done. CREATE FILES NOW!\n"
                context += "# Use write_file() for new files\n"
                context += "# Use edit_file() for small changes to existing files\n"
                context += "```\n\n"
            else:
                context += "EXECUTE THIS PATTERN:\n"
                context += "```python\n"
                context += "# 1. Check what exists\n"
                context += "files = list_files()\n"
                context += "print(files)\n"
                context += "```\n\n"
                context += "```python\n"
                context += "# 2. Create/modify files based on the task\n"
                context += "# Use write_file() for new files\n"
                context += "# Use edit_file() for small changes to existing files\n"
                context += "# Use read_file() + write_file() for major changes\n"
                context += "```\n\n"
            
            # Add specific guidance for project creation tasks
            if "create" in next_todo.content.lower() and "project" in next_todo.content.lower():
                context += "🚨 PROJECT CREATION TASK - YOU MUST CREATE FILES:\n"
                context += "When creating a project directory, you MUST also create initial files:\n"
                context += "- Create the project directory structure\n"
                context += "- Initialize the project with appropriate config files\n"
                context += "- Create initial source files\n"
                context += "- Add a README.md file\n\n"
                context += "IMPORTANT: Creating just the directory is NOT enough. You MUST create files!\n\n"
            
            # Legacy: Check if we have sub-tasks to execute
            if hasattr(self, 'current_subtask_manager') and self.current_subtask_manager:
                next_subtask = self.current_subtask_manager.get_next_subtask()
                if next_subtask:
                    context += "\n[EXECUTING SUB-TASK]\n"
                    context += f"Type: {next_subtask.type.value}\n"
                    context += f"Description: {next_subtask.description}\n\n"
                    context += "Execute ONLY this code:\n"
                    context += "```python\n"
                    context += next_subtask.code
                    context += "\n```\n\n"
                    context += "IMPORTANT: Execute ONLY the code above. Do not add explanations.\n"
                    return context
            
            # Add specific guidance for information gathering tasks
            if "gather" in next_todo.content.lower() or "analyze" in next_todo.content.lower() or "document" in next_todo.content.lower():
                # Check if analysis was already done in previous results
                if previous_results and any(indicator in previous_results.lower() for indicator in 
                    ['files:', 'found:', 'current files:', 'project structure:', 'analysis complete']):
                    context += "\n[ANALYSIS ALREADY COMPLETE - SKIP TO IMPLEMENTATION]\n\n"
                    context += "Previous analysis found the necessary information.\n"
                    context += "Now IMPLEMENT based on what was discovered.\n\n"
                else:
                    context += "\n[ANALYSIS TASK - EXECUTE THESE COMMANDS]\n\n"
                    context += "Execute each code block below one at a time:\n\n"
                    context += "```python\n"
                    context += "# Read project context\n"
                    context += "content = read_file('OLLAMA.md')\n"
                    context += "print(content[:1000])\n"
                    context += "```\n\n"
                    context += "```python\n"
                    context += "# List project files\n"
                    context += "files = list_files()\n"
                    context += "print(files)\n"
                    context += "```\n\n"
                    context += "```python\n"
                    context += "# Find Python files\n"
                    context += "result = bash('find . -name \\\"*.py\\\" | head -20')\n"
                    context += "print(result)\n"
                    context += "```\n\n"
                    context += "After executing, summarize what you found.\n"
            
            # Add specific guidance for file creation tasks
            elif any(word in next_todo.content.lower() for word in ['create', 'write', 'develop', 'implement', 'script', 'test', 'endpoint', 'backend', 'service', 'websocket', 'socket']):
                context += "\n[FILE CREATION/MODIFICATION TASK - EXECUTE NOW]\n\n"
                context += "🚨 YOU MUST EXECUTE CODE TO CREATE/MODIFY FILES!\n\n"
                context += "Step 1: Check what files exist:\n"
                context += "```python\n"
                context += "import os\n"
                context += "files = list_files()\n"
                context += "print(\"Current files:\", files)\n"
                context += "```\n\n"
                context += "Step 2: Read existing files if modifying:\n"
                context += "```python\n"
                context += "# Read any files you need to modify\n"
                context += "# based on what you found in step 1\n"
                context += "```\n\n"
                context += "Step 3: CREATE THE FILES NOW:\n"
                context += "```python\n"
                context += "# STOP! DO NOT SKIP THIS STEP!\n"
                context += "# You MUST execute write_file() commands here!\n"
                context += "\n"
                context += "# Example (replace with actual implementation):\n"
                context += "write_file(\"server.js\", \"\"\"// Your server code here\"\"\")\n"
                context += "write_file(\"index.html\", \"\"\"<!-- Your HTML here -->\"\"\")\n"
                context += "\n"
                context += "# THE TASK WILL FAIL IF YOU DON'T CREATE FILES!\n"
                context += "```\n\n"
                context += "🚨 CRITICAL: EXECUTE write_file() COMMANDS NOW!\n\n"
                
                # Add bash command guidance
                context += "BASH COMMAND GUIDELINES:\n"
                context += "- Always use proper directory navigation: bash('cd project && command')\n"
                context += "- Check if directories exist before navigating: bash('ls')\n"
                context += "- Use && to chain commands that depend on each other\n"
                context += "- Use ; to run independent commands\n"
                context += "- Always quote paths with spaces\n\n"
                
                # Add directory creation guidance for GUI tasks
                if "gui" in next_todo.content.lower() or "html" in next_todo.content.lower():
                    context += "📁 FOR GUI FILES - CREATE DIRECTORIES FIRST:\n"
                    context += "- Create appropriate directory structure (e.g., public/, src/, assets/)\n"
                    context += "- Place HTML/CSS/JS files in the correct directories\n\n"
                
                # Add working directory context
                context += f"CURRENT WORKING DIRECTORY: {os.getcwd()}\n\n"
                
                # Add Ollama-specific context if relevant
                if "ollama" in next_todo.content.lower():
                    context += "OLLAMA API REFERENCE:\n"
                    context += "- Base URL: http://localhost:11434\n"
                    context += "- Chat endpoint: POST /api/chat with {model, messages, stream}\n"
                    context += "- Generate endpoint: POST /api/generate with {model, prompt, stream}\n"
                    context += "- Models endpoint: GET /api/tags\n"
                    context += "- Use 'llama2' as default model name\n\n"
                
                # Provide general file creation guidance
                context += "IMPORTANT: Always use Python code blocks with write_file() - NEVER use other language code blocks!\n"
            
            # Add specific guidance for OLLAMA.md update tasks
            elif "ollama.md" in next_todo.content.lower() and ("update" in next_todo.content.lower() or "document" in next_todo.content.lower()):
                context += "\n[Guidance for updating OLLAMA.md:]"
                context += "\n- Use read_file('OLLAMA.md') to check current content"
                context += "\n- If it doesn't exist, create it with write_file()"
                context += "\n- Add or update sections based on work completed:"
                context += "\n  - New features implemented"
                context += "\n  - API endpoints created"
                context += "\n  - Configuration changes"
                context += "\n  - Usage instructions"
                context += "\n- Keep the documentation concise and helpful\n"
            
            # Don't include information about other tasks to maintain focus
            # The AI should only know about the current task
            
            return context
        return None
    
    def mark_current_task_complete(self, result: str = None):
        """Mark the current in-progress task as complete and store result"""
        in_progress = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
        if in_progress:
            task = in_progress[0]
            self.todo_manager.update_todo(
                task.id,
                status=TodoStatus.COMPLETED.value
            )
            # Store the result if provided
            if result:
                self.task_results[task.id] = result
            # Clear subtasks when task completes
            self.current_subtasks = []
            self.current_subtask_index = 0
            self.current_todo_id = None
            # Display completion message
            console.print(f"\n✅ [green]Task completed:[/green] {task.content}")
    
    def display_thinking_process(self, thought: str):
        """Display the AI's thinking process"""
        thought_panel = Panel(
            Text(thought, style="dim italic"),
            title="💭 Thinking",
            border_style="blue",
            padding=(0, 1)
        )
        console.print(thought_panel)
    
    def should_continue_tasks(self) -> bool:
        """Check if there are more tasks to complete"""
        pending = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
        in_progress = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
        return len(pending) > 0 or len(in_progress) > 0
    
    def get_progress_summary(self) -> str:
        """Get a summary of task progress"""
        total = len(self.todo_manager.todos)
        completed = len(self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED))
        in_progress = len(self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS))
        pending = len(self.todo_manager.get_todos_by_status(TodoStatus.PENDING))
        
        if total == 0:
            return ""
        
        progress = f"📊 Progress: {completed}/{total} tasks completed"
        if in_progress > 0:
            progress += f" ({in_progress} in progress)"
        
        # Add subtask progress if applicable
        if self.current_subtasks:
            completed_subtasks = sum(1 for st in self.current_subtasks if st.completed)
            progress += f"\n   📋 Subtasks: {completed_subtasks}/{len(self.current_subtasks)} completed"
        
        return progress
    
    def mark_subtask_complete(self, output: str) -> bool:
        """Mark current subtask as complete if it passes validation"""
        if not self.current_subtasks or self.current_subtask_index >= len(self.current_subtasks):
            return False
        
        current_subtask = self.current_subtasks[self.current_subtask_index]
        
        # Validate the subtask
        if self.task_decomposer.validate_subtask(current_subtask, output):
            current_subtask.completed = True
            current_subtask.result = output
            self.current_subtask_index += 1
            
            console.print(f"✅ [green]Subtask completed:[/green] {current_subtask.description}")
            
            # Check if all subtasks are complete
            if all(st.completed for st in self.current_subtasks):
                console.print("🎉 [green]All subtasks completed![/green]")
                return True
        else:
            console.print(f"❌ [red]Subtask validation failed:[/red] {current_subtask.validation}")
        
        return False
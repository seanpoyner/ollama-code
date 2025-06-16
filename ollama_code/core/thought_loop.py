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
        # Expanded list of complex indicators
        complex_indicators = [
            'create.*application',
            'build.*system',
            'implement.*feature',
            'design.*architecture',
            'setup.*project',
            'develop.*with',
            'make.*that.*and',
            'multiple.*files',
            'full.*stack',
            'complete.*solution',
            'write.*and.*test',
            'create.*web',
            'create.*gui',
            'create.*api',
            'analyze.*and',
            'debug.*and.*fix',
            'refactor.*code',
            'add.*functionality',
            'integrate.*with',
            'multiple.*steps',
            'requires.*steps',
            'improve.*project',
            'enhance.*project',
            'do.*something.*improve',
            'several.*tasks'
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
            r'^\s*$'
        ]
        
        request_lower = request.lower()
        
        # Check if it's explicitly simple
        if any(re.match(pattern, request_lower) for pattern in simple_indicators):
            return False
        
        # Check if it contains complex patterns
        if any(re.search(pattern, request_lower) for pattern in complex_indicators):
            return True
        
        # Check word count and structure complexity
        words = request.split()
        if len(words) > 15:  # Longer requests often need breakdown
            return True
        
        # Check for multiple actions (and, then, also, plus)
        if any(word in request_lower for word in [' and ', ' then ', ' also ', ' plus ']):
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
        next_todo = self.todo_manager.get_next_todo()
        if next_todo:
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
            
            # Create sub-tasks for this task
            subtask_manager = SubTaskManager()
            subtasks = subtask_manager.create_subtasks_for_task(next_todo.content)
            if subtasks:
                console.print(f"\n🔧 [dim]Breaking down into {len(subtasks)} sub-tasks[/dim]")
                # Store subtask manager for this task
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
            if doc_context:
                context += doc_context
            if previous_results:
                context += previous_results + "\n"
            
            context += "🚨 CRITICAL EXECUTION RULES - TASK WILL FAIL IF NOT FOLLOWED:\n"
            context += "1. You MUST use ```python code blocks for ALL file creation\n"
            context += "2. You MUST call write_file() inside the Python code blocks\n"
            context += "3. NEVER use ```html, ```css, ```javascript, ```js blocks\n"
            context += "4. NEVER just show file content without write_file()\n"
            context += "5. The task validator REQUIRES actual files to be created\n\n"
            context += "⚠️ TASK VALIDATION: No files created = TASK FAILED!\n\n"
            
            context += "✅ CORRECT APPROACH (YOU MUST DO THIS):\n"
            context += "```python\n"
            context += "# Create HTML file\n"
            context += 'write_file("index.html", """<!DOCTYPE html>\n<html>\n<body>\n  <h1>Hello</h1>\n</body>\n</html>""")\n'
            context += "```\n\n"
            context += "```python\n"
            context += "# Create CSS file\n"
            context += 'write_file("styles.css", """body { margin: 0; }""")\n'
            context += "```\n\n"
            
            context += "❌ WRONG APPROACH (NEVER DO THIS):\n"
            context += "```html\n"
            context += "<!-- This doesn't create a file! -->\n"
            context += "<html>...</html>\n"
            context += "```\n\n"
            context += "Remember: The task validator will FAIL if no files are created!\n\n"
            
            # Add specific guidance for project creation tasks
            if "create" in next_todo.content.lower() and "project" in next_todo.content.lower():
                context += "🚨 PROJECT CREATION TASK - YOU MUST CREATE FILES:\n"
                context += "When creating a project directory, you MUST also create initial files:\n\n"
                context += "```python\n"
                context += "# Step 1: Create the directory\n"
                context += 'bash("mkdir -p ollama-chat")\n\n'
                context += "# Step 2: Create initial project files\n"
                context += 'write_file("ollama-chat/requirements.txt", """flask>=2.0.0\nollama>=0.1.0\nrequests>=2.25.0""")\n\n'
                context += 'write_file("ollama-chat/app.py", """from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "Ollama Chat App"\\n\\nif __name__ == "__main__":\n    app.run(debug=True)""")\n\n'
                context += 'write_file("ollama-chat/README.md", """# Ollama Chat\\n\\nA web interface for chatting with Ollama models.""")\n'
                context += "```\n\n"
                context += "IMPORTANT: Creating just the directory is NOT enough. You MUST create files!\n\n"
            
            # Check if we have sub-tasks to execute
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
            elif any(word in next_todo.content.lower() for word in ['create', 'write', 'develop', 'implement', 'script', 'test', 'endpoint', 'backend', 'service']):
                context += "\n[FILE CREATION TASK]\n\n"
                context += "CRITICAL: You MUST create actual files using Python code blocks with write_file().\n"
                context += "DO NOT just show file contents in HTML/CSS/JS code blocks.\n"
                context += "DO NOT explain what you would do - EXECUTE the code.\n\n"
                context += "CORRECT approach - use Python code blocks:\n"
                context += "```python\n"
                context += "# Create the actual file\n"
                context += 'write_file("myfile.py", """file contents here""")\n'
                context += "```\n\n"
                context += "WRONG approach - DO NOT do this:\n"
                context += "```html\n"
                context += "<!-- This just shows content, doesn't create a file -->\n"
                context += "```\n\n"
                
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
                
                # Add directory guidance if task mentions a specific project
                if "full-web-app-dev" in next_todo.content:
                    context += "IMPORTANT: File Creation Guidelines:\n"
                    context += "1. Check your current directory with: print(os.getcwd())\n"
                    context += "2. If not in 'full-web-app-dev', navigate there first\n"
                    context += "3. Create subdirectories as needed\n\n"
                    context += "Example workflow:\n"
                    context += "```python\n"
                    context += "import os\n"
                    context += "print(f\"Current directory: {os.getcwd()}\")\n"
                    context += "\n"
                    context += "# If not in project directory, navigate there\n"
                    context += "if not os.getcwd().endswith('full-web-app-dev'):\n"
                    context += "    if os.path.exists('full-web-app-dev'):\n"
                    context += "        os.chdir('full-web-app-dev')\n"
                    context += "        print(f\"Changed to: {os.getcwd()}\")\n"
                    context += "    else:\n"
                    context += "        print(\"Project directory not found!\")\n"
                    context += "```\n\n"
                
                # Provide clear examples for different file types
                context += "EXAMPLES - You MUST follow these patterns:\n\n"
                context += "For Python files:\n"
                context += "```python\n"
                context += 'write_file("app.py", """from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef home():\n    return "Hello World"\n""")\n'
                context += "```\n\n"
                context += "For HTML files:\n"
                context += "```python\n"
                context += 'write_file("index.html", """<!DOCTYPE html>\n<html>\n<head>\n    <title>My App</title>\n</head>\n<body>\n    <h1>Welcome</h1>\n</body>\n</html>""")\n'
                context += "```\n\n"
                context += "For JavaScript files:\n"
                context += "```python\n"
                context += 'write_file("script.js", """function init() {\n    console.log("App started");\n}\n\ninit();""")\n'
                context += "```\n\n"
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
        
        return progress
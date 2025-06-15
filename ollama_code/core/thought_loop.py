"""Thought loop processing with integrated todo management"""

import re
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .todos import TodoManager, TodoStatus, TodoPriority
from .task_planner import AITaskPlanner

console = Console()


class ThoughtLoop:
    """Manages the AI's thought process and task decomposition"""
    
    def __init__(self, todo_manager: TodoManager = None, model_name: str = None):
        self.todo_manager = todo_manager or TodoManager()
        self.current_task_context = []
        self.thinking_steps = []
        self.model_name = model_name
        self.task_planner = AITaskPlanner(model_name) if model_name else None
    
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
            
            # Build context from previous completed tasks
            completed = self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
            pending = self.todo_manager.get_todos_by_status(TodoStatus.PENDING)
            
            # Create focused context for this specific task
            context = f"Please complete the following task:\n\n{next_todo.content}\n\n"
            context += "Instructions:\n"
            context += "- Focus ONLY on this specific task\n"
            context += "- Complete the task thoroughly\n"
            context += "- Do NOT attempt to work on any other tasks\n"
            context += "- When done, provide a brief summary of what you accomplished\n\n"
            context += "IMPORTANT: When creating files, you MUST use the write_file() function in a Python code block:\n"
            context += "```python\n"
            context += 'write_file("filename.ext", """file contents here""")\n'
            context += "```\n"
            context += "Do NOT just show file contents in code blocks - actually create them!\n\n"
            context += "CRITICAL: If you are confused about the project context or what files exist:\n"
            context += "1. Use read_file() to read OLLAMA.md for project context\n"
            context += "2. Use list_files() to see what files exist in the project\n"
            context += "3. Use bash('ls -la') to see all files including hidden ones\n"
            context += "4. Actually implement what the task asks for - don't just say it's not possible!"
            
            # Add specific guidance for information gathering tasks
            if "gather" in next_todo.content.lower() or "analyze" in next_todo.content.lower():
                context += "\n[CRITICAL: Information Gathering Requirements]"
                context += "\n\nIMPORTANT: Keep your response CONCISE and FOCUSED!"
                context += "\n\n1. EXPLORATION STEPS (execute these):"
                context += "\n   - read_file('OLLAMA.md')  # Read project context"
                context += "\n   - list_files()  # See directory structure"
                context += "\n   - bash('find . -name \"*.py\" -o -name \"*.js\"')  # Find code files"
                context += "\n   - Read any relevant files you find"
                context += "\n\n2. RESPONSE FORMAT:"
                context += "\n   - Execute exploration commands one by one"
                context += "\n   - Keep code blocks SHORT (under 20 lines)"
                context += "\n   - Summarize findings in 3-5 bullet points"
                context += "\n   - DO NOT create long documentation files"
                context += "\n   - DO NOT use multi-line f-strings"
                context += "\n\n3. EXAMPLE GOOD RESPONSE:"
                context += "\n   ```python"
                context += "\n   # Check project structure"
                context += "\n   files = list_files()"
                context += "\n   print(files)"
                context += "\n   ```"
                context += "\n   ```python"
                context += "\n   # Read project context"
                context += "\n   content = read_file('OLLAMA.md')"
                context += "\n   print(content[:500])  # First 500 chars"
                context += "\n   ```"
                context += "\n   Then summarize: 'Found X files, project uses Y framework...'"
                context += "\n\n4. AVOID:"
                context += "\n   - Long code blocks that might get truncated"
                context += "\n   - Creating documentation files during analysis"
                context += "\n   - Multi-line f-strings or complex string formatting"
                context += "\n   - Writing more than necessary for analysis\n"
            
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
    
    def mark_current_task_complete(self):
        """Mark the current in-progress task as complete"""
        in_progress = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
        if in_progress:
            task = in_progress[0]
            self.todo_manager.update_todo(
                task.id,
                status=TodoStatus.COMPLETED.value
            )
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
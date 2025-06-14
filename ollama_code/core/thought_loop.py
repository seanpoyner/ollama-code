"""Thought loop processing with integrated todo management"""

import re
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .todos import TodoManager, TodoStatus, TodoPriority

console = Console()


class ThoughtLoop:
    """Manages the AI's thought process and task decomposition"""
    
    def __init__(self, todo_manager: TodoManager = None):
        self.todo_manager = todo_manager or TodoManager()
        self.current_task_context = []
        self.thinking_steps = []
    
    def process_request(self, request: str) -> Tuple[List[Dict], str]:
        """
        Process a user request by breaking it down into tasks
        Returns: (tasks, initial_response)
        """
        # Analyze if this is a complex request that needs task breakdown
        if self._is_complex_request(request):
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
            'integrate.*with'
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
        """Break down a complex request into tasks"""
        tasks = []
        
        # Common task patterns based on request type
        if 'web' in request.lower() and ('gui' in request.lower() or 'interface' in request.lower()):
            tasks = [
                {"name": "Design the application structure", "priority": TodoPriority.HIGH},
                {"name": "Create HTML structure", "priority": TodoPriority.HIGH},
                {"name": "Add CSS styling", "priority": TodoPriority.MEDIUM},
                {"name": "Implement JavaScript functionality", "priority": TodoPriority.HIGH},
                {"name": "Add API integration", "priority": TodoPriority.HIGH},
                {"name": "Test and refine the interface", "priority": TodoPriority.MEDIUM}
            ]
        elif 'api' in request.lower() or 'backend' in request.lower():
            tasks = [
                {"name": "Define API endpoints", "priority": TodoPriority.HIGH},
                {"name": "Set up server framework", "priority": TodoPriority.HIGH},
                {"name": "Implement data models", "priority": TodoPriority.HIGH},
                {"name": "Create route handlers", "priority": TodoPriority.HIGH},
                {"name": "Add error handling", "priority": TodoPriority.MEDIUM},
                {"name": "Write API documentation", "priority": TodoPriority.LOW}
            ]
        elif 'script' in request.lower() or 'automate' in request.lower():
            tasks = [
                {"name": "Analyze requirements", "priority": TodoPriority.HIGH},
                {"name": "Design script structure", "priority": TodoPriority.HIGH},
                {"name": "Implement core functionality", "priority": TodoPriority.HIGH},
                {"name": "Add error handling", "priority": TodoPriority.MEDIUM},
                {"name": "Test the script", "priority": TodoPriority.MEDIUM}
            ]
        else:
            # Generic complex task breakdown
            tasks = [
                {"name": "Understand and analyze requirements", "priority": TodoPriority.HIGH},
                {"name": "Design the solution architecture", "priority": TodoPriority.HIGH},
                {"name": "Implement core functionality", "priority": TodoPriority.HIGH},
                {"name": "Add supporting features", "priority": TodoPriority.MEDIUM},
                {"name": "Test and refine", "priority": TodoPriority.MEDIUM}
            ]
        
        # Customize tasks based on specific request details
        for task in tasks:
            task["context"] = request
        
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
        
        response += "\nLet me start with the first task..."
        return response
    
    def get_next_task_context(self) -> Optional[str]:
        """Get context for the next task to work on"""
        next_todo = self.todo_manager.get_next_todo()
        if next_todo:
            # Mark as in progress
            self.todo_manager.update_todo(next_todo.id, status=TodoStatus.IN_PROGRESS.value)
            
            # Build context from previous completed tasks
            completed = self.todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
            context = f"Working on: {next_todo.content}\n"
            
            if completed:
                context += "\nPreviously completed:\n"
                for todo in completed[-3:]:  # Last 3 completed tasks
                    context += f"- {todo.content}\n"
            
            return context
        return None
    
    def mark_current_task_complete(self):
        """Mark the current in-progress task as complete"""
        in_progress = self.todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS)
        if in_progress:
            self.todo_manager.update_todo(
                in_progress[0].id,
                status=TodoStatus.COMPLETED.value
            )
    
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
"""Todo list management for tracking tasks across sessions"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoItem:
    def __init__(self, content: str, priority: TodoPriority = TodoPriority.MEDIUM, 
                 status: TodoStatus = TodoStatus.PENDING, id: str = None,
                 created_at: str = None, updated_at: str = None):
        self.id = id or str(uuid.uuid4())
        self.content = content
        self.priority = priority
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TodoItem':
        return cls(
            content=data["content"],
            priority=TodoPriority(data["priority"]),
            status=TodoStatus(data["status"]),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )


class TodoManager:
    def __init__(self, todos_file: Path = None):
        # Create .ollama-code directory if it doesn't exist
        ollama_code_dir = Path.cwd() / ".ollama-code"
        ollama_code_dir.mkdir(exist_ok=True)
        
        # Use .ollama-code directory for todos file
        self.todos_file = todos_file or ollama_code_dir / "todos.json"
        self.todos: List[TodoItem] = []
        self.load_todos()
    
    def load_todos(self):
        """Load todos from file"""
        if self.todos_file.exists():
            try:
                with open(self.todos_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.todos = [TodoItem.from_dict(item) for item in data.get("todos", [])]
            except Exception as e:
                console.print(f"⚠️ [yellow]Could not load todos: {e}[/yellow]")
                self.todos = []
        else:
            self.todos = []
    
    def save_todos(self):
        """Save todos to file"""
        try:
            data = {
                "todos": [todo.to_dict() for todo in self.todos],
                "last_updated": datetime.now().isoformat()
            }
            with open(self.todos_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"❌ [red]Could not save todos: {e}[/red]")
    
    def add_todo(self, content: str, priority: TodoPriority = TodoPriority.MEDIUM) -> TodoItem:
        """Add a new todo"""
        todo = TodoItem(content, priority)
        self.todos.append(todo)
        self.save_todos()
        return todo
    
    def update_todo(self, todo_id: str, **kwargs) -> Optional[TodoItem]:
        """Update a todo by ID"""
        for todo in self.todos:
            if todo.id == todo_id:
                if "content" in kwargs:
                    todo.content = kwargs["content"]
                if "priority" in kwargs:
                    todo.priority = TodoPriority(kwargs["priority"])
                if "status" in kwargs:
                    todo.status = TodoStatus(kwargs["status"])
                todo.updated_at = datetime.now().isoformat()
                self.save_todos()
                return todo
        return None
    
    def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo by ID"""
        for i, todo in enumerate(self.todos):
            if todo.id == todo_id:
                del self.todos[i]
                self.save_todos()
                return True
        return False
    
    def get_todo(self, todo_id: str) -> Optional[TodoItem]:
        """Get a todo by ID"""
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None
    
    def get_todos_by_status(self, status: TodoStatus) -> List[TodoItem]:
        """Get all todos with a specific status"""
        return [todo for todo in self.todos if todo.status == status]
    
    def get_next_todo(self) -> Optional[TodoItem]:
        """Get the next pending or in-progress todo (prioritized by high > medium > low)"""
        # First check in-progress todos
        in_progress = self.get_todos_by_status(TodoStatus.IN_PROGRESS)
        if in_progress:
            return in_progress[0]
        
        # Then check pending todos by priority
        pending = self.get_todos_by_status(TodoStatus.PENDING)
        for priority in [TodoPriority.HIGH, TodoPriority.MEDIUM, TodoPriority.LOW]:
            for todo in pending:
                if todo.priority == priority:
                    return todo
        
        return None
    
    def display_todos(self, status_filter: Optional[TodoStatus] = None):
        """Display todos in a nice table"""
        todos_to_show = self.todos
        if status_filter:
            todos_to_show = self.get_todos_by_status(status_filter)
        
        if not todos_to_show:
            console.print("📋 [dim]No todos found[/dim]")
            return
        
        table = Table(title="📋 Todo List", style="cyan")
        table.add_column("#", style="bold yellow", width=3)
        table.add_column("Status", width=12)
        table.add_column("Priority", width=8)
        table.add_column("Task", style="white")
        table.add_column("ID", style="dim", width=8)
        
        # Define status emojis and colors
        status_display = {
            TodoStatus.PENDING: ("⏳", "yellow"),
            TodoStatus.IN_PROGRESS: ("🔄", "blue"),
            TodoStatus.COMPLETED: ("✅", "green"),
            TodoStatus.CANCELLED: ("❌", "red")
        }
        
        priority_display = {
            TodoPriority.HIGH: ("[red]HIGH[/red]", 1),
            TodoPriority.MEDIUM: ("[yellow]MEDIUM[/yellow]", 2),
            TodoPriority.LOW: ("[dim]LOW[/dim]", 3)
        }
        
        # Sort by status (in-progress first), then priority
        sorted_todos = sorted(todos_to_show, 
                            key=lambda t: (
                                0 if t.status == TodoStatus.IN_PROGRESS else 1,
                                priority_display[t.priority][1],
                                t.created_at
                            ))
        
        for i, todo in enumerate(sorted_todos, 1):
            emoji, color = status_display[todo.status]
            priority_text, _ = priority_display[todo.priority]
            
            table.add_row(
                str(i),
                f"{emoji} [{color}]{todo.status.value}[/{color}]",
                priority_text,
                todo.content[:60] + "..." if len(todo.content) > 60 else todo.content,
                todo.id[:8]
            )
        
        console.print(table)
        
        # Show summary
        pending_count = len(self.get_todos_by_status(TodoStatus.PENDING))
        in_progress_count = len(self.get_todos_by_status(TodoStatus.IN_PROGRESS))
        completed_count = len(self.get_todos_by_status(TodoStatus.COMPLETED))
        
        console.print(f"\n📊 Summary: {pending_count} pending, {in_progress_count} in progress, {completed_count} completed")
    
    def display_next_todo(self):
        """Display the next todo to work on"""
        next_todo = self.get_next_todo()
        if next_todo:
            priority_colors = {
                TodoPriority.HIGH: "red",
                TodoPriority.MEDIUM: "yellow",
                TodoPriority.LOW: "dim"
            }
            
            color = priority_colors[next_todo.priority]
            status_text = "🔄 In Progress" if next_todo.status == TodoStatus.IN_PROGRESS else "⏳ Next Up"
            
            console.print(Panel(
                f"[{color}]{next_todo.content}[/{color}]\n\n"
                f"Priority: [{color}]{next_todo.priority.value.upper()}[/{color}]\n"
                f"ID: [dim]{next_todo.id[:8]}[/dim]",
                title=f"{status_text}",
                border_style="blue"
            ))
        else:
            console.print("✨ [green]All todos completed![/green]")
    
    def parse_todo_command(self, command: str) -> Dict:
        """Parse todo commands like: /todo add high Fix the bug"""
        parts = command.split(maxsplit=3)
        
        if len(parts) < 2:
            return {"action": "list"}
        
        action = parts[1].lower()
        
        if action == "add" and len(parts) >= 4:
            priority_str = parts[2].lower()
            content = parts[3]
            priority = TodoPriority.MEDIUM
            
            if priority_str in ["high", "medium", "low"]:
                priority = TodoPriority(priority_str)
            else:
                # If priority not specified, treat as content
                content = f"{parts[2]} {parts[3]}"
            
            return {"action": "add", "priority": priority, "content": content}
        
        elif action == "done" and len(parts) >= 3:
            return {"action": "done", "id": parts[2]}
        
        elif action == "start" and len(parts) >= 3:
            return {"action": "start", "id": parts[2]}
        
        elif action == "cancel" and len(parts) >= 3:
            return {"action": "cancel", "id": parts[2]}
        
        elif action == "delete" and len(parts) >= 3:
            return {"action": "delete", "id": parts[2]}
        
        elif action == "next":
            return {"action": "next"}
        
        elif action == "clear":
            return {"action": "clear"}
        
        else:
            return {"action": "list"}
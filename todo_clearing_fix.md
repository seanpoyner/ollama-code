# Todo Clearing Fix

## Changes Made

### 1. Added `clear()` method to TodoManager
**File:** `ollama_code/core/todos.py` (line 239-242)

Added a new method to clear all todos:
```python
def clear(self):
    """Clear all todos"""
    self.todos = []
    self.save_todos()
```

### 2. Updated task completion handling
**File:** `ollama_code/core/agent.py` (line 778-780)

Modified `_execute_tasks_sequentially` to clear todos after all tasks are completed:
```python
# Clear todos after completion
self.todo_manager.clear()
console.print("\n🧹 [dim]Todo list cleared[/dim]")
```

## Behavior

Now when task execution completes (either all tasks are done or execution is interrupted):
1. A completion summary is shown with all completed tasks
2. The todo list is automatically cleared
3. A subtle message "Todo list cleared" is displayed
4. Control returns to the user with "Ready for your next command!"

This ensures that each new user request starts with a fresh todo list, preventing old tasks from lingering across different requests.

## Testing

To test this functionality:
1. Give the agent a multi-task request
2. Let it complete all tasks (or interrupt with timeout)
3. Check that the completion summary shows
4. Run `/todo` command to verify the list is empty
5. Give a new request and verify it starts fresh
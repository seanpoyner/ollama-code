"""AI-powered task decomposition for breaking down any task into concrete subtasks"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SubTaskType(Enum):
    ANALYZE = "analyze"          # Understand requirements, read files
    CREATE_FILE = "create_file"  # Create a new file
    MODIFY_FILE = "modify_file"  # Modify existing file
    EXECUTE_CMD = "execute_cmd"  # Run a command
    VALIDATE = "validate"        # Check if something works

@dataclass
class ConcreteSubTask:
    """A concrete subtask with specific actions and validation criteria"""
    id: str
    type: SubTaskType
    description: str
    action: str  # The specific action to take (e.g., "write_file('server.js', ...)")
    validation: str  # How to validate this subtask is complete
    dependencies: List[str] = None  # IDs of subtasks that must complete first
    completed: bool = False
    result: Optional[str] = None

class TaskDecomposer:
    """Decomposes high-level tasks into concrete, validatable subtasks"""
    
    def __init__(self):
        self.subtask_templates = {
            'backend': self._decompose_backend_task,
            'frontend': self._decompose_frontend_task,
            'test': self._decompose_test_task,
            'generic': self._decompose_generic_task
        }
    
    def decompose_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a task into concrete subtasks"""
        task_lower = task_content.lower()
        
        # Determine task type
        if any(word in task_lower for word in ['backend', 'api', 'server', 'websocket']):
            return self._decompose_backend_task(task_content)
        elif any(word in task_lower for word in ['frontend', 'interface', 'gui', 'html', 'app.js', 'javascript']):
            return self._decompose_frontend_task(task_content)
        elif 'test' in task_lower:
            return self._decompose_test_task(task_content)
        else:
            return self._decompose_generic_task(task_content)
    
    def _decompose_backend_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a backend/server task"""
        subtasks = []
        task_lower = task_content.lower()
        
        # 1. Always start by understanding current state
        subtasks.append(ConcreteSubTask(
            id="analyze_backend",
            type=SubTaskType.ANALYZE,
            description="Analyze current backend structure",
            action="files = list_files(); print(f'Files: {files}')",
            validation="Shows list"
        ))
        
        # 2. Determine specific backend needs
        if 'package' in task_lower or 'dependencies' in task_lower:
            subtasks.append(ConcreteSubTask(
                id="check_deps",
                type=SubTaskType.ANALYZE,
                description="Check package.json for dependencies",
                action="import os; content = read_file('package.json') if os.path.exists('package.json') else 'Not found'; print(content)",
                validation="Shows content or 'Not found'",
                dependencies=["analyze_backend"]
            ))
        
        if 'server' in task_lower or 'api' in task_lower or 'websocket' in task_lower:
            subtasks.append(ConcreteSubTask(
                id="implement_server",
                type=SubTaskType.CREATE_FILE,
                description="Implement server functionality",
                action="# Implement server based on requirements",
                validation="Server implementation complete",
                dependencies=["analyze_backend"]
            ))
        
        return subtasks
    
    def _decompose_frontend_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a frontend task"""
        subtasks = []
        
        # Analyze what the task is asking for
        task_lower = task_content.lower()
        
        # First, understand the current state
        subtasks.append(ConcreteSubTask(
            id="analyze_current_state",
            type=SubTaskType.ANALYZE,
            description="Analyze the current state of the project",
            action="files = list_files(); print(f'Current files: {files}')",
            validation="Shows list"
        ))
        
        # Determine what needs to be done based on the task content
        if 'app.js' in task_lower and ('create' in task_lower or 'missing' in task_lower or 'not' in task_lower):
            # Task is specifically about creating app.js
            subtasks.append(ConcreteSubTask(
                id="create_app_js",
                type=SubTaskType.CREATE_FILE,
                description="Create the missing app.js file",
                action='write_file("public/app.js", "// TODO: Implement chat functionality\\n")',
                validation="File 'public/app.js' exists",
                dependencies=["analyze_current_state"]
            ))
        elif 'error' in task_lower and 'handling' in task_lower:
            # Task is about adding error handling
            subtasks.append(ConcreteSubTask(
                id="read_current_js",
                type=SubTaskType.ANALYZE,
                description="Read the current app.js to understand its structure",
                action='content = read_file("public/app.js"); print(content)',
                validation="Shows file content",
                dependencies=["analyze_current_state"]
            ))
            subtasks.append(ConcreteSubTask(
                id="update_with_error_handling",
                type=SubTaskType.EDIT_FILE,
                description="Update app.js with error handling",
                action='# Use edit_file() to add try-catch blocks and error handling',
                validation="File updated with error handling",
                dependencies=["read_current_js"]
            ))
        elif 'style' in task_lower or 'css' in task_lower:
            # Task is about styling
            subtasks.append(ConcreteSubTask(
                id="update_styles",
                type=SubTaskType.CREATE_FILE,
                description="Create or update CSS styles",
                action='# Create or update style.css',
                validation="CSS file exists or updated",
                dependencies=["analyze_current_state"]
            ))
        else:
            # Generic frontend task - analyze what files might be needed
            subtasks.append(ConcreteSubTask(
                id="determine_needed_files",
                type=SubTaskType.ANALYZE,
                description="Determine what files need to be created or modified",
                action='# Analyze the task requirements and current state',
                validation="Analysis complete",
                dependencies=["analyze_current_state"]
            ))
        
        return subtasks
    
    def _decompose_test_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a test task"""
        subtasks = []
        
        subtasks.append(ConcreteSubTask(
            id="run_tests",
            type=SubTaskType.EXECUTE_CMD,
            description="Run the application to test it",
            action='bash("npm start")',
            validation="Server starts without errors"
        ))
        
        return subtasks
    
    def _decompose_generic_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a generic task"""
        subtasks = []
        
        # Always start by understanding the current state
        subtasks.append(ConcreteSubTask(
            id="analyze_context",
            type=SubTaskType.ANALYZE,
            description="Understand the current context and requirements",
            action="# Analyze what needs to be done based on the task: " + task_content[:100],
            validation="Analysis complete"
        ))
        
        # Let the AI figure out the next steps based on the analysis
        return subtasks
    
    def validate_subtask(self, subtask: ConcreteSubTask, output: str) -> bool:
        """Validate if a subtask completed successfully"""
        validation_lower = subtask.validation.lower()
        output_lower = output.lower()
        
        # Check for common validation patterns
        if "exists" in validation_lower and "file" in validation_lower:
            # Extract filename from validation
            filename_match = re.search(r"['\"]([^'\"]+)['\"]", subtask.validation)
            if filename_match:
                filename = filename_match.group(1)
                return (f"created file: {filename}" in output_lower or 
                        f"wrote to {filename}" in output_lower or
                        f"updated existing file: {filename}" in output_lower or
                        f"overwriting existing file: {filename}" in output_lower)
        
        if "contains" in validation_lower:
            # Check if output contains expected content
            expected_match = re.search(r"contains ([^'\"]+)", validation_lower)
            if expected_match:
                expected = expected_match.group(1)
                return expected.lower() in output_lower
        
        if "shows" in validation_lower and "list" in validation_lower:
            # Check if output shows a list (has brackets)
            return "[" in output and "]" in output
        
        if "without errors" in validation_lower:
            return "error" not in output_lower and "exception" not in output_lower
        
        # Default: check if any output was produced
        return len(output.strip()) > 0
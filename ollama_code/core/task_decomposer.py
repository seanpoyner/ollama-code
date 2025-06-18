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
        elif any(word in task_lower for word in ['frontend', 'interface', 'gui', 'html']):
            return self._decompose_frontend_task(task_content)
        elif 'test' in task_lower:
            return self._decompose_test_task(task_content)
        else:
            return self._decompose_generic_task(task_content)
    
    def _decompose_backend_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a backend/server task"""
        subtasks = []
        
        # 1. Analyze existing structure
        subtasks.append(ConcreteSubTask(
            id="analyze_structure",
            type=SubTaskType.ANALYZE,
            description="Analyze existing project structure",
            action="files = list_files(); print(files)",
            validation="Output contains list of files"
        ))
        
        # 2. Check dependencies
        subtasks.append(ConcreteSubTask(
            id="check_deps",
            type=SubTaskType.ANALYZE,
            description="Check package.json for dependencies",
            action="content = read_file('package.json') if os.path.exists('package.json') else 'Not found'; print(content)",
            validation="Either shows package.json content or 'Not found'",
            dependencies=["analyze_structure"]
        ))
        
        # 3. Create/update server file
        if 'websocket' in task_content.lower():
            server_template = '''const express = require('express');
const http = require('http');
const socketIO = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

app.use(express.static('public'));

io.on('connection', (socket) => {
    console.log('New client connected');
    
    socket.on('message', (data) => {
        // Handle incoming messages
        socket.emit('response', { message: 'Response from server' });
    });
    
    socket.on('disconnect', () => {
        console.log('Client disconnected');
    });
});

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => console.log(`Server running on port ${PORT}`));'''
        else:
            server_template = '''const express = require('express');
const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());
app.use(express.static('public'));

// Add your routes here
app.get('/api/test', (req, res) => {
    res.json({ message: 'API is working' });
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});'''
        
        subtasks.append(ConcreteSubTask(
            id="create_server",
            type=SubTaskType.CREATE_FILE,
            description="Create/update server.js file",
            action=f'write_file("server.js", """{server_template}""")',
            validation="File 'server.js' exists",
            dependencies=["check_deps"]
        ))
        
        return subtasks
    
    def _decompose_frontend_task(self, task_content: str) -> List[ConcreteSubTask]:
        """Decompose a frontend task"""
        subtasks = []
        
        # 1. Check existing files
        subtasks.append(ConcreteSubTask(
            id="check_frontend",
            type=SubTaskType.ANALYZE,
            description="Check for existing frontend files",
            action="import os; public_files = list_files() if os.path.exists('public') else []; print(f'Public files: {public_files}')",
            validation="Shows list of public files or empty list"
        ))
        
        # 2. Create HTML
        html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Interface</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <div id="messages" class="messages"></div>
        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Type a message...">
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>'''
        
        subtasks.append(ConcreteSubTask(
            id="create_html",
            type=SubTaskType.CREATE_FILE,
            description="Create index.html",
            action=f'write_file("public/index.html", """{html_template}""")',
            validation="File 'public/index.html' exists",
            dependencies=["check_frontend"]
        ))
        
        # 3. Create CSS
        css_template = '''body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f0f0f0;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background-color: white;
}

.input-area {
    display: flex;
    padding: 20px;
    background-color: white;
    border-top: 1px solid #ddd;
}

#messageInput {
    flex: 1;
    padding: 10px;
    margin-right: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

button {
    padding: 10px 20px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}'''
        
        subtasks.append(ConcreteSubTask(
            id="create_css",
            type=SubTaskType.CREATE_FILE,
            description="Create style.css",
            action=f'write_file("public/style.css", """{css_template}""")',
            validation="File 'public/style.css' exists",
            dependencies=["create_html"]
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
        # For generic tasks, don't create subtasks - let the AI handle it naturally
        # This prevents the infinite loop of meaningless subtasks
        return []
    
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
        
        if "without errors" in validation_lower:
            return "error" not in output_lower and "exception" not in output_lower
        
        # Default: check if any output was produced
        return len(output.strip()) > 0
"""Sub-task management for breaking down complex tasks into executable steps"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class SubTaskType(Enum):
    EXPLORE = "explore"      # Read files, search codebase
    CREATE = "create"        # Create new files
    MODIFY = "modify"        # Modify existing files
    EXECUTE = "execute"      # Run commands
    TEST = "test"           # Run tests


@dataclass
class SubTask:
    """Represents a single executable sub-task"""
    type: SubTaskType
    description: str
    code: str
    expected_output: Optional[str] = None
    completed: bool = False


class SubTaskManager:
    """Manages breaking down tasks into executable sub-tasks"""
    
    def __init__(self):
        self.subtasks: List[SubTask] = []
        self.current_index = 0
    
    def create_subtasks_for_task(self, task_content: str) -> List[SubTask]:
        """Create sub-tasks based on the main task content"""
        subtasks = []
        task_lower = task_content.lower()
        
        # Analysis tasks
        if "analyze" in task_lower or "document" in task_lower:
            subtasks.extend([
                SubTask(
                    type=SubTaskType.EXPLORE,
                    description="Read project context",
                    code='content = read_file("OLLAMA.md")\nprint("=== OLLAMA.md Content ===")\nprint(content[:1000])'
                ),
                SubTask(
                    type=SubTaskType.EXPLORE,
                    description="Find relevant Python files",
                    code='files = bash("find . -name \\"*.py\\" | grep -v __pycache__ | head -20")\nprint("=== Python Files ===")\nprint(files)'
                ),
                SubTask(
                    type=SubTaskType.EXPLORE,
                    description="Search for API usage",
                    code='api_usage = bash("grep -r \\"localhost:11434\\" . --include=\\"*.py\\" | head -10")\nprint("=== API Usage ===")\nprint(api_usage)'
                )
            ])
        
        # Backend/endpoint creation tasks
        elif "endpoint" in task_lower or "backend" in task_lower:
            subtasks.extend([
                SubTask(
                    type=SubTaskType.CREATE,
                    description="Create backend service file",
                    code='''write_file("ollama_backend.py", """from flask import Flask, jsonify
import requests

app = Flask(__name__)

def fetch_available_models():
    \\"\\"\\"Fetch available Ollama models from the API\\"\\"\\"
    try:
        response = requests.get("http://localhost:11434/api/tags")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500

@app.route("/api/models", methods=["GET"])
def get_available_models():
    \\"\\"\\"Endpoint to get available Ollama models\\"\\"\\"
    result = fetch_available_models()
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
""")'''
                )
            ])
        
        # Function implementation tasks
        elif "function" in task_lower or "implement" in task_lower:
            if "fetch_available_models" in task_content:
                subtasks.extend([
                    SubTask(
                        type=SubTaskType.CREATE,
                        description="Create ollama_models.py with fetch function",
                        code='''write_file("ollama_models.py", """import requests
from typing import List, Dict, Any

def fetch_available_models() -> List[Dict[str, Any]]:
    \\"\\"\\"Fetch available models from Ollama API\\"\\"\\"
    try:
        response = requests.get("http://localhost:11434/api/tags")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching models: {e}")
        return []

def format_model_info(models: List[Dict[str, Any]]) -> str:
    \\"\\"\\"Format model information for display\\"\\"\\"
    if not models:
        return "No models available"
    
    output = f"Found {len(models)} models:\\\\n"
    for model in models:
        name = model.get("name", "Unknown")
        size = model.get("size", "Unknown")
        output += f"  - {name} (Size: {size})\\\\n"
    return output

if __name__ == "__main__":
    models = fetch_available_models()
    print(format_model_info(models))
""")'''
                    )
                ])
        
        # Test creation tasks
        elif "test" in task_lower:
            subtasks.extend([
                SubTask(
                    type=SubTaskType.CREATE,
                    description="Create test file",
                    code='''write_file("test_ollama_models.py", """import unittest
from unittest.mock import patch, Mock
from ollama_models import fetch_available_models, format_model_info

class TestOllamaModels(unittest.TestCase):
    
    @patch('requests.get')
    def test_fetch_models_success(self, mock_get):
        \\"\\"\\"Test successful model fetching\\"\\"\\"
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2", "size": "7B"},
                {"name": "codellama", "size": "13B"}
            ]
        }
        mock_get.return_value = mock_response
        
        result = fetch_available_models()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "llama2")
    
    @patch('requests.get')
    def test_fetch_models_error(self, mock_get):
        \\"\\"\\"Test error handling\\"\\"\\"
        mock_get.side_effect = Exception("Connection error")
        result = fetch_available_models()
        self.assertEqual(result, [])
    
    def test_format_model_info(self):
        \\"\\"\\"Test model info formatting\\"\\"\\"
        models = [{"name": "test", "size": "1B"}]
        output = format_model_info(models)
        self.assertIn("Found 1 models", output)
        self.assertIn("test", output)

if __name__ == "__main__":
    unittest.main()
""")'''
                )
            ])
        
        # Configuration file tasks
        elif "configuration" in task_lower or "config" in task_lower:
            subtasks.extend([
                SubTask(
                    type=SubTaskType.CREATE,
                    description="Create configuration file",
                    code='''import json
config = {
    "api_endpoint": "http://localhost:11434",
    "timeout": 30,
    "retry_attempts": 3,
    "models": {
        "default": "llama2",
        "available": []
    }
}
write_file("models_config.json", json.dumps(config, indent=2))'''
                )
            ])
        
        # README creation tasks
        elif "readme" in task_lower:
            subtasks.extend([
                SubTask(
                    type=SubTaskType.CREATE,
                    description="Create README file",
                    code='''write_file("README_BACKEND.md", """# Ollama Backend Integration

## Overview
This backend integration provides endpoints to interact with the Ollama model API.

## Setup

1. Install dependencies:
   ```bash
   pip install flask requests
   ```

2. Start the backend server:
   ```bash
   python ollama_backend.py
   ```

## API Endpoints

### GET /api/models
Returns a list of available Ollama models.

**Example Response:**
```json
{
  "models": [
    {"name": "llama2", "size": "7B"},
    {"name": "codellama", "size": "13B"}
  ]
}
```

## Usage

```python
import requests

response = requests.get("http://localhost:5000/api/models")
models = response.json()
print(models)
```
""")'''
                )
            ])
        
        return subtasks
    
    def get_next_subtask(self) -> Optional[SubTask]:
        """Get the next uncompleted sub-task"""
        while self.current_index < len(self.subtasks):
            subtask = self.subtasks[self.current_index]
            if not subtask.completed:
                return subtask
            self.current_index += 1
        return None
    
    def mark_current_complete(self):
        """Mark the current sub-task as complete"""
        if self.current_index < len(self.subtasks):
            self.subtasks[self.current_index].completed = True
            self.current_index += 1
    
    def get_progress(self) -> str:
        """Get progress summary"""
        completed = sum(1 for st in self.subtasks if st.completed)
        total = len(self.subtasks)
        return f"Sub-tasks: {completed}/{total} completed"
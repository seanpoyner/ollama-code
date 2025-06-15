"""Task validation and retry system for ensuring tasks actually complete successfully"""

import re
import subprocess
from typing import Dict, List, Optional, Tuple
from enum import Enum


class ValidationResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_RETRY = "needs_retry"


class TaskValidator:
    """Validates that tasks were actually completed successfully"""
    
    def __init__(self):
        self.validation_rules = {
            'create': self._validate_file_creation,
            'test': self._validate_test_execution,
            'implement': self._validate_implementation,
            'backend': self._validate_backend,
            'api': self._validate_api,
            'gui': self._validate_gui,
            'function': self._validate_function
        }
    
    def validate_task_completion(self, task_content: str, result: str, files_created: List[str] = None) -> Tuple[ValidationResult, str]:
        """
        Validate if a task was actually completed successfully
        Returns: (validation_result, feedback_message)
        """
        task_lower = task_content.lower()
        files_created = files_created or []
        
        # Special handling for directory creation tasks
        if "create" in task_lower and "directory" in task_lower and "mkdir" in result:
            # Check if directory was created in bash output
            if "command executed successfully" in result.lower() or "created file:" in result.lower():
                return ValidationResult.PASSED, ""
        
        # For analysis/exploration tasks, don't require file creation
        if any(word in task_lower for word in ["analyze", "explore", "gather", "document", "thoroughly"]):
            # Just check if some exploration was done
            if "read_file" in result or "bash" in result or "search_docs" in result or "get_api_info" in result:
                return ValidationResult.PASSED, ""
        
        # Determine task type and validate
        for task_type, validator in self.validation_rules.items():
            if task_type in task_lower:
                return validator(task_content, result, files_created)
        
        # Default validation - check if any files were created
        if any(word in task_lower for word in ['create', 'write', 'implement', 'develop']):
            if not files_created:
                return ValidationResult.NEEDS_RETRY, "No files were created. You must use write_file() to create actual files."
        
        return ValidationResult.PASSED, ""
    
    def _validate_file_creation(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate file creation tasks"""
        if not files_created:
            return ValidationResult.NEEDS_RETRY, "No files were created. Use write_file() to create the required files."
        
        # Check for placeholder content
        if files_created:
            for file in files_created:
                if self._is_placeholder_code(file, result):
                    return ValidationResult.NEEDS_RETRY, f"File {file} contains placeholder code. Create actual working implementation."
        
        return ValidationResult.PASSED, ""
    
    def _validate_test_execution(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate test tasks"""
        if not files_created:
            return ValidationResult.NEEDS_RETRY, "No test files created. Create actual test files with working tests."
        
        # Check if tests were run
        if "error" in result.lower() or "failed" in result.lower():
            return ValidationResult.NEEDS_RETRY, "Tests failed to execute. Fix the errors and try again."
        
        # Check for actual test implementation
        if any("pass" in result for file in files_created if file.endswith('.py')):
            return ValidationResult.NEEDS_RETRY, "Tests contain only 'pass' statements. Implement actual test logic."
        
        return ValidationResult.PASSED, ""
    
    def _validate_implementation(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate implementation tasks"""
        if not files_created:
            return ValidationResult.NEEDS_RETRY, "No implementation files created. Create the actual implementation."
        
        # Check for errors in execution
        if "error" in result.lower() or "exception" in result.lower():
            error_msg = self._extract_error_message(result)
            return ValidationResult.NEEDS_RETRY, f"Implementation has errors: {error_msg}. Fix and retry."
        
        return ValidationResult.PASSED, ""
    
    def _validate_backend(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate backend/API tasks"""
        if not files_created:
            return ValidationResult.NEEDS_RETRY, "No backend files created. Create actual backend implementation files."
        
        # Check for proper Ollama API usage
        if "ollama" in task_content.lower():
            if not any("localhost:11434" in result for file in files_created):
                return ValidationResult.NEEDS_RETRY, "Backend must use Ollama API at http://localhost:11434. Update to use correct endpoint."
        
        # Check for connection errors
        if "connection" in result.lower() and "refused" in result.lower():
            return ValidationResult.NEEDS_RETRY, "Connection refused. Update code to handle connection errors and use correct endpoints."
        
        return ValidationResult.PASSED, ""
    
    def _validate_api(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate API integration tasks"""
        # Similar to backend validation
        return self._validate_backend(task_content, result, files_created)
    
    def _validate_gui(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate GUI tasks"""
        if "html" in task_content.lower() and not any(f.endswith('.html') for f in files_created):
            return ValidationResult.NEEDS_RETRY, "No HTML file created for GUI task. Create the HTML file."
        
        if "javascript" in task_content.lower() and not any(f.endswith('.js') for f in files_created):
            return ValidationResult.NEEDS_RETRY, "No JavaScript file created. Create the JS file for functionality."
        
        return ValidationResult.PASSED, ""
    
    def _validate_function(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate function implementation"""
        if not files_created:
            return ValidationResult.NEEDS_RETRY, "No function implementation created. Create the actual function."
        
        # Check for actual function implementation
        if "def " not in result and "function " not in result:
            return ValidationResult.NEEDS_RETRY, "No function definition found. Implement the actual function."
        
        return ValidationResult.PASSED, ""
    
    def _is_placeholder_code(self, filename: str, content: str) -> bool:
        """Check if code contains placeholder/dummy content"""
        placeholders = [
            "YOUR_API_KEY",
            "api.example.com",
            "https://api.ollama.com",  # Wrong endpoint
            "# Implementation here",
            "# Your code here",
            "pass  # TODO",
            "// TODO",
            "<!-- TODO -->"
        ]
        
        return any(placeholder in content for placeholder in placeholders)
    
    def _extract_error_message(self, result: str) -> str:
        """Extract error message from result"""
        error_patterns = [
            r"Error: (.+)",
            r"Exception: (.+)",
            r"Failed: (.+)",
            r"(\w+Error): (.+)"
        ]
        
        for pattern in error_patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                return match.group(1)[:100]  # Limit length
        
        return "Unknown error"
    
    def generate_retry_context(self, task_content: str, validation_feedback: str, attempt_number: int) -> str:
        """Generate context for retry attempt"""
        context = f"\n[RETRY ATTEMPT {attempt_number}]\n\n"
        context += f"Previous attempt failed validation: {validation_feedback}\n\n"
        context += "You MUST fix the issues and create working code:\n"
        
        # Add specific guidance based on task type
        if "backend" in task_content.lower() or "api" in task_content.lower():
            context += self._get_backend_retry_guidance()
        elif "test" in task_content.lower():
            context += self._get_test_retry_guidance()
        elif "gui" in task_content.lower():
            context += self._get_gui_retry_guidance()
        
        context += "\nDO NOT use placeholder code. Create actual working implementation!\n"
        return context
    
    def _get_backend_retry_guidance(self) -> str:
        """Get retry guidance for backend tasks"""
        return """
For Ollama backend integration:
1. Use the correct Ollama API endpoint: http://localhost:11434
2. Available endpoints:
   - POST /api/chat - For chat completions
     Request body: {
       "model": "llama2",
       "messages": [{"role": "user", "content": "message"}],
       "stream": false
     }
   - POST /api/generate - For text generation
     Request body: {
       "model": "llama2", 
       "prompt": "your prompt",
       "stream": false
     }
   - GET /api/tags - List available models
3. COMPLETE working Flask backend with frontend:

```python
# app.py - Backend
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Call Ollama API
        ollama_response = requests.post(
            'http://localhost:11434/api/chat',
            json={
                'model': 'llama2',
                'messages': [{'role': 'user', 'content': user_message}],
                'stream': False
            },
            timeout=30
        )
        
        if ollama_response.status_code == 200:
            result = ollama_response.json()
            return jsonify({
                'response': result['message']['content'],
                'success': True
            })
        else:
            return jsonify({'error': 'Ollama API error', 'success': False}), 500
            
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to Ollama. Is it running?', 'success': False}), 500
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    try:
        response = requests.get('http://localhost:11434/api/tags')
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch models'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

And create a simple HTML frontend:
```html
<!-- index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Ollama Chat</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
        #chat-container { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
        .message { margin: 10px 0; }
        .user { color: blue; }
        .assistant { color: green; }
        #input-container { display: flex; gap: 10px; }
        #message-input { flex: 1; padding: 10px; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>Ollama Chat</h1>
    <div id="chat-container"></div>
    <div id="input-container">
        <input type="text" id="message-input" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendMessage()">
        <button onclick="sendMessage()">Send</button>
    </div>
    
    <script>
        async function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            if (!message) return;
            
            // Display user message
            addMessage('You', message, 'user');
            input.value = '';
            
            // Send to backend
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                });
                
                const data = await response.json();
                if (data.success) {
                    addMessage('Assistant', data.response, 'assistant');
                } else {
                    addMessage('Error', data.error, 'error');
                }
            } catch (error) {
                addMessage('Error', 'Failed to send message: ' + error, 'error');
            }
        }
        
        function addMessage(sender, text, className) {
            const chatContainer = document.getElementById('chat-container');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + className;
            messageDiv.innerHTML = '<b>' + sender + ':</b> ' + text;
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    </script>
</body>
</html>
```
"""
    
    def _get_test_retry_guidance(self) -> str:
        """Get retry guidance for test tasks"""
        return """
For test implementation:
1. Create actual test cases, not just 'pass' statements
2. Use proper assertions
3. Test both success and failure cases
4. Example:

```python
import unittest
from unittest.mock import patch, Mock

class TestOllamaIntegration(unittest.TestCase):
    def test_get_models_success(self):
        # Actual test implementation
        self.assertTrue(True)  # Replace with real assertion
```
"""
    
    def _get_gui_retry_guidance(self) -> str:
        """Get retry guidance for GUI tasks"""
        return """
For GUI implementation:
1. Create a working HTML interface
2. Add JavaScript for Ollama interaction
3. Include proper error handling
4. Example structure:

- index.html - Main interface
- script.js - JavaScript functionality
- styles.css - Styling

Make it actually functional, not just placeholder HTML!
"""
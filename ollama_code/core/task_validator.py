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
        
        # Track partial progress across validation attempts
        self.partial_progress = {}
        
        # Expanded analysis keywords
        self.analysis_keywords = [
            'analyze', 'gather', 'information', 'examine', 'explore',
            'understand', 'review', 'assess', 'evaluate', 'study',
            'investigate', 'inspect', 'survey', 'scan', 'research',
            'document', 'thoroughly', 'check', 'verify', 'identify',
            'determine', 'find', 'discover', 'detect', 'observe'
        ]
        
        # Valid first steps for any task
        self.valid_first_steps = [
            'list_files', 'read_file', 'bash', 'search_docs', 'get_api_info',
            'import os', 'print(', 'files =', '# Check', '# Analyze',
            'ls', 'pwd', 'cd', 'mkdir', 'find', 'grep'
        ]
    
    def validate_task_completion(self, task_content: str, result: str, files_created: List[str] = None) -> Tuple[ValidationResult, str]:
        """
        Validate if a task was actually completed successfully
        Returns: (validation_result, feedback_message)
        """
        task_lower = task_content.lower()
        files_created = files_created or []
        task_id = hash(task_content)  # Simple task identifier
        
        # Track partial progress
        if task_id not in self.partial_progress:
            self.partial_progress[task_id] = {
                'steps_completed': [],
                'meaningful_actions': 0,
                'attempt_count': 0
            }
        
        progress = self.partial_progress[task_id]
        progress['attempt_count'] += 1
        
        # Check for meaningful progress indicators
        if self._has_meaningful_progress(result, progress):
            progress['meaningful_actions'] += 1
        
        # Special handling for directory creation tasks
        if "create" in task_lower and "directory" in task_lower and "mkdir" in result:
            # Check if directory was created in bash output
            if "command executed successfully" in result.lower() or "created file:" in result.lower():
                return ValidationResult.PASSED, ""
        
        # Special handling for package installation tasks
        if "install" in task_lower and ("npm" in task_lower or "pip" in task_lower or "package" in task_lower):
            # Check for npm install success patterns
            if "npm" in task_lower and "bash(" in result:
                if "packages are looking for funding" in result or "added" in result or "audited" in result:
                    return ValidationResult.PASSED, ""
                elif "npm err!" in result.lower():
                    return ValidationResult.NEEDS_RETRY, "npm install failed. Fix errors and retry with: bash('cd ollama-chat && npm install')"
                elif "npm install" in result:
                    # Command was executed, assume success if no errors
                    return ValidationResult.PASSED, ""
            # Check for pip install success patterns
            elif "pip" in task_lower and "bash(" in result:
                if "successfully installed" in result.lower() or "requirement already satisfied" in result.lower():
                    return ValidationResult.PASSED, ""
                elif "error:" in result.lower() and "pip" in result.lower():
                    return ValidationResult.NEEDS_RETRY, "pip install failed. Check errors and retry."
                elif "pip install" in result:
                    return ValidationResult.PASSED, ""
        
        # For analysis/exploration tasks, be more lenient
        if self._is_analysis_task(task_lower):
            # Check if meaningful analysis was performed
            analysis_actions = [
                "read_file" in result,
                "bash" in result,
                "search_docs" in result,
                "get_api_info" in result,
                "list_files" in result,
                any(step in result for step in self.valid_first_steps),
                "===" in result,  # Analysis output format
                "found" in result.lower(),
                "identified" in result.lower(),
                "discovered" in result.lower(),
                progress['meaningful_actions'] > 0
            ]
            
            if any(analysis_actions):
                return ValidationResult.PASSED, ""
            
            # Allow partial progress for analysis tasks
            if progress['attempt_count'] == 1:
                return ValidationResult.NEEDS_RETRY, "Please complete the analysis by examining the relevant files or information."
        
        # Determine task type and validate
        for task_type, validator in self.validation_rules.items():
            if task_type in task_lower:
                return validator(task_content, result, files_created)
        
        # Check for project-specific file creation
        if "ollama-chat" in task_lower:
            # Verify files are created in the project directory
            if files_created:
                wrong_location_files = [f for f in files_created if not f.startswith("ollama-chat/")]
                if wrong_location_files:
                    return ValidationResult.NEEDS_RETRY, f"Files created in wrong location! Use paths like 'ollama-chat/filename'. Wrong: {wrong_location_files}"
        
        # Default validation - check if any files were created
        if any(word in task_lower for word in ['create', 'write', 'implement', 'develop']):
            if not files_created:
                return ValidationResult.NEEDS_RETRY, "No files were created. You must use write_file() to create actual files."
        
        return ValidationResult.PASSED, ""
    
    def _validate_file_creation(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate file creation tasks"""
        if not files_created:
            # Check if it's a Node.js project initialization
            if "node" in task_content.lower() or "npm" in task_content.lower():
                # Check if npm init was run successfully
                if "npm init" in result and ("package.json" in result or "Wrote to" in result):
                    return ValidationResult.PASSED, ""
                return ValidationResult.NEEDS_RETRY, "Node.js project initialization failed. You must create the directory and run 'npm init -y' to create package.json"
            
            # Check if it's a project initialization task
            if ("initialize" in task_content.lower() or "project" in task_content.lower()) and "directory" in task_content.lower():
                # Python projects need specific files
                if "python" in task_content.lower() or "flask" in task_content.lower() or "django" in task_content.lower():
                    return ValidationResult.NEEDS_RETRY, "Python project initialization failed. You must create both the directory AND initial files (requirements.txt, app.py/main.py, README.md). Just creating the directory is NOT enough!"
                # Node.js projects need package.json
                elif "node" in task_content.lower() or "npm" in task_content.lower():
                    return ValidationResult.NEEDS_RETRY, "Node.js project initialization failed. Create the directory and run 'npm init -y' to create package.json"
                else:
                    return ValidationResult.NEEDS_RETRY, "Project initialization requires creating initial files. Create at least a README.md or configuration file."
            
            # Check if the AI just showed content without creating files
            if any(marker in result for marker in ['```html', '```css', '```javascript', '```js']):
                return ValidationResult.NEEDS_RETRY, "You showed file content but didn't create files! Use ```python blocks with write_file() instead of language-specific blocks."
            else:
                return ValidationResult.NEEDS_RETRY, "No files were created. You MUST use write_file() inside ```python code blocks. Example: ```python\\nwrite_file('file.txt', 'content')\\n```"
        
        # Check for placeholder content
        if files_created:
            for file in files_created:
                if self._is_placeholder_code(file, result):
                    return ValidationResult.NEEDS_RETRY, f"File {file} contains placeholder code. Create actual working implementation."
        
        return ValidationResult.PASSED, ""
    
    def _validate_test_execution(self, task_content: str, result: str, files_created: List[str]) -> Tuple[ValidationResult, str]:
        """Validate test tasks"""
        # For web app testing, we don't always need test files
        if "web app" in task_content.lower() or "server" in task_content.lower():
            # Check if they're actually testing the app
            if any(term in result.lower() for term in ["running", "server", "localhost", "testing", "curl", "http"]):
                return ValidationResult.PASSED, ""
            return ValidationResult.NEEDS_RETRY, "Test the web app by running the server (e.g., 'node server.js') and checking if it works."
        
        # For other test tasks, we need test files
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
        task_id = hash(task_content)
        progress = self.partial_progress.get(task_id, {'meaningful_actions': 0, 'attempt_count': 1})
        
        # Check if this is a package installation task
        if "install" in task_content.lower() and ("npm" in task_content.lower() or "pip" in task_content.lower()):
            # For package installation, check for successful installation messages
            if "npm install" in result:
                if "packages are looking for funding" in result or "added" in result or "audited" in result:
                    return ValidationResult.PASSED, ""
                elif "npm err!" in result.lower():
                    return ValidationResult.NEEDS_RETRY, "Package installation failed. Check npm errors and retry."
            elif "pip install" in result:
                if "successfully installed" in result.lower() or "requirement already satisfied" in result.lower():
                    return ValidationResult.PASSED, ""
                elif "error" in result.lower():
                    return ValidationResult.NEEDS_RETRY, "Package installation failed. Check pip errors and retry."
            # If we ran the command but no clear success/failure indicator
            if "bash(" in result:
                return ValidationResult.PASSED, ""
        
        # Check if this is a multi-step implementation
        is_multi_step = any(indicator in task_content.lower() for indicator in [
            'and', 'then', 'with', 'including', 'also', 'plus',
            'frontend', 'backend', 'api', 'database', 'test'
        ])
        
        # For multi-step tasks, allow partial progress
        if is_multi_step and progress['attempt_count'] == 1:
            # Check if initial analysis was done
            if any(step in result for step in self.valid_first_steps):
                return ValidationResult.NEEDS_RETRY, "Good start! Now implement the actual functionality based on your analysis."
            
            # Check if some files were created but not all
            if files_created and len(files_created) < 3:  # Arbitrary threshold
                return ValidationResult.NEEDS_RETRY, "Partial implementation detected. Continue implementing the remaining components."
        
        # For other implementation tasks, require files
        if not files_created:
            # Allow first step to be analysis
            if progress['attempt_count'] == 1 and any(step in result for step in self.valid_first_steps):
                return ValidationResult.NEEDS_RETRY, "Analysis complete. Now create the implementation files."
            return ValidationResult.NEEDS_RETRY, "No implementation files created. Create the actual implementation."
        
        # Check for errors in execution
        if "error" in result.lower() or "exception" in result.lower():
            # Ignore common non-error patterns
            if any(pattern in result.lower() for pattern in ["no error", "0 errors", "error handling", "error message"]):
                return ValidationResult.PASSED, ""
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
        # Check if files are in the wrong location
        if files_created and "ollama-chat" in task_content.lower():
            root_files = [f for f in files_created if "/" not in f]
            if root_files:
                return ValidationResult.NEEDS_RETRY, f"GUI files created in root directory! Use 'ollama-chat/public/index.html' not just 'index.html'. Wrong files: {root_files}"
        
        if "html" in task_content.lower() and not any(f.endswith('.html') for f in files_created):
            return ValidationResult.NEEDS_RETRY, "No HTML file created for GUI task. Create the HTML file with path like 'ollama-chat/public/index.html'."
        
        if "javascript" in task_content.lower() and not any(f.endswith('.js') for f in files_created):
            return ValidationResult.NEEDS_RETRY, "No JavaScript file created. Create the JS file with path like 'ollama-chat/public/script.js'."
        
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
    
    def _is_analysis_task(self, task_content: str) -> bool:
        """Check if a task is primarily analysis/information gathering"""
        return any(keyword in task_content for keyword in self.analysis_keywords)
    
    def _has_meaningful_progress(self, result: str, progress: Dict) -> bool:
        """Check if the result shows meaningful progress towards task completion"""
        meaningful_indicators = [
            # File operations
            'write_file(' in result,
            'created file:' in result.lower(),
            'mkdir' in result and 'successfully' in result.lower(),
            
            # Code execution
            'bash(' in result,
            'subprocess.run' in result,
            'execute_code' in result,
            
            # Analysis actions
            'read_file(' in result,
            'list_files(' in result,
            'search_docs(' in result,
            'get_api_info(' in result,
            
            # Implementation indicators
            'def ' in result,
            'function ' in result,
            'class ' in result,
            'import ' in result,
            
            # Package management
            'npm install' in result,
            'pip install' in result,
            'requirements.txt' in result,
            'package.json' in result,
            
            # Testing
            'test' in result.lower() and ('passed' in result.lower() or 'ok' in result.lower()),
            'pytest' in result,
            'unittest' in result,
            
            # API/Backend
            'route' in result,
            'endpoint' in result,
            'server' in result.lower(),
            'flask' in result.lower(),
            'express' in result.lower()
        ]
        
        # Check if this action hasn't been done before
        current_action = None
        for indicator in meaningful_indicators:
            if indicator:
                current_action = indicator
                break
        
        if current_action and current_action not in progress.get('steps_completed', []):
            progress['steps_completed'].append(current_action)
            return True
        
        return False
    
    def generate_retry_context(self, task_content: str, validation_feedback: str, attempt_number: int) -> str:
        """Generate context for retry attempt"""
        task_id = hash(task_content)
        progress = self.partial_progress.get(task_id, {'steps_completed': [], 'meaningful_actions': 0})
        
        context = f"\n🔄 [RETRY ATTEMPT {attempt_number}]\n\n"
        context += f"❌ Previous attempt: {validation_feedback}\n\n"
        
        # If progress was made, acknowledge it
        if progress['steps_completed']:
            context += f"✅ Progress made: {', '.join(progress['steps_completed'][:3])}\n"
            context += "Continue from where you left off.\n\n"
        
        # More encouraging tone for partial progress
        if progress['meaningful_actions'] > 0:
            context += "You're on the right track! Complete the remaining steps.\n\n"
        else:
            context += "🚨 STOP EXPLAINING AND START DOING!\n\n"
        
        # Provide more specific guidance based on what's missing
        if "no files" in validation_feedback.lower():
            context += "EXECUTE THIS CODE NOW:\n"
            context += "```python\n"
            context += "# Create the required files\n"
            context += "# Example: write_file('filename.py', 'content')\n"
            context += "```\n\n"
        elif "partial implementation" in validation_feedback.lower():
            context += "Continue implementing the remaining components:\n"
            context += "```python\n"
            context += "# Check what's already done\n"
            context += "files = list_files()\n"
            context += "print(files)\n"
            context += "# Then implement the missing parts\n"
            context += "```\n\n"
        else:
            context += "EXECUTE THIS CODE NOW:\n"
            context += "```python\n"
            context += "# Step 1: Check existing files\n"
            context += "import os\n"
            context += "files = list_files()\n"
            context += "print(files)\n"
            context += "```\n\n"
            context += "```python\n"
            context += "# Step 2: Implement the actual task\n"
            context += "# Create/modify the required files for THIS SPECIFIC TASK\n"
            context += "# Don't just show examples - IMPLEMENT THE ACTUAL SOLUTION!\n"
            context += "```\n\n"
        
        context += "Remember: Each code block runs in isolation. Use multiple blocks if needed.\n\n"
        
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
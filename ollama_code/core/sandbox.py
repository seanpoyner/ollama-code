"""Code execution sandbox for safe Python execution"""

import subprocess
import tempfile
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Check for Docker availability
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.info("Docker package not available - using subprocess mode for code execution")


class CodeSandbox:
    def __init__(self, write_confirmation_callback=None, doc_request_callback=None):
        self.docker_client = None
        # Disable Docker by default for better reliability
        self.use_docker = False
        self.write_confirmation_callback = write_confirmation_callback
        self.doc_request_callback = doc_request_callback
        self.current_project_dir = None  # Track current project directory
        
        if DOCKER_AVAILABLE and self.use_docker:
            try:
                self.docker_client = docker.from_env()
                print("🐳 Docker connected")
            except:
                print("⚠️ Docker not available, using subprocess mode")
        else:
            print("⚙️ Using subprocess mode for code execution")
    
    def execute_python(self, code, timeout=120):
        """Execute Python code safely"""
        if self.docker_client and self.use_docker:
            return self._execute_docker_python(code, timeout)
        else:
            return self._execute_subprocess_python(code, timeout)
    
    def _execute_docker_python(self, code, timeout):
        """Execute Python in Docker container"""
        try:
            # Create a temporary file to avoid shell escaping issues
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Copy file to container and execute
            container = self.docker_client.containers.run(
                'python:3.11-slim',
                f'python /tmp/script.py',
                volumes={temp_file: {'bind': '/tmp/script.py', 'mode': 'ro'}},
                remove=True,
                stdout=True,
                stderr=True,
                mem_limit='512m',
                network_disabled=False,
                detach=False
            )
            
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
            
            return {
                'success': True,
                'output': container.decode('utf-8') if isinstance(container, bytes) else str(container),
                'error': None
            }
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_file)
            except:
                pass
                
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }
    
    def _execute_subprocess_python(self, code, timeout):
        """Execute Python using subprocess"""
        import queue
        import threading
        
        temp_file = None
        confirmation_file = None
        confirmation_queue = queue.Queue()
        
        try:
            # Create a temporary file for confirmation results
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                confirmation_file = f.name
            
            # Inject file operations into the code context
            # Import environment detector code
            env_detector_path = Path(__file__).parent.parent / 'utils' / 'environment.py'
            with open(env_detector_path, 'r', encoding='utf-8') as f:
                env_detector_code = f.read()
            
            setup_code = f"""
import os
import sys
import json
from pathlib import Path

# Track initial directory and current working directory
# Get the user's working directory from environment
USER_CWD = os.environ.get("OLLAMA_CODE_USER_CWD", "")
if USER_CWD:
    INITIAL_DIR = USER_CWD
else:
    # Fallback to PWD or current directory
    INITIAL_DIR = os.environ.get("PWD", os.getcwd())
CURRENT_DIR = INITIAL_DIR

# Only show debug in verbose mode
if os.environ.get('OLLAMA_CODE_VERBOSE'):
    print(f"[DEBUG] USER_CWD from env: {{USER_CWD}}")
    print(f"[DEBUG] PWD from env: {{os.environ.get('PWD', 'Not set')}}")
    print(f"[DEBUG] Current directory before chdir: {{os.getcwd()}}")

# Change to user's working directory
os.chdir(INITIAL_DIR)
print(f"📂 Working directory: {{INITIAL_DIR}}")

# Confirmation file for write operations
CONFIRMATION_FILE = r'{confirmation_file}'

# Helper to ensure we're in the right directory
def ensure_project_dir(project_name=None):
    global CURRENT_DIR
    if project_name and os.path.exists(os.path.join(INITIAL_DIR, project_name)):
        target = os.path.join(INITIAL_DIR, project_name)
        os.chdir(target)
        CURRENT_DIR = target
        return target
    return os.getcwd()

# Inject environment detector
exec({repr(env_detector_code)})

# Get environment detector instance
_env = get_environment_detector()

def write_file(filename, content):
    \"\"\"Write content to a file\"\"\"
    try:
        # Check if file already exists
        file_exists = os.path.exists(filename)
        
        # Request confirmation through temp file
        confirmation_request = {{
            'action': 'write_file',
            'filename': filename,
            'content': content,
            'exists': file_exists
        }}
        
        with open(CONFIRMATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(confirmation_request, f)
        
        # Signal that we need confirmation by printing special marker
        print("###CONFIRMATION_NEEDED###", flush=True)
        if file_exists:
            print(f"⚠️  Overwriting existing file: {{filename}}", flush=True)
        else:
            print(f"Writing to: {{filename}}", flush=True)
        
        # Wait for confirmation result
        import time
        timeout_occurred = True
        for _ in range(300):  # Wait up to 30 seconds
            try:
                with open(CONFIRMATION_FILE, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    if 'approved' in result:
                        timeout_occurred = False
                        if result['approved']:
                            # Actually write the file
                            file_path = Path(filename)
                            if file_path.parent != Path('.'):
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(filename, 'w', encoding='utf-8') as f:
                                f.write(content)
                            if file_exists:
                                print(f"Updated existing file: {{filename}}")
                            else:
                                print(f"Created file: {{filename}}")
                            return f"File {{filename}} {{'updated' if file_exists else 'created'}} successfully"
                        else:
                            feedback = result.get('feedback', 'File write cancelled by user')
                            print(f"File write cancelled: {{feedback}}")
                            return f"File write cancelled: {{feedback}}"
                        break
            except:
                pass
            time.sleep(0.1)
        
        if timeout_occurred:
            print("###TIMEOUT_OCCURRED###")
            print("ERROR: Timeout waiting for file write confirmation")
            return "Timeout waiting for confirmation"
    except Exception as e:
        print(f"Failed to create file: {{e}}")
        return f"Failed to create file: {{e}}"

def edit_file(filename, search_text, replace_text):
    \"\"\"Edit a file by replacing specific text\"\"\"
    try:
        # First read the file
        if not os.path.exists(filename):
            return f"Error: File {{filename}} does not exist. Use write_file() to create it first."
        
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if search text exists
        if search_text not in content:
            # Provide helpful context about what's in the file
            preview = content[:200] + "..." if len(content) > 200 else content
            return f"Error: Text to replace not found in {{filename}}. File starts with:\\n{{preview}}\\n\\nConsider using write_file() to replace the entire file instead."
        
        # Replace the text
        new_content = content.replace(search_text, replace_text)
        
        # Write back using the existing write_file function for confirmation
        return write_file(filename, new_content)
    except Exception as e:
        print(f"Failed to edit file: {{e}}")
        return f"Failed to edit file: {{e}}"

def read_file(filename):
    \"\"\"Read content from a file\"\"\"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"Failed to read file: {{e}}")
        return f"Failed to read file: {{e}}"

def list_files(directory="."):
    \"\"\"List files in a directory\"\"\"
    try:
        files = list(Path(directory).iterdir())
        file_list = [f.name for f in files]
        return file_list
    except Exception as e:
        print(f"Failed to list files: {{e}}")
        return f"Failed to list files: {{e}}"

def cd(directory):
    \"\"\"Change the current working directory persistently\"\"\"
    try:
        # Handle relative and absolute paths
        if os.path.isabs(directory):
            target = directory
        else:
            target = os.path.join(os.getcwd(), directory)
        
        # Create directory if it doesn't exist
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
            print(f"📁 Created directory: {{target}}")
        
        # Change to the directory
        os.chdir(target)
        new_cwd = os.getcwd()
        print(f"📂 Changed to: {{new_cwd}}")
        return new_cwd
    except Exception as e:
        print(f"Failed to change directory: {{e}}")
        return f"Failed to change directory: {{e}}"

def bash(command):
    \"\"\"Execute a bash/shell command\"\"\"
    import re
    
    try:
        # Track the actual working directory for the command
        # This ensures npm commands run in the right directory
        actual_cwd = os.getcwd()
        
        # Validate common mistakes
        if "npm install" in command and not ("cd " in command or actual_cwd.endswith(('ollama-chat', 'full-web-app-dev'))):
            print("⚠️  WARNING: Running npm install in root directory. Consider: bash('cd project-name && npm install')")
        
        if "npm init" in command and not ("cd " in command or actual_cwd.endswith(('ollama-chat', 'full-web-app-dev'))):
            print("⚠️  WARNING: Running npm init in root directory. Consider: bash('cd project-name && npm init -y')")
        
        # Check if the command contains a cd operation
        if "cd " in command and "&&" in command:
            # Extract the directory change and the actual command
            parts = command.split("&&", 1)
            cd_part = parts[0].strip()
            actual_command = parts[1].strip() if len(parts) > 1 else ""
            
            # Extract the target directory from cd command
            cd_match = re.match(r'cd\\s+([^;]+)', cd_part)
            if cd_match:
                target_dir = cd_match.group(1).strip().strip('"').strip("'")
                # Resolve the target directory
                target_path = os.path.join(actual_cwd, target_dir)
                if os.path.exists(target_path):
                    actual_cwd = target_path
                    # If we have a command after cd, execute it in that directory
                    if actual_command:
                        command = actual_command
                else:
                    print(f"⚠️  WARNING: Directory does not exist. It will be created if needed.")
        
        # Detect if this is a Flask/server command that would block
        is_blocking_command = any(pattern in command.lower() for pattern in [
            'python app.py',
            'python server.py',
            'flask run',
            'python -m flask',
            'uvicorn',
            'gunicorn',
            'python backend.py',
            'python api.py',
            'python web.py',
            'python main.py',
            'node server.js',
            'npm start',
            'npm run dev'
        ])
        
        if is_blocking_command and not any(flag in command for flag in ['&', 'nohup', '--daemon']):
            # For blocking commands, run in background and capture initial output
            print(f"Starting server in background mode: {{command}}")
            print(f"Working directory: {{actual_cwd}}")
            
            # Modify command to run in background
            if _env.os_type == 'windows':
                # Windows: use start command
                bg_command = f'start /B {{command}}'
            else:
                # Unix-like: append & to run in background
                bg_command = f'{{command}} > server.log 2>&1 & echo $!'
            
            result = _env.execute_command(bg_command, timeout=3, cwd=actual_cwd)
            
            if result['success']:
                output = "Server started in background. "
                
                # Try to read initial log output
                try:
                    import time
                    time.sleep(1)  # Give server time to start
                    log_result = _env.execute_command('head -20 server.log 2>/dev/null || echo "No log output yet"', timeout=2, cwd=actual_cwd)
                    if log_result['success'] and log_result['output']:
                        output += f"\\nInitial server output:\\n{{log_result['output']}}"
                except:
                    pass
                
                output += "\\n\\nNote: Server is running in background. Use 'ps aux | grep python' to check process."
                return output
            else:
                return f"Failed to start server: {{result['error']}}"
        else:
            # Normal command execution
            # For debugging, show the working directory for npm commands
            if "npm" in command or "node" in command:
                print(f"Executing: {{command}}")
                print(f"Working directory: {{actual_cwd}}")
            
            result = _env.execute_command(command, timeout=30, cwd=actual_cwd)
            
            if result['success']:
                return result['output'] if result['output'] else "Command executed successfully (no output)"
            else:
                return f"Command failed: {{result['error']}}\\n{{result['output']}}"
        
    except Exception as e:
        return f"Failed to execute command: {{e}}"

# Documentation tools (will be injected by agent if available)
# These provide access to documentation search and knowledge base
search_docs = None
get_api_info = None
remember_solution = None

# User code starts here
"""
            full_code = setup_code + code
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(full_code)
                temp_file = f.name
            
            # Start the subprocess with UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            process = subprocess.Popen(
                [sys.executable, temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                cwd=tempfile.gettempdir(),
                env=env
            )
            
            output_lines = []
            error_lines = []
            
            # Monitor process output
            import json
            import threading
            
            def read_stdout():
                skip_next = False
                for line in process.stdout:
                    line = line.rstrip()
                    
                    # Skip the line after confirmation markers
                    if skip_next and (line.startswith("Writing to:") or line.startswith("Command:") or line.startswith("Searching docs for:") or line.startswith("Getting API info for:") or line.startswith("Remembering solution:")):
                        skip_next = False
                        continue
                    
                    # Check for confirmation request before appending to output
                    if line == "###CONFIRMATION_NEEDED###":
                        skip_next = True
                        logger.info("File write confirmation requested")
                        # Read the confirmation request
                        try:
                            import time
                            time.sleep(0.2)  # Give time for file to be written
                            with open(confirmation_file, 'r', encoding='utf-8') as f:
                                request = json.load(f)
                            
                            if request.get('action') == 'write_file' and self.write_confirmation_callback:
                                logger.info(f"Requesting confirmation for file: {request['filename']}")
                                # Put request in queue for main thread to handle
                                confirmation_queue.put(('write_file', request))
                                
                                # Wait for response from main thread
                                response_received = False
                                for _ in range(1200):  # Wait up to 2 minutes
                                    try:
                                        with open(confirmation_file, 'r', encoding='utf-8') as f:
                                            response_data = json.load(f)
                                            if 'approved' in response_data:
                                                response_received = True
                                                break
                                    except:
                                        pass
                                    time.sleep(0.1)
                                
                                if not response_received:
                                    logger.error("Timeout waiting for confirmation response")
                        except Exception as e:
                            logger.error(f"Error handling confirmation: {e}")
                    
                    # Check for documentation request
                    elif line == "###DOCUMENTATION_REQUEST###":
                        skip_next = True
                        logger.info("Documentation request detected")
                        # Read the documentation request
                        try:
                            import time
                            time.sleep(0.2)  # Give time for file to be written
                            with open(confirmation_file, 'r', encoding='utf-8') as f:
                                request = json.load(f)
                            
                            if request.get('action') in ['search_docs', 'get_api_info', 'remember_solution'] and self.doc_request_callback:
                                logger.info(f"Processing documentation request: {request['action']}")
                                # Put request in queue for main thread to handle
                                confirmation_queue.put(('doc_request', request))
                                
                                # Wait for response from main thread
                                response_received = False
                                for _ in range(100):  # Wait up to 10 seconds
                                    try:
                                        with open(confirmation_file, 'r', encoding='utf-8') as f:
                                            response_data = json.load(f)
                                            if 'result' in response_data:
                                                response_received = True
                                                break
                                    except:
                                        pass
                                    time.sleep(0.1)
                                
                                if not response_received:
                                    logger.error("Timeout waiting for documentation response")
                        except Exception as e:
                            logger.error(f"Error handling documentation request: {e}")
                    
                    # Check for timeout marker
                    elif line == "###TIMEOUT_OCCURRED###":
                        skip_next = True
                        logger.warning("File write confirmation timeout detected")
                    # Removed bash confirmation handling - now handled directly in bash()
                    else:
                        # Only add to output if not a confirmation marker or timeout
                        if not skip_next or not line.startswith("ERROR: Timeout"):
                            output_lines.append(line)
                        skip_next = False
            
            def read_stderr():
                for line in process.stderr:
                    error_lines.append(line.rstrip())
            
            # Start threads to read output
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)
            stdout_thread.start()
            stderr_thread.start()
            
            # Monitor confirmation queue in main thread
            while process.poll() is None:  # While process is running
                try:
                    # Check for confirmation requests (non-blocking)
                    action, request = confirmation_queue.get(timeout=0.1)
                    
                    if action == 'write_file' and self.write_confirmation_callback:
                        # Handle confirmation in main thread
                        approved, feedback = self.write_confirmation_callback(
                            request['filename'],
                            request['content'],
                            request.get('exists', False)
                        )
                        
                        # Write response
                        response = {
                            'approved': approved,
                            'feedback': feedback
                        }
                        with open(confirmation_file, 'w', encoding='utf-8') as f:
                            json.dump(response, f)
                        logger.info(f"Confirmation response written: approved={approved}")
                    
                    elif action == 'doc_request' and self.doc_request_callback:
                        # Handle documentation request in main thread
                        result = self.doc_request_callback(request)
                        
                        # Write response
                        response = {
                            'result': result
                        }
                        with open(confirmation_file, 'w', encoding='utf-8') as f:
                            json.dump(response, f)
                        logger.info(f"Documentation response written for: {request.get('action')}")
                except queue.Empty:
                    # No confirmation requests, continue monitoring
                    pass
                except Exception as e:
                    logger.error(f"Error processing confirmation: {e}")
            
            # Process has finished, wait for threads to finish reading
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            # Combine output
            output = '\n'.join(output_lines)
            error = '\n'.join(error_lines) if error_lines else None
            
            return {
                'success': process.returncode == 0,
                'output': output,
                'error': error if process.returncode != 0 else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': None,
                'error': 'Code execution timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }
        finally:
            # Clean up temp files
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            if confirmation_file:
                try:
                    os.unlink(confirmation_file)
                except:
                    pass
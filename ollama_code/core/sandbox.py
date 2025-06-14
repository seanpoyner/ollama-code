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
    def __init__(self, write_confirmation_callback=None):
        self.docker_client = None
        # Disable Docker by default for better reliability
        self.use_docker = False
        self.write_confirmation_callback = write_confirmation_callback
        
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
        temp_file = None
        confirmation_file = None
        try:
            # Create a temporary file for confirmation results
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                confirmation_file = f.name
            
            # Inject file operations into the code context
            setup_code = f"""
import os
import sys
import json
from pathlib import Path

# Change to user's working directory
os.chdir(r'{str(Path.cwd())}')

# Confirmation file for write operations
CONFIRMATION_FILE = r'{confirmation_file}'

def write_file(filename, content):
    \"\"\"Write content to a file\"\"\"
    try:
        # Request confirmation through temp file
        confirmation_request = {{
            'action': 'write_file',
            'filename': filename,
            'content': content
        }}
        
        with open(CONFIRMATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(confirmation_request, f)
        
        # Signal that we need confirmation by printing special marker
        print("###CONFIRMATION_NEEDED###", flush=True)
        print(f"Writing to: {{filename}}", flush=True)
        
        # Wait for confirmation result
        import time
        for _ in range(300):  # Wait up to 30 seconds
            try:
                with open(CONFIRMATION_FILE, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    if 'approved' in result:
                        if result['approved']:
                            # Actually write the file
                            file_path = Path(filename)
                            if file_path.parent != Path('.'):
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(filename, 'w', encoding='utf-8') as f:
                                f.write(content)
                            print(f"Created file: {{filename}}")
                            return f"File {{filename}} created successfully"
                        else:
                            feedback = result.get('feedback', 'File write cancelled by user')
                            print(f"File write cancelled: {{feedback}}")
                            return f"File write cancelled: {{feedback}}"
                        break
            except:
                pass
            time.sleep(0.1)
        
        print("Timeout waiting for file write confirmation")
        return "Timeout waiting for confirmation"
    except Exception as e:
        print(f"Failed to create file: {{e}}")
        return f"Failed to create file: {{e}}"

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

def bash(command):
    \"\"\"Execute a bash/shell command\"\"\"
    try:
        # Request confirmation through temp file
        confirmation_request = {{
            'action': 'bash_command',
            'command': command
        }}
        
        with open(CONFIRMATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(confirmation_request, f)
        
        # Signal that we need confirmation by printing special marker
        print("###BASH_CONFIRMATION_NEEDED###", flush=True)
        print(f"Command: {{command}}", flush=True)
        
        # Wait for confirmation result
        import time
        for _ in range(300):  # Wait up to 30 seconds
            try:
                with open(CONFIRMATION_FILE, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    if 'approved' in result:
                        if result['approved']:
                            # Actually execute the command
                            import subprocess
                            proc_result = subprocess.run(
                                command,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=30,
                                cwd=os.getcwd()
                            )
                            
                            output = proc_result.stdout
                            if proc_result.stderr:
                                output += f"\\n[stderr]\\n{{proc_result.stderr}}"
                            
                            if proc_result.returncode != 0:
                                print(f"Command failed with exit code {{proc_result.returncode}}")
                                return f"Command failed with exit code {{proc_result.returncode}}:\\n{{output}}"
                            
                            print(f"Command executed successfully")
                            return output if output else "Command executed successfully (no output)"
                        else:
                            print(f"Command cancelled by user")
                            return "Command cancelled by user"
                        break
            except:
                pass
            time.sleep(0.1)
        
        print("Timeout waiting for command confirmation")
        return "Timeout waiting for confirmation"
    except subprocess.TimeoutExpired:
        print("Command timed out")
        return "Command timed out after 30 seconds"
    except Exception as e:
        print(f"Failed to execute command: {{e}}")
        return f"Failed to execute command: {{e}}"

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
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    
                    # Check for confirmation request
                    if line == "###CONFIRMATION_NEEDED###":
                        logger.info("File write confirmation requested")
                        # Read the confirmation request
                        try:
                            import time
                            time.sleep(0.2)  # Give time for file to be written
                            with open(confirmation_file, 'r', encoding='utf-8') as f:
                                request = json.load(f)
                            
                            if request.get('action') == 'write_file' and self.write_confirmation_callback:
                                logger.info(f"Requesting confirmation for file: {request['filename']}")
                                # Get confirmation from user
                                approved, feedback = self.write_confirmation_callback(
                                    request['filename'],
                                    request['content']
                                )
                                
                                # Write response
                                response = {
                                    'approved': approved,
                                    'feedback': feedback
                                }
                                with open(confirmation_file, 'w', encoding='utf-8') as f:
                                    json.dump(response, f)
                                logger.info(f"Confirmation response: approved={approved}")
                        except Exception as e:
                            logger.error(f"Error handling confirmation: {e}")
                    
                    # Check for bash confirmation request
                    elif line == "###BASH_CONFIRMATION_NEEDED###":
                        try:
                            import time
                            time.sleep(0.1)  # Give time for file to be written
                            with open(confirmation_file, 'r', encoding='utf-8') as f:
                                request = json.load(f)
                            
                            if request.get('action') == 'bash_command' and hasattr(self, 'bash_confirmation_callback'):
                                # Get confirmation from user
                                approved = self.bash_confirmation_callback(request['command'])
                                
                                # Write response
                                response = {'approved': approved}
                                with open(confirmation_file, 'w', encoding='utf-8') as f:
                                    json.dump(response, f)
                        except Exception as e:
                            logger.error(f"Error handling bash confirmation: {e}")
            
            def read_stderr():
                for line in process.stderr:
                    error_lines.append(line.rstrip())
            
            # Start threads to read output
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            process.wait(timeout=timeout)
            
            # Wait for threads to finish reading
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
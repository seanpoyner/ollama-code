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
    def __init__(self):
        self.docker_client = None
        # Disable Docker by default for better reliability
        self.use_docker = False
        
        if DOCKER_AVAILABLE and self.use_docker:
            try:
                self.docker_client = docker.from_env()
                print("🐳 Docker connected")
            except:
                print("⚠️ Docker not available, using subprocess mode")
        else:
            print("⚙️ Using subprocess mode for code execution")
    
    def execute_python(self, code, timeout=30):
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
        try:
            # Inject file operations into the code context
            setup_code = """
import os
import sys
from pathlib import Path

# Change to user's working directory
os.chdir(r'""" + str(Path.cwd()) + """')

def write_file(filename, content):
    \"\"\"Write content to a file\"\"\"
    try:
        file_path = Path(filename)
        if file_path.parent != Path('.'):
            file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Created file: {filename}")
        return f"File {filename} created successfully"
    except Exception as e:
        print(f"❌ Failed to create file: {e}")
        return f"Failed to create file: {e}"

def read_file(filename):
    \"\"\"Read content from a file\"\"\"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        return f"Failed to read file: {e}"

def list_files(directory="."):
    \"\"\"List files in a directory\"\"\"
    try:
        files = list(Path(directory).iterdir())
        file_list = [f.name for f in files]
        return file_list
    except Exception as e:
        print(f"❌ Failed to list files: {e}")
        return f"Failed to list files: {e}"

# User code starts here
"""
            full_code = setup_code + code
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(full_code)
                temp_file = f.name
            
            # Use a try-except for timeout parameter compatibility
            try:
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tempfile.gettempdir()
                )
            except TypeError:
                # Fallback for older Python versions without timeout
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    cwd=tempfile.gettempdir()
                )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
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
            # Clean up temp file
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass
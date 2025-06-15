"""Environment detection and configuration management"""

import platform
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class EnvironmentDetector:
    """Detects and manages environment-specific configurations"""
    
    def __init__(self):
        self.os_type = self._detect_os()
        self.shell = self._detect_shell()
        self.shell_command = self._get_shell_command()
        self.env_info = self._gather_environment_info()
    
    def _detect_os(self) -> str:
        """Detect the operating system"""
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'macos'
        elif system == 'linux':
            # Check if running in WSL
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        return 'wsl'
            except:
                pass
            return 'linux'
        else:
            return 'unknown'
    
    def _detect_shell(self) -> str:
        """Detect the preferred shell for the current OS"""
        if self.os_type == 'windows':
            # Check if PowerShell is available
            try:
                result = subprocess.run(['powershell', '-Command', 'echo test'], 
                                     capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    return 'powershell'
            except:
                pass
            return 'cmd'
        
        elif self.os_type in ['linux', 'wsl', 'macos']:
            # Check SHELL environment variable
            shell = os.environ.get('SHELL', '')
            if 'bash' in shell:
                return 'bash'
            elif 'zsh' in shell:
                return 'zsh'
            elif 'fish' in shell:
                return 'fish'
            else:
                # Default to bash
                return 'bash'
        
        return 'unknown'
    
    def _get_shell_command(self) -> List[str]:
        """Get the shell command args for subprocess"""
        if self.os_type == 'windows':
            if self.shell == 'powershell':
                return ['powershell', '-NoProfile', '-Command']
            else:
                return ['cmd', '/c']
        
        elif self.os_type in ['linux', 'wsl', 'macos']:
            if self.shell == 'zsh':
                return ['/usr/bin/env', 'zsh', '-c']
            elif self.shell == 'fish':
                return ['/usr/bin/env', 'fish', '-c']
            else:
                return ['/bin/bash', '-c']
        
        # Fallback
        return ['sh', '-c']
    
    def _gather_environment_info(self) -> Dict:
        """Gather detailed environment information"""
        info = {
            'os_type': self.os_type,
            'os_name': platform.system(),
            'os_version': platform.version(),
            'os_release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'shell': self.shell,
            'shell_command': self.shell_command,
            'platform': platform.platform(),
            'home_directory': str(Path.home()),
            'current_directory': str(Path.cwd()),
        }
        
        # Add environment-specific info
        if self.os_type == 'windows':
            info['windows_version'] = platform.win32_ver()[0]
            info['windows_edition'] = platform.win32_edition() if hasattr(platform, 'win32_edition') else 'unknown'
        
        elif self.os_type == 'wsl':
            # Try to get WSL version
            try:
                result = subprocess.run(['wsl', '--version'], 
                                     capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    info['wsl_version'] = result.stdout.strip()
            except:
                pass
        
        return info
    
    def execute_command(self, command: str, timeout: int = 30, cwd: Optional[str] = None) -> Dict[str, any]:
        """Execute a shell command using the appropriate shell for the OS"""
        try:
            # Prepare the command based on OS
            if self.os_type == 'windows':
                if self.shell == 'powershell':
                    # PowerShell command
                    cmd_args = ['powershell', '-NoProfile', '-Command', command]
                else:
                    # CMD command
                    cmd_args = ['cmd', '/c', command]
            else:
                # Unix-like systems
                cmd_args = self.shell_command + [command]
            
            # Execute the command
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or os.getcwd(),
                encoding='utf-8',
                errors='replace'  # Handle encoding errors gracefully
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': None if result.returncode == 0 else f"Exit code: {result.returncode}",
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': f'Command timed out after {timeout} seconds',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'returncode': -1
            }
    
    def save_environment_config(self, directory: Path) -> bool:
        """Save environment configuration to a JSON file"""
        try:
            env_file = directory / 'environment.json'
            with open(env_file, 'w', encoding='utf-8') as f:
                json.dump(self.env_info, f, indent=2)
            logger.info(f"Saved environment configuration to {env_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save environment configuration: {e}")
            return False
    
    def load_environment_config(self, directory: Path) -> Optional[Dict]:
        """Load environment configuration from a JSON file"""
        try:
            env_file = directory / 'environment.json'
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load environment configuration: {e}")
        return None
    
    def get_safe_command(self, command: str) -> str:
        """Get a safe version of the command for the current OS"""
        if self.os_type == 'windows' and self.shell == 'powershell':
            # Escape special characters for PowerShell
            command = command.replace('"', '`"')
        return command


# Global instance
_env_detector = None


def get_environment_detector() -> EnvironmentDetector:
    """Get or create the global environment detector instance"""
    global _env_detector
    if _env_detector is None:
        _env_detector = EnvironmentDetector()
    return _env_detector
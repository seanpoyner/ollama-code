"""Automatic dependency management for ollama-code"""

import subprocess
import sys
import importlib
import importlib.metadata
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DependencyManager:
    """Manages automatic installation of dependencies"""
    
    # Core dependencies that must be installed
    # Format: 'import_name': ('pip_name', 'version_spec')
    REQUIRED_PACKAGES = {
        'ollama': ('ollama', '>=0.1.0'),
        'rich': ('rich', '>=13.0.0'),
        'requests': ('requests', '>=2.25.0'),
        'yaml': ('pyyaml', '>=5.4.0'),  # PyYAML imports as 'yaml'
    }
    
    # Optional packages with fallbacks
    OPTIONAL_PACKAGES = {
        'chromadb': '>=0.4.0',
        'docker': '>=5.0.0',
        'fastmcp': '>=0.1.0',
    }
    
    @staticmethod
    def check_package(package_name: str) -> bool:
        """Check if a package is installed"""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_installed_version(package_name: str) -> Optional[str]:
        """Get installed version of a package"""
        try:
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            return None
    
    @staticmethod
    def install_package(package_name: str, version_spec: str = '', verify_import: bool = True) -> bool:
        """Install a package using pip"""
        try:
            package_spec = f"{package_name}{version_spec}"
            logger.info(f"Installing {package_spec}...")
            
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", package_spec],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            
            if verify_import:
                # Only verify if package name matches import name
                importlib.invalidate_caches()
                try:
                    importlib.import_module(package_name)
                except ImportError:
                    # Package might have different import name (like pyyaml -> yaml)
                    pass
            
            logger.info(f"Successfully installed {package_spec}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install {package_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error installing {package_name}: {e}")
            return False
    
    @classmethod
    def ensure_dependencies(cls, auto_install: bool = True) -> Tuple[bool, List[str]]:
        """
        Ensure all required dependencies are installed.
        
        Args:
            auto_install: If True, automatically install missing packages
            
        Returns:
            Tuple of (success, list of missing packages)
        """
        missing_packages = []
        
        # Check required packages
        for import_name, package_info in cls.REQUIRED_PACKAGES.items():
            if isinstance(package_info, tuple):
                pip_name, version_spec = package_info
            else:
                # For backward compatibility
                pip_name = import_name
                version_spec = package_info
            
            if not cls.check_package(import_name):
                missing_packages.append(f"{pip_name}{version_spec}")
                if auto_install:
                    if not cls.install_package(pip_name, version_spec):
                        return False, missing_packages
                    # Verify the import works with the correct import name
                    if not cls.check_package(import_name):
                        return False, missing_packages
        
        # If any required packages are missing and we couldn't install them
        if missing_packages and not auto_install:
            return False, missing_packages
        
        return True, []
    
    @classmethod
    def check_optional_features(cls) -> dict:
        """
        Check which optional features are available.
        
        Returns:
            Dictionary mapping feature names to availability
        """
        features = {}
        
        # Check ChromaDB for vector search
        features['vector_search'] = cls.check_package('chromadb')
        
        # Check Docker for sandboxed execution
        features['docker'] = cls.check_package('docker')
        
        # Check MCP for extended tools
        features['mcp'] = cls.check_package('fastmcp')
        
        return features
    
    @classmethod
    def install_optional_package(cls, package_name: str) -> bool:
        """Install an optional package"""
        if package_name in cls.OPTIONAL_PACKAGES:
            version_spec = cls.OPTIONAL_PACKAGES[package_name]
            return cls.install_package(package_name, version_spec)
        return False
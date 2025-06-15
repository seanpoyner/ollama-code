#!/usr/bin/env python3
"""
Dependency installer for ollama-code.

This script handles installing dependencies, including ChromaDB,
in a way that works with system-managed Python environments.
"""

import subprocess
import sys
import os
from pathlib import Path

def install_with_pip(package, break_system_packages=False):
    """Install a package using pip."""
    cmd = [sys.executable, "-m", "pip", "install", package]
    if break_system_packages:
        cmd.append("--break-system-packages")
    
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False

def check_chromadb():
    """Check if ChromaDB is installed."""
    try:
        import chromadb
        return True
    except ImportError:
        return False

def main():
    print("🔧 Ollama Code Dependency Installer\n")
    
    # Check if ChromaDB is already installed
    if check_chromadb():
        print("✅ ChromaDB is already installed!")
        return 0
    
    print("ChromaDB is not installed. This is required for semantic documentation search.\n")
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if in_venv:
        print("📦 Installing ChromaDB in virtual environment...")
        if install_with_pip("chromadb>=0.4.0"):
            print("✅ ChromaDB installed successfully!")
            return 0
        else:
            print("❌ Failed to install ChromaDB")
            return 1
    else:
        # System Python environment
        print("⚠️  System Python detected. ChromaDB installation requires special handling.\n")
        print("Options:")
        print("1. Create a virtual environment (recommended)")
        print("2. Install with --break-system-packages (not recommended)")
        print("3. Use pipx to manage the installation")
        print("4. Skip ChromaDB (use SQLite fallback)\n")
        
        choice = input("Select an option (1-4): ").strip()
        
        if choice == "1":
            # Create virtual environment
            venv_path = Path.cwd() / "venv"
            print(f"\n📁 Creating virtual environment at {venv_path}...")
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
            
            # Determine the correct activation script
            if os.name == 'nt':  # Windows
                activate_cmd = f"{venv_path}\\Scripts\\activate"
                pip_path = f"{venv_path}\\Scripts\\pip"
            else:  # Unix-like
                activate_cmd = f"source {venv_path}/bin/activate"
                pip_path = f"{venv_path}/bin/pip"
            
            print("\n✅ Virtual environment created!")
            print(f"\nTo use it:")
            print(f"1. Activate: {activate_cmd}")
            print(f"2. Install deps: pip install -e .")
            print(f"3. Run: ollama-code")
            
            # Install in the venv
            print(f"\n📦 Installing dependencies in virtual environment...")
            subprocess.check_call([pip_path, "install", "-e", "."])
            print("\n✅ All dependencies installed!")
            
        elif choice == "2":
            print("\n⚠️  Installing with --break-system-packages...")
            if install_with_pip("chromadb>=0.4.0", break_system_packages=True):
                print("✅ ChromaDB installed successfully!")
                return 0
            else:
                print("❌ Failed to install ChromaDB")
                return 1
                
        elif choice == "3":
            print("\n📦 Installing with pipx...")
            print("First, install pipx if not already installed:")
            print("  python3 -m pip install --user pipx")
            print("  python3 -m pipx ensurepath")
            print("\nThen install ollama-code:")
            print("  pipx install --editable .")
            
        elif choice == "4":
            print("\n⚠️  Skipping ChromaDB installation.")
            print("The application will use SQLite for documentation search.")
            print("This may result in less accurate search results.")
            return 0
        else:
            print("\n❌ Invalid choice")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
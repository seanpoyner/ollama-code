#!/usr/bin/env python3
"""
Universal installer for ollama-code
"""

import subprocess
import sys
import os

def run_command(cmd, check=True):
    """Run a command and return success status"""
    try:
        subprocess.run(cmd, shell=True, check=check)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("\n🦙 Ollama Code Installer\n")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return 1
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Ask about installation type
    print("\nChoose installation type:")
    print("1. Basic (minimal dependencies)")
    print("2. Recommended (with ChromaDB for better search)")
    print("3. Full (all optional features)")
    print("4. Custom (choose features)")
    
    choice = input("\nSelect (1-4) [2]: ").strip() or "2"
    
    # Determine what to install
    if choice == "1":
        extras = ""
        print("\n📦 Installing basic version...")
    elif choice == "2":
        extras = "[chromadb]"
        print("\n📦 Installing with ChromaDB for better search...")
    elif choice == "3":
        extras = "[all]"
        print("\n📦 Installing all features...")
    elif choice == "4":
        features = []
        if input("Include ChromaDB for better search? (y/N): ").lower() == 'y':
            features.append("chromadb")
        if input("Include Docker support? (y/N): ").lower() == 'y':
            features.append("docker")
        if input("Include MCP tools? (y/N): ").lower() == 'y':
            features.append("mcp")
        extras = f"[{','.join(features)}]" if features else ""
        print(f"\n📦 Installing with: {extras or 'basic features'}")
    else:
        print("Invalid choice, using recommended")
        extras = "[chromadb]"
    
    # Check if in virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_venv:
        print("\n⚠️  Not in a virtual environment")
        if input("Create one? (Y/n): ").lower() != 'n':
            print("\nCreating virtual environment...")
            run_command(f"{sys.executable} -m venv venv")
            print("\n✅ Virtual environment created!")
            print("\nTo activate it:")
            if os.name == 'nt':
                print("  venv\\Scripts\\activate")
            else:
                print("  source venv/bin/activate")
            print("\nThen run this installer again.")
            return 0
    
    # Install
    print("\nInstalling ollama-code...")
    cmd = f"pip install -e .{extras}"
    
    if run_command(cmd):
        print("\n✅ Installation complete!")
        print("\nTo run ollama-code:")
        print("  ollama-code")
        print("\nMake sure Ollama is running:")
        print("  ollama serve")
        
        if "chromadb" in extras:
            print("\nFor best vector search results:")
            print("  ollama pull nomic-embed-text")
        
        return 0
    else:
        print("\n❌ Installation failed")
        print("\nTry installing manually:")
        print(f"  pip install -e .{extras}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
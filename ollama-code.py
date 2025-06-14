#!/usr/bin/env python
"""
ollama-code.py - Legacy entry point

This file is kept for backward compatibility.
The code has been refactored into a modular structure.
"""

import sys
import os

# Add the current directory to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_code.main import run

if __name__ == "__main__":
    run()
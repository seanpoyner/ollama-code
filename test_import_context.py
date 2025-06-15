#!/usr/bin/env python3
"""Test to reproduce the exact import context issue"""

import sys
import os
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Replicate the exact import setup from ollama-code.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Testing ChromaDB Import in Full Context ===")

# First, let's see what happens when we import in the exact order
try:
    # Import logging setup first (as main.py does)
    from ollama_code.utils.logging import setup_logging
    logger = setup_logging()
    print("✓ Logging setup complete")
    
    # Import other utilities
    from ollama_code.utils.messages import get_message
    print("✓ Messages imported")
    
    # Import core components
    from ollama_code.core.agent import OllamaCodeAgent
    print("✓ Agent imported")
    
    # Now check if ChromaDB is available
    from ollama_code.core.doc_vector_store import CHROMADB_AVAILABLE
    print(f"\n✓ doc_vector_store imported")
    print(f"  CHROMADB_AVAILABLE = {CHROMADB_AVAILABLE}")
    
    if not CHROMADB_AVAILABLE:
        print("\n✗ ChromaDB is reported as NOT AVAILABLE!")
        # Let's try importing it directly here
        try:
            import chromadb
            print(f"  But direct import works! Version: {chromadb.__version__}")
            print("  This suggests the import failed during module loading")
        except ImportError as e:
            print(f"  Direct import also fails: {e}")
    
except Exception as e:
    print(f"\n✗ Import failed: {e}")
    import traceback
    traceback.print_exc()

# Let's also check if there's any module name shadowing
print("\n=== Checking for module shadowing ===")
import importlib.util

# Check if there's a local chromadb module
spec = importlib.util.find_spec("chromadb")
if spec:
    print(f"chromadb module found at: {spec.origin}")
    
# Check for utils module
spec = importlib.util.find_spec("utils")
if spec:
    print(f"utils module found at: {spec.origin}")
    
# Check ollama_code.utils
spec = importlib.util.find_spec("ollama_code.utils")
if spec:
    print(f"ollama_code.utils module found at: {spec.origin}")
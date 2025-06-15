#!/usr/bin/env python3
"""Test script to debug ChromaDB import issue in ollama-code context"""

import sys
import os

print("=== Testing ChromaDB Import Issue ===")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")

# Test 1: Import without modifying sys.path
print("\n1. Testing import WITHOUT modifying sys.path:")
try:
    import chromadb
    print("✓ ChromaDB imported successfully!")
    print(f"  Location: {chromadb.__file__}")
    from chromadb.utils import embedding_functions
    print("✓ embedding_functions imported successfully!")
except ImportError as e:
    print(f"✗ Import failed: {e}")

# Test 2: Import after adding current directory to sys.path (like ollama-code.py does)
print("\n2. Testing import AFTER adding current directory to sys.path:")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
print(f"Added to sys.path: {os.path.dirname(os.path.abspath(__file__))}")

# Clear any cached imports
if 'chromadb' in sys.modules:
    del sys.modules['chromadb']
if 'chromadb.utils' in sys.modules:
    del sys.modules['chromadb.utils']

try:
    import chromadb
    print("✓ ChromaDB imported successfully!")
    print(f"  Location: {chromadb.__file__}")
    from chromadb.utils import embedding_functions
    print("✓ embedding_functions imported successfully!")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

# Test 3: Check for utils module conflicts
print("\n3. Checking for 'utils' module conflicts:")
try:
    import utils
    print(f"✗ Found local 'utils' module at: {utils.__file__}")
    print("  This might be interfering with chromadb.utils imports!")
except ImportError:
    print("✓ No top-level 'utils' module found (good)")

# Test 4: Check sys.path order
print("\n4. Current sys.path order:")
for i, path in enumerate(sys.path[:5]):  # Show first 5 entries
    print(f"  [{i}] {path}")
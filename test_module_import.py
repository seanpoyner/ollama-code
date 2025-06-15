#!/usr/bin/env python3
"""Test importing doc_vector_store in the ollama-code context"""

import sys
import os

# Replicate the exact import setup from ollama-code.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Testing doc_vector_store Import ===")
print(f"Python path[0]: {sys.path[0]}")

# Test the imports in the same order as the application
try:
    print("\n1. Testing ollama_code.main import:")
    from ollama_code.main import run
    print("✓ ollama_code.main imported successfully!")
    
    print("\n2. Testing doc_vector_store import directly:")
    from ollama_code.core.doc_vector_store import DocVectorStore, CHROMADB_AVAILABLE
    print(f"✓ doc_vector_store imported successfully!")
    print(f"  CHROMADB_AVAILABLE: {CHROMADB_AVAILABLE}")
    
    print("\n3. Testing doc_integration import:")
    from ollama_code.core.doc_integration import DocumentationAssistant
    print("✓ doc_integration imported successfully!")
    
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

# Check if ChromaDB is actually available
print("\n4. Checking ChromaDB availability:")
try:
    import chromadb
    print(f"✓ ChromaDB is installed: {chromadb.__version__}")
except ImportError:
    print("✗ ChromaDB is not installed")

# Test creating a DocVectorStore instance
print("\n5. Testing DocVectorStore instantiation:")
try:
    if CHROMADB_AVAILABLE:
        store = DocVectorStore()
        print("✓ DocVectorStore created successfully!")
    else:
        print("✗ ChromaDB is not available in doc_vector_store module")
except Exception as e:
    print(f"✗ Failed to create DocVectorStore: {e}")
    import traceback
    traceback.print_exc()
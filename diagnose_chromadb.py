#!/usr/bin/env python3
"""Comprehensive diagnostic for ChromaDB import issues"""

import sys
import os
import subprocess
import importlib

print("=== ChromaDB Import Diagnostics ===\n")

# 1. Check Python environment
print("1. Python Environment:")
print(f"   Python version: {sys.version}")
print(f"   Python executable: {sys.executable}")
print(f"   Virtual environment: {os.environ.get('VIRTUAL_ENV', 'None')}")

# 2. Check if ChromaDB is installed
print("\n2. ChromaDB Installation:")
try:
    result = subprocess.run([sys.executable, "-m", "pip", "show", "chromadb"], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✓ ChromaDB is installed via pip")
        for line in result.stdout.split('\n'):
            if line.startswith(('Version:', 'Location:')):
                print(f"     {line}")
    else:
        print("   ✗ ChromaDB is NOT installed via pip")
except Exception as e:
    print(f"   Error checking pip: {e}")

# 3. Test direct import
print("\n3. Direct Import Test:")
try:
    import chromadb
    print(f"   ✓ Direct import successful")
    print(f"     Version: {chromadb.__version__}")
    print(f"     Location: {chromadb.__file__}")
except ImportError as e:
    print(f"   ✗ Direct import failed: {e}")

# 4. Test in ollama-code context
print("\n4. Import in ollama-code Context:")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from ollama_code.core.doc_vector_store import CHROMADB_AVAILABLE, DocVectorStore
    print(f"   ✓ doc_vector_store import successful")
    print(f"     CHROMADB_AVAILABLE = {CHROMADB_AVAILABLE}")
    
    if CHROMADB_AVAILABLE:
        # Try to create an instance
        store = DocVectorStore()
        print("   ✓ DocVectorStore instantiation successful")
    else:
        print("   ✗ ChromaDB reported as unavailable in module")
except Exception as e:
    print(f"   ✗ Import/instantiation failed: {e}")
    import traceback
    traceback.print_exc()

# 5. Check for conflicting modules
print("\n5. Module Conflicts Check:")
modules_to_check = ['chromadb', 'utils', 'sqlite3', 'typing']
for module_name in modules_to_check:
    try:
        spec = importlib.util.find_spec(module_name)
        if spec and spec.origin:
            print(f"   {module_name}: {spec.origin}")
    except Exception:
        print(f"   {module_name}: Not found")

# 6. Environment variables
print("\n6. Relevant Environment Variables:")
env_vars = ['PYTHONPATH', 'LD_LIBRARY_PATH', 'PATH']
for var in env_vars:
    value = os.environ.get(var, 'Not set')
    if len(value) > 100:
        value = value[:100] + "..."
    print(f"   {var}: {value}")

# 7. Test ChromaDB functionality
print("\n7. ChromaDB Functionality Test:")
try:
    import chromadb
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        client = chromadb.PersistentClient(path=tmpdir)
        collection = client.create_collection("test")
        print("   ✓ Can create ChromaDB client and collection")
except Exception as e:
    print(f"   ✗ ChromaDB functionality test failed: {e}")

print("\n=== End of Diagnostics ===")
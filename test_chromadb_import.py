#!/usr/bin/env python3
"""Test ChromaDB import and availability"""

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Python path:")
for p in sys.path:
    print(f"  {p}")

print("\nTrying to import chromadb...")
try:
    import chromadb
    print(f"✓ ChromaDB imported successfully!")
    print(f"  Version: {chromadb.__version__}")
    print(f"  Location: {chromadb.__file__}")
except ImportError as e:
    print(f"✗ Failed to import chromadb: {e}")
    print("\nTrying to find chromadb in site-packages...")
    import os
    for path in sys.path:
        if os.path.exists(path):
            chromadb_path = os.path.join(path, "chromadb")
            if os.path.exists(chromadb_path):
                print(f"  Found chromadb at: {chromadb_path}")

print("\nChecking if we can import specific chromadb modules...")
try:
    from chromadb.utils import embedding_functions
    print("✓ Can import embedding_functions")
except ImportError as e:
    print(f"✗ Cannot import embedding_functions: {e}")
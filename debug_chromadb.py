#!/usr/bin/env python
"""Debug ChromaDB import in current environment"""

import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    import chromadb
    print(f"✓ ChromaDB imported successfully!")
    print(f"  Version: {chromadb.__version__}")
    print(f"  Location: {chromadb.__file__}")
    
    # Try to create a client
    client = chromadb.Client()
    print("✓ ChromaDB client created successfully!")
except ImportError as e:
    print(f"✗ Failed to import chromadb: {e}")
except Exception as e:
    print(f"✗ Error creating client: {e}")
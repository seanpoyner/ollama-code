#!/usr/bin/env python3
"""Test script to verify WSL to Windows Ollama connection"""

import os
import subprocess
import ollama

def test_connection():
    print("Testing Ollama connection from WSL...")
    
    # Check if we're in WSL
    if 'microsoft' in os.uname().release.lower() or 'WSL' in os.uname().release:
        print("✓ Running in WSL")
        
        # Get Windows host IP
        try:
            result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'default' in line:
                    windows_ip = line.split()[2]
                    print(f"✓ Windows host IP: {windows_ip}")
                    
                    # Test connections
                    print("\nTesting connections:")
                    
                    # Test localhost
                    print("1. Testing localhost:11434...")
                    try:
                        client_local = ollama.Client()
                        response = client_local.list()
                        print(f"   ✓ SUCCESS: Found {len(response.get('models', []))} models")
                    except Exception as e:
                        print(f"   ✗ FAILED: {type(e).__name__}: {e}")
                    
                    # Test Windows host
                    print(f"\n2. Testing {windows_ip}:11434...")
                    try:
                        client_windows = ollama.Client(host=f'http://{windows_ip}:11434')
                        response = client_windows.list()
                        print(f"   ✓ SUCCESS: Found {len(response.get('models', []))} models")
                        print("\n   Models found:")
                        for model in response.get('models', []):
                            print(f"   - {model.get('name')}")
                    except Exception as e:
                        print(f"   ✗ FAILED: {type(e).__name__}: {e}")
                    
                    break
        except Exception as e:
            print(f"✗ Error getting Windows IP: {e}")
    else:
        print("✗ Not running in WSL")

if __name__ == "__main__":
    test_connection()
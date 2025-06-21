#!/usr/bin/env python3
"""Diagnose Ollama connectivity issues in WSL"""

import os
import subprocess
import socket
import time

def check_port(host, port, timeout=2):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def diagnose():
    print("🔍 Ollama Connection Diagnostics\n")
    
    # 1. Check environment
    print("1. Environment Check:")
    print(f"   - OS: {os.uname().sysname}")
    print(f"   - Release: {os.uname().release}")
    is_wsl = 'microsoft' in os.uname().release.lower() or 'WSL' in os.uname().release
    print(f"   - Is WSL: {is_wsl}")
    print(f"   - OLLAMA_HOST env: {os.getenv('OLLAMA_HOST', 'not set')}")
    
    # 2. Get Windows host IP
    windows_ip = None
    if is_wsl:
        print("\n2. Windows Host IP:")
        try:
            result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'default' in line:
                    windows_ip = line.split()[2]
                    print(f"   - Windows IP: {windows_ip}")
                    break
        except Exception as e:
            print(f"   - Error: {e}")
    
    # 3. Check port connectivity
    print("\n3. Port Connectivity (11434):")
    hosts_to_check = [
        ('localhost', '127.0.0.1'),
        ('::1', '::1'),
    ]
    if windows_ip:
        hosts_to_check.append(('Windows host', windows_ip))
    
    for name, host in hosts_to_check:
        print(f"   - {name} ({host}): ", end='')
        if check_port(host, 11434):
            print("✓ OPEN")
        else:
            print("✗ CLOSED/UNREACHABLE")
    
    # 4. Try curl
    print("\n4. HTTP Connectivity Test:")
    for name, host in hosts_to_check:
        print(f"   - {name} ({host}): ", end='', flush=True)
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '2', f'http://{host}:11434/'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✓ HTTP OK (Response: {result.stdout[:50]}...)")
            else:
                print(f"✗ HTTP FAILED (Code: {result.returncode})")
        except Exception as e:
            print(f"✗ ERROR: {e}")
    
    # 5. Suggestions
    print("\n5. Diagnosis:")
    if is_wsl:
        print("   You are running in WSL. Ollama running on Windows needs special configuration:")
        print("   \n   Option 1: Configure Ollama to listen on all interfaces")
        print("   - Set OLLAMA_HOST=0.0.0.0 before starting Ollama on Windows")
        print("   - Or run: ollama serve --host 0.0.0.0")
        print("   \n   Option 2: Set OLLAMA_HOST in WSL")
        print(f"   - export OLLAMA_HOST=http://{windows_ip or 'YOUR_WINDOWS_IP'}:11434")
        print("   \n   Option 3: Run Ollama inside WSL")
        print("   - Install and run Ollama directly in WSL")

if __name__ == "__main__":
    diagnose()
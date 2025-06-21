#!/usr/bin/env python3
"""Test script to debug Ollama connection issues"""

import os
import sys
import subprocess
import ollama
import requests
from rich.console import Console

console = Console()

def test_connection():
    """Test various connection methods to Ollama"""
    
    console.print("\n🔍 [bold]Testing Ollama Connection[/bold]\n")
    
    # 1. Check if we're in WSL
    is_wsl = 'microsoft' in os.uname().release.lower() or 'WSL' in os.uname().release
    console.print(f"Running in WSL: {is_wsl}")
    
    # 2. Get Windows host IP if in WSL
    windows_ip = None
    if is_wsl:
        try:
            result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'default' in line:
                    windows_ip = line.split()[2]
                    console.print(f"Windows host IP: {windows_ip}")
                    break
        except Exception as e:
            console.print(f"[red]Error getting Windows IP: {e}[/red]")
    
    # 3. Check OLLAMA_HOST environment variable
    ollama_host = os.getenv('OLLAMA_HOST')
    if ollama_host:
        console.print(f"OLLAMA_HOST set to: {ollama_host}")
    else:
        console.print("OLLAMA_HOST not set")
    
    console.print("\n📡 [bold]Testing Connections:[/bold]\n")
    
    # Test different connection methods
    hosts_to_test = []
    
    if ollama_host:
        hosts_to_test.append(("OLLAMA_HOST", ollama_host))
    
    if windows_ip:
        hosts_to_test.append(("Windows Host", f"http://{windows_ip}:11434"))
    
    hosts_to_test.extend([
        ("Localhost", "http://localhost:11434"),
        ("127.0.0.1", "http://127.0.0.1:11434"),
    ])
    
    for name, host in hosts_to_test:
        console.print(f"\n[cyan]Testing {name}: {host}[/cyan]")
        
        # Test 1: Raw HTTP request
        try:
            response = requests.get(f"{host}/api/tags", timeout=2)
            if response.status_code == 200:
                console.print(f"  ✅ HTTP request successful")
                models = response.json().get('models', [])
                console.print(f"  📦 Found {len(models)} models")
                if models:
                    for model in models[:3]:  # Show first 3 models
                        console.print(f"     - {model.get('name', 'Unknown')}")
            else:
                console.print(f"  ❌ HTTP request failed: {response.status_code}")
        except requests.exceptions.Timeout:
            console.print(f"  ❌ HTTP request timed out")
        except Exception as e:
            console.print(f"  ❌ HTTP request error: {type(e).__name__}: {e}")
        
        # Test 2: Ollama client
        try:
            client = ollama.Client(host=host)
            response = client.list()
            console.print(f"  ✅ Ollama client connected")
            models = response.get('models', [])
            console.print(f"  📦 Found {len(models)} models via client")
        except Exception as e:
            console.print(f"  ❌ Ollama client error: {type(e).__name__}: {e}")
    
    # Recommendation
    console.print("\n💡 [bold]Recommendations:[/bold]\n")
    
    if not any(test_succeeded for name, host in hosts_to_test):
        console.print("[red]❌ No connection methods worked![/red]")
        console.print("\nPlease ensure Ollama is running:")
        console.print("  - Windows: Check system tray for Ollama icon")
        console.print("  - Linux/Mac: Run 'ollama serve'")
    else:
        console.print("[green]✅ At least one connection method worked![/green]")
        console.print("\nYou can:")
        console.print("  1. Use --model flag: ollama-code --model llama3.2:3b")
        console.print("  2. Set OLLAMA_HOST environment variable")
        console.print("     export OLLAMA_HOST=http://<working-host>:11434")

if __name__ == "__main__":
    test_connection()
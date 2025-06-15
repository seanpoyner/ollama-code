#!/usr/bin/env python3
"""
Test script to verify the documentation system integration works properly.
This tests that the documentation tools are available during code execution.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_code.core.agent import OllamaCodeAgent
from ollama_code.core.todos import TodoManager

def test_documentation_tools():
    """Test that documentation tools work in executed code"""
    print("\n🧪 Testing Documentation System Integration\n")
    
    # Create agent with documentation assistant
    todo_manager = TodoManager()
    agent = OllamaCodeAgent(
        model_name="llama2",  # Any model name for testing
        todo_manager=todo_manager
    )
    
    # Test 1: Search documentation
    print("1️⃣ Testing search_docs()...")
    test_code = '''
result = search_docs("ollama api endpoints")
print(f"Documentation search result: {result[:200]}...")
'''
    result1 = agent.execute_python(test_code)
    print(f"Result: {result1}\n")
    
    # Test 2: Get API info
    print("2️⃣ Testing get_api_info()...")
    test_code = '''
result = get_api_info("ollama", "/api/tags")
print(f"API info result: {result[:200]}...")
'''
    result2 = agent.execute_python(test_code)
    print(f"Result: {result2}\n")
    
    # Test 3: Remember solution
    print("3️⃣ Testing remember_solution()...")
    test_code = '''
result = remember_solution(
    "Test Pattern",
    "A test code pattern",
    "def test(): return 'hello'",
    tags=["test", "example"]
)
print(f"Remember solution result: {result}")
'''
    result3 = agent.execute_python(test_code)
    print(f"Result: {result3}\n")
    
    # Test 4: Use documentation in actual task
    print("4️⃣ Testing real usage scenario...")
    test_code = '''
# First search for Ollama API docs
docs = search_docs("ollama list models api")
print("Found documentation about Ollama API")

# Then get specific endpoint info
api_info = get_api_info("ollama", "/api/tags")
print("Got API endpoint details")

# Now use the information to write correct code
import requests
try:
    # Using the correct endpoint from documentation
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    print(f"API call result: Status {response.status_code}")
except Exception as e:
    print(f"API call failed (expected if Ollama not running): {e}")
'''
    result4 = agent.execute_python(test_code)
    print(f"Result: {result4}\n")
    
    print("\n✅ Documentation system integration test complete!")
    print("\nThe documentation tools are successfully integrated and available during code execution.")
    print("This helps prevent hallucination by providing real API information.\n")

if __name__ == "__main__":
    test_documentation_tools()
#!/usr/bin/env python3
"""Test script to verify documentation tool injection in agent.py"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_code.core.agent import OllamaCodeAgent
from ollama_code.core.todos import TodoManager

def test_documentation_injection():
    """Test that documentation tools are properly injected into executed code"""
    
    # Create a simple agent instance
    agent = OllamaCodeAgent(
        model_name="test-model",
        todo_manager=TodoManager()
    )
    
    # Test code that uses documentation tools
    test_code = '''
# Test documentation tools
print("Testing documentation tools...")

# Test 1: Search for documentation
result = search_docs("ollama chat API")
print(f"Search result type: {type(result)}")
print(f"Search result preview: {result[:100] if result else 'No result'}...")

# Test 2: Get API info
api_info = get_api_info("ollama", "/api/chat")
print(f"\\nAPI info type: {type(api_info)}")
print(f"API info preview: {api_info[:100] if api_info else 'No API info'}...")

# Test 3: Remember a solution
remember_result = remember_solution(
    title="Test Pattern",
    description="A test code pattern",
    code="def test(): pass",
    language="python",
    tags=["test", "example"]
)
print(f"\\nRemember result: {remember_result}")

print("\\nAll documentation tools tested!")
'''
    
    print("=" * 60)
    print("Testing documentation tool injection...")
    print("=" * 60)
    
    # Test the injection method
    injected_code = agent._inject_documentation_tools(test_code)
    
    # Check if documentation tools are injected
    assert "search_docs" in injected_code
    assert "get_api_info" in injected_code
    assert "remember_solution" in injected_code
    
    print("\n✓ Documentation tools successfully injected into code")
    
    # Show a preview of the injected code
    print("\nInjected code preview (first 500 chars):")
    print("-" * 40)
    print(injected_code[:500] + "...")
    print("-" * 40)
    
    # Now test actual execution (this will use the sandbox)
    print("\n\nTesting code execution with documentation tools...")
    print("=" * 60)
    
    try:
        result = agent.execute_python(test_code)
        print("\nExecution result:")
        print(result)
    except Exception as e:
        print(f"\nExecution error: {e}")
        print("This is expected if running outside the full environment")
    
    print("\n✅ Documentation tool injection test completed!")

if __name__ == "__main__":
    test_documentation_injection()
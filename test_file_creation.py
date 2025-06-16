#!/usr/bin/env python3
"""
Test script to verify the AI properly creates files using write_file()
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_code.core.thought_loop import ThoughtLoop
from ollama_code.core.todos import TodoManager

def test_file_creation_guidance():
    """Test that the guidance properly instructs AI to create files"""
    
    # Create a thought loop with a todo manager
    todo_manager = TodoManager()
    thought_loop = ThoughtLoop(todo_manager)
    
    # Test different types of tasks - make them complex enough to trigger task breakdown
    test_tasks = [
        "Create a web application with HTML homepage and CSS styling",
        "Implement a Python backend service with multiple endpoints and error handling", 
        "Write comprehensive test scripts for the API with multiple test cases",
        "Develop a complete configuration system with JSON files and validation"
    ]
    
    for task in test_tasks:
        print(f"\n{'='*60}")
        print(f"Testing task: {task}")
        print('='*60)
        
        # Process the request (this would normally add to todos)
        tasks, response = thought_loop.process_request(task)
        
        if tasks:
            print(f"\nTask breakdown created: {len(tasks)} tasks")
            
            # Get the context that would be sent to the AI
            todo_manager.add_todo(content=task, priority="high")
            context = thought_loop.get_next_task_context()
            
            if context:
                print("\nContext sent to AI:")
                print("-" * 40)
                # Show key parts of the context
                if "[FILE CREATION TASK]" in context:
                    start = context.find("[FILE CREATION TASK]")
                    end = context.find("CURRENT WORKING DIRECTORY:", start)
                    if end == -1:
                        end = start + 500
                    print(context[start:end])
                else:
                    print(context[:500])
                
                # Check for proper guidance
                checks = {
                    "write_file mentioned": "write_file" in context,
                    "Python blocks required": "```python" in context,
                    "Warning about other blocks": any(x in context for x in ["```html", "```css", "```javascript"]),
                    "Validation warning": "TASK VALIDATION" in context or "task validator" in context
                }
                
                print("\nValidation checks:")
                for check, result in checks.items():
                    status = "✓" if result else "✗"
                    print(f"  {status} {check}")
            
            # Clear for next test
            todo_manager.clear()

if __name__ == "__main__":
    test_file_creation_guidance()
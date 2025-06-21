#!/usr/bin/env python3
"""Test script to verify model selection works correctly"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_code.cli import get_ollama_client

def test_model_listing():
    """Test that model listing works with both response formats"""
    print("Testing model listing...")
    
    try:
        client = get_ollama_client()
        response = client.list()
        
        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")
        
        # Handle both dict and object responses
        if hasattr(response, 'models'):
            models = response.models
            print(f"✓ Found models attribute")
        else:
            models = response.get('models', [])
            print(f"✓ Using dict access")
        
        print(f"\nFound {len(models)} models:")
        for i, model in enumerate(models):
            # Handle both dict and object model formats
            if hasattr(model, 'model'):
                name = model.model
                print(f"  {i+1}. {name} (object format)")
            else:
                name = model.get('name', model.get('model', 'Unknown'))
                print(f"  {i+1}. {name} (dict format)")
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Ollama Model Selection Test")
    print("=" * 40)
    
    success = test_model_listing()
    
    if success:
        print("\n✅ Model selection should work correctly!")
    else:
        print("\n❌ Model selection may have issues")
        print("\nMake sure Ollama is running:")
        print("  - In Docker: ollama serve &")
        print("  - On host: Make sure Ollama is installed and running")
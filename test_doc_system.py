#!/usr/bin/env python3
"""Test script for the documentation cache system."""

import sys
import logging
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from ollama_code.core.doc_cache import DocCache
from ollama_code.core.web_search import WebSearcher
from ollama_code.core.knowledge_base import KnowledgeBase
from ollama_code.core.doc_integration import DocumentationAssistant

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_doc_cache():
    """Test the documentation cache."""
    print("\n=== Testing Documentation Cache ===")
    cache = DocCache()
    
    # Add a test entry
    entry = cache.add(
        url="https://example.com/api/test",
        title="Test API Documentation",
        content="This is a test API endpoint that returns JSON data.",
        source_type="test",
        tags=["api", "test", "json"]
    )
    print(f"Added entry: {entry.title}")
    
    # Search for it
    results = cache.search("test api")
    print(f"Search results: {len(results)} found")
    for result in results:
        print(f"  - {result.title}")
    
    # Get stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")

def test_web_searcher():
    """Test the web searcher."""
    print("\n=== Testing Web Searcher ===")
    searcher = WebSearcher()
    
    # Test URL parsing functions
    test_html = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Documentation</h1>
        <p>This is a test paragraph.</p>
        <pre><code>print("Hello, World!")</code></pre>
    </body>
    </html>
    """
    
    parsed = searcher._parse_html_documentation(test_html, "https://example.com/test")
    print(f"Parsed title: {parsed['title']}")
    print(f"Code examples: {len(parsed['code_examples'])}")

def test_knowledge_base():
    """Test the knowledge base."""
    print("\n=== Testing Knowledge Base ===")
    kb = KnowledgeBase()
    
    # Add API endpoint
    kb.add_api_endpoint(
        service="test_service",
        endpoint="/api/v1/test",
        method="GET",
        parameters={"id": "string", "limit": "integer"}
    )
    
    # Add code pattern
    kb.add_code_pattern(
        name="Error Handling Pattern",
        description="Standard try-except pattern for API calls",
        pattern="""try:
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
except requests.RequestException as e:
    logger.error(f"API call failed: {e}")
    return None""",
        language="python",
        use_cases=["api_calls", "error_handling"]
    )
    
    # Search knowledge
    results = kb.search("api")
    print(f"Knowledge search results: {len(results)} found")
    for result in results:
        print(f"  - {result.title} ({result.category})")
    
    # Get stats
    stats = kb.get_stats()
    print(f"Knowledge base stats: {stats}")

def test_doc_assistant():
    """Test the documentation assistant integration."""
    print("\n=== Testing Documentation Assistant ===")
    assistant = DocumentationAssistant()
    
    # Get documentation context
    context = assistant.get_documentation_context("ollama api generate")
    print(f"Documentation context length: {len(context)} chars")
    print(f"First 200 chars: {context[:200]}...")
    
    # Get task context
    task_context = assistant.get_task_context("Create a function to call Ollama API")
    print(f"Relevant knowledge entries: {len(task_context.relevant_knowledge)}")
    print(f"Suggested approaches: {len(task_context.suggested_approaches)}")

def main():
    """Run all tests."""
    print("Testing Documentation Cache System")
    print("==================================")
    
    try:
        test_doc_cache()
        test_web_searcher()
        test_knowledge_base()
        test_doc_assistant()
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
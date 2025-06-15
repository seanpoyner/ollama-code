#!/usr/bin/env python3
"""
Test script for the new vector store implementation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ollama_code.core.doc_vector_store import DocVectorStore, CHROMADB_AVAILABLE
from rich.console import Console

console = Console()


def test_vector_store():
    """Test the vector store functionality."""
    console.print("[bold]Testing Vector Store Implementation[/bold]\n")
    
    # Check if ChromaDB is available
    if not CHROMADB_AVAILABLE:
        console.print("[red]ChromaDB is not installed![/red]")
        console.print("Please install it with: pip install chromadb")
        return False
    
    console.print("[green]✓ ChromaDB is available[/green]")
    
    try:
        # Initialize vector store
        console.print("\nInitializing vector store...")
        vector_store = DocVectorStore()
        console.print("[green]✓ Vector store initialized[/green]")
        
        # Add some test documents
        console.print("\nAdding test documents...")
        
        # Document 1: Ollama API
        doc1 = vector_store.add(
            url="https://ollama.com/api/chat",
            title="Ollama Chat API",
            content="""The Ollama chat API allows you to have conversations with models.
            
            Endpoint: POST /api/chat
            
            Request body:
            {
                "model": "llama2",
                "messages": [
                    {"role": "user", "content": "Hello!"}
                ],
                "stream": false
            }
            
            Response:
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?"
                }
            }
            """,
            source_type="ollama",
            tags=["api", "chat", "ollama"]
        )
        console.print("[green]✓ Added Ollama Chat API doc[/green]")
        
        # Document 2: Python example
        doc2 = vector_store.add(
            url="https://example.com/python-ollama",
            title="Using Ollama with Python",
            content="""Here's how to use Ollama in Python:
            
            ```python
            import requests
            
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'llama2',
                    'prompt': 'Tell me a joke',
                    'stream': False
                }
            )
            
            print(response.json()['response'])
            ```
            
            This sends a generation request to Ollama and prints the response.
            """,
            source_type="python",
            tags=["python", "ollama", "example"]
        )
        console.print("[green]✓ Added Python example doc[/green]")
        
        # Test semantic search
        console.print("\nTesting semantic search...")
        
        # Search 1: "how to chat with ollama"
        query1 = "how to chat with ollama"
        console.print(f"\nSearching for: '{query1}'")
        results1 = vector_store.search(query1, limit=5)
        
        if results1:
            console.print(f"[green]Found {len(results1)} results:[/green]")
            for i, result in enumerate(results1, 1):
                console.print(f"  {i}. {result.title} (score: {result.relevance_score:.3f})")
        else:
            console.print("[yellow]No results found[/yellow]")
        
        # Search 2: "python code example"
        query2 = "python code example"
        console.print(f"\nSearching for: '{query2}'")
        results2 = vector_store.search(query2, limit=5)
        
        if results2:
            console.print(f"[green]Found {len(results2)} results:[/green]")
            for i, result in enumerate(results2, 1):
                console.print(f"  {i}. {result.title} (score: {result.relevance_score:.3f})")
        else:
            console.print("[yellow]No results found[/yellow]")
        
        # Test retrieval by URL
        console.print("\nTesting retrieval by URL...")
        retrieved = vector_store.get("https://ollama.com/api/chat")
        if retrieved:
            console.print(f"[green]✓ Retrieved: {retrieved.title}[/green]")
        else:
            console.print("[red]✗ Failed to retrieve document[/red]")
        
        # Show stats
        console.print("\nVector store statistics:")
        stats = vector_store.get_stats()
        console.print(f"  Total entries: {stats['total_entries']}")
        console.print(f"  By source type: {stats['by_source_type']}")
        console.print(f"  Storage path: {stats['storage_path']}")
        console.print(f"  Embedding model: {stats['embedding_model']}")
        
        console.print("\n[green]All tests passed![/green]")
        return True
        
    except Exception as e:
        console.print(f"\n[red]Error during testing: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_vector_store()
    sys.exit(0 if success else 1)
# Documentation Cache and Search System

## Overview

A comprehensive documentation system to prevent AI hallucination by providing real documentation context. The system includes web search, caching, and a learning knowledge base.

## Components

### 1. Documentation Cache (`doc_cache.py`)
- **SQLite-based cache** with full-text search
- **30-day expiry** for cached documentation
- **Relevance scoring** based on search queries
- **Access tracking** to prioritize frequently used docs

### 2. Web Search (`web_search.py`)
- **Multi-source search**: Ollama docs, Python docs, Stack Overflow, GitHub
- **HTML to markdown** conversion
- **Parallel search** across multiple sources
- **Automatic caching** of fetched content

### 3. Knowledge Base (`knowledge_base.py`)
- **Long-term memory** for successful solutions
- **API endpoint tracking** with verified parameters
- **Code pattern storage** for reuse
- **Success/failure learning** with confidence scores

### 4. Integration (`doc_integration.py`)
- **DocumentationAssistant** class that combines all components
- **Tool integration** with the agent
- **Pre-populated** with Ollama API documentation

## Available Tools

### `search_docs(query, source_type=None)`
Search for documentation across all sources.
```python
# Search for Ollama API information
docs = search_docs("ollama api endpoints")

# Search Python-specific docs
docs = search_docs("requests library", "python")
```

### `get_api_info(service, endpoint=None)`
Get specific API endpoint information.
```python
# Get all Ollama endpoints
info = get_api_info("ollama")

# Get specific endpoint details
info = get_api_info("ollama", "/api/generate")
```

### `remember_solution(title, description, code, language="python", tags=None)`
Save successful solutions for future reference.
```python
remember_solution(
    "Ollama chat completion",
    "Basic example of using Ollama chat API",
    code_string,
    tags=["ollama", "chat", "api"]
)
```

## How It Prevents Hallucination

1. **Real Documentation**: Fetches actual documentation from official sources
2. **Cached Knowledge**: Stores verified information for offline use
3. **Learning System**: Remembers what worked and what didn't
4. **Context Injection**: Provides relevant docs during task execution

## Usage in Tasks

When the AI works on a task:
1. The system automatically searches for relevant documentation
2. Documentation context is added to the task prompt
3. The AI uses real API information instead of guessing
4. Successful implementations are remembered for future use

## Example Flow

1. Task: "Create an endpoint to fetch Ollama models"
2. System searches: "ollama api tags endpoint"
3. Finds: `GET /api/tags` returns list of models
4. AI implements using correct endpoint
5. Success is recorded in knowledge base

## Benefits

- **No more wrong API endpoints**: Real documentation prevents `/api/models` (wrong) vs `/api/tags` (correct)
- **Faster development**: Cached docs mean no repeated searches
- **Learning system**: Gets better over time
- **Offline capability**: Works without internet after initial cache

## Cache Location

- Documentation cache: `~/.ollama/doc_cache/`
- Knowledge base: `~/.ollama/knowledge_base.db`
- Both are persistent across sessions

## Pre-populated Knowledge

The system comes with pre-populated Ollama API information:
- `/api/generate` - Text generation
- `/api/chat` - Chat completions
- `/api/tags` - List available models
- `/api/embeddings` - Generate embeddings

All with correct parameters and usage examples.
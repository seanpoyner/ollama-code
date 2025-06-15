# Vector Store Migration Guide

## Overview

The documentation search system has been upgraded from SQLite FTS5 to ChromaDB vector search, providing semantic search capabilities that understand the meaning of queries rather than just matching keywords.

## Benefits of Vector Search

1. **Semantic Understanding**: Finds relevant documentation based on meaning, not just exact keyword matches
2. **No Special Character Issues**: Eliminates the FTS5 syntax errors with special characters like `*`, `.`, etc.
3. **Better Relevance**: Uses Ollama's embedding models to understand context and relationships
4. **Improved Search Quality**: Returns more relevant results for natural language queries

## Installation

ChromaDB is now a required dependency. Install it with:

```bash
pip install chromadb
```

Or reinstall ollama-code with all dependencies:

```bash
pip install -e .
```

## Migration from SQLite

If you have existing documentation cached in SQLite, you can migrate it to the vector store:

```bash
python -m ollama_code.utils.migrate_doc_cache
```

This will:
1. Read all non-expired entries from your SQLite cache
2. Convert them to vector embeddings using Ollama
3. Store them in the new ChromaDB vector store
4. Preserve all metadata (tags, source types, etc.)

## Usage

The vector store works transparently - no code changes are needed. The system will:

1. Automatically use ChromaDB if available
2. Fall back to SQLite FTS5 if ChromaDB is not installed
3. Use the same API as before

## Configuration

The vector store uses:
- **Storage Location**: `~/.ollama/doc_vectors/`
- **Embedding Model**: `nomic-embed-text` (by default)
- **Ollama URL**: `http://localhost:11434`

## Testing

To test the vector store implementation:

```bash
python test_vector_store.py
```

This will:
1. Check ChromaDB availability
2. Add test documents
3. Perform semantic searches
4. Verify retrieval functionality

## Troubleshooting

### ChromaDB Not Found

If you see "ChromaDB is not installed", run:
```bash
pip install chromadb
```

### Ollama Connection Error

Make sure Ollama is running:
```bash
ollama serve
```

### Embedding Model Not Found

Pull the embedding model:
```bash
ollama pull nomic-embed-text
```

## Technical Details

### Architecture

- **Storage**: ChromaDB persistent client with cosine similarity
- **Embeddings**: Generated using Ollama's embedding API
- **Indexing**: HNSW (Hierarchical Navigable Small World) for fast similarity search
- **Metadata**: Stored alongside vectors for filtering and retrieval

### Fallback Behavior

The system gracefully falls back to SQLite if ChromaDB is unavailable:

```python
try:
    from .doc_vector_store import DocVectorStore as DocCache
except ImportError:
    from .doc_cache import DocCache  # SQLite fallback
```

### Performance

- **Initial Embedding**: First-time document addition requires embedding generation
- **Search Speed**: Near-instantaneous after embeddings are created
- **Storage**: Slightly larger than SQLite due to vector storage
- **Quality**: Significantly better search relevance

## Future Improvements

1. **Hybrid Search**: Combine vector search with keyword matching
2. **Multi-Model Support**: Allow different embedding models
3. **Incremental Updates**: Update embeddings without full re-indexing
4. **Query Expansion**: Use synonyms and related terms
5. **Relevance Feedback**: Learn from user interactions
"""
Vector database implementation for semantic documentation search.

This module provides a vector-based semantic search system using ChromaDB
and Ollama embeddings to replace the SQLite FTS5 implementation.
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, asdict
import re

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    embedding_functions = None

logger = logging.getLogger(__name__)


@dataclass
class DocEntry:
    """Represents a cached documentation entry."""
    url: str
    title: str
    content: str
    source_type: str  # 'ollama', 'python', 'github', 'stackoverflow', etc.
    tags: List[str]
    created_at: datetime
    expires_at: datetime
    relevance_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'source_type': self.source_type,
            'tags': json.dumps(self.tags),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'relevance_score': self.relevance_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocEntry':
        """Create from dictionary."""
        return cls(
            url=data['url'],
            title=data['title'],
            content=data['content'],
            source_type=data['source_type'],
            tags=json.loads(data['tags']) if isinstance(data['tags'], str) else data['tags'],
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']),
            relevance_score=data.get('relevance_score', 1.0)
        )


class DocVectorStore:
    """
    Vector database for storing and retrieving documentation using semantic search.
    
    Uses ChromaDB with Ollama embeddings for semantic similarity search.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, expiry_days: int = 30,
                 embedding_model: str = "nomic-embed-text",
                 ollama_base_url: str = "http://localhost:11434"):
        """
        Initialize the documentation vector store.
        
        Args:
            cache_dir: Directory to store cache (defaults to ~/.ollama/doc_vectors/)
            expiry_days: Number of days before cache entries expire
            embedding_model: Ollama embedding model to use
            ollama_base_url: Base URL for Ollama API
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. Please install it with: pip install chromadb"
            )
        
        if cache_dir is None:
            cache_dir = Path.home() / '.ollama' / 'doc_vectors'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_days = expiry_days
        self.embedding_model = embedding_model
        
        # Initialize ChromaDB with Ollama embeddings
        try:
            # Create embedding function using Ollama
            self.embedding_function = embedding_functions.OllamaEmbeddingFunction(
                url=ollama_base_url,
                model_name=embedding_model
            )
            
            # Create persistent client
            self.client = chromadb.PersistentClient(path=str(self.cache_dir))
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(
                    name="documentation",
                    embedding_function=self.embedding_function
                )
                logger.info("Loaded existing documentation collection")
            except:
                self.collection = self.client.create_collection(
                    name="documentation",
                    embedding_function=self.embedding_function,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Created new documentation collection")
            
            # Clean expired entries on init
            self._clean_expired()
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    def _clean_expired(self):
        """Remove expired cache entries."""
        try:
            # Get all documents
            results = self.collection.get(include=["metadatas"])
            
            if not results['ids']:
                return
            
            # Find expired entries
            now = datetime.utcnow()
            expired_ids = []
            
            for i, metadata in enumerate(results['metadatas']):
                if metadata and 'expires_at' in metadata:
                    expires_at = datetime.fromisoformat(metadata['expires_at'])
                    if expires_at < now:
                        expired_ids.append(results['ids'][i])
            
            # Delete expired entries
            if expired_ids:
                self.collection.delete(ids=expired_ids)
                logger.info(f"Cleaned {len(expired_ids)} expired cache entries")
                
        except Exception as e:
            logger.error(f"Error cleaning expired entries: {e}")
    
    def _generate_doc_id(self, url: str) -> str:
        """Generate a unique ID for a document based on URL."""
        return hashlib.sha256(url.encode()).hexdigest()
    
    def add(self, url: str, title: str, content: str, source_type: str, 
            tags: Optional[List[str]] = None) -> DocEntry:
        """
        Add documentation to vector store.
        
        Args:
            url: Source URL
            title: Document title
            content: Document content
            source_type: Type of source ('ollama', 'python', etc.)
            tags: Optional tags for categorization
            
        Returns:
            DocEntry object
        """
        if tags is None:
            tags = self._extract_tags(content, title)
        
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.expiry_days)
        
        entry = DocEntry(
            url=url,
            title=title,
            content=content,
            source_type=source_type,
            tags=tags,
            created_at=now,
            expires_at=expires_at
        )
        
        # Create document for embedding
        # Combine title and content for better semantic representation
        document_text = f"{title}\n\n{content}"
        
        # Prepare metadata
        metadata = {
            'url': url,
            'title': title,
            'source_type': source_type,
            'tags': json.dumps(tags),
            'created_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'relevance_score': entry.relevance_score
        }
        
        # Generate unique ID
        doc_id = self._generate_doc_id(url)
        
        try:
            # Add or update document in collection
            self.collection.upsert(
                documents=[document_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.info(f"Added documentation to vector store: {title}")
            
        except Exception as e:
            logger.error(f"Failed to add to vector store: {e}")
            raise
        
        return entry
    
    def get(self, url: str) -> Optional[DocEntry]:
        """
        Retrieve documentation by URL.
        
        Args:
            url: Source URL
            
        Returns:
            DocEntry if found and not expired, None otherwise
        """
        doc_id = self._generate_doc_id(url)
        
        try:
            results = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if results['ids'] and results['metadatas'][0]:
                metadata = results['metadatas'][0]
                
                # Check if expired
                expires_at = datetime.fromisoformat(metadata['expires_at'])
                if expires_at < datetime.utcnow():
                    return None
                
                # Extract content from document (remove title prefix)
                document = results['documents'][0]
                content = document
                if '\n\n' in document:
                    # Remove title from combined document
                    content = document.split('\n\n', 1)[1]
                
                # Create DocEntry from metadata and content
                entry = DocEntry(
                    url=metadata['url'],
                    title=metadata['title'],
                    content=content,
                    source_type=metadata['source_type'],
                    tags=json.loads(metadata['tags']),
                    created_at=datetime.fromisoformat(metadata['created_at']),
                    expires_at=expires_at,
                    relevance_score=metadata.get('relevance_score', 1.0)
                )
                
                return entry
                
        except Exception as e:
            logger.error(f"Error retrieving document: {e}")
        
        return None
    
    def search(self, query: str, source_type: Optional[str] = None, 
               limit: int = 10) -> List[DocEntry]:
        """
        Search documentation using semantic similarity.
        
        Args:
            query: Search query
            source_type: Optional filter by source type
            limit: Maximum number of results
            
        Returns:
            List of matching DocEntry objects
        """
        try:
            # Build where clause for filtering
            where = None
            if source_type:
                where = {"source_type": source_type}
            
            # Add expiration filter
            now = datetime.utcnow().isoformat()
            if where:
                where = {"$and": [where, {"expires_at": {"$gt": now}}]}
            else:
                where = {"expires_at": {"$gt": now}}
            
            # Perform semantic search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            entries = []
            if results['ids'][0]:  # Check if we have results
                for i, (doc_id, document, metadata, distance) in enumerate(zip(
                    results['ids'][0],
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Extract content from document
                    content = document
                    if '\n\n' in document:
                        # Remove title from combined document
                        content = document.split('\n\n', 1)[1]
                    
                    # Create DocEntry
                    entry = DocEntry(
                        url=metadata['url'],
                        title=metadata['title'],
                        content=content,
                        source_type=metadata['source_type'],
                        tags=json.loads(metadata['tags']),
                        created_at=datetime.fromisoformat(metadata['created_at']),
                        expires_at=datetime.fromisoformat(metadata['expires_at']),
                        relevance_score=1.0 - distance  # Convert distance to similarity score
                    )
                    entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[DocEntry]:
        """
        Search documentation by tags.
        
        Args:
            tags: List of tags to search for
            limit: Maximum number of results
            
        Returns:
            List of matching DocEntry objects
        """
        try:
            # Build query from tags
            tag_query = " ".join(tags)
            
            # Search with tag-based query
            return self.search(tag_query, limit=limit)
            
        except Exception as e:
            logger.error(f"Error searching by tags: {e}")
            return []
    
    def extract_relevant_sections(self, content: str, query: str, 
                                  max_sections: int = 3, 
                                  section_size: int = 500) -> List[str]:
        """
        Extract relevant sections from documentation based on query.
        
        This uses the same algorithm as the original implementation
        for consistency.
        
        Args:
            content: Full documentation content
            query: Search query
            max_sections: Maximum number of sections to return
            section_size: Approximate size of each section in characters
            
        Returns:
            List of relevant text sections
        """
        # Split content into paragraphs
        paragraphs = content.split('\n\n')
        
        # Score each paragraph based on query relevance
        query_terms = query.lower().split()
        scored_paragraphs = []
        
        for i, para in enumerate(paragraphs):
            para_lower = para.lower()
            score = sum(1 for term in query_terms if term in para_lower)
            
            # Boost score for code blocks
            if '```' in para or '    ' in para[:4]:
                score *= 1.5
            
            # Boost score for headers
            if para.startswith('#') or para.startswith('##'):
                score *= 1.3
            
            scored_paragraphs.append((score, i, para))
        
        # Sort by score and select top paragraphs
        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
        
        sections = []
        used_indices = set()
        
        for score, idx, para in scored_paragraphs:
            if score == 0 or len(sections) >= max_sections:
                break
            
            # Build section with context
            section_parts = []
            current_size = 0
            
            # Add preceding context
            for j in range(max(0, idx - 1), idx):
                if j not in used_indices and current_size + len(paragraphs[j]) < section_size:
                    section_parts.append(paragraphs[j])
                    used_indices.add(j)
                    current_size += len(paragraphs[j])
            
            # Add main paragraph
            section_parts.append(para)
            used_indices.add(idx)
            current_size += len(para)
            
            # Add following context
            for j in range(idx + 1, min(len(paragraphs), idx + 3)):
                if j not in used_indices and current_size + len(paragraphs[j]) < section_size:
                    section_parts.append(paragraphs[j])
                    used_indices.add(j)
                    current_size += len(paragraphs[j])
            
            if section_parts:
                sections.append('\n\n'.join(section_parts))
        
        return sections
    
    def _extract_tags(self, content: str, title: str) -> List[str]:
        """Extract tags from content and title."""
        tags = []
        
        # Extract from title
        title_words = re.findall(r'\b\w+\b', title.lower())
        tags.extend([w for w in title_words if len(w) > 3])
        
        # Extract code language indicators
        code_langs = re.findall(r'```(\w+)', content)
        tags.extend(code_langs)
        
        # Extract common programming terms
        prog_terms = ['api', 'function', 'class', 'method', 'variable', 
                      'error', 'exception', 'import', 'module', 'package']
        for term in prog_terms:
            if term in content.lower():
                tags.append(term)
        
        # Extract framework/library names
        frameworks = ['ollama', 'python', 'javascript', 'react', 'django', 
                      'flask', 'numpy', 'pandas', 'tensorflow', 'pytorch']
        for fw in frameworks:
            if fw in content.lower():
                tags.append(fw)
        
        return list(set(tags))[:10]  # Limit to 10 unique tags
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        try:
            # Get collection info
            count = self.collection.count()
            
            # Get all metadata to analyze
            results = self.collection.get(include=["metadatas"])
            
            # Count by source type
            by_source = {}
            if results['metadatas']:
                for metadata in results['metadatas']:
                    if metadata and 'source_type' in metadata:
                        source = metadata['source_type']
                        by_source[source] = by_source.get(source, 0) + 1
            
            # Note: ChromaDB doesn't track access counts by default
            # This would need to be implemented separately if needed
            
            return {
                'total_entries': count,
                'by_source_type': by_source,
                'storage_path': str(self.cache_dir),
                'embedding_model': self.embedding_model
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                'total_entries': 0,
                'by_source_type': {},
                'error': str(e)
            }
    
    def clear(self, source_type: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            source_type: If provided, only clear entries of this type
        """
        try:
            if source_type:
                # Get IDs of documents with specific source type
                results = self.collection.get(
                    where={"source_type": source_type},
                    include=[]
                )
                if results['ids']:
                    self.collection.delete(ids=results['ids'])
                    logger.info(f"Cleared {len(results['ids'])} entries for source type: {source_type}")
            else:
                # Clear all documents
                # ChromaDB doesn't have a direct "delete all" method,
                # so we need to get all IDs first
                results = self.collection.get(include=[])
                if results['ids']:
                    self.collection.delete(ids=results['ids'])
                    logger.info(f"Cleared all {len(results['ids'])} cache entries")
                    
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise


# Note: ChromaDB availability is checked at runtime when DocVectorStore is instantiated
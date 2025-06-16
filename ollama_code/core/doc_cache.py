"""
Documentation cache system for storing and retrieving documentation.

This module provides a caching system for documentation to reduce API calls
and provide offline access to previously fetched documentation.
"""

import os
import json
import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
import re
from urllib.parse import urlparse

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


class DocCache:
    """
    Documentation cache for storing and retrieving documentation.
    
    Uses SQLite for efficient storage and querying.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, expiry_days: int = 30):
        """
        Initialize the documentation cache.
        
        Args:
            cache_dir: Directory to store cache (defaults to ~/.ollama/doc_cache/)
            expiry_days: Number of days before cache entries expire
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.ollama' / 'doc_cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'doc_cache.db'
        self.expiry_days = expiry_days
        
        self._init_db()
        self._clean_expired()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS doc_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    relevance_score REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT
                )
            ''')
            
            # Create indexes for efficient searching
            conn.execute('CREATE INDEX IF NOT EXISTS idx_source_type ON doc_cache(source_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON doc_cache(expires_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_relevance ON doc_cache(relevance_score)')
            
            # Full-text search table
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS doc_cache_fts
                USING fts5(url, title, content, tags, content=doc_cache, content_rowid=id)
            ''')
            
            # Trigger to keep FTS in sync
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS doc_cache_ai AFTER INSERT ON doc_cache BEGIN
                    INSERT INTO doc_cache_fts(rowid, url, title, content, tags)
                    VALUES (new.id, new.url, new.title, new.content, new.tags);
                END
            ''')
    
    def _clean_expired(self):
        """Remove expired cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.utcnow().isoformat()
            conn.execute('DELETE FROM doc_cache WHERE expires_at < ?', (now,))
            logger.info(f"Cleaned expired cache entries")
    
    def _generate_cache_key(self, url: str) -> str:
        """Generate a cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()
    
    def add(self, url: str, title: str, content: str, source_type: str, 
            tags: Optional[List[str]] = None) -> DocEntry:
        """
        Add documentation to cache.
        
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
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO doc_cache 
                    (url, title, content, source_type, tags, created_at, expires_at, relevance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry.url, entry.title, entry.content, entry.source_type,
                    json.dumps(entry.tags), entry.created_at.isoformat(),
                    entry.expires_at.isoformat(), entry.relevance_score
                ))
                logger.info(f"Added documentation to cache: {title}")
            except sqlite3.Error as e:
                logger.error(f"Failed to add to cache: {e}")
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM doc_cache 
                WHERE url = ? AND expires_at > ?
            ''', (url, datetime.utcnow().isoformat()))
            
            row = cursor.fetchone()
            if row:
                # Update access count and last accessed
                conn.execute('''
                    UPDATE doc_cache 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE url = ?
                ''', (datetime.utcnow().isoformat(), url))
                
                return DocEntry.from_dict(dict(row))
        
        return None
    
    def _escape_fts_query(self, query: str) -> str:
        """Escape special characters for FTS5"""
        # For FTS5, we need to be more careful with escaping
        # Simply quote the entire query if it contains special characters
        special_chars = ['"', '*', '(', ')', ':', '.', ',', ';', '@', '-']
        
        # Check if query contains any special characters
        if any(char in query for char in special_chars):
            # Remove any existing quotes and wrap in quotes
            cleaned = query.replace('"', '')
            return f'"{cleaned}"'
        
        return query
    
    def search(self, query: str, source_type: Optional[str] = None, 
               limit: int = 10) -> List[DocEntry]:
        """
        Search documentation using full-text search.
        
        Args:
            query: Search query
            source_type: Optional filter by source type
            limit: Maximum number of results
            
        Returns:
            List of matching DocEntry objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Escape special characters in query
            try:
                escaped_query = self._escape_fts_query(query)
            except Exception as e:
                logger.warning(f"Failed to escape query '{query}': {e}. Using simple search.")
                escaped_query = query.replace('"', '')
            
            try:
                if source_type:
                    cursor = conn.execute('''
                        SELECT doc_cache.*, rank as rank_score FROM doc_cache
                        JOIN doc_cache_fts ON doc_cache.id = doc_cache_fts.rowid
                        WHERE doc_cache_fts MATCH ? 
                        AND doc_cache.source_type = ?
                        AND doc_cache.expires_at > ?
                        ORDER BY rank_score, doc_cache.relevance_score DESC
                        LIMIT ?
                    ''', (escaped_query, source_type, datetime.utcnow().isoformat(), limit))
                else:
                    cursor = conn.execute('''
                        SELECT doc_cache.*, rank as rank_score FROM doc_cache
                        JOIN doc_cache_fts ON doc_cache.id = doc_cache_fts.rowid
                        WHERE doc_cache_fts MATCH ?
                        AND doc_cache.expires_at > ?
                        ORDER BY rank_score, doc_cache.relevance_score DESC
                        LIMIT ?
                    ''', (escaped_query, datetime.utcnow().isoformat(), limit))
                
                results = []
                for row in cursor:
                    results.append(DocEntry.from_dict(dict(row)))
                
                return results
                
            except sqlite3.OperationalError as e:
                if "fts5: syntax error" in str(e):
                    logger.warning(f"FTS5 syntax error for query '{query}': {e}. Falling back to LIKE search.")
                    # Fall back to simple LIKE search
                    if source_type:
                        cursor = conn.execute('''
                            SELECT * FROM doc_cache
                            WHERE (title LIKE ? OR content LIKE ?)
                            AND source_type = ?
                            AND expires_at > ?
                            ORDER BY relevance_score DESC
                            LIMIT ?
                        ''', (f'%{query}%', f'%{query}%', source_type, datetime.utcnow().isoformat(), limit))
                    else:
                        cursor = conn.execute('''
                            SELECT * FROM doc_cache
                            WHERE (title LIKE ? OR content LIKE ?)
                            AND expires_at > ?
                            ORDER BY relevance_score DESC
                            LIMIT ?
                        ''', (f'%{query}%', f'%{query}%', datetime.utcnow().isoformat(), limit))
                    
                    results = []
                    for row in cursor:
                        results.append(DocEntry.from_dict(dict(row)))
                    
                    return results
                else:
                    raise
    
    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[DocEntry]:
        """
        Search documentation by tags.
        
        Args:
            tags: List of tags to search for
            limit: Maximum number of results
            
        Returns:
            List of matching DocEntry objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Build query to find entries containing any of the tags
            tag_conditions = ' OR '.join(['tags LIKE ?' for _ in tags])
            tag_values = [f'%"{tag}"%' for tag in tags]
            
            cursor = conn.execute(f'''
                SELECT * FROM doc_cache
                WHERE ({tag_conditions})
                AND expires_at > ?
                ORDER BY relevance_score DESC
                LIMIT ?
            ''', tag_values + [datetime.utcnow().isoformat(), limit])
            
            results = []
            for row in cursor:
                results.append(DocEntry.from_dict(dict(row)))
            
            return results
    
    def extract_relevant_sections(self, content: str, query: str, 
                                  max_sections: int = 3, 
                                  section_size: int = 500) -> List[str]:
        """
        Extract relevant sections from documentation based on query.
        
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
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total entries
            total = conn.execute('SELECT COUNT(*) FROM doc_cache').fetchone()[0]
            
            # Entries by source type
            by_source = {}
            for row in conn.execute('SELECT source_type, COUNT(*) FROM doc_cache GROUP BY source_type'):
                by_source[row[0]] = row[1]
            
            # Most accessed
            most_accessed = []
            for row in conn.execute('''
                SELECT title, url, access_count 
                FROM doc_cache 
                ORDER BY access_count DESC 
                LIMIT 5
            '''):
                most_accessed.append({
                    'title': row[0],
                    'url': row[1],
                    'access_count': row[2]
                })
            
            # Cache size
            cache_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
            
            return {
                'total_entries': total,
                'by_source_type': by_source,
                'most_accessed': most_accessed,
                'cache_size_mb': round(cache_size, 2)
            }
    
    def clear(self, source_type: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            source_type: If provided, only clear entries of this type
        """
        with sqlite3.connect(self.db_path) as conn:
            if source_type:
                conn.execute('DELETE FROM doc_cache WHERE source_type = ?', (source_type,))
                logger.info(f"Cleared cache entries for source type: {source_type}")
            else:
                conn.execute('DELETE FROM doc_cache')
                logger.info("Cleared all cache entries")
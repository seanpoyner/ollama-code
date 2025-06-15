"""
Knowledge base system for long-term memory and learning.

This module provides a knowledge base that learns from successful task
completions and provides context for future tasks.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import hashlib
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """Represents a piece of learned knowledge."""
    id: Optional[int]
    category: str  # 'api_endpoint', 'code_pattern', 'solution', 'error_fix'
    title: str
    description: str
    content: Dict[str, Any]
    tags: List[str]
    usage_count: int = 0
    success_rate: float = 1.0
    created_at: datetime = None
    last_used: Optional[datetime] = None
    confidence: float = 1.0  # How confident we are in this knowledge
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'content': json.dumps(self.content),
            'tags': json.dumps(self.tags),
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeEntry':
        """Create from dictionary."""
        return cls(
            id=data.get('id'),
            category=data['category'],
            title=data['title'],
            description=data['description'],
            content=json.loads(data['content']) if isinstance(data['content'], str) else data['content'],
            tags=json.loads(data['tags']) if isinstance(data['tags'], str) else data['tags'],
            usage_count=data.get('usage_count', 0),
            success_rate=data.get('success_rate', 1.0),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            last_used=datetime.fromisoformat(data['last_used']) if data.get('last_used') else None,
            confidence=data.get('confidence', 1.0)
        )


@dataclass
class TaskContext:
    """Context for a specific task."""
    task_description: str
    relevant_knowledge: List[KnowledgeEntry]
    suggested_approaches: List[Dict[str, Any]]
    potential_issues: List[Dict[str, Any]]


class KnowledgeBase:
    """
    Knowledge base for storing and retrieving learned information.
    
    Learns from successful task completions and provides context for new tasks.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the knowledge base.
        
        Args:
            db_path: Path to SQLite database (defaults to ~/.ollama/knowledge.db)
        """
        if db_path is None:
            db_dir = Path.home() / '.ollama'
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / 'knowledge.db'
        
        self.db_path = db_path
        self._init_db()
        
        # In-memory caches
        self._pattern_cache = {}
        self._api_cache = {}
        
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Main knowledge table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    confidence REAL DEFAULT 1.0,
                    UNIQUE(category, title)
                )
            ''')
            
            # Task history table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_description TEXT NOT NULL,
                    approach TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    knowledge_used TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # API endpoints table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    parameters TEXT,
                    response_format TEXT,
                    examples TEXT,
                    last_verified TEXT,
                    UNIQUE(service, endpoint, method)
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_confidence ON knowledge(confidence DESC)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_usage ON knowledge(usage_count DESC)')
            
            # Full-text search
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(title, description, tags, content=knowledge, content_rowid=id)
            ''')
            
            # Keep FTS in sync
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                    INSERT INTO knowledge_fts(rowid, title, description, tags)
                    VALUES (new.id, new.title, new.description, new.tags);
                END
            ''')
    
    def add_knowledge(self, category: str, title: str, description: str,
                      content: Dict[str, Any], tags: Optional[List[str]] = None) -> KnowledgeEntry:
        """
        Add new knowledge to the base.
        
        Args:
            category: Knowledge category ('api_endpoint', 'code_pattern', etc.)
            title: Short title
            description: Detailed description
            content: Structured content (varies by category)
            tags: Optional tags for categorization
            
        Returns:
            Created KnowledgeEntry
        """
        if tags is None:
            tags = self._extract_tags(title, description, content)
        
        entry = KnowledgeEntry(
            id=None,
            category=category,
            title=title,
            description=description,
            content=content,
            tags=tags
        )
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO knowledge 
                    (category, title, description, content, tags, created_at, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry.category, entry.title, entry.description,
                    json.dumps(entry.content), json.dumps(entry.tags),
                    entry.created_at.isoformat(), entry.confidence
                ))
                entry.id = cursor.lastrowid
                logger.info(f"Added knowledge: {title}")
            except sqlite3.Error as e:
                logger.error(f"Failed to add knowledge: {e}")
                raise
        
        # Clear relevant caches
        self._clear_cache(category)
        
        return entry
    
    def learn_from_task(self, task_description: str, approach: Dict[str, Any],
                        success: bool, error_message: Optional[str] = None,
                        knowledge_used: Optional[List[int]] = None):
        """
        Learn from a completed task.
        
        Args:
            task_description: What the task was
            approach: How it was approached
            success: Whether it succeeded
            error_message: Error message if failed
            knowledge_used: IDs of knowledge entries used
        """
        # Record task history
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO task_history 
                (task_description, approach, success, error_message, knowledge_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                task_description, json.dumps(approach), success,
                error_message, json.dumps(knowledge_used) if knowledge_used else None,
                datetime.utcnow().isoformat()
            ))
            
            # Update confidence of used knowledge
            if knowledge_used:
                for kid in knowledge_used:
                    if success:
                        # Increase confidence
                        conn.execute('''
                            UPDATE knowledge 
                            SET usage_count = usage_count + 1,
                                success_rate = (success_rate * usage_count + 1) / (usage_count + 1),
                                confidence = MIN(confidence * 1.1, 1.0),
                                last_used = ?
                            WHERE id = ?
                        ''', (datetime.utcnow().isoformat(), kid))
                    else:
                        # Decrease confidence
                        conn.execute('''
                            UPDATE knowledge 
                            SET usage_count = usage_count + 1,
                                success_rate = (success_rate * usage_count) / (usage_count + 1),
                                confidence = MAX(confidence * 0.9, 0.1),
                                last_used = ?
                            WHERE id = ?
                        ''', (datetime.utcnow().isoformat(), kid))
        
        # Extract patterns from successful tasks
        if success:
            self._extract_patterns_from_success(task_description, approach)
    
    def get_task_context(self, task_description: str) -> TaskContext:
        """
        Get relevant context for a task.
        
        Args:
            task_description: Description of the task
            
        Returns:
            TaskContext with relevant knowledge and suggestions
        """
        # Search for relevant knowledge
        relevant_knowledge = self.search(task_description, limit=10)
        
        # Get suggested approaches based on similar tasks
        suggested_approaches = self._get_similar_task_approaches(task_description)
        
        # Get potential issues from failed similar tasks
        potential_issues = self._get_potential_issues(task_description)
        
        return TaskContext(
            task_description=task_description,
            relevant_knowledge=relevant_knowledge,
            suggested_approaches=suggested_approaches,
            potential_issues=potential_issues
        )
    
    def search(self, query: str, category: Optional[str] = None,
               limit: int = 10) -> List[KnowledgeEntry]:
        """
        Search the knowledge base.
        
        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of matching KnowledgeEntry objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if category:
                cursor = conn.execute('''
                    SELECT k.* FROM knowledge k
                    JOIN knowledge_fts ON k.id = knowledge_fts.rowid
                    WHERE knowledge_fts MATCH ? AND k.category = ?
                    ORDER BY rank, k.confidence DESC, k.usage_count DESC
                    LIMIT ?
                ''', (query, category, limit))
            else:
                cursor = conn.execute('''
                    SELECT k.* FROM knowledge k
                    JOIN knowledge_fts ON k.id = knowledge_fts.rowid
                    WHERE knowledge_fts MATCH ?
                    ORDER BY rank, k.confidence DESC, k.usage_count DESC
                    LIMIT ?
                ''', (query, limit))
            
            results = []
            for row in cursor:
                results.append(KnowledgeEntry.from_dict(dict(row)))
            
            return results
    
    def add_api_endpoint(self, service: str, endpoint: str, method: str,
                         parameters: Optional[Dict[str, Any]] = None,
                         response_format: Optional[Dict[str, Any]] = None,
                         examples: Optional[List[Dict[str, Any]]] = None):
        """
        Add a verified API endpoint.
        
        Args:
            service: Service name (e.g., 'ollama', 'github')
            endpoint: API endpoint path
            method: HTTP method
            parameters: Optional parameter schema
            response_format: Optional response schema
            examples: Optional usage examples
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO api_endpoints
                (service, endpoint, method, parameters, response_format, examples, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                service, endpoint, method,
                json.dumps(parameters) if parameters else None,
                json.dumps(response_format) if response_format else None,
                json.dumps(examples) if examples else None,
                datetime.utcnow().isoformat()
            ))
        
        # Also add to general knowledge
        self.add_knowledge(
            category='api_endpoint',
            title=f"{service} {method} {endpoint}",
            description=f"API endpoint for {service}",
            content={
                'service': service,
                'endpoint': endpoint,
                'method': method,
                'parameters': parameters,
                'response_format': response_format,
                'examples': examples
            },
            tags=[service, 'api', method.lower()]
        )
    
    def get_api_endpoints(self, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get known API endpoints."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if service:
                cursor = conn.execute(
                    'SELECT * FROM api_endpoints WHERE service = ?', 
                    (service,)
                )
            else:
                cursor = conn.execute('SELECT * FROM api_endpoints')
            
            endpoints = []
            for row in cursor:
                endpoint = dict(row)
                # Parse JSON fields
                for field in ['parameters', 'response_format', 'examples']:
                    if endpoint[field]:
                        endpoint[field] = json.loads(endpoint[field])
                endpoints.append(endpoint)
            
            return endpoints
    
    def add_code_pattern(self, name: str, description: str, pattern: str,
                         language: str, use_cases: List[str],
                         examples: Optional[List[str]] = None):
        """
        Add a reusable code pattern.
        
        Args:
            name: Pattern name
            description: What it does
            pattern: The code pattern
            language: Programming language
            use_cases: When to use this pattern
            examples: Optional usage examples
        """
        self.add_knowledge(
            category='code_pattern',
            title=name,
            description=description,
            content={
                'pattern': pattern,
                'language': language,
                'use_cases': use_cases,
                'examples': examples or []
            },
            tags=[language, 'pattern'] + use_cases[:3]
        )
    
    def get_code_patterns(self, language: Optional[str] = None,
                          use_case: Optional[str] = None) -> List[KnowledgeEntry]:
        """Get relevant code patterns."""
        if language and use_case:
            query = f"{language} {use_case}"
        elif language:
            query = language
        elif use_case:
            query = use_case
        else:
            query = "pattern"
        
        return self.search(query, category='code_pattern')
    
    def _extract_patterns_from_success(self, task_description: str, 
                                       approach: Dict[str, Any]):
        """Extract reusable patterns from successful task."""
        # Look for common patterns
        if 'code' in approach:
            code = approach['code']
            language = approach.get('language', 'unknown')
            
            # Simple pattern extraction (can be enhanced)
            patterns = {
                'error_handling': r'try:.*except.*:',
                'api_call': r'requests\.(get|post|put|delete)',
                'file_operation': r'with open\(.*\) as',
                'list_comprehension': r'\[.*for.*in.*\]',
                'async_operation': r'async def|await ',
            }
            
            for pattern_name, pattern_regex in patterns.items():
                import re
                if re.search(pattern_regex, code, re.DOTALL):
                    # Store this pattern usage
                    self.add_knowledge(
                        category='solution',
                        title=f"{pattern_name} in {task_description[:50]}",
                        description=f"Successful use of {pattern_name} pattern",
                        content={
                            'task': task_description,
                            'pattern': pattern_name,
                            'code_snippet': code[:500],
                            'language': language
                        },
                        tags=[language, pattern_name, 'success']
                    )
    
    def _get_similar_task_approaches(self, task_description: str) -> List[Dict[str, Any]]:
        """Get approaches from similar successful tasks."""
        approaches = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Simple similarity based on common words
            words = set(task_description.lower().split())
            
            cursor = conn.execute('''
                SELECT * FROM task_history 
                WHERE success = 1 
                ORDER BY created_at DESC 
                LIMIT 100
            ''')
            
            for row in cursor:
                task_words = set(row['task_description'].lower().split())
                similarity = len(words & task_words) / max(len(words), len(task_words))
                
                if similarity > 0.3:  # Threshold for similarity
                    approaches.append({
                        'task': row['task_description'],
                        'approach': json.loads(row['approach']),
                        'similarity': similarity,
                        'knowledge_used': json.loads(row['knowledge_used']) if row['knowledge_used'] else []
                    })
            
            # Sort by similarity
            approaches.sort(key=lambda x: x['similarity'], reverse=True)
            
        return approaches[:5]
    
    def _get_potential_issues(self, task_description: str) -> List[Dict[str, Any]]:
        """Get potential issues from similar failed tasks."""
        issues = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Similar approach as above but for failed tasks
            words = set(task_description.lower().split())
            
            cursor = conn.execute('''
                SELECT * FROM task_history 
                WHERE success = 0 AND error_message IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 100
            ''')
            
            for row in cursor:
                task_words = set(row['task_description'].lower().split())
                similarity = len(words & task_words) / max(len(words), len(task_words))
                
                if similarity > 0.3:
                    issues.append({
                        'task': row['task_description'],
                        'error': row['error_message'],
                        'approach': json.loads(row['approach']),
                        'similarity': similarity
                    })
            
            # Sort by similarity
            issues.sort(key=lambda x: x['similarity'], reverse=True)
            
        return issues[:3]
    
    def _extract_tags(self, title: str, description: str, 
                      content: Dict[str, Any]) -> List[str]:
        """Extract tags from content."""
        tags = []
        
        # From title and description
        import re
        words = re.findall(r'\b\w+\b', f"{title} {description}".lower())
        
        # Common programming terms
        tech_terms = {
            'api', 'function', 'class', 'method', 'error', 'exception',
            'async', 'callback', 'promise', 'request', 'response',
            'database', 'query', 'model', 'view', 'controller'
        }
        
        tags.extend([w for w in words if w in tech_terms])
        
        # From content
        if 'language' in content:
            tags.append(content['language'])
        if 'service' in content:
            tags.append(content['service'])
        if 'tags' in content:
            tags.extend(content['tags'])
        
        return list(set(tags))[:10]
    
    def _clear_cache(self, category: Optional[str] = None):
        """Clear in-memory caches."""
        if category == 'code_pattern' or category is None:
            self._pattern_cache.clear()
        if category == 'api_endpoint' or category is None:
            self._api_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total entries by category
            cursor = conn.execute('''
                SELECT category, COUNT(*) as count 
                FROM knowledge 
                GROUP BY category
            ''')
            stats['by_category'] = dict(cursor.fetchall())
            
            # Total tasks
            stats['total_tasks'] = conn.execute(
                'SELECT COUNT(*) FROM task_history'
            ).fetchone()[0]
            
            # Success rate
            success_count = conn.execute(
                'SELECT COUNT(*) FROM task_history WHERE success = 1'
            ).fetchone()[0]
            stats['task_success_rate'] = success_count / max(stats['total_tasks'], 1)
            
            # Most used knowledge
            cursor = conn.execute('''
                SELECT title, usage_count, success_rate 
                FROM knowledge 
                ORDER BY usage_count DESC 
                LIMIT 5
            ''')
            stats['most_used'] = [dict(row) for row in cursor]
            
            # API endpoints
            stats['api_endpoints'] = conn.execute(
                'SELECT COUNT(*) FROM api_endpoints'
            ).fetchone()[0]
            
        return stats
"""
Integration module for documentation cache with the agent system.

This module integrates the documentation cache, web search, and knowledge base
with the existing agent to provide contextual documentation during tasks.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import vector store first, fall back to SQLite cache if not available
try:
    from .doc_vector_store import DocVectorStore as DocCache, DocEntry
    logger.info("Using vector-based documentation search (ChromaDB)")
except ImportError:
    from .doc_cache import DocCache, DocEntry
    logger.info("Using SQLite FTS5 for documentation search (install chromadb for better search)")

from .web_search import WebSearcher
from .knowledge_base import KnowledgeBase, TaskContext


class DocumentationAssistant:
    """
    Assistant that provides documentation context to the agent.
    
    Integrates documentation cache, web search, and knowledge base
    to help prevent hallucination and provide accurate information.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the documentation assistant.
        
        Args:
            cache_dir: Optional cache directory path
        """
        self.doc_cache = DocCache(cache_dir)
        self.web_searcher = WebSearcher()
        self.knowledge_base = KnowledgeBase()
        
        # Load cache stats on startup
        self._log_cache_status()
        
        # Pre-populate with some common Ollama documentation
        self._initialize_ollama_docs()
    
    def _initialize_ollama_docs(self):
        """Initialize with known Ollama API documentation."""
        # Add known Ollama API endpoints
        ollama_endpoints = [
            {
                'endpoint': '/api/generate',
                'method': 'POST',
                'description': 'Generate a completion',
                'parameters': {
                    'model': 'string (required)',
                    'prompt': 'string (required)',
                    'stream': 'boolean (optional)',
                    'options': {
                        'temperature': 'float',
                        'top_p': 'float',
                        'num_predict': 'integer',
                        'stop': 'array of strings'
                    }
                }
            },
            {
                'endpoint': '/api/chat',
                'method': 'POST',
                'description': 'Chat with a model',
                'parameters': {
                    'model': 'string (required)',
                    'messages': 'array of message objects (required)',
                    'stream': 'boolean (optional)',
                    'options': 'object (optional)'
                }
            },
            {
                'endpoint': '/api/embeddings',
                'method': 'POST',
                'description': 'Generate embeddings',
                'parameters': {
                    'model': 'string (required)',
                    'prompt': 'string (required)'
                }
            },
            {
                'endpoint': '/api/tags',
                'method': 'GET',
                'description': 'List available models',
                'parameters': {}
            }
        ]
        
        for endpoint_data in ollama_endpoints:
            self.knowledge_base.add_api_endpoint(
                service='ollama',
                endpoint=endpoint_data['endpoint'],
                method=endpoint_data['method'],
                parameters=endpoint_data.get('parameters', {}),
                response_format=endpoint_data.get('response', {}),
                examples=endpoint_data.get('examples', [])
            )
    
    def get_documentation_context(self, query: str, 
                                  source_type: Optional[str] = None,
                                  auto_fetch: bool = True) -> str:
        """
        Get relevant documentation context for a query.
        
        Args:
            query: The search query
            source_type: Optional source type filter
            auto_fetch: Whether to automatically fetch from web if not found
            
        Returns:
            Formatted documentation context string
        """
        context_parts = []
        
        # 1. Check cache first
        logger.info(f"Searching documentation cache for: {query}")
        try:
            cached_docs = self.doc_cache.search(query, source_type=source_type, limit=5)
        except Exception as e:
            logger.error(f"Documentation cache search failed: {e}")
            # Check if it's an Ollama connection issue
            if "Connection refused" in str(e) or "Failed to connect" in str(e) or "ConnectError" in str(e):
                logger.warning("ChromaDB needs Ollama running for embeddings. Documentation search disabled.")
            cached_docs = []
        
        # If no cached docs and auto_fetch is enabled, try web search
        if not cached_docs and auto_fetch:
            logger.info(f"No cached documentation found. Searching web for: {query}")
            from rich.console import Console
            console = Console()
            from ..utils.messages import get_message
            console.print(get_message('app.fetching_docs_from_web'))
            self._fetch_and_cache_documentation(query)
            
            # Try cache search again after fetching
            try:
                cached_docs = self.doc_cache.search(query, source_type=source_type, limit=5)
            except Exception as e:
                logger.error(f"Cache search after web fetch failed: {e}")
                cached_docs = []
        
        if cached_docs:
            context_parts.append("## Documentation\n")
            for doc in cached_docs[:3]:
                context_parts.append(f"### {doc.title}")
                # Extract most relevant sections
                sections = self.doc_cache.extract_relevant_sections(
                    doc.content, query, max_sections=2
                )
                for section in sections:
                    context_parts.append(section)
                context_parts.append("")
        
        # 2. Check knowledge base
        logger.info(f"Searching knowledge base for: {query}")
        try:
            knowledge_entries = self.knowledge_base.search(query, limit=5)
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}")
            knowledge_entries = []
        
        if knowledge_entries:
            context_parts.append("## Known Patterns and Solutions\n")
            for entry in knowledge_entries[:3]:
                context_parts.append(f"### {entry.title}")
                context_parts.append(entry.description)
                if entry.category == 'code_pattern' and 'pattern' in entry.content:
                    context_parts.append(f"```{entry.content.get('language', '')}")
                    context_parts.append(entry.content['pattern'])
                    context_parts.append("```")
                elif entry.category == 'api_endpoint':
                    context_parts.append(f"**Method:** {entry.content.get('method', 'GET')}")
                    context_parts.append(f"**Endpoint:** {entry.content.get('endpoint', '')}")
                    if 'parameters' in entry.content:
                        context_parts.append("**Parameters:**")
                        context_parts.append(f"```json\n{entry.content['parameters']}\n```")
                context_parts.append("")
        
        # 3. If little context found, search online
        if len(context_parts) < 5:
            logger.info(f"Searching online documentation for: {query}")
            search_results = self.web_searcher.search(query, source_type=source_type, max_results=3)
            
            if search_results:
                context_parts.append("## Online Documentation (Not Cached)\n")
                context_parts.append("*Note: These results are from online search and may need verification*\n")
                
                for result in search_results[:2]:
                    # Fetch and cache the documentation
                    doc_content = self.web_searcher.fetch_documentation(result['url'])
                    if doc_content:
                        # Add to cache
                        self.doc_cache.add(
                            url=result['url'],
                            title=doc_content['title'],
                            content=doc_content['content'],
                            source_type=result.get('source_type', 'unknown'),
                            tags=result.get('tags', [])
                        )
                        
                        # Add to context
                        context_parts.append(f"### {doc_content['title']}")
                        context_parts.append(f"*Source: {result['url']}*")
                        
                        # Extract relevant sections
                        sections = self.doc_cache.extract_relevant_sections(
                            doc_content['content'], query, max_sections=1
                        )
                        for section in sections:
                            context_parts.append(section)
                        context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _fetch_and_cache_documentation(self, query: str):
        """
        Fetch documentation from web and cache it in vector store.
        
        Args:
            query: The search query
        """
        try:
            # Extract key terms from query for better search
            key_terms = self._extract_key_terms(query)
            
            # Search for documentation
            for term in key_terms[:3]:  # Limit to top 3 terms
                search_results = self.web_searcher.search(f"{term} documentation site:docs.python.org OR site:stackoverflow.com OR site:github.com")
                
                for result in search_results[:2]:  # Process top 2 results per term
                    try:
                        # Fetch the content
                        content = self.web_searcher.fetch_content(result['url'])
                        
                        if content and len(content) > 100:  # Ensure meaningful content
                            # Determine source type
                            source_type = 'web'
                            if 'python.org' in result['url']:
                                source_type = 'python'
                            elif 'stackoverflow.com' in result['url']:
                                source_type = 'stackoverflow'
                            elif 'github.com' in result['url']:
                                source_type = 'github'
                            
                            # Add to cache
                            self.doc_cache.add(
                                url=result['url'],
                                title=result.get('title', 'Documentation'),
                                content=content,
                                source_type=source_type,
                                tags=key_terms
                            )
                            logger.info(f"Cached documentation from: {result['url']}")
                    except Exception as e:
                        logger.error(f"Failed to fetch/cache {result['url']}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to fetch documentation for '{query}': {e}")
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from a query for better search."""
        # Simple extraction - can be improved with NLP
        import re
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                      'how', 'when', 'where', 'why', 'what', 'which', 'who', 'whom', 'this',
                      'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'may', 'might', 'must', 'can', 'create', 'make',
                      'new', 'initialize', 'implement', 'develop', 'build'}
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter and prioritize
        key_terms = []
        for word in words:
            if len(word) > 2 and word not in stop_words:
                key_terms.append(word)
        
        # Look for specific patterns
        # Framework names
        frameworks = ['flask', 'django', 'fastapi', 'react', 'vue', 'angular', 'express',
                      'rails', 'spring', 'laravel', 'symfony', 'ollama', 'chromadb']
        for fw in frameworks:
            if fw in query.lower():
                key_terms.insert(0, fw)  # Prioritize framework names
        
        # Programming concepts
        concepts = ['api', 'database', 'backend', 'frontend', 'gui', 'cli', 'web', 'app',
                    'server', 'client', 'model', 'view', 'controller', 'route', 'endpoint']
        for concept in concepts:
            if concept in query.lower() and concept not in key_terms:
                key_terms.append(concept)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in key_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms
    
    def _log_cache_status(self):
        """Log the current cache status."""
        try:
            stats = self.doc_cache.get_stats()
            if stats['total_entries'] > 0:
                logger.info(f"Documentation cache loaded: {stats['total_entries']} entries")
                if 'by_source_type' in stats:
                    for source, count in stats['by_source_type'].items():
                        logger.info(f"  - {source}: {count} entries")
            else:
                logger.info("Documentation cache is empty. Will fetch docs as needed.")
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
    
    def clear_cache(self, source_type: Optional[str] = None):
        """
        Clear the documentation cache.
        
        Args:
            source_type: Optional source type to clear (clears all if None)
        """
        self.doc_cache.clear(source_type)
        if source_type:
            logger.info(f"Cleared {source_type} documentation from cache")
        else:
            logger.info("Cleared all documentation from cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.doc_cache.get_stats()
    
    def get_task_context(self, task_description: str) -> TaskContext:
        """
        Get comprehensive context for a task.
        
        Args:
            task_description: Description of the task
            
        Returns:
            TaskContext object with relevant information
        """
        return self.knowledge_base.get_task_context(task_description)
    
    def learn_from_execution(self, task_description: str, 
                             code: str, success: bool, 
                             error_message: Optional[str] = None):
        """
        Learn from code execution results.
        
        Args:
            task_description: What the task was
            code: The code that was executed
            success: Whether execution succeeded
            error_message: Error message if failed
        """
        approach = {
            'code': code,
            'language': self._detect_language(code),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Get which knowledge entries were used (if any)
        # This would need to be tracked during execution
        knowledge_used = []
        
        self.knowledge_base.learn_from_task(
            task_description=task_description,
            approach=approach,
            success=success,
            error_message=error_message,
            knowledge_used=knowledge_used
        )
        
        # If successful, extract any API calls or patterns
        if success:
            self._extract_patterns_from_code(code, task_description)
    
    def _detect_language(self, code: str) -> str:
        """Simple language detection based on syntax."""
        if 'import ' in code or 'def ' in code or 'class ' in code:
            return 'python'
        elif 'function ' in code or 'const ' in code or 'let ' in code:
            return 'javascript'
        elif '#include' in code or 'int main' in code:
            return 'c'
        else:
            return 'unknown'
    
    def _extract_patterns_from_code(self, code: str, task_description: str):
        """Extract reusable patterns from successful code."""
        import re
        
        # Extract Ollama API usage patterns
        ollama_patterns = [
            (r'ollama\.generate\((.*?)\)', 'ollama_generate'),
            (r'ollama\.chat\((.*?)\)', 'ollama_chat'),
            (r'requests\.(get|post|put|delete)\(["\'].*?/api/(.*?)["\']', 'api_call'),
        ]
        
        for pattern_regex, pattern_name in ollama_patterns:
            matches = re.findall(pattern_regex, code, re.DOTALL)
            if matches:
                for match in matches:
                    self.knowledge_base.add_knowledge(
                        category='code_pattern',
                        title=f"{pattern_name} usage",
                        description=f"Pattern found in: {task_description[:50]}",
                        content={
                            'pattern': match if isinstance(match, str) else str(match),
                            'full_code': code[:500],
                            'task': task_description
                        },
                        tags=[pattern_name, self._detect_language(code)]
                    )
    
    def add_documentation_tools(self, agent):
        """
        Add documentation tools to an agent.
        
        Args:
            agent: The OllamaCodeAgent instance
        """
        def search_docs(query: str, source_type: Optional[str] = None) -> str:
            """Search documentation and return relevant context."""
            return self.get_documentation_context(query, source_type)
        
        def get_api_info(service: str, endpoint: Optional[str] = None) -> str:
            """Get API endpoint information."""
            endpoints = self.knowledge_base.get_api_endpoints(service)
            if endpoint:
                endpoints = [e for e in endpoints if endpoint in e['endpoint']]
            
            if not endpoints:
                return f"No API information found for {service}"
            
            result = []
            for ep in endpoints:
                result.append(f"## {ep['method']} {ep['endpoint']}")
                if ep.get('parameters'):
                    result.append("**Parameters:**")
                    result.append(f"```json\n{ep['parameters']}\n```")
                if ep.get('examples'):
                    result.append("**Examples:**")
                    for ex in ep['examples']:
                        result.append(f"```\n{ex}\n```")
            
            return "\n".join(result)
        
        def remember_solution(title: str, description: str, code: str, 
                              language: str = 'python', tags: List[str] = None):
            """Remember a successful solution for future use."""
            self.knowledge_base.add_code_pattern(
                name=title,
                description=description,
                pattern=code,
                language=language,
                use_cases=tags or [],
                examples=[]
            )
            return f"Solution remembered: {title}"
        
        # Add these as tools the agent can use
        agent.search_docs = search_docs
        agent.get_api_info = get_api_info
        agent.remember_solution = remember_solution
        
        # Hook into execution to learn (if method exists)
        if hasattr(agent, 'execute_code'):
            original_execute = agent.execute_code
            
            def wrapped_execute(code, language='python'):
                result = original_execute(code, language)
                # Learn from execution
                task_desc = getattr(agent, 'current_task_description', 'Code execution')
                success = 'error' not in result.lower()
                error_msg = result if not success else None
                self.learn_from_execution(task_desc, code, success, error_msg)
                return result
            
            agent.execute_code = wrapped_execute
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the documentation system."""
        return {
            'cache_stats': self.doc_cache.get_stats(),
            'knowledge_stats': self.knowledge_base.get_stats()
        }
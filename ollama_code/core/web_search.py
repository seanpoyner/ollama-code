"""
Web search module for finding and retrieving documentation.

This module provides functionality to search for documentation across
various sources including GitHub, official docs, and Stack Overflow.
"""

import re
import json
import logging
import requests
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse, quote
from datetime import datetime
import html
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Web searcher for finding documentation and code examples.
    
    Supports multiple documentation sources and intelligent parsing.
    """
    
    # Common documentation domains
    DOC_SOURCES = {
        'ollama': ['ollama.ai', 'github.com/ollama'],
        'python': ['docs.python.org', 'python.org'],
        'javascript': ['developer.mozilla.org', 'javascript.info'],
        'react': ['react.dev', 'reactjs.org'],
        'django': ['docs.djangoproject.com'],
        'flask': ['flask.palletsprojects.com'],
        'numpy': ['numpy.org/doc'],
        'pandas': ['pandas.pydata.org/docs'],
        'stackoverflow': ['stackoverflow.com'],
        'github': ['github.com']
    }
    
    def __init__(self, timeout: int = 10, max_workers: int = 3):
        """
        Initialize the web searcher.
        
        Args:
            timeout: Request timeout in seconds
            max_workers: Maximum concurrent requests
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search(self, query: str, source_type: Optional[str] = None, 
               max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for documentation across multiple sources.
        
        Args:
            query: Search query
            source_type: Optional source type to limit search
            max_results: Maximum number of results
            
        Returns:
            List of search results with title, url, snippet
        """
        results = []
        
        # Determine which sources to search
        if source_type and source_type in self.DOC_SOURCES:
            sources_to_search = {source_type: self.DOC_SOURCES[source_type]}
        else:
            sources_to_search = self.DOC_SOURCES
        
        # Search each source in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {}
            
            for source_name, domains in sources_to_search.items():
                if source_name == 'stackoverflow':
                    future = executor.submit(self._search_stackoverflow, query, max_results)
                elif source_name == 'github':
                    future = executor.submit(self._search_github, query, max_results)
                else:
                    future = executor.submit(self._search_docs, query, domains, max_results)
                
                future_to_source[future] = source_name
            
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    source_results = future.result()
                    for result in source_results:
                        result['source_type'] = source_name
                    results.extend(source_results)
                except Exception as e:
                    logger.error(f"Error searching {source_name}: {e}")
        
        # Sort by relevance and limit results
        results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return results[:max_results]
    
    def fetch_documentation(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse documentation from a URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Dictionary with title, content, and metadata
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse based on content type
            content_type = response.headers.get('content-type', '').lower()
            
            if 'json' in content_type:
                return self._parse_json_response(response.json(), url)
            elif 'html' in content_type:
                return self._parse_html_documentation(response.text, url)
            else:
                # Try to parse as plain text
                return {
                    'title': self._extract_title_from_url(url),
                    'content': response.text,
                    'url': url,
                    'fetched_at': datetime.utcnow().isoformat()
                }
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _search_stackoverflow(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Stack Overflow for relevant questions."""
        results = []
        
        try:
            # Use Stack Exchange API
            api_url = 'https://api.stackexchange.com/2.3/search/advanced'
            params = {
                'q': query,
                'site': 'stackoverflow',
                'order': 'desc',
                'sort': 'relevance',
                'accepted': 'True',
                'pagesize': max_results
            }
            
            response = self.session.get(api_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('items', []):
                results.append({
                    'title': item['title'],
                    'url': item['link'],
                    'snippet': self._strip_html(item.get('body', ''))[:200] + '...',
                    'relevance_score': item.get('score', 0) / 100.0,
                    'tags': item.get('tags', [])
                })
                
        except Exception as e:
            logger.error(f"Stack Overflow search failed: {e}")
        
        return results
    
    def _search_github(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search GitHub for code and documentation."""
        results = []
        
        try:
            # Search repositories
            api_url = 'https://api.github.com/search/repositories'
            params = {
                'q': query,
                'sort': 'stars',
                'order': 'desc',
                'per_page': max_results
            }
            
            response = self.session.get(api_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            for repo in data.get('items', []):
                # Check for documentation files
                readme_url = f"https://raw.githubusercontent.com/{repo['full_name']}/main/README.md"
                
                results.append({
                    'title': f"{repo['name']} - {repo.get('description', '')}",
                    'url': repo['html_url'],
                    'snippet': repo.get('description', ''),
                    'relevance_score': min(repo.get('stargazers_count', 0) / 1000.0, 1.0),
                    'readme_url': readme_url
                })
                
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
        
        return results
    
    def _search_docs(self, query: str, domains: List[str], 
                     max_results: int) -> List[Dict[str, Any]]:
        """Search documentation sites using site-specific search."""
        results = []
        
        for domain in domains:
            try:
                # Try common documentation URL patterns
                search_urls = [
                    f"https://{domain}/search/?q={quote(query)}",
                    f"https://{domain}/search?q={quote(query)}",
                    f"https://{domain}/api/search/?q={quote(query)}"
                ]
                
                for search_url in search_urls:
                    try:
                        response = self.session.get(search_url, timeout=self.timeout)
                        if response.status_code == 200:
                            # Parse search results
                            domain_results = self._parse_search_results(
                                response.text, domain, query
                            )
                            results.extend(domain_results[:max_results])
                            break
                    except:
                        continue
                        
            except Exception as e:
                logger.debug(f"Search failed for {domain}: {e}")
        
        return results
    
    def _parse_search_results(self, html_content: str, domain: str, 
                              query: str) -> List[Dict[str, Any]]:
        """Parse search results from HTML using regex."""
        results = []
        
        # Common patterns for search results
        # Look for links with titles
        link_pattern = r'<a[^>]*href=["\']([^"\'>]+)["\'][^>]*>([^<]+)</a>'
        matches = re.findall(link_pattern, html_content, re.IGNORECASE)
        
        for href, title in matches[:10]:
            if href and title:
                # Clean up the title
                title = html.unescape(self._strip_html(title)).strip()
                if len(title) < 5:  # Skip very short titles
                    continue
                
                # Build full URL
                if href.startswith('http'):
                    url = href
                else:
                    url = urljoin(f"https://{domain}", href)
                
                # Try to find snippet around this link
                snippet = self._extract_snippet_around_link(html_content, href, title)
                
                # Calculate relevance
                relevance = self._calculate_relevance(title, snippet, query)
                
                results.append({
                    'title': title,
                    'url': url,
                    'snippet': snippet,
                    'relevance_score': relevance
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:5]
    
    def _parse_html_documentation(self, html_content: str, url: str) -> Dict[str, Any]:
        """Parse HTML documentation into structured format using regex."""
        # Extract title
        title = self._extract_title_from_html(html_content, url)
        
        # Remove script and style content
        clean_html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<style[^>]*>.*?</style>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<nav[^>]*>.*?</nav>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<footer[^>]*>.*?</footer>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<header[^>]*>.*?</header>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract main content
        content = self._extract_main_content_regex(clean_html)
        
        # Extract code examples
        code_examples = self._extract_code_examples_regex(clean_html)
        
        # Extract metadata
        metadata = self._extract_metadata_regex(html_content)
        
        return {
            'title': title,
            'content': content,
            'code_examples': code_examples,
            'url': url,
            'metadata': metadata,
            'fetched_at': datetime.utcnow().isoformat()
        }
    
    def _extract_title_from_html(self, html_content: str, url: str) -> str:
        """Extract page title from HTML using regex."""
        # Try to find h1 tag
        h1_match = re.search(r'<h1[^>]*>(.+?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
        if h1_match:
            return html.unescape(self._strip_html(h1_match.group(1))).strip()
        
        # Try title tag
        title_match = re.search(r'<title[^>]*>(.+?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            return html.unescape(self._strip_html(title_match.group(1))).strip()
        
        # Try og:title meta tag
        og_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\'>]+)["\']', html_content, re.IGNORECASE)
        if og_match:
            return html.unescape(og_match.group(1)).strip()
        
        # Try h2 as fallback
        h2_match = re.search(r'<h2[^>]*>(.+?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
        if h2_match:
            return html.unescape(self._strip_html(h2_match.group(1))).strip()
        
        return self._extract_title_from_url(url)
    
    def _extract_main_content_regex(self, html_content: str) -> str:
        """Extract main content from HTML using regex."""
        # Look for main content containers
        content_patterns = [
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class=["\'][^"\'>]*content[^"\'>]*["\'][^>]*>(.*?)</div>',
            r'<div[^>]*class=["\'][^"\'>]*documentation[^"\'>]*["\'][^>]*>(.*?)</div>',
            r'<div[^>]*class=["\'][^"\'>]*markdown-body[^"\'>]*["\'][^>]*>(.*?)</div>',
            r'<div[^>]*id=["\']content["\'][^>]*>(.*?)</div>'
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if match:
                return self._html_to_markdown_regex(match.group(1))
        
        # Fallback to extracting body content
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            return self._html_to_markdown_regex(body_match.group(1))
        
        # Last resort: strip all HTML
        return self._strip_html(html_content)
    
    def _extract_code_examples_regex(self, html_content: str) -> List[Dict[str, str]]:
        """Extract code examples from HTML using regex."""
        examples = []
        
        # Find pre blocks
        pre_pattern = r'<pre[^>]*>(.+?)</pre>'
        pre_matches = re.findall(pre_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for pre_content in pre_matches:
            # Extract code from within the pre block
            code_match = re.search(r'<code[^>]*>(.+?)</code>', pre_content, re.DOTALL | re.IGNORECASE)
            if code_match:
                code_text = html.unescape(self._strip_html(code_match.group(1))).strip()
            else:
                code_text = html.unescape(self._strip_html(pre_content)).strip()
            
            if len(code_text) > 20:  # Skip very short snippets
                # Try to detect language from class attribute
                language = 'text'
                lang_match = re.search(r'class=["\'][^"\'>]*language-([\w]+)', pre_content, re.IGNORECASE)
                if lang_match:
                    language = lang_match.group(1)
                
                examples.append({
                    'code': code_text,
                    'language': language
                })
        
        # Also look for standalone code blocks
        code_pattern = r'<code[^>]*>(.+?)</code>'
        code_matches = re.findall(code_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for code_content in code_matches:
            code_text = html.unescape(self._strip_html(code_content)).strip()
            if len(code_text) > 20 and '\n' in code_text:  # Multi-line code blocks
                examples.append({
                    'code': code_text,
                    'language': 'text'
                })
        
        return examples
    
    def _extract_metadata_regex(self, html_content: str) -> Dict[str, Any]:
        """Extract metadata from HTML using regex."""
        metadata = {}
        
        # Extract meta tags with name attribute
        meta_name_pattern = r'<meta[^>]*name=["\']([^"\'>]+)["\'][^>]*content=["\']([^"\'>]+)["\']'
        for match in re.finditer(meta_name_pattern, html_content, re.IGNORECASE):
            metadata[match.group(1)] = html.unescape(match.group(2))
        
        # Extract meta tags with property attribute
        meta_prop_pattern = r'<meta[^>]*property=["\']([^"\'>]+)["\'][^>]*content=["\']([^"\'>]+)["\']'
        for match in re.finditer(meta_prop_pattern, html_content, re.IGNORECASE):
            metadata[match.group(1)] = html.unescape(match.group(2))
        
        # Extract last modified date
        time_match = re.search(r'<time[^>]*>(.+?)</time>', html_content, re.IGNORECASE)
        if time_match:
            metadata['last_modified'] = html.unescape(self._strip_html(time_match.group(1))).strip()
        
        return metadata
    
    def _html_to_markdown_regex(self, html_content: str) -> str:
        """Convert HTML to markdown-like text using regex."""
        # Replace headers
        text = re.sub(r'<h1[^>]*>(.+?)</h1>', r'\n# \1\n', html_content, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<h2[^>]*>(.+?)</h2>', r'\n## \1\n', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<h3[^>]*>(.+?)</h3>', r'\n### \1\n', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Replace paragraphs
        text = re.sub(r'<p[^>]*>(.+?)</p>', r'\n\1\n', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Replace pre/code blocks
        text = re.sub(r'<pre[^>]*><code[^>]*>(.+?)</code></pre>', r'\n```\n\1\n```\n', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<pre[^>]*>(.+?)</pre>', r'\n```\n\1\n```\n', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<code[^>]*>(.+?)</code>', r'`\1`', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Replace lists
        text = re.sub(r'<li[^>]*>(.+?)</li>', r'- \1\n', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Replace breaks
        text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
        
        # Replace links with markdown format
        text = re.sub(r'<a[^>]*href=["\']([^"\'>]+)["\'][^>]*>(.+?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)
        
        # Replace emphasis
        text = re.sub(r'<strong[^>]*>(.+?)</strong>', r'**\1**', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<b[^>]*>(.+?)</b>', r'**\1**', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<em[^>]*>(.+?)</em>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<i[^>]*>(.+?)</i>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Strip remaining HTML
        text = self._strip_html(text)
        
        # Unescape HTML entities
        text = html.unescape(text)
        
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _calculate_relevance(self, title: str, content: str, query: str) -> float:
        """Calculate relevance score for search result."""
        score = 0.0
        query_terms = query.lower().split()
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Title matches
        for term in query_terms:
            if term in title_lower:
                score += 0.3
        
        # Content matches
        for term in query_terms:
            if term in content_lower:
                score += 0.1
        
        # Exact phrase match
        if query.lower() in title_lower:
            score += 0.5
        elif query.lower() in content_lower:
            score += 0.2
        
        return min(score, 1.0)
    
    def _strip_html(self, html: str) -> str:
        """Remove HTML tags from string."""
        return re.sub('<[^<]+?>', '', html)
    
    def _extract_snippet_around_link(self, html_content: str, href: str, title: str) -> str:
        """Extract text snippet around a link."""
        # Try to find context around the link
        escaped_href = re.escape(href)
        pattern = rf'.{{0,100}}<a[^>]*href=["\']?{escaped_href}["\']?[^>]*>.{{0,200}}'
        
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            snippet = self._strip_html(match.group(0))
            snippet = html.unescape(snippet).strip()
            # Clean up whitespace
            snippet = ' '.join(snippet.split())
            return snippet[:200] + '...' if len(snippet) > 200 else snippet
        
        # Fallback to title
        return title
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract a title from URL path."""
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p]
        if parts:
            # Use last meaningful part
            title = parts[-1].replace('-', ' ').replace('_', ' ')
            return title.title()
        return "Documentation"
    
    def _parse_json_response(self, data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Parse JSON API response."""
        # Handle different JSON structures
        content = json.dumps(data, indent=2)
        
        # Try to extract meaningful title
        title = (
            data.get('title') or 
            data.get('name') or 
            data.get('endpoint') or
            self._extract_title_from_url(url)
        )
        
        return {
            'title': title,
            'content': content,
            'url': url,
            'data': data,
            'fetched_at': datetime.utcnow().isoformat()
        }
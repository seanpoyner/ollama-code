"""File operation utilities"""

import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def create_file(filename, content):
    """Create a file with the given content"""
    try:
        # Create directory if it doesn't exist
        file_path = Path(filename)
        if file_path.parent != Path('.'):
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        console.print(f"📝 [green]Created file: {filename}[/green]")
        return f"File {filename} created successfully"
    except Exception as e:
        return f"Failed to create file: {e}"


def read_file(filename):
    """Read and display a file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        console.print(Panel(
            Syntax(content, get_lexer_from_filename(filename), theme="monokai"),
            title=f"📄 {filename}",
            border_style="cyan"
        ))
        return content
    except Exception as e:
        return f"Failed to read file: {e}"


def list_files(directory="."):
    """List files in a directory"""
    try:
        files = list(Path(directory).iterdir())
        file_list = "\n".join([f.name for f in files])
        console.print(Panel(file_list, title=f"📁 Files in {directory}", border_style="yellow"))
        return file_list
    except Exception as e:
        return f"Failed to list files: {e}"


def get_lexer_from_filename(filename):
    """Get lexer name from filename for syntax highlighting"""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript', 
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.md': 'markdown',
        '.txt': 'text'
    }
    ext = Path(filename).suffix.lower()
    return ext_map.get(ext, 'text')


def extract_function_calls(text):
    """Extract function calls from AI response"""
    calls = []
    
    # First check for markdown files with file indicators - these take priority
    # This prevents nested code examples in documentation from being extracted
    md_pattern = r'```(?:markdown|md)\n(.*?)\n```'
    md_matches = re.findall(md_pattern, text, re.DOTALL)
    for md in md_matches:
        # Check for filename comment
        if md.strip().startswith('<!-- File:') or md.strip().startswith('<!-- file:'):
            lines = md.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'<!--\s*[Ff]ile:\s*(.+?)\s*-->', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    # If we found a markdown file to create, skip other code extraction
                    # This prevents example code in README from being executed
                    return calls
    
    # Extract Python code blocks for execution
    code_pattern = r'```python\n(.*?)\n```'
    code_matches = re.findall(code_pattern, text, re.DOTALL)
    for code in code_matches:
        # Check if this is a file creation block
        if code.strip().startswith('# File:') or code.strip().startswith('# file:'):
            # Extract filename and content
            lines = code.strip().split('\n')
            if len(lines) > 1:
                filename_line = lines[0]
                filename_match = re.search(r'#\s*[Ff]ile:\s*(.+)', filename_line)
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    continue
        # Otherwise treat as executable Python code
        calls.append(('execute_python', code.strip()))
    
    # Extract HTML files
    html_pattern = r'```html\n(.*?)\n```'
    html_matches = re.findall(html_pattern, text, re.DOTALL)
    for i, html in enumerate(html_matches):
        # Check for filename comment
        if html.strip().startswith('<!-- File:') or html.strip().startswith('<!-- file:'):
            lines = html.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'<!--\s*[Ff]ile:\s*(.+?)\s*-->', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    continue
        # If no filename specified, generate one
        filename = f'index.html' if i == 0 else f'page{i+1}.html'
        calls.append(('create_file', (filename, html.strip())))
    
    # Extract CSS files
    css_pattern = r'```css\n(.*?)\n```'
    css_matches = re.findall(css_pattern, text, re.DOTALL)
    for i, css in enumerate(css_matches):
        # Check for filename comment
        if css.strip().startswith('/* File:') or css.strip().startswith('/* file:'):
            lines = css.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'/\*\s*[Ff]ile:\s*(.+?)\s*\*/', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    continue
        # If no filename specified, generate one
        filename = f'styles.css' if i == 0 else f'styles{i+1}.css'
        calls.append(('create_file', (filename, css.strip())))
    
    # Extract JavaScript files
    js_pattern = r'```(?:javascript|js)\n(.*?)\n```'
    js_matches = re.findall(js_pattern, text, re.DOTALL)
    for i, js in enumerate(js_matches):
        # Check for filename comment
        if js.strip().startswith('// File:') or js.strip().startswith('// file:'):
            lines = js.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'//\s*[Ff]ile:\s*(.+)', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    continue
        # If no filename specified, generate one
        filename = f'script.js' if i == 0 else f'script{i+1}.js'
        calls.append(('create_file', (filename, js.strip())))
    
    # Extract JSON files
    json_pattern = r'```json\n(.*?)\n```'
    json_matches = re.findall(json_pattern, text, re.DOTALL)
    for i, json_content in enumerate(json_matches):
        # Check for filename comment
        if json_content.strip().startswith('// File:') or json_content.strip().startswith('// file:'):
            lines = json_content.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'//\s*[Ff]ile:\s*(.+)', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
                    continue
        # Skip if it looks like it's just example data, not a file to create
        if len(json_matches) == 1 and i == 0 and not any(keyword in text.lower() for keyword in ['create', 'file', 'save']):
            continue
        filename = f'data.json' if i == 0 else f'data{i+1}.json'
        calls.append(('create_file', (filename, json_content.strip())))
    
    # Note: Markdown extraction is handled at the beginning of the function
    # to prioritize documentation file creation over example code extraction
    
    # Extract plain text files
    txt_pattern = r'```(?:text|txt|plaintext)\n(.*?)\n```'
    txt_matches = re.findall(txt_pattern, text, re.DOTALL)
    for txt in txt_matches:
        # Check for filename comment
        if txt.strip().startswith('# File:') or txt.strip().startswith('# file:'):
            lines = txt.strip().split('\n')
            if len(lines) > 1:
                filename_match = re.search(r'#\s*[Ff]ile:\s*(.+)', lines[0])
                if filename_match:
                    filename = filename_match.group(1).strip()
                    content = '\n'.join(lines[1:])
                    calls.append(('create_file', (filename, content)))
    
    return calls
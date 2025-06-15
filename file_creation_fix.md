# File Creation Fix for Ollama Code

## Problem
The AI was going through tasks but not actually creating files. It would show file contents in HTML/CSS/JavaScript code blocks instead of using the `write_file()` function to create them.

## Root Cause
The AI was treating file creation as a documentation task - showing what the files would contain rather than actually creating them using the available tools.

## Solution
Enhanced the prompts and task context to explicitly require using `write_file()` function:

### 1. Updated Task Context (thought_loop.py)
Added explicit instructions to each task context:
```python
context += "IMPORTANT: When creating files, you MUST use the write_file() function in a Python code block:\n"
context += "```python\n"
context += 'write_file("filename.ext", """file contents here""")\n'
context += "```\n"
context += "Do NOT just show file contents in code blocks - actually create them!"
```

### 2. Enhanced prompts.yaml
Added critical file creation rules:
```yaml
CRITICAL FILE CREATION RULE:
When showing HTML, CSS, JavaScript, or any other file content:
- DO NOT use ```html, ```css, ```javascript code blocks just to show content
- ALWAYS use ```python code blocks with write_file() to actually create files

WRONG (just showing content):
```html
<!DOCTYPE html>
<html>...
```

CORRECT (actually creating the file):
```python
write_file("index.html", """<!DOCTYPE html>
<html>...
""")
```
```

### 3. Templates Already Include write_file()
The init templates already have proper instructions for using write_file().

## Expected Behavior Now

When asked to create files, the AI should:

1. Use Python code blocks with `write_file()` calls
2. The code blocks will be automatically executed
3. User will see file write confirmation prompts
4. Files will actually be created on disk

Example:
```python
# Create HTML file
write_file("index.html", """<!DOCTYPE html>
<html>
<head>
    <title>Ollama Dashboard</title>
</head>
<body>
    <h1>Ollama Model Status</h1>
    <div id="status"></div>
</body>
</html>""")

# Create JavaScript file
write_file("app.js", """async function checkOllamaStatus() {
    try {
        const response = await fetch('http://localhost:11434/api/tags');
        const data = await response.json();
        document.getElementById('status').textContent = 'Connected';
    } catch (error) {
        document.getElementById('status').textContent = 'Not Connected';
    }
}

checkOllamaStatus();
""")
```

## Testing
To verify the fix works:
1. Ask the AI to create a file: "Create a Python script that prints hello world"
2. Should see a Python code block with `write_file("hello.py", ...)`
3. Should get a file write confirmation prompt
4. File should be created after approval
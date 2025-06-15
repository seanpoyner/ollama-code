# File Exploration Fix for Ollama Code

## Problem

The AI was not properly reading files or exploring the codebase before making implementation decisions. Specifically:

1. **Minimal File Reading**: The AI would only read 50 characters from files like OLLAMA.md
2. **No File Searching**: The AI wouldn't check for existing files (index.html, app.js, styles.css) before making assumptions
3. **Incorrect Assumptions**: The AI would claim features didn't exist (like "no backend") without actually investigating
4. **No Bash Usage**: The AI wasn't using bash commands to search for relevant code

## Root Causes

1. **Task Name Truncation**: The fallback task generation was truncating user requests to 50 characters (e.g., `request[:50]`), which may have confused the AI into thinking it should also read only 50 characters from files.

2. **Insufficient Guidance**: The information gathering guidance in `thought_loop.py` wasn't explicit enough about reading complete files and performing thorough searches.

3. **Missing Emphasis in Prompts**: The system prompts didn't emphasize the importance of complete file reading and thorough exploration.

## Solutions Implemented

### 1. Fixed Task Name Truncation

**Files Modified**: 
- `ollama_code/core/thought_loop.py`
- `ollama_code/core/task_planner.py`

**Changes**:
- Increased truncation limit from 50 to 100 characters
- Added proper ellipsis handling to preserve context
- Example: `request[:50]` → `request if len(request) <= 100 else request[:97] + "..."`

### 2. Enhanced Information Gathering Guidance

**File Modified**: `ollama_code/core/thought_loop.py` (lines 204-234)

**New Guidance Includes**:
```
[CRITICAL: Information Gathering Requirements]

IMPORTANT: You MUST thoroughly explore the codebase before making any assumptions!

1. READ FILES COMPLETELY:
   - Use read_file() to read the FULL content of files (not just 50 characters!)
   - ALWAYS read OLLAMA.md if it exists for project context
   - Check README.md, package.json, requirements.txt, setup.py, etc.
   - Read configuration files (*.json, *.yaml, *.toml)

2. SEARCH FOR EXISTING CODE:
   - Use bash('find . -name "*.py" -o -name "*.js" -o -name "*.html"') to find all code files
   - Use bash('grep -r "backend" . --include="*.py" --include="*.js"') to search for specific features
   - Use bash('rg "API" --type-add "web:*.{html,css,js}" -t web -t py') for better searching

3. EXPLORE PROJECT STRUCTURE:
   - Use list_files() to see directory structure
   - Use bash('ls -la') to see all files including hidden ones
   - Use bash('tree -I "node_modules|__pycache__|.git" -L 3') if available

4. READ KEY FILES:
   - index.html, app.js, main.py, server.py, api.py
   - Any files mentioned in README or documentation
   - Configuration and setup files

5. NEVER ASSUME:
   - Don't claim features don't exist without checking
   - Don't say 'no backend' without searching for backend code
   - Base your analysis on actual file contents, not assumptions

6. TIME GUIDELINE:
   - Spend 30-60 seconds thoroughly exploring
   - Better to be thorough than to miss important details
```

### 3. Updated Task Planning Prompts

**File Modified**: `ollama_code/core/task_planner.py`

**Added to AI Prompt**:
```
CRITICAL FOR ANALYSIS TASKS:
- Analysis tasks should explicitly state that files must be read completely
- Include phrases like "thoroughly explore the codebase" in analysis task descriptions
- Mention specific tools: "using read_file(), list_files(), and bash commands"
- Example: "Analyze requirements: thoroughly explore the codebase and read all relevant files completely"
- NEVER make assumptions about file contents without reading them
- Emphasize complete exploration over quick scanning
```

### 4. Enhanced System Prompts

**File Modified**: `prompts.yaml`

**Key Updates**:
1. Clarified `read_file()` documentation:
   ```yaml
   3. read_file(filename): Read a file's contents
      - Returns the FULL file content as a string
      - ALWAYS use this to read entire files, not just portions
      - Example: content = read_file("app.js")  # Reads the ENTIRE file
   ```

2. Added critical section for information gathering:
   ```yaml
   CRITICAL FOR INFORMATION GATHERING TASKS:
   When analyzing or gathering information about a project:
   1. ALWAYS read files COMPLETELY using read_file() - never just read portions
   2. NEVER make assumptions about what exists - always check first
   3. Use bash commands to search thoroughly:
      - bash('find . -name "*.py" -o -name "*.js"') to find all code files
      - bash('grep -r "backend" . --include="*.py"') to search for features
      - bash('ls -la') to see ALL files including hidden ones
   4. Read ALL relevant files before making conclusions:
      - Configuration files (package.json, requirements.txt, etc.)
      - Main entry points (index.html, app.js, main.py, etc.)
      - Documentation (README.md, OLLAMA.md, etc.)
   5. If you claim something doesn't exist, you MUST show evidence of searching for it
   ```

## Expected Behavior Now

When the AI receives an analysis or information gathering task, it will:

1. **Read Files Completely**: Use `read_file()` to read entire file contents, not just snippets
2. **Search Thoroughly**: Use bash commands to find files and search for specific features
3. **Check Before Assuming**: Look for existing implementations before claiming they don't exist
4. **Explore Project Structure**: Use multiple tools to understand the codebase organization
5. **Provide Evidence**: Show search results when claiming something doesn't exist

## Testing the Fix

To verify these improvements work:

1. Ask the AI to analyze a project with existing files
2. The AI should:
   - Use `read_file()` to read complete files
   - Use `bash('find')` or `bash('grep')` to search for files
   - Use `list_files()` to explore directories
   - Read multiple relevant files before drawing conclusions
   - Not make assumptions without evidence

Example test command:
```bash
ollama-code -p "Analyze this project and tell me about the backend implementation"
```

The AI should now thoroughly explore the codebase instead of making quick assumptions.
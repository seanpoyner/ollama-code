# Analysis Task Truncation Fix

## Problem

The AI was generating responses that were too long for analysis tasks, leading to:
1. Responses being truncated at 800 chunks
2. Python code blocks being cut off mid-string, causing `SyntaxError: unterminated triple-quoted f-string literal`
3. The AI trying to create massive documentation files during simple analysis

## Root Cause

1. The token limit for analysis tasks was set too high (800-1500 tokens)
2. The AI was trying to create comprehensive documentation files with multi-line f-strings
3. No guidance to keep analysis responses concise

## Solutions Implemented

### 1. Reduced Token Limits (agent.py)
```python
# Before:
'num_predict': 800 if self.quick_analysis_mode else 1500

# After:
'num_predict': 500 if self.quick_analysis_mode else 800
```

Also added stop sequences to halt at natural breaks:
```python
'stop': ['```\n\n```', '\n\n##', '\n\nStep']
```

### 2. Updated Analysis Guidance (thought_loop.py)

Changed from verbose exploration instructions to concise, focused guidance:

**Key Changes:**
- Emphasize keeping responses CONCISE and FOCUSED
- Limit code blocks to under 20 lines
- No multi-line f-strings
- Execute commands one by one
- Summarize findings in 3-5 bullet points
- DO NOT create documentation files during analysis

**Example Good Response Format:**
```python
# Check project structure
files = list_files()
print(files)
```

```python
# Read project context
content = read_file('OLLAMA.md')
print(content[:500])  # First 500 chars
```

Then summarize: "Found X files, project uses Y framework..."

## Expected Behavior Now

1. Analysis tasks will generate shorter, more focused responses
2. No more truncated code blocks or syntax errors
3. AI will execute exploration commands step by step
4. Results will be summarized concisely rather than creating long documentation

## Testing

To test the fix:
1. Run: `ollama-code -p "Analyze this project and document the API requirements"`
2. The AI should:
   - Execute short code blocks to explore the project
   - Print summaries rather than creating files
   - Complete without syntax errors
   - Stay within token limits
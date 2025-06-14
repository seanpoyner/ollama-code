"""UI and display utilities"""

import time
import threading
import sys
import select
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt
from rich.live import Live

console = Console()


def detect_thinking_status(response):
    """Detect what the AI is currently doing based on response content"""
    response_lower = response.lower()
    
    # Check for various thinking patterns
    if '```python' in response:
        return "Writing Python code..."
    elif '```html' in response:
        return "Creating HTML structure..."
    elif '```css' in response:
        return "Styling with CSS..."
    elif '```javascript' in response or '```js' in response:
        return "Writing JavaScript..."
    elif 'analyzing' in response_lower or 'looking at' in response_lower:
        return "Analyzing the request..."
    elif 'creating' in response_lower or 'building' in response_lower:
        return "Building solution..."
    elif 'let me' in response_lower or "i'll" in response_lower:
        return "Planning approach..."
    elif 'first' in response_lower or 'step' in response_lower:
        return "Breaking down steps..."
    elif 'error' in response_lower or 'issue' in response_lower:
        return "Handling issues..."
    elif 'file:' in response_lower:
        return "Preparing files..."
    elif len(response) < 50:
        return "Starting response..."
    else:
        return "Processing..."


def setup_esc_handler():
    """Set up ESC key handling for cancellation"""
    cancel_event = threading.Event()
    
    def check_for_esc():
        """Check for ESC key press in a separate thread"""
        # Small delay to avoid catching buffered input
        time.sleep(0.5)
        
        try:
            import msvcrt  # Windows
            # Clear any buffered keystrokes
            while msvcrt.kbhit():
                msvcrt.getch()
            
            while not cancel_event.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESC key
                        cancel_event.set()
                        return
                time.sleep(0.1)
        except ImportError:
            # Unix/Linux
            import termios, tty
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                # Clear any buffered input
                while select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.read(1)
                
                while not cancel_event.is_set():
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        if ord(key) == 27:  # ESC key
                            cancel_event.set()
                            return
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    # Start ESC monitoring thread
    esc_thread = threading.Thread(target=check_for_esc, daemon=True)
    esc_thread.start()
    
    return cancel_event


def display_code_execution(code):
    """Display code that's being executed"""
    console.print(Panel(
        Syntax(code, "python", theme="monokai", line_numbers=True),
        title="🐍 Executing Python Code",
        border_style="blue"
    ))


def display_execution_result(result):
    """Display code execution result"""
    if result['success']:
        if result['output']:
            console.print(Panel(
                result['output'],
                title="✅ Output",
                border_style="green"
            ))
        else:
            console.print("✅ [green]Code executed successfully (no output)[/green]")
    else:
        console.print(Panel(
            result['error'],
            title="❌ Error",
            border_style="red"
        ))
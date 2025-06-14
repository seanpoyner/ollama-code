"""Message loading and management utilities"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Global messages dictionary
MESSAGES = {}


def remove_comments(obj):
    """Recursively remove comment keys from a dictionary"""
    if isinstance(obj, dict):
        return {k: remove_comments(v) for k, v in obj.items() if not k.startswith("//")}
    elif isinstance(obj, list):
        return [remove_comments(item) for item in obj]
    else:
        return obj


def load_messages():
    """Load messages from messages.json file"""
    try:
        # Use absolute path resolution
        import ollama_code
        package_dir = Path(ollama_code.__file__).parent.parent
        messages_file = package_dir / "messages.json"
        
        if messages_file.exists():
            with open(messages_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Recursively remove comment keys
                cleaned_data = remove_comments(data)
                return cleaned_data
        else:
            logger.error(f"messages.json not found at {messages_file}")
            return {}
    except Exception as e:
        logger.error(f"Could not load messages.json: {e}")
        return {}


def get_message(path, **kwargs):
    """Get a message from the messages dictionary with formatting"""
    # If messages aren't loaded, try loading them now
    global MESSAGES
    if not MESSAGES:
        MESSAGES = load_messages()
    
    keys = path.split('.')
    msg = MESSAGES
    
    # Navigate through the dictionary
    for i, key in enumerate(keys):
        if isinstance(msg, dict) and key in msg:
            msg = msg[key]
        else:
            # If we can't find the key, return the path itself
            return path
    
    # Extract text from the message
    if isinstance(msg, dict):
        # If it has a 'text' key, use that
        if 'text' in msg:
            text = msg['text']
        else:
            # Otherwise, return the path as fallback
            text = path
    else:
        # If it's a string or other type, use it directly
        text = str(msg)
    
    # Format with any provided kwargs
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            # If formatting fails, return the unformatted text
            pass
    
    return text


# Load messages immediately after defining the function
MESSAGES = load_messages()
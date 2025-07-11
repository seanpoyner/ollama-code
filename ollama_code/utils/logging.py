"""Logging configuration for Ollama Code"""

import logging
from pathlib import Path


def setup_logging(verbose=False):
    """Setup logging to file only"""
    log_dir = Path.home() / '.ollama' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('ollama_code')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Only log to file, not console
    file_handler = logging.FileHandler(log_dir / 'ollama-code.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Only add handler if not already present
    if not logger.handlers:
        logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("ollama").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger
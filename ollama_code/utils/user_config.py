"""User configuration management"""

import json
from pathlib import Path
from typing import Dict, Any


class UserConfig:
    """Manages user preferences and configuration"""
    
    def __init__(self):
        self.config_dir = Path.home() / '.ollama' / 'ollama-code'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'config.json'
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self.config[key] = value
        self._save_config()
    
    def has_asked_about_chromadb(self) -> bool:
        """Check if we've already asked about ChromaDB installation"""
        return self.get('asked_chromadb', False)
    
    def mark_chromadb_asked(self):
        """Mark that we've asked about ChromaDB"""
        self.set('asked_chromadb', True)
    
    def get_chromadb_preference(self) -> str:
        """Get user's ChromaDB preference"""
        return self.get('chromadb_preference', 'ask')  # 'yes', 'no', or 'ask'
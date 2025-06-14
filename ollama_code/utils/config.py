"""Configuration and prompt loading utilities"""

import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_prompts():
    """Load prompts from prompts.yaml file"""
    try:
        # Use absolute path resolution
        import ollama_code
        package_dir = Path(ollama_code.__file__).parent.parent
        prompts_file = package_dir / "prompts.yaml"
        
        if prompts_file.exists():
            with open(prompts_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            logger.info("prompts.yaml not found, using defaults")
            return None
    except Exception as e:
        logger.error(f"Could not load prompts.yaml: {e}")
        return None


def load_ollama_md():
    """Load OLLAMA.md from the current working directory"""
    try:
        # Look for OLLAMA.md in current directory
        ollama_md_path = Path.cwd() / "OLLAMA.md"
        if ollama_md_path.exists():
            with open(ollama_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"Loaded OLLAMA.md from {ollama_md_path}")
                return content
        else:
            logger.info("No OLLAMA.md found in current directory")
            return None
    except Exception as e:
        logger.error(f"Could not load OLLAMA.md: {e}")
        return None


def load_ollama_code_config():
    """Load additional configuration from .ollama-code directory"""
    try:
        config_dir = Path.cwd() / ".ollama-code"
        config = {}
        
        if config_dir.exists() and config_dir.is_dir():
            # Load any .md files in the directory
            for md_file in config_dir.glob("*.md"):
                with open(md_file, 'r', encoding='utf-8') as f:
                    config[md_file.stem] = f.read()
                    logger.info(f"Loaded {md_file.name} from .ollama-code")
            
            # Load any .yaml files for additional prompts
            for yaml_file in config_dir.glob("*.yaml"):
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config[yaml_file.stem] = yaml.safe_load(f)
                    logger.info(f"Loaded {yaml_file.name} from .ollama-code")
        
        return config if config else None
    except Exception as e:
        logger.error(f"Could not load .ollama-code config: {e}")
        return None
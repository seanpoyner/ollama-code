"""Main entry point for Ollama Code CLI"""

import asyncio
import ollama
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt

from .core.agent import OllamaCodeAgent
from .utils.logging import setup_logging
from .utils.messages import get_message
from .utils.config import load_prompts, load_ollama_md, load_ollama_code_config

console = Console()
logger = setup_logging()


async def main():
    console.print(Panel(
        Text(get_message('app.title'), justify="center"),
        style="bold blue"
    ))
    
    # Load prompts
    prompts_data = load_prompts()
    
    # Load OLLAMA.md and .ollama-code config
    ollama_md = load_ollama_md()
    ollama_config = load_ollama_code_config()
    
    # Show status if project config was loaded
    if ollama_md:
        console.print("📚 [green]Loaded project context from OLLAMA.md[/green]")
    if ollama_config:
        console.print(f"📁 [green]Loaded {len(ollama_config)} additional config files from .ollama-code[/green]")
    
    # Check if Ollama is running
    try:
        models = ollama.list()
        console.print(get_message('connection.ollama_connected'))
        logger.info(f"Connected to Ollama, found {len(models.models)} models")
        
    except Exception as e:
        console.print(get_message('connection.ollama_not_connected'))
        console.print(f"Error: {e}")  # Keep raw error for debugging
        console.print(get_message('connection.ollama_start_hint'))
        logger.error(f"Failed to connect to Ollama: {e}")
        return
    
    # Extract model names properly
    try:
        available_models = []
        for model in models.models:
            # Extract the model name from the Model object
            model_name = model.model if hasattr(model, 'model') else str(model)
            available_models.append(model_name)
            
        if not available_models:
            console.print(get_message('models.no_models'))
            console.print(get_message('models.model_pull_example'))
            return
            
    except Exception as e:
        console.print(get_message('errors.parsing_models', error=e))
        logger.error(f"Error parsing models: {e}")
        return
    
    # Display available models and let user choose
    console.print(get_message('models.available_models_header'))
    models_table = Table(style="cyan")
    models_table.add_column(get_message('table_headers.models.index'), style="bold yellow")
    models_table.add_column(get_message('table_headers.models.model'), style="white")
    
    for i, model in enumerate(available_models, 1):
        models_table.add_row(str(i), model)
    
    console.print(models_table)
    
    # Let user select model
    while True:
        try:
            choice = Prompt.ask(
                get_message('models.model_selection_prompt'), 
                default="1"
            )
            
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(available_models):
                    model_name = available_models[index]
                    break
                else:
                    console.print(get_message('models.invalid_selection'))
            else:
                console.print(get_message('models.enter_number'))
                
        except KeyboardInterrupt:
            console.print("\n" + get_message('app.goodbye'))
            return
    
    console.print(get_message('models.model_selected', model_name=model_name))
    logger.info(f"Selected model: {model_name}")
    
    # Initialize agent with prompts data, OLLAMA.md, and config
    agent = OllamaCodeAgent(model_name, prompts_data, ollama_md, ollama_config)
    
    # Connect to MCP servers
    await agent.connect_mcp_servers()
    
    console.print(get_message('interface.ready'))
    if not ollama_md:  # Only show init hint if no OLLAMA.md exists
        console.print(get_message('interface.init_hint'))
    console.print(get_message('interface.example_hint'))
    console.print(get_message('interface.tools_hint'))
    console.print(get_message('interface.exit_hint') + "\n")
    
    while True:
        try:
            user_input = input(get_message('interface.user_prompt'))
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input.lower() == '/tools':
                agent.show_mcp_tools()
                continue
            elif user_input.lower() == '/help':
                console.print(Panel(
                    get_message('help.panel_content'),
                    title=get_message('help.panel_title'),
                    border_style="blue"
                ))
                continue
            elif user_input.lower().startswith('/init'):
                # Parse the init command
                parts = user_input.split(maxsplit=1)
                force = '--force' in user_input
                
                # Extract user context if provided
                user_context = ""
                if len(parts) > 1:
                    # Remove --force flag if present and get the context
                    context_part = parts[1].replace('--force', '').strip()
                    if context_part:
                        user_context = context_part
                
                await agent.init_project(force=force, user_context=user_context)
                continue
            elif user_input.lower() == '/prompts':
                if prompts_data and 'code' in prompts_data:
                    prompts_table = Table(title=get_message('prompts.available_prompts_header'), style="cyan")
                    prompts_table.add_column(get_message('table_headers.prompts.name'), style="bold yellow")
                    prompts_table.add_column(get_message('table_headers.prompts.description'), style="white")
                    
                    for key, value in prompts_data['code'].items():
                        if key != 'default_system' and isinstance(value, dict):
                            desc = value.get('system', '')[:60] + "..." if len(value.get('system', '')) > 60 else value.get('system', '')
                            prompts_table.add_row(key, desc)
                    
                    console.print(prompts_table)
                else:
                    console.print(get_message('prompts.no_prompts'))
                continue
            elif user_input.startswith('/prompt '):
                prompt_name = user_input.split()[1] if len(user_input.split()) > 1 else ''
                if prompt_name and prompts_data and 'code' in prompts_data and prompt_name in prompts_data['code']:
                    prompt_config = prompts_data['code'][prompt_name]
                    agent.system_prompt = prompt_config.get('system', agent.system_prompt)
                    console.print(get_message('prompts.prompt_loaded', prompt_name=prompt_name))
                else:
                    console.print(get_message('prompts.prompt_not_found', prompt_name=prompt_name))
                continue
            
            if not user_input.strip():
                continue
            
            logger.info(f"User query: {user_input}")
            await agent.chat(user_input)
            
        except KeyboardInterrupt:
            console.print("\n" + get_message('app.goodbye'))
            break
        except Exception as e:
            console.print(get_message('errors.unexpected', error=e))
            logger.error(f"Unexpected error: {e}")
    
    # Cleanup
    await agent.mcp.disconnect_all()
    console.print(get_message('app.logs_saved'))


def run():
    """Entry point for the CLI"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
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
from .core.todos import TodoManager, TodoStatus, TodoPriority
from .core.conversation import ConversationHistory
from .utils.logging import setup_logging
from .utils.messages import get_message
from .utils.config import load_prompts, load_ollama_md, load_ollama_code_config

console = Console()
logger = setup_logging()


async def main(resume=False):
    console.print(Panel(
        Text(get_message('app.title'), justify="center"),
        style="bold blue"
    ))
    
    # Initialize environment detection
    from .utils.environment import get_environment_detector
    env_detector = get_environment_detector()
    
    # Create .ollama-code directory if it doesn't exist
    ollama_code_dir = Path.cwd() / '.ollama-code'
    ollama_code_dir.mkdir(exist_ok=True)
    
    # Save environment configuration
    env_detector.save_environment_config(ollama_code_dir)
    console.print(f"🌍 [green]Detected environment: {env_detector.os_type} with {env_detector.shell} shell[/green]")
    
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
    
    # Initialize todo manager and conversation history
    todo_manager = TodoManager()
    conversation_history = ConversationHistory()
    
    # Initialize agent with prompts data, OLLAMA.md, and config
    agent = OllamaCodeAgent(model_name, prompts_data, ollama_md, ollama_config, todo_manager)
    
    # Connect to MCP servers
    await agent.connect_mcp_servers()
    
    # Handle --resume flag for conversation history
    if resume:
        console.print("\n📚 [cyan]Checking for previous conversations...[/cyan]")
        selected_id = conversation_history.display_conversations()
        if selected_id:
            # Load the conversation
            messages = conversation_history.load_conversation(selected_id)
            if messages:
                # Restore conversation to agent
                agent.conversation = messages
                
                # Show summary
                summary = conversation_history.get_conversation_summary(selected_id)
                console.print(Panel(summary, title="📚 Resuming Conversation", border_style="blue"))
                console.print(f"\n✅ [green]Conversation restored with {len(messages)} messages[/green]\n")
        else:
            # Start new conversation
            console.print("\n🆕 [green]Starting new conversation[/green]\n")
            conversation_history.start_new_conversation()
    
    console.print(get_message('interface.ready'))
    if not ollama_md:  # Only show init hint if no OLLAMA.md exists
        console.print(get_message('interface.init_hint'))
    console.print(get_message('interface.example_hint'))
    console.print(get_message('interface.tools_hint'))
    console.print(get_message('interface.todo_hint'))
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
                help_content = get_message('help.panel_content')
                # Add quick mode to help if not already there
                if '/quick' not in help_content:
                    help_content += "\n• /quick - Toggle quick analysis mode (30s limit for analysis tasks)"
                console.print(Panel(
                    help_content,
                    title=get_message('help.panel_title'),
                    border_style="blue"
                ))
                continue
            elif user_input.lower() == '/auto':
                # Toggle auto-continue mode
                if hasattr(agent, 'auto_mode'):
                    agent.auto_mode = not agent.auto_mode
                else:
                    agent.auto_mode = True
                
                status = "enabled" if agent.auto_mode else "disabled"
                console.print(f"🤖 [cyan]Auto-continue mode {status}[/cyan]")
                
                if agent.auto_mode:
                    console.print("[dim]Tasks will be completed automatically without manual intervention[/dim]")
                else:
                    console.print("[dim]Tasks will pause for review after each completion[/dim]")
                continue
            elif user_input.lower() == '/quick':
                # Toggle quick analysis mode
                agent.quick_analysis_mode = not agent.quick_analysis_mode
                status = "enabled" if agent.quick_analysis_mode else "disabled"
                console.print(f"⚡ [cyan]Quick analysis mode {status}[/cyan]")
                
                if agent.quick_analysis_mode:
                    console.print("[dim]Analysis tasks limited to 30 seconds with brief responses[/dim]")
                else:
                    console.print("[dim]Analysis tasks allowed more time for thorough examination[/dim]")
                continue
            elif user_input.lower() == '/tasks':
                # Show current task progress
                todo_manager.display_todos()
                progress = agent.thought_loop.get_progress_summary()
                if progress:
                    console.print(f"\n{progress}")
                continue
            elif user_input.lower().startswith('/todo'):
                # Parse todo command
                cmd_info = todo_manager.parse_todo_command(user_input)
                
                if cmd_info["action"] == "list":
                    todo_manager.display_todos()
                
                elif cmd_info["action"] == "add":
                    todo = todo_manager.add_todo(cmd_info["content"], cmd_info["priority"])
                    console.print(get_message('todos.added', content=todo.content))
                
                elif cmd_info["action"] == "done":
                    todo = todo_manager.get_todo(cmd_info["id"])
                    if todo:
                        todo_manager.update_todo(todo.id, status=TodoStatus.COMPLETED.value)
                        console.print(get_message('todos.marked_done', content=todo.content))
                    else:
                        console.print(get_message('todos.not_found', id=cmd_info["id"]))
                
                elif cmd_info["action"] == "start":
                    todo = todo_manager.get_todo(cmd_info["id"])
                    if todo:
                        # Mark any other in-progress todos as pending
                        for t in todo_manager.get_todos_by_status(TodoStatus.IN_PROGRESS):
                            todo_manager.update_todo(t.id, status=TodoStatus.PENDING.value)
                        # Mark this one as in progress
                        todo_manager.update_todo(todo.id, status=TodoStatus.IN_PROGRESS.value)
                        console.print(get_message('todos.started', content=todo.content))
                    else:
                        console.print(get_message('todos.not_found', id=cmd_info["id"]))
                
                elif cmd_info["action"] == "cancel":
                    todo = todo_manager.get_todo(cmd_info["id"])
                    if todo:
                        todo_manager.update_todo(todo.id, status=TodoStatus.CANCELLED.value)
                        console.print(get_message('todos.cancelled', content=todo.content))
                    else:
                        console.print(get_message('todos.not_found', id=cmd_info["id"]))
                
                elif cmd_info["action"] == "delete":
                    todo = todo_manager.get_todo(cmd_info["id"])
                    if todo:
                        content = todo.content
                        todo_manager.delete_todo(todo.id)
                        console.print(get_message('todos.deleted'))
                    else:
                        console.print(get_message('todos.not_found', id=cmd_info["id"]))
                
                elif cmd_info["action"] == "next":
                    todo_manager.display_next_todo()
                
                elif cmd_info["action"] == "clear":
                    # Clear completed todos
                    completed = todo_manager.get_todos_by_status(TodoStatus.COMPLETED)
                    for todo in completed:
                        todo_manager.delete_todo(todo.id)
                    console.print(get_message('todos.cleared'))
                
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
            
            # Save user message to conversation history
            conversation_history.add_message("user", user_input)
            
            # Chat with agent
            response = await agent.chat(user_input)
            
            # Save assistant response to conversation history
            if response:
                conversation_history.add_message("assistant", response)
            
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
    import sys
    
    # Check for --resume flag
    resume = '--resume' in sys.argv
    
    asyncio.run(main(resume=resume))


if __name__ == "__main__":
    run()
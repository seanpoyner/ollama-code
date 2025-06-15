"""Command-line interface for ollama-code"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

import ollama
from rich.console import Console

from .core.agent import OllamaCodeAgent
from .core.todos import TodoManager, TodoStatus
from .core.conversation import ConversationHistory
from .utils.logging import setup_logging
from .utils.config import load_prompts, load_ollama_md, load_ollama_code_config
from .utils.messages import get_message

console = Console()


def create_parser():
    """Create the argument parser for ollama-code CLI"""
    parser = argparse.ArgumentParser(
        prog='ollama-code',
        description='AI-powered coding assistant using Ollama',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ollama-code                                    # Start interactive mode
  ollama-code -p "Create a Python web scraper"   # Execute a single prompt
  ollama-code --init "FastAPI project"           # Initialize project with context
  ollama-code --resume                           # Resume previous conversation
  ollama-code --model qwen2.5-coder:7b           # Use a specific model
  ollama-code --auto --quick                     # Auto-mode with quick analysis
"""
    )
    
    # Main arguments
    parser.add_argument(
        '-p', '--prompt',
        type=str,
        help='Execute a single prompt and exit'
    )
    
    parser.add_argument(
        '--init',
        type=str,
        nargs='?',
        const='',
        metavar='CONTEXT',
        help='Initialize project with OLLAMA.md. Optional context description.'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume the previous conversation'
    )
    
    # Model and behavior options
    parser.add_argument(
        '-m', '--model',
        type=str,
        help='Specify the Ollama model to use'
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Enable auto-continue mode for task execution'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Enable quick analysis mode (30s limit for analysis tasks)'
    )
    
    parser.add_argument(
        '--no-quick',
        action='store_true',
        help='Disable quick analysis mode'
    )
    
    # Output options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Minimize output, only show essential information'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    # File and approval options
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        help='Auto-approve all file writes and commands'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite existing files (e.g., OLLAMA.md)'
    )
    
    # Advanced options
    parser.add_argument(
        '--temperature',
        type=float,
        metavar='T',
        help='Set model temperature (0.0-2.0)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        metavar='N',
        help='Maximum tokens for model response'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=120,
        metavar='SECONDS',
        help='Timeout for model responses (default: 120s)'
    )
    
    # Utility commands
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available Ollama models and exit'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    return parser


async def handle_init_command(agent: OllamaCodeAgent, context: str, force: bool):
    """Handle the --init command"""
    await agent.init_project(force=force, user_context=context)


async def handle_single_prompt(agent: OllamaCodeAgent, prompt: str):
    """Handle a single prompt execution"""
    # Process the prompt
    response = await agent.chat(prompt, enable_esc_cancel=False)
    
    # If tasks were created, execute them
    pending_tasks = agent.todo_manager.get_todos_by_status(TodoStatus.PENDING)
    if pending_tasks:
        console.print(f"\n🚀 [cyan]Executing {len(pending_tasks)} tasks...[/cyan]")
        await agent._execute_tasks_sequentially(enable_esc_cancel=False)


async def list_available_models():
    """List all available Ollama models"""
    try:
        response = ollama.list()
        models = response.get('models', [])
        
        if not models:
            console.print("❌ [red]No models available. Please pull a model first.[/red]")
            console.print("Example: ollama pull qwen2.5-coder:7b")
            return
        
        from rich.table import Table
        
        table = Table(title="Available Ollama Models", style="cyan")
        table.add_column("Model", style="bold yellow")
        table.add_column("Size", style="green")
        table.add_column("Modified", style="blue")
        
        for model in models:
            name = model.get('name', 'Unknown')
            size = f"{model.get('size', 0) / 1e9:.1f}GB"
            modified = model.get('modified_at', 'Unknown')[:10]
            table.add_row(name, size, modified)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ [red]Error listing models: {e}[/red]")


async def run_cli(args):
    """Run the CLI with parsed arguments"""
    # Handle utility commands first
    if args.list_models:
        await list_available_models()
        return
    
    # Setup environment
    if args.no_color:
        console = Console(no_color=True)
    
    # Setup logging
    logger = setup_logging(verbose=args.verbose)
    
    # Load configurations
    prompts_data = load_prompts()
    ollama_md = load_ollama_md()
    ollama_config = load_ollama_code_config()
    
    # Show project context if loaded
    if ollama_md and not args.quiet:
        console.print("📚 [green]Loaded project context from OLLAMA.md[/green]")
    
    # Initialize todo manager
    todo_manager = TodoManager()
    
    # Load conversation history if resuming
    conversation_history = ConversationHistory()
    if args.resume:
        if conversation_history.load():
            if not args.quiet:
                console.print("📂 [green]Resumed previous conversation[/green]")
    
    # Check Ollama connection
    try:
        ollama.list()
    except:
        console.print("❌ [red]Cannot connect to Ollama server[/red]")
        console.print("Please start Ollama: ollama serve")
        return
    
    # Select model
    model_name = args.model
    if not model_name:
        # Try to get default model
        import ollama
        try:
            response = ollama.list()
            models = response.get('models', [])
            if models:
                model_name = models[0]['name']
                if not args.quiet:
                    console.print(f"🤖 [cyan]Using model: {model_name}[/cyan]")
            else:
                console.print("❌ [red]No models available. Please pull a model first.[/red]")
                return
        except:
            console.print("❌ [red]Error selecting model[/red]")
            return
    
    # Create agent
    agent = OllamaCodeAgent(
        model_name=model_name,
        prompts_data=prompts_data,
        ollama_md=ollama_md,
        ollama_config=ollama_config,
        todo_manager=todo_manager
    )
    
    # Apply settings from arguments
    if args.auto:
        agent.auto_mode = True
    if args.quick:
        agent.quick_analysis_mode = True
    if args.no_quick:
        agent.quick_analysis_mode = False
    if args.auto_approve:
        agent.auto_approve_writes = True
    
    # Restore conversation if resuming
    if args.resume and conversation_history.messages:
        agent.conversation = conversation_history.messages
    
    # Handle commands
    if args.init is not None:
        await handle_init_command(agent, args.init, args.force)
    elif args.prompt:
        await handle_single_prompt(agent, args.prompt)
    else:
        # Interactive mode
        if not args.quiet:
            console.print("🚀 [green]Code agent ready![/green]")
            console.print("💡 [dim]Type '/help' for available commands[/dim]")
        
        # Import and run the main interactive loop
        from .main import interactive_loop
        await interactive_loop(agent, conversation_history, todo_manager, prompts_data)


def main():
    """Main entry point for the CLI"""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        asyncio.run(run_cli(args))
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!")
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
#! /usr/bin/env python

"""
ollama-chat.py

Ollama Chat Interface:
- Requires: ollama, rich, requests
- Run with: python ollama-chat.py 
    or add to $PROFILE with:
        function ollama-chat {
            python ollama-chat.py
        }
    or add to linux alias:
        alias ollama-chat='python ~/.ollama/ollama-chat.py'
- Ensure Ollama server is running on localhost:11434
"""

import ollama
import sys
import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.markdown import Markdown
from rich.columns import Columns
from rich.align import Align
from rich.table import Table
import time

console = Console()

def display_header():
    header = Text("🤖 OLLAMA CHAT 🤖", style="bold cyan")
    console.print(Panel(Align.center(header), style="bold blue"))

def display_welcome_info(model_name):
    # Model info
    console.print(f"\n🚀 [bold green]Starting chat with {model_name}[/bold green]")
    
    # Welcome panel with basic instructions
    welcome_text = Text()
    welcome_text.append("Welcome to Ollama Chat! Here's how to get started:\n\n", style="bold white")
    welcome_text.append("💭 ", style="cyan")
    welcome_text.append("Just type your message and press Enter\n", style="white")
    welcome_text.append("🔧 ", style="yellow")
    welcome_text.append("Type ", style="white")
    welcome_text.append("/help", style="bold cyan")
    welcome_text.append(" to see all available commands\n", style="white")
    welcome_text.append("⚙️ ", style="magenta")
    welcome_text.append("Use ", style="white")
    welcome_text.append("/temp", style="bold cyan")
    welcome_text.append(", ", style="white")
    welcome_text.append("/system", style="bold cyan")
    welcome_text.append(", etc. to customize AI behavior\n", style="white")
    welcome_text.append("🔄 ", style="green")
    welcome_text.append("Type ", style="white")
    welcome_text.append("/models", style="bold cyan")
    welcome_text.append(" to switch models anytime\n", style="white")
    welcome_text.append("🚪 ", style="red")
    welcome_text.append("Type ", style="white")
    welcome_text.append("/quit", style="bold cyan")
    welcome_text.append(" or ", style="white")
    welcome_text.append("/exit", style="bold cyan")
    welcome_text.append(" to leave", style="white")
    
    console.print(Panel(welcome_text, title="ℹ️ Quick Start Guide", title_align="left", style="dim"))

def show_help():
    help_table = Table(title="🔧 Available Commands", style="cyan")
    help_table.add_column("Command", style="bold yellow")
    help_table.add_column("Description", style="white")
    
    commands = [
        ("/help", "Show this help message"),
        ("/models", "Switch to a different model"),
        ("/show", "Show current model information"),
        ("/system <msg>", "Set system prompt"),
        ("/temp <0.0-2.0>", "Set temperature (creativity)"),
        ("/top_p <0.0-1.0>", "Set top_p (focus)"),
        ("/top_k <number>", "Set top_k (vocabulary limit)"),
        ("/repeat_penalty <1.0+>", "Set repetition penalty"),
        ("/seed <number>", "Set random seed"),
        ("/clear", "Clear conversation history"),
        ("/save <name>", "Save current conversation"),
        ("/load <name>", "Load saved conversation"),
        ("/multiline", "Toggle multiline input mode"),
        ("/settings", "Show current AI parameters"),
        ("/quit or /exit", "Exit the chat"),
    ]
    
    for cmd, desc in commands:
        help_table.add_row(cmd, desc)
    
    console.print(help_table)

def select_model():
    # Get models (same as before)
    try:
        response = requests.get('http://localhost:11434/api/tags')
        if response.status_code != 200:
            console.print("❌ [red]Error: Ollama API not responding[/red]")
            return None
    except Exception as e:
        console.print(f"❌ [red]Error connecting to Ollama: {e}[/red]")
        return None

    models = []
    
    try:
        response = ollama.list()
        if hasattr(response, 'models'):
            for model in response.models:
                if hasattr(model, 'model'):
                    models.append(model.model)
        elif isinstance(response, dict) and 'models' in response:
            for model in response['models']:
                if isinstance(model, dict):
                    name = model.get('name') or model.get('model')
                    if name:
                        models.append(name)
    except Exception:
        pass
    
    if not models:
        try:
            resp = requests.get('http://localhost:11434/api/tags')
            data = resp.json()
            if 'models' in data:
                for model in data['models']:
                    name = model.get('name') or model.get('model')
                    if name:
                        models.append(name)
        except Exception:
            pass

    if not models:
        console.print("❌ [red]No models found. Run 'ollama pull <model>' first.[/red]")
        return None

    console.print(f"\n🎯 [bold cyan]Available Models:[/bold cyan]")
    
    model_panels = []
    for i, model in enumerate(models, 1):
        model_text = Text(f"{i}. {model}", style="bold white")
        panel = Panel(model_text, style="green", width=30)
        model_panels.append(panel)
    
    console.print(Columns(model_panels, equal=True, expand=True))
    
    while True:
        try:
            choice = Prompt.ask(f"\n🔍 [bold yellow]Select model[/bold yellow]", 
                              choices=[str(i) for i in range(1, len(models) + 1)])
            return models[int(choice) - 1]
        except (ValueError, IndexError):
            console.print("❌ [red]Invalid selection, please try again[/red]")

def show_model_info(model_name):
    try:
        info = ollama.show(model_name)
        
        info_table = Table(title=f"📊 Model: {model_name}", style="green")
        info_table.add_column("Property", style="bold cyan")
        info_table.add_column("Value", style="white")
        
        if hasattr(info, 'details'):
            details = info.details
            if hasattr(details, 'parameter_size'):
                info_table.add_row("Parameter Size", details.parameter_size)
            if hasattr(details, 'quantization_level'):
                info_table.add_row("Quantization", details.quantization_level)
            if hasattr(details, 'family'):
                info_table.add_row("Family", details.family)
        
        console.print(info_table)
        
    except Exception as e:
        console.print(f"❌ [red]Error getting model info: {e}[/red]")

def display_chat_message(role, content, model_name=None):
    if role == "user":
        user_text = Text("You", style="bold blue")
        panel = Panel(content, title=user_text, title_align="left", 
                     style="blue", border_style="blue")
    else:
        ai_title = f"🤖 {model_name}" if model_name else "🤖 AI"
        ai_text = Text(ai_title, style="bold green")
        
        try:
            content_display = Markdown(content)
        except:
            content_display = content
            
        panel = Panel(content_display, title=ai_text, title_align="left",
                     style="green", border_style="green")
    
    console.print(panel)

def display_settings(settings):
    settings_table = Table(title="⚙️ Current Settings", style="yellow")
    settings_table.add_column("Parameter", style="bold cyan")
    settings_table.add_column("Value", style="white")
    settings_table.add_column("Description", style="dim")
    
    descriptions = {
        'temperature': 'Creativity (0.0=focused, 2.0=creative)',
        'top_p': 'Focus (0.0=precise, 1.0=diverse)',
        'top_k': 'Vocabulary limit (lower=focused)',
        'repeat_penalty': 'Repetition penalty (1.0=none)',
        'seed': 'Random seed (for reproducibility)'
    }
    
    for key, value in settings.items():
        if value is not None:
            desc = descriptions.get(key, '')
            settings_table.add_row(key, str(value), desc)
    
    console.print(settings_table)

def main():
    console.clear()
    display_header()
    
    # Model selection
    selected_model = select_model()
    if not selected_model:
        return
    
    # Display welcome info
    display_welcome_info(selected_model)

    conversation = []
    system_prompt = None
    multiline_mode = False
    
    # Ollama parameters
    settings = {
        'temperature': 0.7,
        'top_p': 0.9,
        'top_k': 40,
        'repeat_penalty': 1.1,
        'seed': None
    }
    
    while True:
        try:
            # Get user input
            if multiline_mode:
                console.print("📝 [bold cyan]Multiline mode (type 'END' on new line to finish):[/bold cyan]")
                lines = []
                while True:
                    line = input()
                    if line.strip() == 'END':
                        break
                    lines.append(line)
                user_input = '\n'.join(lines)
            else:
                user_input = Prompt.ask("\n💭 [bold cyan]Your message[/bold cyan]")
            
            # Handle slash commands
            if user_input.startswith('/'):
                cmd_parts = user_input.split()
                cmd = cmd_parts[0].lower()
                
                if cmd in ['/quit', '/exit']:
                    console.print("\n👋 [bold yellow]Goodbye![/bold yellow]")
                    break
                elif cmd == '/help':
                    show_help()
                    continue
                elif cmd == '/models':
                    new_model = select_model()
                    if new_model:
                        selected_model = new_model
                        display_welcome_info(selected_model)
                    continue
                elif cmd == '/show':
                    show_model_info(selected_model)
                    continue
                elif cmd == '/clear':
                    conversation = []
                    console.print("🧹 [bold yellow]Conversation cleared[/bold yellow]")
                    continue
                elif cmd == '/settings':
                    display_settings(settings)
                    continue
                elif cmd == '/multiline':
                    multiline_mode = not multiline_mode
                    status = "enabled" if multiline_mode else "disabled"
                    console.print(f"📝 [bold yellow]Multiline mode {status}[/bold yellow]")
                    continue
                elif cmd == '/system' and len(cmd_parts) > 1:
                    system_prompt = ' '.join(cmd_parts[1:])
                    console.print(f"🎯 [bold yellow]System prompt set: {system_prompt}[/bold yellow]")
                    continue
                elif cmd == '/temp' and len(cmd_parts) > 1:
                    try:
                        settings['temperature'] = float(cmd_parts[1])
                        console.print(f"🌡️ [bold yellow]Temperature set to {settings['temperature']}[/bold yellow]")
                    except ValueError:
                        console.print("❌ [red]Invalid temperature value (use 0.0-2.0)[/red]")
                    continue
                elif cmd == '/top_p' and len(cmd_parts) > 1:
                    try:
                        settings['top_p'] = float(cmd_parts[1])
                        console.print(f"🎯 [bold yellow]Top_p set to {settings['top_p']}[/bold yellow]")
                    except ValueError:
                        console.print("❌ [red]Invalid top_p value (use 0.0-1.0)[/red]")
                    continue
                elif cmd == '/top_k' and len(cmd_parts) > 1:
                    try:
                        settings['top_k'] = int(cmd_parts[1])
                        console.print(f"🔢 [bold yellow]Top_k set to {settings['top_k']}[/bold yellow]")
                    except ValueError:
                        console.print("❌ [red]Invalid top_k value (use positive integer)[/red]")
                    continue
                elif cmd == '/repeat_penalty' and len(cmd_parts) > 1:
                    try:
                        settings['repeat_penalty'] = float(cmd_parts[1])
                        console.print(f"🔁 [bold yellow]Repeat penalty set to {settings['repeat_penalty']}[/bold yellow]")
                    except ValueError:
                        console.print("❌ [red]Invalid repeat penalty value (use 1.0+)[/red]")
                    continue
                elif cmd == '/seed' and len(cmd_parts) > 1:
                    try:
                        settings['seed'] = int(cmd_parts[1])
                        console.print(f"🌱 [bold yellow]Seed set to {settings['seed']}[/bold yellow]")
                    except ValueError:
                        console.print("❌ [red]Invalid seed value (use integer)[/red]")
                    continue
                else:
                    console.print("❌ [red]Unknown command. Type '/help' for available commands[/red]")
                    continue
            
            if user_input.lower() in ['quit', 'exit']:
                console.print("\n👋 [bold yellow]Goodbye![/bold yellow]")
                break
            
            # Display user message
            display_chat_message("user", user_input)
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            
            messages.extend(conversation)
            messages.append({'role': 'user', 'content': user_input})
            
            # Show thinking indicator
            with console.status("🤔 [bold yellow]AI is thinking...[/bold yellow]", spinner="dots"):
                # Get AI response with settings
                response_content = ""
                stream = ollama.chat(
                    model=selected_model,
                    messages=messages,
                    stream=True,
                    options={
                        'temperature': settings['temperature'],
                        'top_p': settings['top_p'],
                        'top_k': settings['top_k'],
                        'repeat_penalty': settings['repeat_penalty'],
                        'seed': settings['seed']
                    }
                )
                
                # Collect the full response
                for chunk in stream:
                    response_content += chunk['message']['content']
            
            # Add to conversation
            conversation.append({'role': 'user', 'content': user_input})
            conversation.append({'role': 'assistant', 'content': response_content})
            
            # Display AI response
            display_chat_message("assistant", response_content, selected_model)
            
        except KeyboardInterrupt:
            console.print("\n\n👋 [bold yellow]Goodbye![/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n❌ [red]Error: {e}[/red]")

if __name__ == "__main__":
    main()
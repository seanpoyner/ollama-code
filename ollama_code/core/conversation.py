"""Conversation history management for resuming sessions"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console()


class ConversationHistory:
    def __init__(self, history_dir: Path = None):
        self.history_dir = history_dir or Path.cwd() / ".ollama-code" / "conversations"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.current_conversation_id = None
        self.current_conversation = []
    
    def _generate_id(self) -> str:
        """Generate unique conversation ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    def _get_conversation_path(self, conversation_id: str) -> Path:
        """Get path for a conversation file"""
        return self.history_dir / f"conversation_{conversation_id}.json"
    
    def start_new_conversation(self, first_message: str = None) -> str:
        """Start a new conversation"""
        self.current_conversation_id = self._generate_id()
        self.current_conversation = []
        
        metadata = {
            "id": self.current_conversation_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "title": self._generate_title(first_message) if first_message else "New Conversation",
            "messages": []
        }
        
        # Save initial metadata
        self._save_conversation(metadata)
        return self.current_conversation_id
    
    def _generate_title(self, first_message: str) -> str:
        """Generate a title from the first message"""
        # Clean and truncate the message
        title = first_message.strip()
        if len(title) > 50:
            title = title[:47] + "..."
        return title
    
    def add_message(self, role: str, content: str):
        """Add a message to the current conversation"""
        if not self.current_conversation_id:
            self.start_new_conversation(content if role == "user" else None)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_conversation.append(message)
        
        # Load existing conversation
        conv_path = self._get_conversation_path(self.current_conversation_id)
        if conv_path.exists():
            with open(conv_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                "id": self.current_conversation_id,
                "created_at": datetime.now().isoformat(),
                "title": "New Conversation",
                "messages": []
            }
        
        # Update conversation
        data["messages"].append(message)
        data["last_updated"] = datetime.now().isoformat()
        
        # Update title if this is the first user message
        if role == "user" and len(data["messages"]) == 1:
            data["title"] = self._generate_title(content)
        
        self._save_conversation(data)
    
    def _save_conversation(self, data: Dict):
        """Save conversation to file"""
        conv_path = self._get_conversation_path(data["id"])
        with open(conv_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load_conversation(self, conversation_id: str) -> List[Dict]:
        """Load a conversation by ID"""
        conv_path = self._get_conversation_path(conversation_id)
        if conv_path.exists():
            with open(conv_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.current_conversation_id = conversation_id
                self.current_conversation = data["messages"]
                
                # Update last accessed time
                data["last_updated"] = datetime.now().isoformat()
                self._save_conversation(data)
                
                return data["messages"]
        return []
    
    def list_conversations(self) -> List[Dict]:
        """List all conversations with metadata"""
        conversations = []
        
        for conv_file in self.history_dir.glob("conversation_*.json"):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Calculate time differences
                    created = datetime.fromisoformat(data["created_at"])
                    updated = datetime.fromisoformat(data["last_updated"])
                    now = datetime.now()
                    
                    created_ago = self._format_time_ago(now - created)
                    updated_ago = self._format_time_ago(now - updated)
                    
                    conversations.append({
                        "id": data["id"],
                        "title": data["title"],
                        "created_ago": created_ago,
                        "updated_ago": updated_ago,
                        "message_count": len(data["messages"]),
                        "created_at": created,
                        "last_updated": updated
                    })
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load {conv_file}: {e}[/yellow]")
        
        # Sort by last updated, most recent first
        conversations.sort(key=lambda x: x["last_updated"], reverse=True)
        return conversations
    
    def _format_time_ago(self, delta: timedelta) -> str:
        """Format timedelta as human-readable string"""
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days > 1 else ''} ago"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            months = seconds // 2592000
            return f"{months} month{'s' if months > 1 else ''} ago"
    
    def display_conversations(self) -> Optional[str]:
        """Display conversations and let user select one"""
        conversations = self.list_conversations()
        
        if not conversations:
            console.print("[yellow]No previous conversations found in this directory.[/yellow]")
            return None
        
        # Create table
        table = Table(title="📚 Previous Conversations", style="cyan")
        table.add_column("#", style="bold yellow", width=3)
        table.add_column("Title", style="white")
        table.add_column("Messages", width=10)
        table.add_column("Created", style="dim", width=15)
        table.add_column("Last Used", style="dim", width=15)
        table.add_column("ID", style="dim", width=12)
        
        for i, conv in enumerate(conversations, 1):
            table.add_row(
                str(i),
                conv["title"][:50] + "..." if len(conv["title"]) > 50 else conv["title"],
                str(conv["message_count"]),
                conv["created_ago"],
                conv["updated_ago"],
                conv["id"]
            )
        
        console.print(table)
        
        # Let user select
        while True:
            try:
                choice = Prompt.ask(
                    "\n[cyan]Select a conversation by number (or 'new' for new conversation)[/cyan]",
                    default="new"
                )
                
                if choice.lower() == 'new':
                    return None
                
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(conversations):
                        return conversations[index]["id"]
                    else:
                        console.print("[red]Invalid selection. Please try again.[/red]")
                else:
                    console.print("[red]Please enter a number or 'new'.[/red]")
                    
            except KeyboardInterrupt:
                return None
    
    def get_conversation_summary(self, conversation_id: str) -> str:
        """Generate a summary of the conversation for context"""
        messages = self.load_conversation(conversation_id)
        
        if not messages:
            return ""
        
        summary_lines = ["Previous conversation summary:"]
        summary_lines.append("-" * 40)
        
        # Include first few and last few messages
        if len(messages) <= 6:
            # Include all messages if short conversation
            for msg in messages:
                role = "You" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                summary_lines.append(f"{role}: {content}")
        else:
            # Include first 3 and last 3 messages
            for msg in messages[:3]:
                role = "You" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                summary_lines.append(f"{role}: {content}")
            
            summary_lines.append(f"\n... {len(messages) - 6} messages omitted ...\n")
            
            for msg in messages[-3:]:
                role = "You" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                summary_lines.append(f"{role}: {content}")
        
        summary_lines.append("-" * 40)
        return "\n".join(summary_lines)
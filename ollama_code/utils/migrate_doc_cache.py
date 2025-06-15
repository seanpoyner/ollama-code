#!/usr/bin/env python3
"""
Migration utility to convert SQLite FTS5 documentation cache to ChromaDB vector store.

Usage:
    python -m ollama_code.utils.migrate_doc_cache
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import json

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_sqlite_cache(db_path: Path) -> List[Dict[str, Any]]:
    """Read all entries from SQLite cache."""
    entries = []
    
    if not db_path.exists():
        console.print(f"[red]SQLite cache not found at {db_path}[/red]")
        return entries
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM doc_cache 
                WHERE expires_at > ?
                ORDER BY created_at DESC
            ''', (datetime.utcnow().isoformat(),))
            
            for row in cursor:
                entries.append(dict(row))
        
        console.print(f"[green]Found {len(entries)} non-expired entries in SQLite cache[/green]")
        
    except Exception as e:
        console.print(f"[red]Error reading SQLite cache: {e}[/red]")
    
    return entries


def migrate_to_vector_store(entries: List[Dict[str, Any]]):
    """Migrate entries to ChromaDB vector store."""
    try:
        from ollama_code.core.doc_vector_store import DocVectorStore
    except ImportError:
        console.print("[red]ChromaDB is not installed. Please install it first:[/red]")
        console.print("[yellow]pip install chromadb[/yellow]")
        return False
    
    # Initialize vector store
    try:
        vector_store = DocVectorStore()
        console.print("[green]Initialized ChromaDB vector store[/green]")
    except Exception as e:
        console.print(f"[red]Failed to initialize vector store: {e}[/red]")
        return False
    
    # Migrate entries with progress bar
    success_count = 0
    error_count = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("Migrating entries...", total=len(entries))
        
        for entry in entries:
            try:
                # Parse tags if they're JSON strings
                tags = entry.get('tags', '[]')
                if isinstance(tags, str):
                    tags = json.loads(tags)
                
                # Add to vector store
                vector_store.add(
                    url=entry['url'],
                    title=entry['title'],
                    content=entry['content'],
                    source_type=entry['source_type'],
                    tags=tags
                )
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate entry {entry.get('title', 'Unknown')}: {e}")
                error_count += 1
            
            progress.update(task, advance=1)
    
    # Show results
    table = Table(title="Migration Results")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")
    
    table.add_row("Successfully migrated", str(success_count))
    table.add_row("Failed", str(error_count))
    table.add_row("Total", str(len(entries)))
    
    console.print(table)
    
    return success_count > 0


def main():
    """Main migration function."""
    console.print("[bold]Documentation Cache Migration Tool[/bold]")
    console.print("This will migrate your SQLite FTS5 cache to ChromaDB vector store\n")
    
    # Find SQLite cache
    sqlite_path = Path.home() / '.ollama' / 'doc_cache' / 'doc_cache.db'
    
    # Read entries
    entries = read_sqlite_cache(sqlite_path)
    
    if not entries:
        console.print("[yellow]No entries to migrate[/yellow]")
        return 0
    
    # Confirm migration
    console.print(f"\nReady to migrate {len(entries)} entries to vector store.")
    confirm = console.input("[yellow]Continue? (y/n): [/yellow]")
    
    if confirm.lower() != 'y':
        console.print("[red]Migration cancelled[/red]")
        return 1
    
    # Perform migration
    console.print()
    success = migrate_to_vector_store(entries)
    
    if success:
        console.print("\n[green]Migration completed successfully![/green]")
        console.print("\nThe old SQLite cache is still available at:")
        console.print(f"[dim]{sqlite_path}[/dim]")
        console.print("\nYou can delete it manually if no longer needed.")
        return 0
    else:
        console.print("\n[red]Migration failed[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
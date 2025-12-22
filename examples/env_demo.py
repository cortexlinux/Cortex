#!/usr/bin/env python3
"""
Environment Manager Demo
Demonstrates environment variable management features in Cortex
"""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.env_manager import EnvManager
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def demo_basic_operations():
    """Demonstrate basic environment variable operations"""
    console.print(Panel.fit(
        "[bold cyan]Basic Environment Variable Operations[/bold cyan]",
        border_style="cyan"
    ))
    
    # Use temporary directory for demo
    temp_dir = Path(tempfile.mkdtemp())
    manager = EnvManager(cortex_home=temp_dir)
    
    # Set variables
    console.print("\n[bold]Setting variables...[/bold]")
    manager.set("myapp", "DATABASE_URL", "postgres://localhost/mydb")
    console.print("✓ Set DATABASE_URL")
    
    manager.set("myapp", "API_KEY", "secret123", encrypt=True)
    console.print("✓ Set API_KEY (encrypted)")
    
    manager.set("myapp", "NODE_ENV", "production")
    console.print("✓ Set NODE_ENV")
    
    # List variables
    console.print("\n[bold]Listing variables...[/bold]")
    env_vars = manager.list("myapp")
    for key, var in env_vars.items():
        encrypted_marker = " 🔐" if var.encrypted else ""
        console.print(f"  {key}: {var.value if not var.encrypted else '[encrypted]'}{encrypted_marker}")
    
    # Get specific variable
    console.print("\n[bold]Getting decrypted API_KEY...[/bold]")
    api_key = manager.get("myapp", "API_KEY", decrypt=True)
    console.print(f"  API_KEY = {api_key}")
    
    # Export
    console.print("\n[bold]Exporting to .env format...[/bold]")
    export_output = manager.export("myapp", format="env")
    syntax = Syntax(export_output, "bash", theme="monokai", line_numbers=True)
    console.print(syntax)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def demo_templates():
    """Demonstrate environment templates"""
    console.print(Panel.fit(
        "[bold cyan]Environment Templates[/bold cyan]",
        border_style="cyan"
    ))
    
    temp_dir = Path(tempfile.mkdtemp())
    manager = EnvManager(cortex_home=temp_dir)
    
    # List templates
    console.print("\n[bold]Available templates...[/bold]")
    templates = manager.list_templates()
    for template in templates:
        console.print(f"  [green]{template.name}[/green]: {template.description}")
    
    # Apply Django template
    console.print("\n[bold]Applying Django template...[/bold]")
    manager.apply_template(
        "webapp",
        "django",
        variables={
            "SECRET_KEY": "django-secret-key-xyz",
            "DATABASE_URL": "postgres://localhost/webapp"
        }
    )
    console.print("✓ Template applied")
    
    # Show resulting variables
    console.print("\n[bold]Resulting environment...[/bold]")
    env_vars = manager.list("webapp")
    for key, var in sorted(env_vars.items()):
        console.print(f"  {key}: {var.value}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def demo_import_export():
    """Demonstrate import/export functionality"""
    console.print(Panel.fit(
        "[bold cyan]Import/Export[/bold cyan]",
        border_style="cyan"
    ))
    
    temp_dir = Path(tempfile.mkdtemp())
    manager = EnvManager(cortex_home=temp_dir)
    
    # Set up some variables
    console.print("\n[bold]Setting up environment...[/bold]")
    manager.set("app1", "VAR1", "value1")
    manager.set("app1", "VAR2", "value2")
    manager.set("app1", "SECRET", "secret123", encrypt=True)
    console.print("✓ Variables created")
    
    # Export to JSON
    console.print("\n[bold]Exporting to JSON...[/bold]")
    json_output = manager.export("app1", format="json")
    syntax = Syntax(json_output, "json", theme="monokai", line_numbers=True)
    console.print(syntax)
    
    # Import from string
    console.print("\n[bold]Importing new variables...[/bold]")
    env_data = """
export NEW_VAR="imported_value"
export ANOTHER="test"
"""
    manager.import_env("app2", env_data, format="env")
    console.print("✓ Variables imported to app2")
    
    # Show imported
    env_vars = manager.list("app2")
    for key, var in env_vars.items():
        console.print(f"  {key}: {var.value}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def demo_validation():
    """Demonstrate validation rules"""
    console.print(Panel.fit(
        "[bold cyan]Variable Validation[/bold cyan]",
        border_style="cyan"
    ))
    
    temp_dir = Path(tempfile.mkdtemp())
    manager = EnvManager(cortex_home=temp_dir)
    
    # Valid URL
    console.print("\n[bold]Testing URL validation...[/bold]")
    try:
        manager.set("app", "DATABASE_URL", "postgres://localhost/db")
        console.print("✓ Valid URL accepted")
    except ValueError as e:
        console.print(f"✗ {e}")
    
    # Invalid URL
    try:
        manager.set("app", "API_URL", "not-a-url")
        console.print("✓ Invalid URL accepted (unexpected!)")
    except ValueError as e:
        console.print(f"✓ Invalid URL rejected: [dim]{e}[/dim]")
    
    # Valid port
    console.print("\n[bold]Testing port validation...[/bold]")
    try:
        manager.set("app", "PORT", "3000")
        console.print("✓ Valid port accepted")
    except ValueError as e:
        console.print(f"✗ {e}")
    
    # Invalid port
    try:
        manager.set("app", "PORT", "70000")
        console.print("✓ Invalid port accepted (unexpected!)")
    except ValueError as e:
        console.print(f"✓ Invalid port rejected: [dim]{e}[/dim]")
    
    # Empty API key
    console.print("\n[bold]Testing required field validation...[/bold]")
    try:
        manager.set("app", "API_KEY", "")
        console.print("✓ Empty API key accepted (unexpected!)")
    except ValueError as e:
        console.print(f"✓ Empty value rejected: [dim]{e}[/dim]")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def demo_encryption():
    """Demonstrate encryption features"""
    console.print(Panel.fit(
        "[bold cyan]Encryption[/bold cyan]",
        border_style="cyan"
    ))
    
    temp_dir = Path(tempfile.mkdtemp())
    manager = EnvManager(cortex_home=temp_dir)
    
    # Set encrypted variable
    console.print("\n[bold]Setting encrypted variable...[/bold]")
    original_value = "super-secret-api-key-12345"
    manager.set("app", "API_KEY", original_value, encrypt=True)
    console.print(f"✓ Stored encrypted: {original_value}")
    
    # Get encrypted (raw)
    console.print("\n[bold]Encrypted value (base64)...[/bold]")
    encrypted = manager.get("app", "API_KEY", decrypt=False)
    console.print(f"  [dim]{encrypted[:50]}...[/dim]")
    
    # Get decrypted
    console.print("\n[bold]Decrypted value...[/bold]")
    decrypted = manager.get("app", "API_KEY", decrypt=True)
    console.print(f"  {decrypted}")
    
    # Verify match
    if decrypted == original_value:
        console.print("✓ [green]Decryption successful![/green]")
    else:
        console.print("✗ [red]Decryption failed![/red]")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def main():
    """Run all demos"""
    console.print("\n[bold yellow]Cortex Environment Manager Demo[/bold yellow]\n")
    
    demo_basic_operations()
    console.print("\n" + "─" * 80 + "\n")
    
    demo_templates()
    console.print("\n" + "─" * 80 + "\n")
    
    demo_import_export()
    console.print("\n" + "─" * 80 + "\n")
    
    demo_validation()
    console.print("\n" + "─" * 80 + "\n")
    
    demo_encryption()
    
    console.print("\n[bold green]Demo complete![/bold green]")
    console.print("\n[dim]Run 'cortex env --help' for CLI usage[/dim]\n")


if __name__ == "__main__":
    main()

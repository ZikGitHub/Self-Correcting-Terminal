from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def print_banner():
    console.print(Panel.fit(
        "[bold cyan]Self-Correcting Terminal Agent[/bold cyan]\n"
        "[dim]Autonomous | Environment Aware | Self-Healing[/dim]",
        border_style="cyan"
    ))

def print_step(message: str, style: str = "yellow"):
    console.print(f"[{style}]▶[/] {message}")

def print_success(message: str):
    console.print(f"[bold green]✔[/][green] {message}[/]")

def print_error(message: str):
    console.print(f"[bold red]✘[/][red] {message}[/]")

def print_command(cmd: str):
    console.print(Panel(f"[bold white]$ {cmd}[/]", border_style="dim"))

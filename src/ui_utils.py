from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich.box import DOUBLE_EDGE

console = Console()

def print_banner():
    banner = Text(
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║           SELF-CORRECTING TERMINAL AGENT v1.0              ║\n"
        "╚══════════════════════════════════════════════════════════════╝",
        style="bold green"
    )
    console.print(Panel(banner, border_style="green", box=DOUBLE_EDGE, expand=False))

def print_step(message: str, style: str = "bold cyan"):
    console.print(f"[bold white]>[/] [{style}]{message}[/]")

def print_success(message: str):
    console.print(f"[bold green]✔[/] [green]{message}[/]")

def print_error(message: str):
    console.print(Panel(f"[bold red]ERROR:[/] {message}", border_style="red", title="[bold red]FAILURE[/]"))

def print_command(cmd: str):
    console.print(Panel(f"[bold green]$ {cmd}[/]", border_style="bright_black", padding=(0, 2)))

def print_debug(message: str):
    console.print(f"[dim grey][DEBUG] {message}[/]")

def print_info(message: str):
    console.print(f"[bold blue]ℹ[/] [blue]{message}[/]")


import typer
from src.agent import TerminalAgent

app = typer.Typer()

@app.command()
def run(
    task: str = typer.Argument(..., help="The task you want the terminal agent to perform."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs and full environment context.")
):
    """
    Run an autonomous terminal task with self-correction.
    """
    agent = TerminalAgent()
    agent.run(task, verbose=verbose)

if __name__ == "__main__":
    app()

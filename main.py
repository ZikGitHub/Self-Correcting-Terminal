import typer
from src.agent import TerminalAgent

app = typer.Typer()

@app.command()
def run(task: str = typer.Argument(..., help="The task you want the terminal agent to perform.")):
    """
    Run an autonomous terminal task with self-correction.
    """
    agent = TerminalAgent()
    agent.run(task)

if __name__ == "__main__":
    app()

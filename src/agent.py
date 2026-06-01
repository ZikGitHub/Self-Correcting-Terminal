import os
from dotenv import load_dotenv
from src.core.env_sniffer import EnvSniffer
from src.core.executor import CommandExecutor
from src.core.planner import Planner
import src.ui_utils as ui

load_dotenv()

class TerminalAgent:
    def __init__(self):
        self.sniffer = EnvSniffer()
        self.executor = CommandExecutor()
        self.planner = Planner()
        self.history = []

    def run_generator(self, task: str, cwd: str = None):
        if cwd:
            self.executor.cwd = cwd
        yield {"type": "status", "message": f"Sniffing environment in {cwd or 'root'}..."}
        sys_context = self.sniffer.get_summary_prompt()
        yield {"type": "success", "message": "Environment detected."}
        
        yield {"type": "status", "message": f"Planning task: {task}"}
        plan = self.planner.generate_plan(task, sys_context)
        commands = plan.get("commands", [])
        
        yield {"type": "info", "message": f"Strategy: {plan.get('explanation')}"}
        
        i = 0
        while i < len(commands):
            cmd = commands[i]
            yield {"type": "command", "message": cmd}
            
            result = self.executor.execute(cmd)
            
            if result.success:
                yield {"type": "success", "message": f"Completed in {result.duration:.2f}s"}
                if result.stdout.strip():
                    yield {"type": "output", "message": result.stdout.strip()}
                i += 1
            else:
                yield {"type": "error", "message": f"Command failed (Exit code: {result.exit_code})"}
                yield {"type": "error_details", "message": result.stderr.strip()}
                
                yield {"type": "status", "message": "Consulting the brain for a fix..."}
                fix_plan = self.planner.suggest_fix(task, cmd, result.stderr, sys_context)
                fix_commands = fix_plan.get("commands", [])
                
                yield {"type": "info", "message": f"Adjustment: {fix_plan.get('explanation')}"}
                
                commands[i:i+1] = fix_commands + [cmd]
        
        yield {"type": "done", "message": "Task completed successfully!"}

    def run(self, task: str):
        """Legacy run method for CLI compatibility."""
        ui.print_banner()
        for event in self.run_generator(task):
            etype = event["type"]
            msg = event["message"]
            if etype == "status": ui.print_step(msg)
            elif etype == "success": ui.print_success(msg)
            elif etype == "command": ui.print_command(msg)
            elif etype == "error": ui.print_error(msg)
            elif etype == "output": ui.console.print(f"[dim]{msg}[/]")
            elif etype == "info": ui.print_step(msg, style="cyan")
            elif etype == "error_details": ui.console.print(f"[red]{msg}[/]")

if __name__ == "__main__":
    # Example usage
    agent = TerminalAgent()
    # agent.run("Create a new folder named 'test_project' and initialize a git repo inside it")

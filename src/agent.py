import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from src.core.env_sniffer import EnvSniffer
from src.core.executor import CommandExecutor
from src.core.planner import Planner
from src.core.safety import SafetyGuard
import src.ui_utils as ui

load_dotenv()

class TerminalAgent:
    def __init__(self):
        self.sniffer = EnvSniffer()
        self.executor = CommandExecutor()
        self.planner = Planner()
        self.history_file = ".agent_history.json"
        self.history = self.load_history()
        self.waiting_for_confirmation = False
        self.confirmation_response = None

    def load_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.history_file):
            try:
                import json
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_history(self):
        try:
            import json
            with open(self.history_file, "w") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def respond(self, text: str):
        """Sends input to the currently running command or safety prompt."""
        if self.waiting_for_confirmation:
            self.confirmation_response = text
        else:
            self.executor.send_input(text)

    def run_generator(self, task: str, cwd: str = None, max_retries: int = 3, verbose: bool = False):
        if cwd:
            self.executor.cwd = cwd
        
        if verbose: yield {"type": "debug", "message": f"Initializing in {os.getcwd()}"}
        
        # 1. Heuristic Scope Check
        is_safe, reason = SafetyGuard.is_within_scope(task)
        if not is_safe:
            yield {"type": "error", "message": f"Task blocked: {reason}"}
            return

        yield {"type": "status", "message": f"Sniffing environment..."}
        sys_context = self.sniffer.get_summary_prompt()
        if verbose: yield {"type": "debug", "message": sys_context}
        yield {"type": "success", "message": "Environment detected."}
        
        yield {"type": "status", "message": f"Planning task: {task}"}
        plan = self.planner.generate_plan(task, sys_context, history=self.history)
        
        # 2. LLM Scope Check
        if plan.get("out_of_scope"):
            yield {"type": "error", "message": f"Task refused by Planner: {plan.get('refusal_reason')}"}
            return

        commands = plan.get("commands", [])
        yield {"type": "info", "message": f"Strategy: {plan.get('explanation')}"}
        
        import queue
        import threading

        i = 0
        retry_counts = {} # Track retries per command string
        while i < len(commands):
            cmd = commands[i]
            
            # 3. Command Safety Check
            if SafetyGuard.is_strictly_forbidden(cmd):
                yield {"type": "error", "message": f"Command hard-blocked by SafetyGuard: {cmd}"}
                break
            
            if SafetyGuard.requires_confirmation(cmd):
                yield {"type": "confirmation", "message": f"Potentially destructive command: {cmd}\nDo you want to proceed? (y/n)"}
                self.waiting_for_confirmation = True
                self.confirmation_response = None
                
                # Wait for user response via 'respond' method
                while self.confirmation_response is None:
                    import time
                    time.sleep(0.5)
                
                response = self.confirmation_response.lower().strip()
                self.waiting_for_confirmation = False
                self.confirmation_response = None
                
                if response != 'y':
                    yield {"type": "info", "message": "Command cancelled by user."}
                    break

            yield {"type": "command", "message": cmd}
            
            output_q = queue.Queue()
            def on_output(line, stream):
                if any(p in line for p in ["[y/n]", "(y/n)", "[Y/n]", "[y/N]"]):
                    output_q.put({"type": "prompt", "message": line.strip()})
                elif line.strip():
                    output_q.put({"type": "output", "message": line.strip()})

            def run_exec():
                res = self.executor.execute(cmd, on_output=on_output)
                output_q.put({"type": "result", "result": res})

            exec_thread = threading.Thread(target=run_exec)
            exec_thread.start()

            result = None
            while True:
                try:
                    event = output_q.get(timeout=0.1)
                    if event["type"] == "result":
                        result = event["result"]
                        break
                    yield event
                except queue.Empty:
                    if not exec_thread.is_alive():
                        # Check one last time for anything left in the queue
                        while not output_q.empty():
                            event = output_q.get()
                            if event["type"] == "result":
                                result = event["result"]
                                break
                            yield event
                        break
            
            # Update history
            self.history.append({
                "command": cmd,
                "output": result.stdout + result.stderr,
                "success": result.success
            })

            if result.success:
                yield {"type": "success", "message": f"Completed in {result.duration:.2f}s"}
                i += 1
            else:
                yield {"type": "error", "message": f"Command failed (Exit code: {result.exit_code})"}
                if verbose: yield {"type": "debug", "message": f"Full STDERR: {result.stderr}"}
                yield {"type": "error_details", "message": result.stderr.strip()}
                
                # Check retry limit
                retry_counts[cmd] = retry_counts.get(cmd, 0) + 1
                if retry_counts[cmd] > max_retries:
                    yield {"type": "error", "message": f"Max retries reached for command: {cmd}"}
                    break

                yield {"type": "status", "message": "Consulting the brain for a fix..."}
                fix_plan = self.planner.suggest_fix(task, cmd, result.stderr, sys_context, history=self.history)
                fix_commands = fix_plan.get("commands", [])
                
                yield {"type": "info", "message": f"Adjustment: {fix_plan.get('explanation')}"}
                
                commands[i:i+1] = fix_commands + [cmd]
        
        self.save_history()
        yield {"type": "done", "message": "Task completed successfully!"}

    def run(self, task: str, verbose: bool = False):
        """Legacy run method for CLI compatibility."""
        ui.print_banner()
        for event in self.run_generator(task, verbose=verbose):
            etype = event["type"]
            msg = event["message"]
            if etype == "status": ui.print_step(msg)
            elif etype == "success": ui.print_success(msg)
            elif etype == "command": ui.print_command(msg)
            elif etype == "error": ui.print_error(msg)
            elif etype == "output": ui.console.print(f"[dim]{msg}[/]")
            elif etype == "info": ui.print_info(msg)
            elif etype == "error_details": ui.console.print(f"[red]{msg}[/]")
            elif etype == "debug": ui.print_debug(msg)
            elif etype == "prompt":
                response = ui.console.input(f"[bold yellow]{msg} [/]")
                self.respond(response)
            elif etype == "confirmation":
                response = ui.console.input(f"[bold red]{msg} [/]")
                self.respond(response)

if __name__ == "__main__":
    # Example usage
    agent = TerminalAgent()
    # agent.run("Create a new folder named 'test_project' and initialize a git repo inside it")

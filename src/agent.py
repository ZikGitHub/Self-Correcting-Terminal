import os
import queue
import threading
import time
import re
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
            self.executor.cwd = os.path.abspath(cwd)
        
        effective_cwd = self.executor.cwd
        if verbose: yield {"type": "debug", "message": f"Initializing in {effective_cwd}"}
        
        # 1. Heuristic Scope Check
        is_safe, reason = SafetyGuard.is_within_scope(task)
        if not is_safe:
            yield {"type": "error", "message": f"Task blocked: {reason}"}
            return

        yield {"type": "status", "message": f"Sniffing environment in {effective_cwd}..."}
        sys_context = self.sniffer.get_summary_prompt(cwd=effective_cwd)
        if verbose: yield {"type": "debug", "message": sys_context}
        yield {"type": "success", "message": "Environment detected."}
        
        yield {"type": "status", "message": f"Planning task: {task}"}
        
        # AGGRESSIVE STREAMING: We use a queue to decouple planning from execution
        command_q = queue.Queue()
        planning_done = threading.Event()
        
        def plan_producer():
            try:
                for event in self.planner.stream_plan(task, sys_context, history=self.history):
                    command_q.put(event)
            finally:
                planning_done.set()

        plan_thread = threading.Thread(target=plan_producer)
        plan_thread.start()

        retry_counts = {}
        
        while not planning_done.is_set() or not command_q.empty():
            try:
                event = command_q.get(timeout=0.1)
                etype = event["type"]
                
                if etype == "info":
                    yield event
                    continue
                
                if etype == "command":
                    cmd = event["message"]
                    
                    # 3. Command Safety Check
                    if SafetyGuard.is_strictly_forbidden(cmd):
                        yield {"type": "error", "message": f"Command hard-blocked: {cmd}"}
                        break
                    
                    if SafetyGuard.requires_confirmation(cmd):
                        yield {"type": "confirmation", "message": f"Potentially destructive command: {cmd}\nDo you want to proceed? (y/n)"}
                        self.waiting_for_confirmation = True
                        self.confirmation_response = None
                        while self.confirmation_response is None:
                            time.sleep(0.1)
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
                            exec_event = output_q.get(timeout=0.05)
                            if exec_event["type"] == "result":
                                result = exec_event["result"]
                                break
                            yield exec_event
                        except queue.Empty:
                            if not exec_thread.is_alive():
                                break
                    
                    # Update history
                    self.history.append({
                        "command": cmd,
                        "output": result.stdout + result.stderr,
                        "success": result.success
                    })

                    if result.success:
                        yield {"type": "success", "message": f"Completed in {result.duration:.2f}s"}
                    else:
                        yield {"type": "error", "message": f"Command failed (Exit code: {result.exit_code})"}
                        if verbose: yield {"type": "debug", "message": f"Full STDERR: {result.stderr}"}
                        yield {"type": "error_details", "message": result.stderr.strip()}
                        
                        retry_counts[cmd] = retry_counts.get(cmd, 0) + 1
                        if retry_counts[cmd] > max_retries:
                            yield {"type": "error", "message": f"Max retries reached for: {cmd}"}
                            break

                        yield {"type": "status", "message": "Consulting brain for fix..."}
                        # For fixes, we still use the synchronous suggest_fix for now
                        fix_plan = self.planner.suggest_fix(task, cmd, result.stderr, sys_context, history=self.history)
                        for fix_cmd in fix_plan.get("commands", []):
                            command_q.put({"type": "command", "message": fix_cmd})
                        command_q.put({"type": "command", "message": cmd}) # Retry the original command
                
            except queue.Empty:
                continue
        
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

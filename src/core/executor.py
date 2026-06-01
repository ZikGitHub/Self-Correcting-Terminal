import subprocess
import os
import time
from typing import Dict, Any, Optional

class CommandResult:
    def __init__(self, command: str, stdout: str, stderr: str, exit_code: int, duration: float):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration = duration
        self.success = exit_code == 0

    def __repr__(self):
        return f"<CommandResult success={self.success} exit_code={self.exit_code}>"

class CommandExecutor:
    """
    Executes terminal commands and captures output.
    Maintains the state of the current working directory.
    """

    def __init__(self, cwd: Optional[str] = None):
        self.cwd = cwd or os.getcwd()

    def execute(self, command: str, timeout: int = 300) -> CommandResult:
        """
        Executes a command and returns the result.
        Handles 'cd' commands specially to maintain state.
        """
        start_time = time.time()
        
        # Handle 'cd' commands manually to maintain internal CWD state
        if command.strip().startswith("cd "):
            target_dir = command.strip()[3:].strip().strip('"').strip("'")
            new_path = os.path.normpath(os.path.join(self.cwd, target_dir))
            
            if os.path.exists(new_path) and os.path.isdir(new_path):
                self.cwd = new_path
                return CommandResult(command, f"Changed directory to {self.cwd}", "", 0, time.time() - start_time)
            else:
                return CommandResult(command, "", f"Directory not found: {new_path}", 1, time.time() - start_time)

        try:
            # Use shell=True to support shell built-ins and piping
            # In Windows, this uses cmd.exe or powershell depending on configuration
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            stderr += f"\n[Error] Command timed out after {timeout} seconds."
        except Exception as e:
            stdout, stderr = "", str(e)
            exit_code = 1

        duration = time.time() - start_time
        return CommandResult(command, stdout, stderr, exit_code, duration)

if __name__ == "__main__":
    executor = CommandExecutor()
    res = executor.execute("dir")
    print(f"STDOUT: {res.stdout[:100]}...")
    print(f"SUCCESS: {res.success}")

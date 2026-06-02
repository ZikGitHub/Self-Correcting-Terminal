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

    def _get_env_with_venv(self) -> Dict[str, str]:
        """
        Returns a copy of os.environ with the local venv bin/Scripts prepended to PATH if it exists.
        """
        env = os.environ.copy()
        venv_names = ["venv", ".venv", "env"]
        
        for name in venv_names:
            venv_path = os.path.join(self.cwd, name)
            if os.path.isdir(venv_path):
                if os.name == "nt":
                    scripts_path = os.path.join(venv_path, "Scripts")
                else:
                    scripts_path = os.path.join(venv_path, "bin")
                
                if os.path.isdir(scripts_path):
                    # Prepend venv scripts to PATH
                    path_key = "PATH" if "PATH" in env else "Path"
                    env[path_key] = scripts_path + os.pathsep + env.get(path_key, "")
                    # Also set VIRTUAL_ENV
                    env["VIRTUAL_ENV"] = venv_path
                    return env
        return env

    def execute(self, command: str, timeout: int = 300, on_output: Optional[callable] = None) -> CommandResult:
        """
        Executes a command and returns the result.
        Robustly tracks CWD by appending a hidden marker command.
        Optional on_output callback: on_output(line, stream_name)
        """
        start_time = time.time()
        
        marker = "___CWD_MARKER___"
        if os.name == "nt":
            # Use delayed expansion (!VAR!) to get values after command execution.
            # We wrap the command in parentheses to ensure & applies to the whole thing.
            full_command = f'cmd /v:on /c "({command}) & set EXIT_ERR=!errorlevel! & echo {marker}!cd! & exit /b !EXIT_ERR!"'
        else:
            full_command = f"{command}; EXIT_ERR=$?; echo {marker}$(pwd); exit $EXIT_ERR"

        try:
            self.process = subprocess.Popen(
                full_command,
                shell=True,
                cwd=self.cwd,
                env=self._get_env_with_venv(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=0, # Unbuffered for char-by-char
                universal_newlines=True
            )

            stdout_capture = []
            stderr_capture = []
            new_cwd = [self.cwd] # Use a list to be mutable in thread

            def read_stream(stream, capture_list, stream_name):
                buffer = ""
                while True:
                    char = stream.read(1)
                    if not char:
                        break
                    
                    buffer += char
                    capture_list.append(char)
                    
                    # Call on_output if we have a newline or a likely prompt
                    if char == '\n' or any(p in buffer for p in ["[y/n]", "(y/n)", "[Y/n]", "[y/N]", "? "]):
                        if marker in buffer:
                            parts = buffer.split(marker)
                            if parts[0].strip():
                                capture_list.append(parts[0])
                                if on_output: on_output(parts[0], stream_name)
                            if len(parts) > 1:
                                new_cwd[0] = parts[1].strip()
                        else:
                            if on_output:
                                on_output(buffer, stream_name)
                        buffer = ""
                
                if buffer and on_output:
                    on_output(buffer, stream_name)
                stream.close()

            import threading
            stdout_thread = threading.Thread(target=read_stream, args=(self.process.stdout, stdout_capture, "stdout"))
            stderr_thread = threading.Thread(target=read_stream, args=(self.process.stderr, stderr_capture, "stderr"))

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to finish or timeout
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                stderr_capture.append(f"\n[Error] Command timed out after {timeout} seconds.")
            
            stdout_thread.join()
            stderr_thread.join()
            
            self.cwd = new_cwd[0]
            stdout = "".join(stdout_capture)
            stderr = "".join(stderr_capture)
            exit_code = self.process.returncode
            
        except Exception as e:
            stdout, stderr = "", str(e)
            exit_code = 1

        duration = time.time() - start_time
        return CommandResult(command, stdout, stderr, exit_code, duration)

    def send_input(self, text: str):
        """Sends input to the currently running process."""
        if hasattr(self, 'process') and self.process.poll() is None:
            if not text.endswith('\n'):
                text += '\n'
            self.process.stdin.write(text)
            self.process.stdin.flush()

if __name__ == "__main__":
    executor = CommandExecutor()
    res = executor.execute("dir")
    print(f"STDOUT: {res.stdout[:100]}...")
    print(f"SUCCESS: {res.success}")

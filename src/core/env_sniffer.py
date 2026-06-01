import platform
import sys
import os
import shutil
import subprocess
from typing import Dict, List, Any

class EnvSniffer:
    """
    Sniffs the current environment to provide context to the LLM agent.
    Detects OS, Shell, Python version, and installed tools.
    """

    def __init__(self):
        self.context = {}

    def sniff_all(self) -> Dict[str, Any]:
        """Runs all sniffing methods and returns the combined context."""
        self.context.update(self._sniff_os())
        self.context.update(self._sniff_python())
        self.context.update(self._sniff_shell())
        self.context.update(self._sniff_tools())
        return self.context

    def _sniff_os(self) -> Dict[str, str]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor()
        }

    def _sniff_python(self) -> Dict[str, Any]:
        return {
            "python_version": sys.version.split()[0],
            "is_venv": sys.prefix != sys.base_prefix,
            "venv_path": sys.prefix if sys.prefix != sys.base_prefix else None
        }

    def _sniff_shell(self) -> Dict[str, str]:
        shell = os.environ.get("SHELL") or os.environ.get("COMSPEC", "unknown")
        return {
            "shell": shell,
            "cwd": os.getcwd()
        }

    def _sniff_tools(self) -> Dict[str, List[str]]:
        """Checks for common development tools."""
        tools_to_check = ["git", "docker", "npm", "node", "pip", "uv", "poetry", "make"]
        installed_tools = []
        
        for tool in tools_to_check:
            if shutil.who(tool):
                installed_tools.append(tool)
        
        return {"installed_tools": installed_tools}

    def get_summary_prompt(self) -> str:
        """Returns a string formatted for an LLM system prompt."""
        ctx = self.sniff_all()
        summary = (
            f"SYSTEM CONTEXT:\n"
            f"- OS: {ctx['os']} ({ctx['os_release']})\n"
            f"- Shell: {ctx['shell']}\n"
            f"- Python: {ctx['python_version']} (Venv: {ctx['is_venv']})\n"
            f"- Current Directory: {ctx['cwd']}\n"
            f"- Installed Tools: {', '.join(ctx['installed_tools'])}\n"
        )
        return summary

if __name__ == "__main__":
    sniffer = EnvSniffer()
    print(sniffer.get_summary_prompt())

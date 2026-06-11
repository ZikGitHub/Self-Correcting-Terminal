import json
import os
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

try:
    from src.core.rag_service import PowerShellRagService
except ImportError:
    PowerShellRagService = None

class CommandPlan(BaseModel):
    """Plan for executing terminal commands."""
    commands: List[str] = Field(description="A list of shell commands to execute in sequence.")
    explanation: str = Field(description="Brief explanation of the strategy.")
    out_of_scope: bool = Field(default=False, description="Whether the task is outside the agent's boundaries.")
    refusal_reason: Optional[str] = Field(default=None, description="Reason for refusing the task if out of scope.")

class Planner:
    """
    LLM-powered planner that breaks tasks into commands and handles error correction.
    """

    def __init__(self):
        # Load configuration from environment
        self.model_type = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.model_name = os.getenv("PLANNER_MODEL", "qwen2.5-coder:7b")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

        # Automatic Host Discovery: If we're in Docker and using 127.0.0.1, it's likely wrong.
        if self.ollama_host in ["http://127.0.0.1:11434", "http://localhost:11434"]:
            if os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER'):
                print("[*] Docker detected. Switching OLLAMA_HOST to host.docker.internal")
                self.ollama_host = "http://host.docker.internal:11434"

        if self.model_type == "ollama":
            self.llm = ChatOllama(model=self.model_name, base_url=self.ollama_host)
        else:
            self.llm = ChatGoogleGenerativeAI(model=self.model_name)
            
        # Wrap the LLM with structured output
        self.structured_llm = self.llm.with_structured_output(CommandPlan)
        
        # Initialize RAG Service if database exists and dependencies are installed
        self.rag = None
        if PowerShellRagService and os.path.exists("./rag_data/chroma_db"):
            self.rag = PowerShellRagService()

    def stream_plan(self, task: str, sys_context: str, history: List[Dict[str, Any]] = None):
        """
        Streams the LLM response and yields partial CommandPlan objects.
        Now more robust and includes fallback to full generation.
        """
        history_str = ""
        if history:
            recent_history = history[-5:]
            history_str = "RECENT HISTORY:\n" + "\n".join([
                f"- Command: {h['command']}\n  Success: {h['success']}\n  Output: {h['output'][:200]}"
                for h in recent_history
            ])

        rag_context = ""
        if self.rag:
            rag_context = "\nPOWERSHELL REFERENCE CONTEXT:\n" + self.rag.search(task)

        prompt_text = (
            "You are an expert terminal agent. Your goal is to provide ONLY valid shell commands within your EXPERTISE SCOPE.\n"
            f"{sys_context}\n"
            f"{history_str}\n"
            f"{rag_context}\n"
            f"TASK: {task}\n"
            "\n"
            "EXPERTISE SCOPE:\n"
            "- Local file management (create, read, update, delete in project directories).\n"
            "- Developer tools (git, npm, pip, docker, uv, etc.).\n"
            "- Build, test, and deployment scripts.\n"
            "\n"
            "PROHIBITED AREAS (Set 'out_of_scope' to true):\n"
            "- Global OS configuration (registry, system settings, user management).\n"
            "- Network configuration (firewall, DNS, global proxy settings).\n"
            "- Sensitive data manipulation (passwords, encryption keys).\n"
            "- Destructive global actions (formatting drives, system shutdown).\n"
            "\n"
            "GUIDELINES:\n"
            "1. If the task is OUT OF SCOPE, set 'out_of_scope': true and provide a 'refusal_reason'.\n"
            "2. EVERY string in the 'commands' list MUST be a valid, executable shell command.\n"
            "3. Use non-interactive flags for EVERYTHING: 'npm init -y', 'npx -y', 'pip install -y'.\n"
            "4. Ensure commands are compatible with the detected OS and Shell.\n"
            "Return the plan as a structured JSON object with keys: 'commands' (list), 'explanation' (string), 'out_of_scope' (bool), and 'refusal_reason' (string or null)."
        )

        full_text = ""
        yielded_commands = set()
        explanation_yielded = False
        out_of_scope_yielded = False
        
        try:
            print(f"[*] Planning with {self.model_type} ({self.model_name}) at {self.ollama_host}...")
            for chunk in self.llm.stream(prompt_text):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_text += content
                
                # Robustly find explanation
                if not explanation_yielded:
                    expl_match = re.search(r'"explanation":\s*"(.*?)"', full_text)
                    if expl_match:
                        explanation_yielded = True
                        yield {"type": "info", "message": f"Strategy: {expl_match.group(1)}"}

                # Robustly find out_of_scope
                if not out_of_scope_yielded:
                    scope_match = re.search(r'"out_of_scope":\s*(true|false)', full_text)
                    if scope_match:
                        is_out = scope_match.group(1) == "true"
                        out_of_scope_yielded = True
                        if is_out:
                            # Try to find refusal reason
                            refusal_match = re.search(r'"refusal_reason":\s*"(.*?)"', full_text)
                            reason = refusal_match.group(1) if refusal_match else "Task is out of scope."
                            yield {"type": "error", "message": f"Out of Scope: {reason}"}
                            return

                # Aggressive command streaming
                # Look for the commands array start
                cmds_start = full_text.find('"commands":')
                if cmds_start != -1:
                    cmds_section = full_text[cmds_start:]
                    # Find all double-quoted strings that look like they are in a list
                    found_cmds = re.findall(r'"((?:[^"\\]|\\.)*)"', cmds_section)
                    for cmd in found_cmds:
                        # Filter out the key "commands" itself and other keys
                        if cmd in ["commands", "explanation", "out_of_scope", "refusal_reason", "true", "false"]:
                            continue
                        if cmd not in yielded_commands:
                            # Ensure it's not the explanation we already yielded
                            if explanation_yielded and cmd in full_text[full_text.find('"explanation"'):full_text.find('"', full_text.find('"explanation"')+15)]:
                                continue
                            yielded_commands.add(cmd)
                            yield {"type": "command", "message": cmd}
        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "111" in error_msg:
                yield {"type": "error", "message": f"Connection Refused: Could not reach Ollama at {self.ollama_host}. Is it running?"}
                if "127.0.0.1" in self.ollama_host or "localhost" in self.ollama_host:
                    yield {"type": "info", "message": "HINT: If running in Docker, use OLLAMA_HOST=http://host.docker.internal:11434"}
            else:
                yield {"type": "error", "message": f"Planning failed: {error_msg}"}
            return

        # Final Fallback: Attempt to parse the whole thing as JSON if no commands were yielded
        if not yielded_commands:
            try:
                # Find JSON boundaries
                start = full_text.find('{')
                end = full_text.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = full_text[start:end]
                    data = json.loads(json_str)
                    if data.get("out_of_scope"):
                        yield {"type": "error", "message": f"Out of Scope: {data.get('refusal_reason')}"}
                    elif data.get("commands"):
                        for cmd in data["commands"]:
                            if cmd not in yielded_commands:
                                yielded_commands.add(cmd)
                                yield {"type": "command", "message": cmd}
            except:
                pass

    def generate_plan(self, task: str, sys_context: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generates a sequence of commands to achieve a goal."""
        history_str = ""
        if history:
            recent_history = history[-5:]
            history_str = "RECENT HISTORY:\n" + "\n".join([
                f"- Command: {h['command']}\n  Success: {h['success']}\n  Output: {h['output'][:200]}"
                for h in recent_history
            ])

        rag_context = ""
        if self.rag:
            rag_context = "\nPOWERSHELL REFERENCE CONTEXT:\n" + self.rag.search(task)

        prompt = ChatPromptTemplate.from_template(
            "You are an expert terminal agent. Your goal is to provide ONLY valid shell commands within your EXPERTISE SCOPE.\n"
            "{sys_context}\n"
            "{history_str}\n"
            "{rag_context}\n"
            "TASK: {task}\n"
            "\n"
            "EXPERTISE SCOPE:\n"
            "- Local file management (create, read, update, delete in project directories).\n"
            "- Developer tools (git, npm, pip, docker, uv, etc.).\n"
            "- Build, test, and deployment scripts.\n"
            "\n"
            "PROHIBITED AREAS (Set 'out_of_scope' to true):\n"
            "- Global OS configuration (registry, system settings, user management).\n"
            "- Network configuration (firewall, DNS, global proxy settings).\n"
            "- Sensitive data manipulation (passwords, encryption keys).\n"
            "- Destructive global actions (formatting drives, system shutdown).\n"
            "\n"
            "GUIDELINES:\n"
            "1. If the task is OUT OF SCOPE, set 'out_of_scope': true and provide a 'refusal_reason'.\n"
            "2. EVERY string in the 'commands' list MUST be a valid, executable shell command.\n"
            "3. Use non-interactive flags for EVERYTHING: 'npm init -y', 'npx -y', 'pip install -y'.\n"
            "4. Ensure commands are compatible with the detected OS and Shell.\n"
            "Return the plan as a structured JSON object."
        )
        
        res = self.structured_llm.invoke(prompt.format(
            task=task, 
            sys_context=sys_context,
            history_str=history_str,
            rag_context=rag_context
        ))
        return res.dict() if hasattr(res, 'dict') else res.model_dump()

    def suggest_fix(self, task: str, failed_command: str, error: str, sys_context: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyzes an error and suggests a fix (new commands)."""
        history_str = ""
        if history:
            recent_history = history[-5:]
            history_str = "RECENT HISTORY:\n" + "\n".join([
                f"- Command: {h['command']}\n  Success: {h['success']}\n  Output: {h['output'][:200]}"
                for h in recent_history
            ])

        rag_context = ""
        if self.rag:
            # Search RAG using both the task and the error message
            rag_context = "\nPOWERSHELL REFERENCE CONTEXT:\n" + self.rag.search(f"{failed_command} {error}")

        prompt = ChatPromptTemplate.from_template(
            "You are an expert terminal debugger. Your goal is to fix the FAILED COMMAND.\n"
            "{sys_context}\n"
            "{history_str}\n"
            "{rag_context}\n"
            "ORIGINAL TASK: {task}\n"
            "FAILED COMMAND: {failed_command}\n"
            "ERROR OUTPUT:\n{error}\n"
            "Analyze the error and provide a set of VALID shell commands to fix the issue and proceed.\n"
            "CRITICAL: NO natural language in the 'commands' list. Use only non-interactive flags (e.g., 'npx -y').\n"
            "Return the fix plan as a structured JSON object."
        )
        
        res = self.structured_llm.invoke(prompt.format(
            task=task, 
            failed_command=failed_command, 
            error=error, 
            sys_context=sys_context,
            history_str=history_str,
            rag_context=rag_context
        ))
        return res.dict() if hasattr(res, 'dict') else res.model_dump()

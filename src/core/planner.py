import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

class CommandPlan(BaseModel):
    """Plan for executing terminal commands."""
    commands: List[str] = Field(description="A list of shell commands to execute in sequence.")
    explanation: str = Field(description="Brief explanation of the strategy.")

class Planner:
    """
    LLM-powered planner that breaks tasks into commands and handles error correction.
    """

    def __init__(self):
        # Load configuration from environment
        self.model_type = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.model_name = os.getenv("PLANNER_MODEL", "qwen2.5-coder:7b")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

        if self.model_type == "ollama":
            self.llm = ChatOllama(model=self.model_name, base_url=self.ollama_host)
        else:
            self.llm = ChatGoogleGenerativeAI(model=self.model_name)
            
        # Wrap the LLM with structured output
        self.structured_llm = self.llm.with_structured_output(CommandPlan)

    def generate_plan(self, task: str, sys_context: str) -> Dict[str, Any]:
        """Generates a sequence of commands to achieve a goal."""
        prompt = ChatPromptTemplate.from_template(
            "You are an expert terminal agent.\n"
            "{sys_context}\n"
            "TASK: {task}\n"
            "Generate a sequential plan of terminal commands to complete this task.\n"
            "GUIDELINES:\n"
            "1. Use non-interactive flags where possible (e.g., 'npm init -y', 'pip install -y').\n"
            "2. Ensure commands are compatible with the detected OS and Shell.\n"
            "3. If multiple steps are needed, list them all in order.\n"
            "Return the plan as a structured JSON object."
        )
        
        res = self.structured_llm.invoke(prompt.format(task=task, sys_context=sys_context))
        return res.dict() if hasattr(res, 'dict') else res.model_dump()

    def suggest_fix(self, task: str, failed_command: str, error: str, sys_context: str) -> Dict[str, Any]:
        """Analyzes an error and suggests a fix (new commands)."""
        prompt = ChatPromptTemplate.from_template(
            "You are an expert terminal debugger.\n"
            "{sys_context}\n"
            "ORIGINAL TASK: {task}\n"
            "FAILED COMMAND: {failed_command}\n"
            "ERROR OUTPUT:\n{error}\n"
            "Analyze the error and provide a set of commands to fix the issue and proceed.\n"
            "Return the fix plan as a structured JSON object."
        )
        
        res = self.structured_llm.invoke(prompt.format(
            task=task, 
            failed_command=failed_command, 
            error=error, 
            sys_context=sys_context
        ))
        return res.dict() if hasattr(res, 'dict') else res.model_dump()

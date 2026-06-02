import re
from typing import List, Tuple

class SafetyGuard:
    """
    Ensures the agent stays within boundaries and doesn't execute dangerous commands.
    """
    
    # Commands that are strictly forbidden (Hard Blacklist)
    BLACKLIST = [
        r"\brm\s+-(rf|rf)\s+/",           # rm -rf /
        r"\bdel\s+/s\s+/q\s+C:",           # del /s /q C:
        r"\bformat\s+[a-zA-Z]:",           # format drive
        r"\bfdisk\b",                      # partition disk
        r"\breg\s+delete\b",               # delete registry keys
        r"\bnet\s+user\b",                 # manage users
        r"\bchmod\s+777\s+/\b",            # dangerous permissions
        r"\bshutdown\b",                   # shutdown/reboot
        r"\breboot\b",
        r"\bkillall\b",                    # kill all processes
        r"\bpasswd\b",                     # changing passwords
        r"\bmkfs\b",                       # making file systems
    ]

    # Commands that require user confirmation (Soft Blacklist)
    DESTRUCTIVE_COMMANDS = [
        r"\brm\b",
        r"\bdel\b",
        r"\brndir\b",
        r"\brmdir\b",
        r"\berase\b",
        r"\bdrop\b",
        r"\breset\b",
        r"\btruncate\b",
    ]

    @classmethod
    def is_strictly_forbidden(cls, command: str) -> bool:
        """Checks if a command is in the hard blacklist."""
        for pattern in cls.BLACKLIST:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    @classmethod
    def requires_confirmation(cls, command: str) -> bool:
        """Checks if a command is potentially destructive and needs confirmation."""
        for pattern in cls.DESTRUCTIVE_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_within_scope(cls, task: str) -> Tuple[bool, str]:
        """
        Brief heuristic check for task scope. 
        Detects obvious prohibited areas before calling the LLM.
        """
        prohibited_keywords = [
            "password", "system settings", "registry", "network config", 
            "hack", "bypass", "format drive", "bios", "firmware"
        ]
        for word in prohibited_keywords:
            if word in task.lower():
                return False, f"Task involves prohibited area: {word}"
        return True, ""

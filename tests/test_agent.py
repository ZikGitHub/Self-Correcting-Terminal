import os
import json
import pytest
from src.agent import TerminalAgent

def test_save_load_history():
    agent = TerminalAgent()
    agent.history_file = ".test_history.json"
    
    # Ensure clean state
    if os.path.exists(agent.history_file):
        os.remove(agent.history_file)
        
    try:
        test_history = [
            {"command": "ls", "output": "file1\nfile2", "success": True}
        ]
        agent.history = test_history
        agent.save_history()
        
        assert os.path.exists(agent.history_file)
        
        # New agent should load it
        new_agent = TerminalAgent()
        new_agent.history_file = ".test_history.json"
        new_agent.history = new_agent.load_history()
        
        assert len(new_agent.history) == 1
        assert new_agent.history[0]["command"] == "ls"
        
    finally:
        if os.path.exists(agent.history_file):
            os.remove(agent.history_file)

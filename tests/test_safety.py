import pytest
from src.core.safety import SafetyGuard

def test_blacklist():
    assert SafetyGuard.is_strictly_forbidden("rm -rf /")
    assert SafetyGuard.is_strictly_forbidden("del /s /q C:\\")
    assert SafetyGuard.is_strictly_forbidden("format C:")
    assert not SafetyGuard.is_strictly_forbidden("ls -la")

def test_confirmation_required():
    assert SafetyGuard.requires_confirmation("rm test.txt")
    assert SafetyGuard.requires_confirmation("rmdir my_dir")
    assert SafetyGuard.requires_confirmation("del some_file")
    assert not SafetyGuard.requires_confirmation("echo hello")

def test_heuristic_scope():
    is_safe, reason = SafetyGuard.is_within_scope("Change my windows password")
    assert not is_safe
    assert "password" in reason

    is_safe, reason = SafetyGuard.is_within_scope("Create a react app")
    assert is_safe

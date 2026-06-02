import os
import pytest
from src.core.executor import CommandExecutor

def test_execute_simple_command():
    executor = CommandExecutor()
    result = executor.execute("echo Hello World")
    assert result.success
    assert "Hello World" in result.stdout
    assert result.exit_code == 0

def test_execute_invalid_command():
    executor = CommandExecutor()
    result = executor.execute("non_existent_command_12345")
    assert not result.success
    assert result.exit_code != 0

def test_cd_command():
    executor = CommandExecutor()
    initial_cwd = executor.cwd
    
    # Create a temp dir
    temp_dir = "test_temp_dir"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    try:
        result = executor.execute(f"cd {temp_dir}")
        assert result.success
        assert executor.cwd == os.path.normpath(os.path.join(initial_cwd, temp_dir))
        
        # Verify it actually runs in that dir
        result = executor.execute("echo %cd%" if os.name == "nt" else "pwd")
        assert temp_dir in result.stdout
        
        executor.execute("cd ..")
        assert executor.cwd == initial_cwd
    finally:
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

def test_timeout():
    executor = CommandExecutor()
    # On Windows, 'choice' can be used for delay, or just 'ping'
    cmd = "ping 127.0.0.1 -n 5 > nul" if os.name == "nt" else "sleep 5"
    result = executor.execute(cmd, timeout=1)
    assert not result.success
    assert "timed out" in result.stderr

def test_on_output_callback():
    executor = CommandExecutor()
    captured_output = []
    def callback(line, stream):
        captured_output.append((line.strip(), stream))
    
    result = executor.execute("echo Line1 && echo Line2", on_output=callback)
    assert result.success
    assert ("Line1", "stdout") in captured_output
    assert ("Line2", "stdout") in captured_output

def test_complex_cd_command():
    executor = CommandExecutor()
    initial_cwd = executor.cwd
    temp_dir = "test_complex_dir"
    
    try:
        # Test mkdir and cd in one command
        cmd = f"mkdir {temp_dir} && cd {temp_dir}"
        result = executor.execute(cmd)
        assert result.success
        assert executor.cwd == os.path.normpath(os.path.join(initial_cwd, temp_dir))
        
        # Verify next command runs in the new dir
        result = executor.execute("echo %cd%" if os.name == "nt" else "pwd")
        assert temp_dir in result.stdout
        
    finally:
        executor.execute("cd ..")
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

def test_venv_activation():
    executor = CommandExecutor()
    test_subdir = "test_venv_container"
    temp_venv = "venv" # Use a standard name
    
    venv_root = os.path.join(test_subdir, temp_venv)
    if os.name == "nt":
        scripts_dir = os.path.join(venv_root, "Scripts")
    else:
        scripts_dir = os.path.join(venv_root, "bin")
    
    os.makedirs(scripts_dir, exist_ok=True)
    
    try:
        executor.cwd = os.path.abspath(test_subdir)
        
        # Check if VIRTUAL_ENV is set in the subprocess
        cmd = "echo %VIRTUAL_ENV%" if os.name == "nt" else "echo $VIRTUAL_ENV"
        result = executor.execute(cmd)
        
        assert temp_venv in result.stdout
        assert test_subdir in result.stdout
        
    finally:
        import shutil
        if os.path.exists(test_subdir):
            shutil.rmtree(test_subdir)

import pytest
from src.core.env_sniffer import EnvSniffer

def test_sniff_os():
    sniffer = EnvSniffer()
    res = sniffer._sniff_os()
    assert "os" in res
    assert "os_release" in res

def test_sniff_python():
    sniffer = EnvSniffer()
    res = sniffer._sniff_python()
    assert "python_version" in res
    assert "is_venv" in res

def test_sniff_tools():
    sniffer = EnvSniffer()
    res = sniffer._sniff_tools()
    assert "installed_tools" in res
    assert isinstance(res["installed_tools"], list)

def test_get_summary_prompt():
    sniffer = EnvSniffer()
    summary = sniffer.get_summary_prompt()
    assert "SYSTEM CONTEXT" in summary
    assert "OS:" in summary
    assert "Shell:" in summary

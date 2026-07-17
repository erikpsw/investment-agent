import subprocess
import sys


def test_llm_module_does_not_require_optional_agent_or_tracing_packages():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import pathlib, sys, types; "
                "root = pathlib.Path.cwd(); "
                "package = types.ModuleType('investment'); "
                "package.__path__ = [str(root)]; "
                "sys.modules['investment'] = package; "
                "sys.modules['langgraph'] = None; "
                "sys.modules['langsmith'] = None; "
                "import investment.agents.llm"
            ),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

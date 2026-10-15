"""eq_mcp save tool — listed in --print-tools."""
from __future__ import annotations

import os
import subprocess
import sys


def test_save_tool_appears_in_print_tools():
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "eq_mcp.server", "--print-tools"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    tools = result.stdout.splitlines()
    assert "save" in tools, f"expected 'save' in tools, got {tools}"

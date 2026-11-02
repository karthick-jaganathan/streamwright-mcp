import asyncio
import os
from pathlib import Path

import pytest

from streamwright.mcp.server import server
from streamwright.mcp.workspace import ROOTS_ENV

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_SOURCE = str(FIXTURES / "sample_pipeline")


@pytest.fixture(autouse=True)
def workspace_roots(monkeypatch, tmp_path):
    """Allows the test fixtures and the test's tmp_path as workspace roots."""
    roots = os.pathsep.join([str(Path(__file__).parent), str(tmp_path)])
    monkeypatch.setenv(ROOTS_ENV, roots)


@pytest.fixture
def call():
    """call(tool, **arguments): the tool's result, through the MCP server's call_tool."""

    def invoke(tool, **arguments):
        result = asyncio.run(server.call_tool(tool, arguments)).structured_content
        return result["result"] if set(result) == {"result"} else result

    return invoke


@pytest.fixture
def job_tools():
    """The names of the generated job validate tools (one per installed job engine)."""
    return [tool.name for tool in asyncio.run(server.list_tools()) if tool.name.endswith("_job")]

import argparse
import importlib
import re
import sys
from pathlib import Path

import pytest
from streamwright.core.runtime import plugins

from streamwright.mcp import cli, docs

ROOT = Path(__file__).parent.parent


class FakeEntryPoint:
    def __init__(self, name, target):
        self.name, self.dist, self._target = name, None, target

    def load(self):
        return self._target


def test_the_mcp_subcommand_is_registered_through_the_commands_group():
    def entry_points():
        return {plugins.COMMANDS: [FakeEntryPoint("mcp", cli.register)]}
    register = plugins.load_plugin(plugins.COMMANDS, "mcp", entry_points=entry_points)
    root = argparse.ArgumentParser(prog="streamwright")

    register(root.add_subparsers(dest="command"))
    args = root.parse_args(["mcp", "--transport", "streamable-http", "--allow-http", "--port", "9001"])

    assert (args.command, args.transport, args.allow_http, args.port) == ("mcp", "streamable-http", True, 9001)
    assert callable(args.command_handler)


def test_the_subcommand_serves_over_stdio_by_default(monkeypatch):
    served = []
    def run(transport):
        served.append(transport)
    monkeypatch.setattr("streamwright.mcp.server.server.run", run)
    root = argparse.ArgumentParser(prog="streamwright")
    cli.register(root.add_subparsers(dest="command"))

    args = root.parse_args(["mcp"])

    assert args.command_handler(args) == 0 and served == ["stdio"]


def test_pyproject_declares_the_entry_points_and_the_pins():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'mcp = "streamwright.mcp.cli:register"' in text
    assert 'streamwright-mcp = "streamwright.mcp.cli:main"' in text
    assert '"mcp>=2.3,<3"' in text
    assert "sqlglot" not in text and "requests" not in text


def test_the_old_package_name_still_works_and_warns():
    for name in [module for module in sys.modules if module.startswith("streamwright_mcp")]:
        del sys.modules[name]

    with pytest.warns(DeprecationWarning, match="streamwright.mcp"):
        old_cli = importlib.import_module("streamwright_mcp.cli")
    old_server = importlib.import_module("streamwright_mcp.server")

    assert old_cli.main is cli.main
    assert old_server.server is importlib.import_module("streamwright.mcp.server").server
    assert importlib.import_module("streamwright_mcp").__version__


def test_generated_tool_reference_is_current():
    block = docs.render_reference()

    text = (ROOT / "docs/mcp.md").read_text(encoding="utf-8")  # the full reference; README.md stays a short summary
    assert docs.replace_block(text, block) == text, "out of date: python -m streamwright.mcp.docs docs/mcp.md"
    assert re.search(r"##### `validate_source_config`", block)

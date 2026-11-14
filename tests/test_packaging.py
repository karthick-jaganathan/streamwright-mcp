#!/usr/bin/env python
# /*************************************************************************
# * Copyright 2026 Karthick Jaganathan
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# **************************************************************************/

import argparse
import importlib
import os
import re
import sys
from pathlib import Path

import pytest
from streamwright.core.runtime import plugins

from streamwright.mcp import cli, docs
from streamwright.mcp.workspace import ROOTS_ENV

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


def test_http_options_are_refused_with_stdio(capsys):
    for argv in (["--port", "9001"], ["--host", "0.0.0.0"], ["--allow-http"]):
        with pytest.raises(SystemExit) as usage:
            cli.main(argv)
        assert usage.value.code == 2
    assert "--allow-http only applies to the sse and streamable-http transports" in capsys.readouterr().err


def test_root_sets_the_workspace_roots(tmp_path, monkeypatch):
    monkeypatch.delenv(ROOTS_ENV, raising=False)
    with pytest.raises(SystemExit):
        cli.main(["--root", str(tmp_path / "missing")])
    monkeypatch.setattr("streamwright.mcp.server.server.run", lambda transport: None)
    assert cli.main(["--root", str(tmp_path), "--root", "."]) == 0
    assert os.environ[ROOTS_ENV].split(os.pathsep) == [str(tmp_path), os.path.abspath(".")]

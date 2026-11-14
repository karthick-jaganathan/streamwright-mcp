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

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from streamwright.core.cli import command_parsers


def test_commands_come_from_the_cli_parsers(call):
    reference = call("get_cli_reference")

    assert {"run", "validate", "connectors"} <= set(reference["commands"])
    assert "job" not in reference["commands"]
    assert reference["job_options"]


@pytest.mark.parametrize("command", ["run", "validate"])
def test_a_command_reports_its_real_options(call, command):
    reference = call("get_cli_reference", command=command)

    assert reference["command"] == command
    assert command_parsers()[command].format_help() == reference["help_text"]
    assert "--strict" in reference["help_text"] or command == "run"


def test_validate_is_not_a_stub(call):
    assert "--allow-connector" in call("get_cli_reference", command="validate")["help_text"]


def test_unknown_command_is_an_error(call):
    with pytest.raises(ToolError, match="Unknown command 'nonexistent'"):
        call("get_cli_reference", command="nonexistent")


def test_engine_subcommands_report_their_own_options(call):
    run = call("get_cli_reference", command="duckdb run")
    assert run["command"] == "duckdb run"
    assert "--state-lock-policy" in run["help_text"] and "--state-lock-timeout" in run["help_text"]
    state = call("get_cli_reference", command="duckdb state")
    assert "runtime.state.scope" in state["help_text"]
    assert {"list", "show", "retry", "abandon", "leases", "purge", "migrate", "check"} <= set(state["subcommands"])
    assert "--no-run" in call("get_cli_reference", command="duckdb state retry")["help_text"]
    assert "--strict" not in call("get_cli_reference", command="duckdb state list")["help_text"]
    assert set(call("get_cli_reference", command="duckdb")["subcommands"]) == {"validate", "plan", "run", "state"}
    assert "--dry-run" in call("get_cli_reference", command="state migrate")["help_text"]


def test_run_only_options_are_not_shared_job_options(call):
    assert "--state-lock-policy" not in call("get_cli_reference")["job_options"]
    assert "--state-lock-policy" not in call("get_cli_reference", command="duckdb validate")["help_text"]


def test_spark_subcommands_when_installed(call):
    pytest.importorskip("streamwright.spark")
    assert "--state-lock-policy" in call("get_cli_reference", command="spark run")["help_text"]
    assert "lease" in call("get_cli_reference", command="spark state")["help_text"]


def _without_help(parser, path):
    missing = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helped = {id(action.choices[choice.dest]) for choice in action._choices_actions if choice.help}
            for name, sub in action.choices.items():   # an alias shares its command's parser (and help)
                missing += [] if id(sub) in helped else ["%s %s" % (path, name)]
                missing += _without_help(sub, "%s %s" % (path, name))
        elif not action.help and action.nargs != argparse.REMAINDER:
            missing.append("%s %s" % (path, "/".join(action.option_strings) or action.dest))
    return missing


def test_every_reachable_command_and_option_has_help():
    assert [item for name, parser in command_parsers().items() for item in _without_help(parser, name)] == []

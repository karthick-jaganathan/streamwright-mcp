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

import pytest
from streamwright_mcp.server import (
    get_cli_reference,
    get_connector_contract,
    get_core_schema,
    inspect_stream_transform,
    list_connectors,
    server,
    validate_source_config,
)


def test_server_metadata():
    assert server.name == "streamwright-mcp"


def test_server_list_connectors_tool():
    connectors = list_connectors(include_hub=False)
    assert len(connectors) >= 16
    assert any(c["name"] == "postgres" for c in connectors)


def test_server_get_contract_tool():
    contract = get_connector_contract("postgres")
    assert contract["installed"] is True
    assert "source.yaml" in contract["contract_documentation"]


def test_server_get_core_schema_tool():
    schema = get_core_schema("all")
    assert "source_schema" in schema
    assert "stream_schema" in schema


def test_server_validate_tool():
    example_path = "/Users/kjaganathan/repos/streamwright/examples/sources/ads/openai_ads"
    val = validate_source_config(example_path)
    assert val["valid"] is True


def test_server_inspect_tool():
    example_path = "/Users/kjaganathan/repos/streamwright/examples/sources/ads/openai_ads"
    ins = inspect_stream_transform(example_path, "ad_accounts")
    assert ins["found"] is True


def test_server_get_cli_reference_tool():
    ref = get_cli_reference()
    assert ref["binary"] == "streamwright"
    assert ref["alias"] == "sw"
    assert "available_subcommands" in ref
    assert "run" in ref["available_subcommands"]
    assert "validate" in ref["available_subcommands"]
    assert "sw --help" in ref["recommended_command"]

    run_ref = get_cli_reference("run")
    assert run_ref["command"] == "run"
    assert "sw run --help" in run_ref["recommended_command"]

    val_ref = get_cli_reference("validate")
    assert val_ref["command"] == "validate"
    assert "sw validate --help" in val_ref["recommended_command"]

    # Unknown command falls back gracefully to global instructions
    unknown_ref = get_cli_reference("nonexistent")
    assert "available_subcommands" in unknown_ref



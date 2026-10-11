from pathlib import Path
from unittest.mock import MagicMock, patch
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

FIXTURE_PATH = str(Path(__file__).parent / "fixtures" / "sample_pipeline")


def test_server_metadata():
    assert server.name == "streamwright-mcp"


def test_server_list_connectors_tool():
    # include_hub=False returns list of installed
    connectors = list_connectors(include_hub=False)
    assert isinstance(connectors, list)

    # include_hub=True queries hub registry (mock network to ensure fast, deterministic tests)
    with patch("streamwright_mcp.hub.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"name": "restapi.yaml"}, {"name": "postgres.yaml"}]
        mock_get.return_value = mock_resp

        hub_connectors = list_connectors(include_hub=True)
        assert len(hub_connectors) >= 2
        assert any(c["name"] == "restapi" for c in hub_connectors)


def test_server_get_contract_tool():
    # Non-installed / hub connector check (mock network for determinism)
    with patch("streamwright_mcp.hub.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "title: Shopify Connector\ninstall:\n  git: pip install streamwright-shopify\n"
        mock_get.return_value = mock_resp

        contract = get_connector_contract("shopify")
        assert contract["name"] == "shopify"
        assert "install_command" in contract


def test_server_get_core_schema_tool():
    schema = get_core_schema("all")
    assert "source_schema" in schema
    assert "stream_schema" in schema


def test_server_validate_tool():
    val = validate_source_config(FIXTURE_PATH)
    assert val["valid"] is True
    assert val["error_count"] == 0


def test_server_inspect_tool():
    ins = inspect_stream_transform(FIXTURE_PATH, "orders")
    assert ins["found"] is True
    assert ins["stream_name"] == "orders"


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

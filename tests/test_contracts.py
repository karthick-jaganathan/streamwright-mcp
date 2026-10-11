from unittest.mock import MagicMock, patch
import pytest
from streamwright_mcp.contracts import (
    get_connector_contract,
    get_core_schema,
    list_installed_connectors,
)


class DummyMockConnector:
    spec = type("Spec", (), {
        "name": "mock_conn",
        "title": "Mock Connector",
        "category": "api",
        "transport": "http",
        "package": "streamwright-mock",
    })
    auth_required = ["base_url"]
    auth_optional = ["api_key"]
    __doc__ = "Mock connector documentation with details."


def _make_mock_entry_point():
    ep = MagicMock()
    ep.name = "mock_conn"
    ep.load.return_value = DummyMockConnector
    ep.dist = MagicMock()
    ep.dist.version = "0.0.1"
    return ep


def test_list_installed_connectors():
    connectors = list_installed_connectors()
    assert isinstance(connectors, list)

    # Test with mock entry point to guarantee discovery logic is tested in bare CI environments
    mock_ep = _make_mock_entry_point()
    with patch("importlib.metadata.entry_points") as mock_eps:
        mock_group = MagicMock()
        mock_group.__iter__.return_value = [mock_ep]
        mock_group.select.return_value = [mock_ep]
        mock_eps.return_value = mock_group

        discovered = list_installed_connectors()
        assert len(discovered) == 1
        c = discovered[0]
        assert c["name"] == "mock_conn"
        assert c["title"] == "Mock Connector"
        assert c["category"] == "api"
        assert c["transport"] == "http"
        assert c["installed"] is True


def test_get_connector_contract_installed():
    mock_ep = _make_mock_entry_point()
    with patch("importlib.metadata.entry_points") as mock_eps:
        mock_group = MagicMock()
        mock_group.__iter__.return_value = [mock_ep]
        mock_group.select.return_value = [mock_ep]
        mock_eps.return_value = mock_group

        contract = get_connector_contract("mock_conn")
        assert contract["installed"] is True
        assert contract["name"] == "mock_conn"
        assert contract["spec"]["transport"] == "http"
        assert contract["auth"]["required_fields"] == ["base_url"]
        assert "Mock connector documentation" in contract["contract_documentation"]


def test_get_connector_contract_uninstalled():
    contract = get_connector_contract("nonexistent_unknown_connector")
    assert contract["installed"] is False
    assert "not installed" in contract["message"]
    assert "sw connectors install" in contract["install_command"]
    assert "note" in contract


def test_get_core_schema():
    source_res = get_core_schema("source")
    assert "source_schema" in source_res
    assert "stream_schema" not in source_res
    assert source_res["source_schema"]["$schema"] == "http://json-schema.org/draft-07/schema#"

    stream_res = get_core_schema("stream")
    assert "stream_schema" in stream_res
    assert "source_schema" not in stream_res

    all_res = get_core_schema("all")
    assert "source_schema" in all_res
    assert "stream_schema" in all_res
    assert "dsl_specification" in all_res
    assert len(all_res["dsl_specification"]) > 50


def test_get_core_schema_dsl():
    dsl_res = get_core_schema("dsl")
    assert dsl_res["kind"] == "dsl"
    assert "source_schema" not in dsl_res
    assert "stream_schema" not in dsl_res
    assert "dsl_specification" in dsl_res
    assert len(dsl_res["dsl_specification"]) > 50


def test_get_core_schema_section():
    paginator_res = get_core_schema(section="paginator")
    assert paginator_res["section"] == "paginator"
    assert "definition" in paginator_res
    assert "type" in paginator_res["definition"]

    # Invalid section
    bad_res = get_core_schema(section="unknown_section_xyz")
    assert "error" in bad_res
    assert "available_sections" in bad_res
    assert "paginator" in bad_res["available_sections"]


def test_get_cli_reference_environment_hints():
    from streamwright_mcp.contracts import get_cli_reference

    res_all = get_cli_reference()
    assert "environment_hints" in res_all
    assert len(res_all["environment_hints"]) >= 2
    assert any("sw" in h for h in res_all["environment_hints"])

    res_cmd = get_cli_reference("run")
    assert "environment_hints" in res_cmd
    assert res_cmd["command"] == "run"

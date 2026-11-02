from types import MappingProxyType
from unittest.mock import patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from streamwright.mcp.connectors import get_connector_contract, is_valid_connector_name, list_connectors
from streamwright.mcp.engines import EngineDescriptor, EngineRegistry, source_engine

CATALOG = MappingProxyType({
    "alpha": {"title": "Alpha", "family": "demo", "summary": "an installed one",
              "install": {"pip": "streamwright-alpha"}},
    "beta": {"title": "Beta", "family": "demo", "summary": "not installed", "install": {"git": "git+https://example.invalid/beta"}},
})


def fake_engine(describe=None):
    base = source_engine()
    return EngineDescriptor(kind="FakeJob", key="fake", title="fake", schemas={}, guide=None, validate=base.validate,
                            describe_connector=describe or (lambda name: {"name": name}))


@pytest.fixture
def registry():
    alpha = {"name": "alpha", "distribution": "streamwright-alpha", "version": "1.0"}
    gamma = {"name": "gamma", "distribution": "streamwright-gamma", "version": "2.0"}
    by_engine = {"source": [alpha], "fake": [alpha, gamma]}   # the engines each connector definition has adapters for
    with patch("streamwright.mcp.engines.engine_connectors", side_effect=lambda engine: by_engine.get(engine, [])):
        yield EngineRegistry([source_engine(), fake_engine()])


def test_installed_connectors_list_the_engines_their_definitions_name(registry):
    listed = {item["name"]: item for item in list_connectors(registry)}

    assert listed["alpha"]["engines"] == ["source", "FakeJob"]
    assert listed["gamma"]["engines"] == ["FakeJob"] and listed["gamma"]["distribution"] == "streamwright-gamma"


def test_engine_filter(registry):
    assert [item["name"] for item in list_connectors(registry, engine="source")] == ["alpha"]
    with pytest.raises(ToolError, match="Unknown engine"):
        list_connectors(registry, engine="nope")


def test_the_catalog_adds_install_hints_for_connectors_that_are_not_installed(registry):
    with patch("streamwright.core.catalog.connectors", return_value=CATALOG):
        listed = {item["name"]: item for item in list_connectors(registry, include_hub=True)}

    assert listed["alpha"]["installed"] is True and listed["alpha"]["title"] == "Alpha"
    assert listed["beta"]["installed"] is False
    assert listed["beta"]["install_command"] == "streamwright connectors install beta"
    assert listed["beta"]["install"] == {"git": "git+https://example.invalid/beta"}
    assert "streamwright[spark]" not in repr(listed)


def test_contract_comes_from_each_engine_that_has_the_connector(registry):
    contract = get_connector_contract(registry, "gamma")

    assert contract == {"name": "gamma", "installed": True, "engines": {"FakeJob": {"name": "gamma"}}}


def test_contract_for_an_engine_without_an_adapter(registry):
    contract = get_connector_contract(registry, "gamma", engine="source")

    assert contract["installed"] is True and contract["engines"] == {}
    assert "supports: FakeJob" in contract["message"]


def test_contract_for_a_missing_connector_uses_the_catalog(registry):
    with patch("streamwright.core.catalog.connectors", return_value=CATALOG):
        contract = get_connector_contract(registry, "beta")

    assert contract["installed"] is False
    assert contract["install_command"] == "streamwright connectors install beta"
    assert contract["install"] == {"git": "git+https://example.invalid/beta"}


def test_contract_for_a_missing_connector_survives_an_unreachable_catalog(registry):
    with patch("streamwright.core.catalog.connectors", side_effect=RuntimeError("hub unreachable")):
        contract = get_connector_contract(registry, "beta")

    assert contract["catalog_error"] == "hub unreachable"
    assert contract["install_command"] == "streamwright connectors install beta"


@pytest.mark.parametrize("name", ["../../evil/repo/main/x", "A", "a b", "a/b", "", "1abc", "a" * 64, "a.yaml", "a?b=c"])
def test_invalid_connector_names_are_rejected_before_any_lookup(registry, name):
    assert not is_valid_connector_name(name)
    with patch("streamwright.core.catalog.connectors") as fetch, pytest.raises(ToolError):
        get_connector_contract(registry, name)
    fetch.assert_not_called()


@pytest.mark.parametrize("name", ["postgres", "google_ads", "a", "s3"])
def test_valid_connector_names_are_accepted(name):
    assert is_valid_connector_name(name)


def test_real_installed_connectors_through_the_protocol(call):
    contract = call("get_connector_contract", name="postgres")

    assert contract["installed"] is True
    assert contract["engines"]["DuckDBJob"]["secret_keys"] == ["dsn", "password"]
    listed = {item["name"]: item for item in call("list_connectors")}
    assert {"source", "DuckDBJob"} <= set(listed["postgres"]["engines"])
    # contract v1.2 §6a: a job engine reaches any source connector through a call step, shown as `call` reach
    assert "DuckDBJob" in listed["mongodb"]["engines"]
    assert listed["mongodb"]["reach"]["DuckDBJob"] == "call"      # mongodb has no native duckdb adapter

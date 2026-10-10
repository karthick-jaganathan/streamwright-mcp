import pytest
from streamwright_mcp.contracts import (
    get_connector_contract,
    get_core_schema,
    list_installed_connectors,
)


def test_list_installed_connectors():
    connectors = list_installed_connectors()
    assert len(connectors) >= 16
    names = {c["name"] for c in connectors}
    expected = {
        "restapi", "files", "s3", "gcs", "azure_blob", "postgres",
        "mysql", "mongodb", "deltalake", "google_ads", "microsoft_ads",
        "meta_ads", "openai_ads", "linkedin_ads", "amazon_ads", "apple_ads",
    }
    assert expected.issubset(names)

    # Check structure
    for c in connectors:
        assert "name" in c
        assert "title" in c
        assert "category" in c
        assert "transport" in c
        assert c["installed"] is True


def test_get_connector_contract_installed_s3():
    contract = get_connector_contract("s3")
    assert contract["installed"] is True
    assert contract["name"] == "s3"
    assert contract["spec"]["transport"] == "duckdb"
    assert "source.yaml" in contract["contract_documentation"]
    assert "streams/<stream>.yaml" in contract["contract_documentation"]
    assert "Authentication & Security" in contract["contract_documentation"]
    assert "Transform & Data Shaping" in contract["contract_documentation"]
    assert "Execution & Behavior" in contract["contract_documentation"]


def test_get_connector_contract_installed_postgres():
    contract = get_connector_contract("postgres")
    assert contract["installed"] is True
    assert contract["name"] == "postgres"
    assert contract["spec"]["transport"] == "duckdb"
    assert "statement_timeout" in contract["contract_documentation"]
    assert "database.query" in contract["contract_documentation"]


def test_get_connector_contract_installed_google_ads():
    contract = get_connector_contract("google_ads")
    assert contract["installed"] is True
    assert contract["name"] == "google_ads"
    assert "developer_token" in contract["contract_documentation"]
    assert "GoogleAdsService" in contract["contract_documentation"]


def test_get_connector_contract_uninstalled():
    contract = get_connector_contract("nonexistent_unknown_connector")
    assert contract["installed"] is False
    assert "not installed" in contract["message"]
    assert "pip install" in contract["install_command"]


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
    assert "`source.yaml` Schema Structure" in all_res["dsl_specification"]

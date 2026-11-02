import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from streamwright.mcp.engines import discover_engines
from streamwright.mcp.schemas import get_core_schema, get_engine_guide
from streamwright.mcp.server import server


@pytest.fixture(scope="module")
def registry():
    return discover_engines()


def test_default_is_a_small_index(call):
    index = call("get_core_schema")

    kinds = [engine["kind"] for engine in index["engines"]]
    assert {"source", "DuckDBJob"} <= set(kinds)
    assert len(json.dumps(index)) < 10_000
    assert "http_request" in index["engines"][0]["schemas"]["source"]["sections"]
    assert "schema" not in index


@pytest.mark.parametrize("kind,schema_name", [("source", "source"), ("stream", "stream"), ("DuckDBJob", "duckdb"),
                                              ("duckdb", "duckdb")])
def test_a_schema_by_kind_or_schema_name(registry, kind, schema_name):
    result = get_core_schema(registry, kind)

    assert result["schema_name"] == schema_name and result["schema"]["$schema"]


def test_unknown_kind_is_an_error_through_the_protocol(call):
    with pytest.raises(ToolError, match=r"Unknown kind 'nope'; available: source, stream, .*DuckDBJob, duckdb"):
        call("get_core_schema", kind="nope")


def test_section_needs_a_kind(registry):
    with pytest.raises(ToolError, match="needs a 'kind'"):
        get_core_schema(registry, section="auth")


def test_sections_are_scoped_to_the_engine(registry):
    assert get_core_schema(registry, "source", "paginator")["definition"]["type"] == "object"
    assert get_core_schema(registry, "duckdb", "steps")["section"] == "steps"
    with pytest.raises(ToolError, match="not in the duckdb schema"):
        get_core_schema(registry, "duckdb", "paginator")


def test_schema_resources_serve_each_schema(registry):
    uris = {str(resource.uri) for resource in asyncio.run(server.list_resources())}
    assert {"streamwright://schema/source", "streamwright://schema/stream", "streamwright://schema/duckdb"} <= uris
    contents = asyncio.run(server.read_resource("streamwright://schema/stream"))
    assert "$schema" in json.loads(contents[0].content)


def test_guide_is_paged_by_section(registry):
    sections = get_engine_guide(registry, "source")["sections"]

    assert sections
    page = get_engine_guide(registry, "source", sections[0])
    assert page["section"] == sections[0] and page["text"]


def test_guide_errors(registry):
    with pytest.raises(ToolError, match="Unknown engine"):
        get_engine_guide(registry, "nope")
    with pytest.raises(ResourceError, match="unknown guide section"):
        get_engine_guide(registry, "source", "no such section")

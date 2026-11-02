import asyncio
import json

import pytest
from streamwright.core.jobs import JobReport
from streamwright.core.validation import Issue

from streamwright.mcp.engines import EngineError, EngineRegistry, discover_engines, job_engine, source_engine
from streamwright.mcp.server import build_server

GUIDE = "# Fake\n\nintro\n\n## Pipeline\n\nhow it runs\n\n## Commands\n\nfake run\n"


class FakeEntryPoint:
    def __init__(self, name, target):
        self.name, self.dist, self._target = name, None, target

    def load(self):
        return self._target


class FakeEngine:
    """A JobEngine, as the engines register in `streamwright.job_kinds`."""
    kind = "FakeJob"

    def main(self, argv=None):
        return 0

    def validate_job(self, job, *, overlays=(), config=None, strict=False):
        return JobReport(False, [Issue("error", "fake-problem", f"bad {job}", str(job))], {"name": "f", "steps": [1]})

    def validate_job_text(self, text, *, overlays=(), config=None, strict=False):
        return JobReport(True, [], {"name": text})

    def json_schema(self):
        return {"title": "fake", "properties": {"steps": {"type": "array"}}}

    def guide(self, section=None):
        return GUIDE if section is None else GUIDE.split("## %s\n" % section)[1].split("\n## ", maxsplit=1)[0]

    def describe_connector(self, name):
        return {"provider": name, "methods": ["read"]} if name == "thing" else None


@pytest.fixture
def fake_engine():
    return {"streamwright.job_kinds": [FakeEntryPoint("FakeJob", FakeEngine())]}


def test_engines_are_discovered_from_job_kind_entry_points(fake_engine):
    registry = discover_engines(entry_points=lambda: fake_engine)

    assert registry.kinds() == ["source", "FakeJob"]
    assert registry.problems == {}
    assert registry.find("fake").kind == "FakeJob" and registry.find("FAKEJOB").kind == "FakeJob"
    assert registry.find_schema("stream")[1] == "stream"
    assert registry.find_schema("fakejob")[0].kind == "FakeJob"
    assert registry.find("nope") is None


def test_a_kind_without_a_job_engine_is_a_problem_not_a_crash():
    orphan = FakeEntryPoint("OrphanJob", lambda argv: 0)
    registry = discover_engines(entry_points=lambda: {"streamwright.job_kinds": [orphan]})

    assert registry.kinds() == ["source"]
    assert "invalid type" in registry.problems["OrphanJob"]


def test_tools_and_resources_are_generated_from_the_registry(fake_engine):
    server = build_server(discover_engines(entry_points=lambda: fake_engine))

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert "validate_fake_job" in tools and "validate_duckdb_job" not in tools
    assert "FakeJob" in tools["validate_fake_job"].description
    uris = {str(resource.uri) for resource in asyncio.run(server.list_resources())}
    assert {"streamwright://schema/source", "streamwright://schema/stream", "streamwright://schema/fake",
            "streamwright://guide/fake"} <= uris
    schema = asyncio.run(server.read_resource("streamwright://schema/fake"))
    assert json.loads(schema[0].content)["title"] == "fake"
    result = asyncio.run(server.call_tool("validate_fake_job", {"content": "x"})).structured_content["result"]
    assert result["valid"] is True and result["subject"]["name"] == "x"


def test_job_reports_become_the_common_report(tmp_path):
    engine = job_engine(FakeEngine())

    report = engine.validate(path=str(tmp_path)).to_dict()

    assert report["kind"] == "FakeJob" and report["valid"] is False
    assert report["errors"] == [Issue("error", "fake-problem", f"bad {tmp_path}", str(tmp_path)).to_dict()]
    assert report["subject"]["step_count"] == 1


def test_guide_is_paged_by_section():
    engine = job_engine(FakeEngine())

    assert engine.guide(None) == {"sections": ["Pipeline", "Commands"]}
    assert engine.guide("command")["text"] == "## Commands\n\nfake run"
    with pytest.raises(EngineError, match="sections: Pipeline, Commands"):
        engine.guide("missing")


def test_source_overlays_and_config_are_refused():
    with pytest.raises(ValueError):
        source_engine().validate(path="x", overlays=["o.yaml"])


def test_registry_lists_jobs_apart_from_source():
    registry = EngineRegistry([source_engine()])

    assert registry.job_engines() == []


def test_connectors_are_described_by_the_engine():
    engine = job_engine(FakeEngine())

    assert engine.describe_connector("thing") == {"name": "thing", "kind": "connector", "engine": "FakeJob",
                                                  "provider": "thing", "methods": ["read"]}
    assert engine.describe_connector("missing") is None

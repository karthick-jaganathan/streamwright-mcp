import asyncio
import shutil

import pytest
from conftest import SAMPLE_SOURCE
from mcp.server.mcpserver.exceptions import ToolError
from streamwright.core.validation import Issue

from streamwright.mcp.engines import SOURCE_KIND, EngineRegistry, source_engine
from streamwright.mcp.server import server
from streamwright.mcp.validation import validate_source_config

DUCKDB_JOB = """
kind: DuckDBJob
name: mcp_test_pipeline
connections:
  target_dw:
    provider: duckdb
    path: ":memory:"
steps:
  - name: base_step
    sql: SELECT 1 AS id, 'test' AS name
    materialize: table
outputs:
  - name: out_table
    connection: target_dw
    step: base_step
    table: my_target
    mode: overwrite
"""

SECRET_JOB = """
kind: DuckDBJob
name: secret_pipeline
spec:
  secrets:
    {declared}
connections:
  warehouse:
    provider: postgres
    host: db.example.com
    database: app
    user: reader
    password: "{{{{ secrets.api_token }}}}"
steps:
  - name: base_step
    connection: warehouse
    read: table
    table: public.orders
outputs:
  - name: out_table
    connection: warehouse
    step: base_step
    table: my_target
    mode: overwrite
"""


def test_valid_source_through_the_protocol(call):
    result = call("validate_source_config", source_dir=SAMPLE_SOURCE)

    assert result["valid"] is True
    assert result["kind"] == SOURCE_KIND
    assert result["error_count"] == 0 and result["errors"] == []


def test_missing_source_is_an_issue(call, tmp_path):
    result = call("validate_source_config", source_dir=str(tmp_path / "nope"))

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "unreadable-file"


def test_source_sql_errors_are_reported_with_the_engine_code(call, tmp_path):
    pipeline = tmp_path / "pipeline"
    shutil.copytree(SAMPLE_SOURCE, pipeline)
    stream = pipeline / "streams" / "orders.yaml"
    stream.write_text(stream.read_text(encoding="utf-8").replace("AS status,",
                                                                 "AS status, no_such_fn(record) AS broken,"),
                      encoding="utf-8")

    result = call("validate_source_config", source_dir=str(pipeline))

    assert result["valid"] is False
    assert any(e["code"] == "sql-check" and "no_such_fn" in e["message"] for e in result["errors"])


def test_strict_ignores_only_connector_not_installed(monkeypatch):
    not_installed = Issue("warning", "connector-not-installed", "connector 'x' is not installed", SAMPLE_SOURCE)
    other_warning = Issue("warning", "yaml-boolean", "'yes' is read as a boolean", SAMPLE_SOURCE)
    issues = []
    monkeypatch.setattr("streamwright.mcp.engines.validate_source", lambda *args, **kwargs: list(issues))
    registry = EngineRegistry([source_engine()])

    issues[:] = [not_installed]
    assert validate_source_config(registry, SAMPLE_SOURCE, strict=True)["valid"] is True
    issues[:] = [not_installed, other_warning]
    assert validate_source_config(registry, SAMPLE_SOURCE)["valid"] is True
    assert validate_source_config(registry, SAMPLE_SOURCE, strict=True)["valid"] is False


def test_source_validation_routes_a_job_manifest_to_its_engine(call, tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text(DUCKDB_JOB, encoding="utf-8")

    result = call("validate_source_config", source_dir=str(job))

    assert result["kind"] == "DuckDBJob"
    assert result["valid"] is True


def test_a_manifest_kind_without_an_engine_is_reported(call, tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text("kind: NoSuchJob\nname: j\n", encoding="utf-8")

    result = call("validate_source_config", source_dir=str(job))

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "unknown-kind"


def test_duckdb_job_content_with_plan(call):
    result = call("validate_duckdb_job", content=DUCKDB_JOB, analyze=True)

    assert result["valid"] is True and result["errors"] == []
    assert result["subject"]["name"] == "mcp_test_pipeline" and result["subject"]["step_count"] == 1
    assert "base_step" in result["plan"] and "out_table" in result["plan"]


def test_the_plan_is_left_out_unless_requested(call):
    assert call("validate_duckdb_job", content=DUCKDB_JOB)["plan"] is None


def test_duckdb_job_problems_are_issues(call):
    result = call("validate_duckdb_job", content="kind: DuckDBJob\nname: missing_fields_pipeline\n")

    assert result["valid"] is False
    assert {"severity", "code", "message", "file", "path", "line", "column"} <= set(result["errors"][0])


@pytest.mark.parametrize("arguments", [{}, {"content": DUCKDB_JOB, "path": "x"}])
def test_exactly_one_of_content_and_path(call, arguments):
    result = call("validate_duckdb_job", **arguments)

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "bad-arguments"


def test_missing_job_path_is_reported(call, tmp_path):
    result = call("validate_duckdb_job", path=str(tmp_path / "missing.yaml"))

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "unreadable"


def test_overlays_are_merged(call, tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text(DUCKDB_JOB.replace("name: mcp_test_pipeline", "name: base"), encoding="utf-8")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("name: overlaid\n", encoding="utf-8")

    result = call("validate_duckdb_job", path=str(job), overlays=[str(overlay)])

    assert result["subject"]["name"] == "overlaid"


def test_declared_secret_needs_no_value(call):
    result = call("validate_duckdb_job", content=SECRET_JOB.format(declared="api_token: {type: string}"))

    assert result["valid"] is True, result["errors"]


def test_undeclared_secret_is_reported(call):
    result = call("validate_duckdb_job", content=SECRET_JOB.format(declared="other_token: {type: string}"))

    assert result["valid"] is False
    assert any("api_token" in e["message"] and "not declared" in e["message"] for e in result["errors"])


@pytest.mark.parametrize("tool", ["validate_duckdb_job", "validate_source_config"])
def test_no_validate_tool_takes_secret_values(tool):
    tools = {t.name: t for t in asyncio.run(server.list_tools())}

    assert "secrets" not in tools[tool].input_schema["properties"]


def test_invalid_tool_arguments_are_rejected_by_the_protocol():
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("validate_source_config", {}))

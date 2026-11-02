"""Golden parity: an MCP verdict is the engine's own verdict, the one the CLI prints (MC-19, TST-03)."""

import shutil

import pytest
from conftest import SAMPLE_SOURCE
from streamwright.core.cli import main as cli_main
from streamwright.core.jobs.duckdb import validate_job as duckdb_validate_job
from streamwright.core.jobs.engine import load_job_engine
from streamwright.core.validation import Issue
from streamwright.core.validation.engine import check_components, validate_source

from streamwright.mcp.engines import job_engine

DUCKDB_VALID = """
kind: DuckDBJob
name: parity_valid
connections:
  target:
    provider: duckdb
    path: ":memory:"
steps:
  - name: base
    sql: SELECT 1 AS id
    materialize: table
outputs:
  - name: out
    connection: target
    step: base
    table: result
    mode: overwrite
"""

DUCKDB_INVALID = DUCKDB_VALID.replace("connection: target", "connection: nowhere").replace(
    "materialize: table", "materialize: sideways")

SPARK_INVALID = "kind: SparkJob\nname: parity_spark\nsteps:\n  - name: s\n    sql: SELECT 1 AS id\n"


def _text(issues):
    return [str(issue) for issue in issues]


def _issue(item):
    return Issue(item["severity"], item["code"], item["message"], item["file"], item["path"], item["line"],
                 item["column"])


def _mcp_text(result):
    return _text(_issue(item) for item in result["errors"] + result["warnings"])


def _write(directory, text, name="job.yaml"):
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def _invalid_source(tmp_path):
    pipeline = tmp_path / "invalid_source"
    shutil.copytree(SAMPLE_SOURCE, pipeline)
    stream = pipeline / "streams" / "orders.yaml"
    stream.write_text(stream.read_text(encoding="utf-8").replace("AS status,",
                                                                 "AS status, no_such_fn(record) AS broken,"),
                      encoding="utf-8")
    return str(pipeline.resolve())


def _cli(capsys, *argv):
    code = cli_main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


@pytest.mark.parametrize("make_path", [lambda tmp: SAMPLE_SOURCE, _invalid_source], ids=["valid", "invalid"])
def test_source_verdict_equals_the_engine_and_the_cli(call, capsys, tmp_path, make_path):
    path = make_path(tmp_path)

    result = call("validate_source_config", source_dir=path)

    engine_issues = validate_source(path, source_check=check_components)
    assert _mcp_text(result) == _text(sorted(engine_issues, key=lambda issue: issue.severity != "error"))
    code, output = _cli(capsys, "validate", path)
    assert result["valid"] is (code == 0)
    assert all(message in output for message in _mcp_text(result)[:3])


@pytest.mark.parametrize("text", [DUCKDB_VALID, DUCKDB_INVALID], ids=["valid", "invalid"])
def test_duckdb_job_verdict_equals_the_engine_and_the_cli(call, capsys, tmp_path, text):
    path = _write(tmp_path, text)

    result = call("validate_duckdb_job", path=path, analyze=True)

    report = duckdb_validate_job(path)
    assert result["valid"] is report.valid
    assert _mcp_text(result) == _text(sorted(report.issues, key=lambda issue: issue.severity != "error"))
    assert result["plan"] == report.plan
    code, output = _cli(capsys, "validate", path)
    assert result["valid"] is (code == 0)
    assert all(message in output for message in _mcp_text(result))


def test_duckdb_job_text_and_path_give_the_same_verdict(call, tmp_path):
    path = _write(tmp_path, DUCKDB_INVALID)

    by_path = call("validate_duckdb_job", path=path)
    by_text = call("validate_duckdb_job", content=DUCKDB_INVALID)

    assert [(e["code"], e["message"]) for e in by_path["errors"]] == [(e["code"],
                                                                       e["message"]) for e in by_text["errors"]]


@pytest.fixture
def spark_engine():
    """The installed Spark JobEngine, as the server discovers it."""
    pytest.importorskip("streamwright.spark")
    return job_engine(load_job_engine("SparkJob"))


def test_spark_job_verdict_equals_the_engine(tmp_path, spark_engine):
    validate = pytest.importorskip("streamwright.spark.job").validate
    path = _write(tmp_path, SPARK_INVALID)

    result = spark_engine.validate(path=path).to_dict()

    report = validate(path)
    assert result["valid"] is report.valid is False
    assert _mcp_text(result) == _text(sorted(report.issues, key=lambda issue: issue.severity != "error"))


def test_spark_job_verdict_equals_the_spark_cli(tmp_path, spark_engine, capsys):
    spark_main = pytest.importorskip("streamwright.spark.cli").main
    path = _write(tmp_path, SPARK_INVALID)

    result = spark_engine.validate(path=path).to_dict()

    assert spark_main(["validate", path]) != 0 and result["valid"] is False
    assert result["errors"][0]["message"] in capsys.readouterr().err

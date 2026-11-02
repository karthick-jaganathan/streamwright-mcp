import os
from unittest.mock import patch

import pytest

from streamwright.mcp.workspace import (
    MAX_CONTENT_BYTES,
    ROOTS_ENV,
    WorkspaceError,
    allowed_roots,
    resolve_workspace_path,
)

JOB = "kind: DuckDBJob\nname: j\n"


@pytest.fixture
def outside_credentials(tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    credentials = outside / "credentials"
    credentials.write_text("aws_secret_access_key: TOPSECRETVALUE\n", encoding="utf-8")
    return credentials


def test_roots_default_to_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(ROOTS_ENV)
    monkeypatch.chdir(tmp_path)
    assert allowed_roots() == [os.path.realpath(tmp_path)]


def test_roots_are_pathsep_separated(monkeypatch, tmp_path):
    monkeypatch.setenv(ROOTS_ENV, os.pathsep.join([str(tmp_path / "a"), str(tmp_path / "b")]))
    assert allowed_roots() == [os.path.realpath(tmp_path / "a"), os.path.realpath(tmp_path / "b")]


def test_path_outside_roots_is_rejected_without_being_read(call, job_tools, outside_credentials):
    with patch("builtins.open") as opened:
        results = [call("validate_source_config", source_dir=str(outside_credentials)),
                   call("inspect_stream_transform", source_dir=str(outside_credentials), stream_name="orders")]
        results += [call(tool, path=str(outside_credentials)) for tool in job_tools]
    for result in results:
        assert "outside the allowed workspace roots" in repr(result)
        assert "TOPSECRETVALUE" not in repr(result)
    opened.assert_not_called()


def test_overlay_outside_roots_is_rejected(call, job_tools, tmp_path, outside_credentials):
    job = tmp_path / "job.yaml"
    job.write_text(JOB, encoding="utf-8")

    for tool in job_tools:
        result = call(tool, path=str(job), overlays=[str(outside_credentials)])
        assert result["valid"] is False
        assert "'overlays' is outside the allowed workspace roots" in result["errors"][0]["message"]


def test_parent_traversal_is_rejected(tmp_path):
    with pytest.raises(WorkspaceError):
        resolve_workspace_path(str(tmp_path / ".." / "elsewhere"))


def test_symlink_escape_is_rejected(call, tmp_path, outside_credentials):
    link = tmp_path / "link"
    link.symlink_to(outside_credentials.parent)

    result = call("validate_duckdb_job", path=str(link / "credentials"))

    assert result["valid"] is False
    assert "outside the allowed workspace roots" in result["errors"][0]["message"]


@pytest.mark.parametrize("uri", ["s3://bucket/job.yaml", "http://example.com/job.yaml", "file:///etc/passwd"])
def test_uri_paths_are_rejected(call, job_tools, uri):
    for tool in job_tools:
        result = call(tool, path=uri)
        assert result["valid"] is False
        assert "not a URI" in result["errors"][0]["message"]
    assert "not a URI" in call("validate_source_config", source_dir=uri)["errors"][0]["message"]


def test_oversized_content_is_rejected(call, job_tools):
    for tool in job_tools:
        result = call(tool, content="x" * (MAX_CONTENT_BYTES + 1))
        assert result["valid"] is False
        assert "larger than" in result["errors"][0]["message"]


def test_yaml_error_does_not_echo_file_content(call, tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text("name: j\npassword: [TOPSECRETVALUE\nother: 1\n", encoding="utf-8")

    result = call("validate_duckdb_job", path=str(job))

    assert result["valid"] is False
    assert "TOPSECRETVALUE" not in repr(result)


def test_yaml_error_in_overlay_does_not_echo_file_content(call, tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text(JOB, encoding="utf-8")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("password: [TOPSECRETVALUE\nother: 1\n", encoding="utf-8")

    result = call("validate_duckdb_job", path=str(job), overlays=[str(overlay)])

    assert result["valid"] is False
    assert "TOPSECRETVALUE" not in repr(result)


def test_source_yaml_error_does_not_echo_file_content(call, tmp_path):
    (tmp_path / "source.yaml").write_text("name: s\npassword: [TOPSECRETVALUE\nother: 1\n", encoding="utf-8")

    assert "TOPSECRETVALUE" not in repr(call("validate_source_config", source_dir=str(tmp_path)))
    assert "TOPSECRETVALUE" not in repr(call("inspect_stream_transform", source_dir=str(tmp_path),
                                             stream_name="orders"))

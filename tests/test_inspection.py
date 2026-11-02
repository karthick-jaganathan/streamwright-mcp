import shutil

from conftest import SAMPLE_SOURCE


def test_stream_plan(call):
    result = call("inspect_stream_transform", source_dir=SAMPLE_SOURCE, stream_name="orders")

    assert result["found"] is True
    assert (result["stream_name"], result["source_name"]) == ("orders", "sample_orders")
    assert result["requests"] == [{"name": "raw_orders", "kind": "http", "spec": {"http": {"path": "/v1/orders",
                                                                                           "method": "GET"}}}]
    step = result["transform"]["steps"][0]
    assert step["name"] == "clean_orders" and "SELECT record->>'id'" in step["select_sql"]
    assert step["reads"] == [{"name": "raw_orders", "type": "request"}]
    assert [column["name"] for column in step["columns"]] == ["order_id", "status", "total"]
    export = result["exports"][0]
    assert (export["name"], export["step"], export["primary_key"]) == ("orders", "clean_orders", ["order_id"])
    assert export["primary_key_valid"] is True
    assert result["problems"] == []


def test_stream_names_ignore_case(call):
    assert call("inspect_stream_transform", source_dir=SAMPLE_SOURCE, stream_name="ORDERS")["stream_name"] == "orders"


def test_unknown_stream_lists_the_streams(call):
    result = call("inspect_stream_transform", source_dir=SAMPLE_SOURCE, stream_name="unknown_stream_xyz")

    assert result["found"] is False and result["available_streams"] == ["orders"]


def _stream_file(tmp_path, edit):
    pipeline = tmp_path / "pipeline"
    shutil.copytree(SAMPLE_SOURCE, pipeline)
    stream = pipeline / "streams" / "orders.yaml"
    stream.write_text(edit(stream.read_text(encoding="utf-8")), encoding="utf-8")
    return str(pipeline)


def test_ctes_are_not_reported_as_reads(call, tmp_path):
    pipeline = _stream_file(tmp_path, lambda text: text.replace(
        "FROM raw_orders", "FROM (WITH recent AS (SELECT * FROM raw_orders) SELECT * FROM recent) AS r").replace(
        "record->>'id'", "r.record->>'id'").replace("record->>'status'", "r.record->>'status'").replace(
        "record->>'total'", "r.record->>'total'"))

    step = call("inspect_stream_transform", source_dir=pipeline, stream_name="orders")["transform"]["steps"][0]

    assert step["reads"] == [{"name": "raw_orders", "type": "request"}]


def test_a_missing_primary_key_column_is_reported(call, tmp_path):
    pipeline = _stream_file(tmp_path, lambda text: text.replace("primary_key: [order_id]",
                                                                "primary_key: [order_id, nope]"))

    result = call("inspect_stream_transform", source_dir=pipeline, stream_name="orders")

    assert result["exports"][0]["primary_key_missing"] == ["nope"]
    assert any("primary_key 'nope' is not a column" in problem for problem in result["problems"])


def test_sdk_requests_are_not_http(call, tmp_path):
    pipeline = _stream_file(tmp_path, lambda text: text.replace(
        "    http:\n      path: /v1/orders\n      method: GET",
        "    sdk: restapi\n    service: orders\n    method: list"))

    request = call("inspect_stream_transform", source_dir=pipeline, stream_name="orders")["requests"][0]

    assert request["kind"] == "sdk"


def test_a_non_mapping_source_does_not_crash(call, tmp_path):
    (tmp_path / "source.yaml").write_text("- just\n- a list\n", encoding="utf-8")

    assert call("inspect_stream_transform", source_dir=str(tmp_path / "source.yaml"), stream_name="x")["found"] is False

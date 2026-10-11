from pathlib import Path
import pytest
from streamwright_mcp.inspector import inspect_stream_transform

FIXTURE_PATH = str(Path(__file__).parent / "fixtures" / "sample_pipeline")


def test_inspect_stream_transform():
    result = inspect_stream_transform(FIXTURE_PATH, "orders")

    assert result["found"] is True
    assert result["stream_name"] == "orders"
    assert result["source_name"] == "sample_orders"

    # Check requests
    assert len(result["requests"]) == 1
    req = result["requests"][0]
    assert req["name"] == "raw_orders"
    assert req["kind"] == "http"
    assert req["path"] == "/v1/orders"

    # Check transform
    assert result["transform"]["step_count"] == 1
    step = result["transform"]["steps"][0]
    assert step["name"] == "clean_orders"
    assert "SELECT record->>'id'" in step["select_sql"]
    assert any(inp["name"] == "raw_orders" for inp in step["inputs"])
    assert "order_id" in step["projected_columns"]
    assert "status" in step["projected_columns"]
    assert "total" in step["projected_columns"]

    # Check export
    assert len(result["exports"]) == 1
    exp = result["exports"][0]
    assert exp["name"] == "orders"
    assert exp["step"] == "clean_orders"
    assert exp["primary_key"] == ["order_id"]
    assert exp["primary_key_valid"] is True
    assert exp["primary_key_status"] == "verified"


def test_inspect_stream_transform_not_found():
    result = inspect_stream_transform(FIXTURE_PATH, "unknown_stream_xyz")

    assert result["found"] is False
    assert "not found" in result["error"]
    assert "orders" in result["available_streams"]


def test_extract_projected_columns_sqlglot():
    from streamwright_mcp.inspector import _extract_projected_columns, _extract_sql_sources

    # Function calls, expressions, aliases
    sql1 = "SELECT record->>'id' AS order_id, strptime(record->>'dt', '%Y-%m-%d') AS created_at, total FROM raw_orders"
    assert _extract_projected_columns(sql1) == ["order_id", "created_at", "total"]
    assert _extract_sql_sources(sql1) == ["raw_orders"]

    # Star wildcard
    sql2 = "SELECT * FROM orders_flat"
    assert _extract_projected_columns(sql2) == ["*"]
    assert _extract_sql_sources(sql2) == ["orders_flat"]

    # Joins
    sql3 = "SELECT o.id, c.name AS customer_name FROM orders o JOIN customers c ON o.cid = c.id"
    assert _extract_projected_columns(sql3) == ["id", "customer_name"]
    assert _extract_sql_sources(sql3) == ["customers", "orders"]


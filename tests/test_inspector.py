import pytest
from streamwright_mcp.inspector import inspect_stream_transform


def test_inspect_stream_transform():
    example_path = "/Users/kjaganathan/repos/streamwright/examples/sources/ads/openai_ads"
    result = inspect_stream_transform(example_path, "ad_accounts")

    assert result["found"] is True
    assert result["stream_name"] == "ad_accounts"
    assert result["source_name"] == "openai_ads_demo"

    # Check requests
    assert len(result["requests"]) == 1
    req = result["requests"][0]
    assert req["name"] == "raw_ad_accounts"
    assert req["kind"] == "http"
    assert req["path"] == "/v1/ad_accounts"

    # Check transform
    assert result["transform"]["step_count"] == 1
    step = result["transform"]["steps"][0]
    assert step["name"] == "ad_accounts"
    assert "SELECT record->>'id'" in step["select_sql"]
    assert any(inp["name"] == "raw_ad_accounts" for inp in step["inputs"])

    # Check export
    assert len(result["exports"]) == 1
    exp = result["exports"][0]
    assert exp["name"] == "ad_accounts"
    assert exp["step"] == "ad_accounts"
    assert exp["primary_key"] == ["account_id"]


def test_inspect_stream_transform_not_found():
    example_path = "/Users/kjaganathan/repos/streamwright/examples/sources/ads/openai_ads"
    result = inspect_stream_transform(example_path, "unknown_stream_xyz")

    assert result["found"] is False
    assert "not found" in result["error"]
    assert "ad_accounts" in result["available_streams"]

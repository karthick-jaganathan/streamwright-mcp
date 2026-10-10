import os
import pytest
from streamwright_mcp.validator import validate_source_config


def test_validate_source_config_valid():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example_path = "/Users/kjaganathan/repos/streamwright/examples/sources/ads/openai_ads"
    result = validate_source_config(example_path)
    assert result["valid"] is True
    assert result["error_count"] == 0
    assert "Valid" in result["summary"]


def test_validate_source_config_not_found():
    result = validate_source_config("/nonexistent/directory/path/12345")
    assert result["valid"] is False
    assert result["error_count"] == 1
    assert result["errors"][0]["code"] == "not-found"

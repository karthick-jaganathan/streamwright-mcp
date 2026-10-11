from pathlib import Path
import pytest
from streamwright_mcp.validator import validate_source_config

FIXTURE_PATH = str(Path(__file__).parent / "fixtures" / "sample_pipeline")


def test_validate_source_config_valid():
    result = validate_source_config(FIXTURE_PATH)
    assert result["valid"] is True
    assert result["error_count"] == 0
    assert "Valid" in result["summary"]


def test_validate_source_config_not_found():
    result = validate_source_config("/nonexistent/directory/path/12345")
    assert result["valid"] is False
    assert result["error_count"] == 1
    assert result["errors"][0]["code"] == "not-found"

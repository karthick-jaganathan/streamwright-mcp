"""
Source configuration validation wrapper for StreamWright MCP.

Validates StreamWright source directories without executing them,
returning structured file-and-line diagnostics.
"""

import os
from typing import Any, Dict, List

from streamwright.core.validation.engine import validate_source


def validate_source_config(source_dir: str) -> Dict[str, Any]:
    """
    Validates a StreamWright source folder (source.yaml and streams/*.yaml).

    Args:
        source_dir: Absolute or relative path to the source directory.

    Returns:
        Structured diagnostic dictionary with valid status, error count, warning count,
        and list of issue items.
    """
    abs_path = os.path.abspath(os.path.expanduser(source_dir))
    if not os.path.exists(abs_path):
        return {
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{
                "severity": "error",
                "code": "not-found",
                "message": f"Source directory '{source_dir}' does not exist.",
                "file": source_dir,
                "line": None,
                "column": None,
                "path": "",
            }],
            "warnings": [],
            "summary": f"Failed: Directory '{source_dir}' does not exist.",
        }

    try:
        issues = validate_source(abs_path)
    except Exception as exc:
        return {
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{
                "severity": "error",
                "code": "validator-exception",
                "message": str(exc),
                "file": source_dir,
                "line": None,
                "column": None,
                "path": "",
            }],
            "warnings": [],
            "summary": f"Validation failed with exception: {exc}",
        }

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    for issue in issues:
        item = {
            "severity": issue.severity,
            "code": getattr(issue, "code", ""),
            "message": issue.message,
            "file": getattr(issue, "file", None),
            "line": getattr(issue, "line", None),
            "column": getattr(issue, "column", None),
            "path": getattr(issue, "path", ""),
        }
        if issue.severity == "error":
            errors.append(item)
        else:
            warnings.append(item)

    is_valid = len(errors) == 0
    if is_valid:
        if len(warnings) == 0:
            summary = f"Valid: Source '{os.path.basename(abs_path)}' has no errors or warnings."
        else:
            summary = f"Valid with warnings: Source '{os.path.basename(abs_path)}' has {len(warnings)} warning(s)."
    else:
        summary = f"Invalid: Source '{os.path.basename(abs_path)}' has {len(errors)} error(s) and {len(warnings)} warning(s)."

    return {
        "valid": is_valid,
        "source_path": abs_path,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }

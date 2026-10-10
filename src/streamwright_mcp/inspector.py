"""
Stream transformation and SQL inspection engine for StreamWright MCP.

Analyzes pipeline stream configurations, requests, DuckDB SQL transform steps,
and export definitions.
"""

import os
import re
from typing import Any, Dict, List, Optional

from streamwright.core.config.loader import load_source

_TABLE_REF = re.compile(r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)\b|\bJOIN\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)


def _extract_sql_sources(sql: str) -> List[str]:
    """Extracts table names referenced in FROM or JOIN clauses."""
    sources = set()
    for match in _TABLE_REF.finditer(sql):
        t1, t2 = match.groups()
        table = t1 or t2
        if table:
            sources.add(table)
    return sorted(list(sources))


def inspect_stream_transform(source_dir: str, stream_name: str) -> Dict[str, Any]:
    """
    Parses and inspects a specific stream's requests, SQL transformations, and exports.

    Args:
        source_dir: Absolute or relative path to the source directory.
        stream_name: Name of the stream to inspect.

    Returns:
        Structured breakdown of the stream's execution plan.
    """
    abs_path = os.path.abspath(os.path.expanduser(source_dir))
    if not os.path.exists(abs_path):
        return {
            "found": False,
            "error": f"Source directory '{source_dir}' does not exist.",
        }

    try:
        source_data = load_source(abs_path)
    except Exception as exc:
        return {
            "found": False,
            "error": f"Failed to load source at '{source_dir}': {exc}",
        }

    streams = source_data.get("streams", [])
    matched_stream: Optional[Dict[str, Any]] = None
    all_stream_names = []

    for s in streams:
        name = s.get("name")
        if name:
            all_stream_names.append(name)
            if name == stream_name:
                matched_stream = s

    if not matched_stream:
        return {
            "found": False,
            "stream_name": stream_name,
            "error": f"Stream '{stream_name}' not found in source '{abs_path}'.",
            "available_streams": all_stream_names,
        }

    # Analyze requests
    raw_requests = matched_stream.get("requests", [])
    parsed_requests = []
    request_names = set()
    for req in raw_requests:
        req_name = req.get("name")
        if req_name:
            request_names.add(req_name)
        if "http" in req:
            http_spec = req.get("http", {})
            parsed_requests.append({
                "name": req_name,
                "kind": "http",
                "method": http_spec.get("method", "GET"),
                "path": http_spec.get("path"),
                "params": http_spec.get("params"),
            })
        elif "sdk" in req:
            parsed_requests.append({
                "name": req_name,
                "kind": "sdk",
                "sdk": req.get("sdk"),
                "service": req.get("service"),
                "method": req.get("method"),
                "arguments": req.get("arguments"),
            })
        else:
            parsed_requests.append({
                "name": req_name,
                "kind": "custom",
                "spec": req,
            })

    # Analyze transform steps
    transform_block = matched_stream.get("transform", {})
    mode = transform_block.get("mode", "page")
    steps = transform_block.get("steps", [])

    # If steps is not in transform dict (e.g. shorthand transform: [...])
    if isinstance(transform_block, list):
        steps = transform_block
        mode = "page"

    parsed_steps = []
    for step in steps:
        step_name = step.get("name")
        select_sql = step.get("select", "").strip()
        referenced_tables = _extract_sql_sources(select_sql)

        # Distinguish whether input is a raw request table or intermediate step
        inputs = []
        for ref in referenced_tables:
            if ref in request_names:
                inputs.append({"name": ref, "type": "request"})
            else:
                inputs.append({"name": ref, "type": "step_or_table"})

        parsed_steps.append({
            "name": step_name,
            "description": step.get("description"),
            "select_sql": select_sql,
            "inputs": inputs,
        })

    # Analyze exports
    exports_block = matched_stream.get("export", {})
    parsed_exports = []
    if isinstance(exports_block, dict):
        for exp_name, exp_cfg in exports_block.items():
            if isinstance(exp_cfg, dict):
                parsed_exports.append({
                    "name": exp_name,
                    "step": exp_cfg.get("step"),
                    "primary_key": exp_cfg.get("primary_key", []),
                    "description": exp_cfg.get("description"),
                })
            elif isinstance(exp_cfg, str):
                parsed_exports.append({
                    "name": exp_name,
                    "step": exp_cfg,
                    "primary_key": [],
                })

    return {
        "found": True,
        "stream_name": stream_name,
        "source_name": source_data.get("name"),
        "description": matched_stream.get("description"),
        "partitions": matched_stream.get("partitions"),
        "incremental": matched_stream.get("incremental"),
        "requests": parsed_requests,
        "transform": {
            "mode": mode,
            "step_count": len(parsed_steps),
            "steps": parsed_steps,
        },
        "exports": parsed_exports,
    }

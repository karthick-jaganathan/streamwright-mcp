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


try:
    import sqlglot
    from sqlglot import parse_one, exp
    _SQLGLOT_AVAILABLE = True
except ImportError:
    _SQLGLOT_AVAILABLE = False


def _extract_sql_sources(sql: str) -> List[str]:
    """Extracts table names referenced in FROM or JOIN clauses using sqlglot AST parsing."""
    if not sql or not sql.strip():
        return []

    if _SQLGLOT_AVAILABLE:
        try:
            ast = parse_one(sql.strip(), read="duckdb")
            if ast:
                tables = [t.name for t in ast.find_all(exp.Table) if t.name]
                if tables:
                    return sorted(list(set(tables)))
        except Exception:
            pass

    # Regex fallback
    sources = set()
    for match in _TABLE_REF.finditer(sql):
        t1, t2 = match.groups()
        table = t1 or t2
        if table:
            sources.add(table)
    return sorted(list(sources))


def _extract_projected_columns(sql: str) -> List[str]:
    """Extracts projected column names/aliases from a DuckDB SELECT statement using sqlglot."""
    if not sql or not sql.strip():
        return []

    if _SQLGLOT_AVAILABLE:
        try:
            ast = parse_one(sql.strip(), read="duckdb")
            if ast and hasattr(ast, "selects"):
                columns = []
                for expr in ast.selects:
                    if isinstance(expr, exp.Star):
                        columns.append("*")
                    elif expr.output_name:
                        columns.append(expr.output_name)
                    elif expr.alias_or_name:
                        columns.append(expr.alias_or_name)
                if columns:
                    return columns
        except Exception:
            pass

    # Fallback parser for templated / partial expressions
    match = re.search(r'^\s*SELECT\s+(.*?)\s+FROM\b', sql, re.IGNORECASE | re.DOTALL)
    if not match:
        aliases = re.findall(r'\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b', sql, re.IGNORECASE)
        return sorted(list(set(aliases)))

    select_clause = match.group(1).strip()
    if select_clause == '*':
        return ['*']

    parts = []
    current = []
    depth = 0
    for char in select_clause:
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append(''.join(current).strip())

    columns = []
    for part in parts:
        as_match = re.search(r'\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', part, re.IGNORECASE)
        if as_match:
            columns.append(as_match.group(1))
            continue
        id_match = re.search(r'^(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)$', part)
        if id_match:
            columns.append(id_match.group(1))
            continue
        as_inner = re.search(r'\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b', part, re.IGNORECASE)
        if as_inner:
            columns.append(as_inner.group(1))

    return columns


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
    raw_requests = matched_stream.get("requests")
    if raw_requests is None:
        single_req = matched_stream.get("request")
        raw_requests = [single_req] if isinstance(single_req, dict) else []

    parsed_requests = []
    request_names = set()
    for req in raw_requests:
        req_name = req.get("name") or f"raw_{stream_name}"
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
        elif "path" in req or "method" in req:
            parsed_requests.append({
                "name": req_name,
                "kind": "http",
                "method": req.get("method", "GET"),
                "path": req.get("path"),
                "params": req.get("params"),
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

    step_columns_map = {}
    parsed_steps = []
    for step in steps:
        step_name = step.get("name")
        select_sql = step.get("select", "").strip()
        referenced_tables = _extract_sql_sources(select_sql)
        projected_cols = _extract_projected_columns(select_sql)
        if step_name:
            step_columns_map[step_name] = projected_cols

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
            "projected_columns": projected_cols,
        })

    # Analyze exports
    exports_block = matched_stream.get("export") or matched_stream.get("exports") or {}
    parsed_exports = []
    if isinstance(exports_block, dict):
        for exp_name, exp_cfg in exports_block.items():
            if isinstance(exp_cfg, dict):
                step_ref = exp_cfg.get("step")
                pks = exp_cfg.get("primary_key", [])
                if isinstance(pks, str):
                    pks = [pks]

                step_cols = step_columns_map.get(step_ref, [])
                pk_valid = None
                if step_cols and "*" in step_cols:
                    pk_status = "unverified (wildcard SELECT *)"
                elif step_cols and pks:
                    missing = [k for k in pks if k not in step_cols]
                    if not missing:
                        pk_status = "verified"
                        pk_valid = True
                    else:
                        pk_status = f"unverified (missing in step projections: {missing})"
                        pk_valid = False
                elif not pks:
                    pk_status = "no primary_key defined"
                    pk_valid = True
                else:
                    pk_status = "unverified (step projections not detected)"

                parsed_exports.append({
                    "name": exp_name,
                    "step": step_ref,
                    "primary_key": pks,
                    "primary_key_status": pk_status,
                    "primary_key_valid": pk_valid,
                    "description": exp_cfg.get("description"),
                })
            elif isinstance(exp_cfg, str):
                parsed_exports.append({
                    "name": exp_name,
                    "step": exp_cfg,
                    "primary_key": [],
                    "primary_key_status": "no primary_key defined",
                    "primary_key_valid": True,
                })

    return {
        "found": True,
        "stream_name": stream_name,
        "source_name": source_data.get("source", {}).get("name") if isinstance(source_data.get("source"), dict) else source_data.get("name"),
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

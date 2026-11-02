"""`inspect_stream_transform`: a stream's requests, steps, reads, columns and exports, from the source engine's plan."""

from typing import Any

from streamwright.core.config.loader import SourceFilesError, load_source
from streamwright.core.engine.sql import StreamPlan, plan_source
from streamwright.core.runtime.components import request_body

from streamwright.mcp.workspace import WorkspaceError, resolve_workspace_path


def _request_kind(body: dict[str, Any]) -> str:
    if "sdk" in body:
        return "sdk"
    return "async_job" if "async_job" in body else "http"


def _requests(plan: StreamPlan) -> list[dict[str, Any]]:
    return [{"name": item["name"], "kind": _request_kind(request_body(item)), "spec": request_body(item)}
            for _, item in plan.requests]


def _steps(plan: StreamPlan) -> list[dict[str, Any]]:
    request_names = {item["name"].lower() for _, item in plan.requests}
    steps = []
    for _, step in plan.steps:
        reads = sorted(plan.reads.get(step["name"], ()))
        steps.append({
            "name": step["name"],
            "description": step.get("description"),
            "select_sql": step["select"].strip() if isinstance(step.get("select"), str) else None,
            "reads": [{"name": name, "type": "request" if name in request_names else "step"} for name in reads],
            "parameters": plan.parameters.get(step["name"], []),
            "columns": [{"name": name, "type": type_name} for name, type_name in plan.columns.get(step["name"], [])],
        })
    return steps


def _exports(plan: StreamPlan) -> list[dict[str, Any]]:
    exports = []
    for name, spec, step in plan.exports:
        columns = plan.export_columns(name)
        primary_key = spec.get("primary_key") or []
        primary_key = [primary_key] if isinstance(primary_key, str) else list(primary_key)
        known = None if columns is None else [column for column, _ in columns]
        missing = None if known is None else [key for key in primary_key if key not in known]
        exports.append({
            "name": name,
            "step": step,
            "description": spec.get("description"),
            "primary_key": primary_key,
            "primary_key_valid": None if missing is None else not missing,
            "primary_key_missing": missing,
        })
    return exports


def inspect_stream_transform(source_dir: str, stream_name: str) -> dict[str, Any]:
    """The plan of one stream of the source at `source_dir` (inside the workspace roots)."""
    try:
        path = resolve_workspace_path(source_dir, "source_dir")
        source = load_source(path)
    except (WorkspaceError, SourceFilesError) as exc:
        return {"found": False, "error": str(exc)}
    if not isinstance(source, dict):
        return {"found": False, "error": "The source is not a mapping; run validate_source_config for details."}
    plan = plan_source(source)
    name = plan.names.get(stream_name.lower())
    if name is None:
        return {"found": False, "stream_name": stream_name, "error": f"Stream '{stream_name}' not found in the source.",
                "available_streams": list(plan.streams)}
    stream = plan.streams[name]
    return {
        "found": True,
        "stream_name": name,
        "source_name": source.get("name"),
        "description": stream.stream.get("description"),
        "partitions": stream.stream.get("partitions"),
        "incremental": stream.stream.get("incremental"),
        "requests": _requests(stream),
        "transform": {"mode": stream.mode, "steps": _steps(stream)},
        "exports": _exports(stream),
        "problems": plan.messages([name]),
    }

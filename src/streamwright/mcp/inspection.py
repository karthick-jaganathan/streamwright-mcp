#!/usr/bin/env python
# /*************************************************************************
# * Copyright 2026 Karthick Jaganathan
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# **************************************************************************/

"""`inspect_stream_transform`: a stream's requests, steps, reads, columns and exports, from the source engine's plan."""

from typing import Any

from streamwright.core.config import grammar
from streamwright.core.config.loader import SourceFilesError, read_source
from streamwright.core.engine.sql import StreamPlan, plan_source

from streamwright.mcp.workspace import WorkspaceError, confine_source, resolve_workspace_path


def _request_kind(item: dict[str, Any]) -> str:
    if "async_job" in item:
        return "async_job"
    return "http" if grammar.operation_kind(item.get("operation")) == "request" else "call"


def _requests(plan: StreamPlan, written: dict[str, Any]) -> list[dict[str, Any]]:
    """The stream's requests as the source writes them (`operation:` or `async_job:`), each with its kind."""
    items = {item.get("name"): item for item in written.get("requests") or () if isinstance(item, dict)}
    requests = []
    for _, item in plan.requests:
        public = items.get(item["name"], {})
        requests.append({"name": item["name"], "kind": _request_kind(public),
                         "spec": {key: value for key, value in public.items() if key not in ("name", "partitions")}})
    return requests


def _written_stream(source: dict[str, Any], name: str) -> dict[str, Any]:
    streams = source.get("streams")
    return next((stream for stream in streams if isinstance(stream, dict) and stream.get("name") == name), {}) \
        if isinstance(streams, list) else {}


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
        confine_source(path)
        source = read_source(path)
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
        "requests": _requests(stream, _written_stream(source, name)),
        "transform": {"mode": stream.mode, "steps": _steps(stream)},
        "exports": _exports(stream),
        "problems": plan.messages([name]),
    }

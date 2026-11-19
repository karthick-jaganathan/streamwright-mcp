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

"""
The validate tools: thin wrappers that confine client-supplied paths to the workspace and call the engine's own
validation, so the verdict is the one `streamwright validate` gives.
"""

from typing import Any

from streamwright.core.cli import detect_kind

from streamwright.mcp.engines import SOURCE_KIND, EngineDescriptor, EngineRegistry
from streamwright.mcp.report import Report, failure
from streamwright.mcp.workspace import WorkspaceError, check_content_size, confine_source, resolve_workspace_path


def validate_source_config(registry: EngineRegistry, source_dir: str, strict: bool = False) -> dict[str, Any]:
    """Validates a source folder or file; a path holding a job manifest is validated by that job's engine."""
    try:
        path = resolve_workspace_path(source_dir, "source_dir")
        confine_source(path)                # before anything is read: what the source's files resolve to
    except WorkspaceError as exc:
        return failure(SOURCE_KIND, "path-not-allowed", str(exc), source_dir).to_dict()
    kind = detect_kind(path) or SOURCE_KIND
    engine = registry.get(kind)
    if engine is None:
        installed = ", ".join(registry.kinds())
        message = f"No installed engine runs `kind: {kind}` (installed: {installed})."
        return failure(kind, "unknown-kind", message, path).to_dict()
    return engine.validate(path=path, strict=strict).to_dict()


def validate_job(
    engine: EngineDescriptor,
    content: str | None = None,
    path: str | None = None,
    *,
    config: dict[str, Any] | None = None,
    overlays: list[str] | None = None,
    strict: bool = False,
    analyze: bool = False,
) -> dict[str, Any]:
    """Validates a job manifest given as `content` or `path`; the plan is reported only when `analyze`."""
    if (content is None) == (path is None):
        return failure(engine.kind, "bad-arguments", "Give exactly one of 'content' or 'path'.").to_dict()
    try:
        resolved = resolve_workspace_path(path, "path") if path is not None else None
        resolved_overlays = [resolve_workspace_path(overlay, "overlays") for overlay in overlays or []]
        if content is not None:
            check_content_size(content)
    except WorkspaceError as exc:
        return failure(engine.kind, "path-not-allowed", str(exc)).to_dict()
    report: Report = engine.validate(path=resolved, content=content, overlays=resolved_overlays, config=config,
                                     strict=strict)
    if not analyze:
        report.plan = None
    return report.to_dict()

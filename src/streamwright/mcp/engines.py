"""
The engines the MCP server can describe and validate, discovered from installed plug-ins.

An engine is `source` (core's own) or a job kind registered in the `streamwright.job_kinds` entry-point group, whose
entry point is a `streamwright.core.jobs.engine.JobEngine` object: the server uses only that protocol.
"""

import inspect
import os
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from streamwright.core.jobs.engine import JobEngine, engine_name, load_job_engine
from streamwright.core.runtime import components, plugins
from streamwright.core.runtime.definitions import engine_connectors
from streamwright.core.validation import Issue
from streamwright.core.validation import schema as source_schema
from streamwright.core.validation.engine import check_components, is_valid, validate_source, validate_text

from streamwright.mcp.report import Report

SOURCE_KIND = "source"
_HEADING = re.compile(r"^#{2,3} +(.+?) *$", re.MULTILINE)


class EngineError(ToolError, ResourceError):
    """A request names an engine, schema or guide section that is not available (the message reaches the client)."""


@dataclass(frozen=True)
class EngineDescriptor:
    """What every tool and resource needs from one engine; the only per-engine code path of the server."""

    kind: str
    key: str
    title: str
    schemas: Mapping[str, Callable[[], dict[str, Any]]]
    guide: Callable[[str | None], dict[str, Any]]
    validate: Callable[..., Report]
    describe_connector: Callable[[str], dict[str, Any] | None]

    def connectors(self) -> list[dict[str, Any]]:
        """Name, distribution and version of the installed connectors with an adapter for this engine (their
        definitions say so; only the connectors' specs are imported)."""
        return engine_connectors(self.key)


class EngineRegistry:
    """The descriptors of the installed engines, by kind, and the engines that could not be loaded."""

    def __init__(self, engines: list[EngineDescriptor], problems: dict[str, str] | None = None):
        self._engines = {engine.kind: engine for engine in engines}
        self.problems = dict(problems or {})

    def __iter__(self) -> Iterator[EngineDescriptor]:
        return iter(self._engines.values())

    def kinds(self) -> list[str]:
        return list(self._engines)

    def job_engines(self) -> list[EngineDescriptor]:
        return [engine for engine in self if engine.kind != SOURCE_KIND]

    def get(self, kind: str) -> EngineDescriptor | None:
        return self._engines.get(kind)

    def find(self, name: str) -> EngineDescriptor | None:
        """The engine named by its kind (`DuckDBJob`) or key (`duckdb`), ignoring case."""
        wanted = (name or "").strip().lower()
        for engine in self:
            if wanted in (engine.kind.lower(), engine.key):
                return engine
        return None

    def find_schema(self, name: str) -> tuple[EngineDescriptor, str] | None:
        """The engine and schema name for `name`: an engine, or a schema such as `stream`."""
        wanted = (name or "").strip().lower()
        for engine in self:
            if wanted in (engine.kind.lower(), engine.key):
                return engine, next(iter(engine.schemas))
            if wanted in engine.schemas:
                return engine, wanted
        return None


def split_sections(text: str) -> dict[str, str]:
    """A markdown document by heading: {heading: text of the section}."""
    matches = list(_HEADING.finditer(text))
    sections = {}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.start():end].strip()
    return sections


def paged_guide(text: str) -> Callable[[str | None], dict[str, Any]]:
    """A guide(section) over a markdown document: the section titles, or one section found by title."""
    sections = split_sections(text)

    def guide(section: str | None = None) -> dict[str, Any]:
        if not section:
            return {"sections": list(sections)}
        wanted = section.strip().lower()
        for title, body in sections.items():
            if wanted in title.lower():
                return {"section": title, "text": body}
        raise EngineError(f"unknown guide section '{section}'; sections: {', '.join(sections)}")

    return guide


def _source_report(issues: list[Issue], strict: bool, path: str | None) -> Report:
    subject = {"name": os.path.basename(path.rstrip(os.sep)), "path": path} if path else None
    return Report(SOURCE_KIND, is_valid(issues, strict=strict), issues, subject)


def _validate_source(path=None, content=None, overlays=(), config=None, strict=False) -> Report:
    if overlays or config:
        raise ValueError("a source takes neither overlays nor config values")
    if content is not None:
        return _source_report(validate_text(content, source_check=check_components), strict, None)
    return _source_report(validate_source(path, source_check=check_components), strict, path)


def source_engine() -> EngineDescriptor:
    return EngineDescriptor(
        kind=SOURCE_KIND,
        key=SOURCE_KIND,
        title="Source (kind: source): source.yaml and streams/*.yaml, run by the source engine",
        schemas={"source": source_schema.json_schema, "stream": source_schema.stream_json_schema},
        guide=paged_guide(inspect.getdoc(source_schema) or ""),
        validate=_validate_source,
        describe_connector=components.describe,
    )


def _job_subject(job: Mapping[str, Any] | None, path: str | None) -> dict[str, Any] | None:
    if job is None:
        return {"path": path} if path else None
    steps, outputs, connections = job.get("steps"), job.get("outputs"), job.get("connections")
    subject = {
        "name": job.get("name"),
        "kind": job.get("kind"),
        "step_count": len(steps) if isinstance(steps, list) else 0,
        "output_count": len(outputs) if isinstance(outputs, list) else 0,
        "connection_count": len(connections) if isinstance(connections, dict) else 0,
    }
    if path:
        subject["path"] = path
    return subject


def _job_report(kind: str, result: Any, path: str | None) -> Report:
    return Report(kind, result.valid, list(result.issues), _job_subject(result.job, path), result.plan)


def job_engine(engine: JobEngine) -> EngineDescriptor:
    kind = engine.kind
    key = engine_name(kind)

    def validate(path=None, content=None, overlays=(), config=None, strict=False) -> Report:
        if content is not None:
            result = engine.validate_job_text(content, overlays=overlays, config=config, strict=strict)
        else:
            result = engine.validate_job(path, overlays=overlays, config=config, strict=strict)
        return _job_report(kind, result, path)

    def describe_connector(name: str) -> dict[str, Any] | None:
        description = engine.describe_connector(name)
        return None if description is None else {"name": name, "kind": "connector", "engine": kind, **description}

    return EngineDescriptor(
        kind=kind,
        key=key,
        title=f"{kind}: a job manifest run by the {key} engine",
        schemas={key: engine.json_schema},
        guide=paged_guide(engine.guide()),
        validate=validate,
        describe_connector=describe_connector,
    )


def discover_engines(entry_points=None) -> EngineRegistry:
    """The `source` engine and one engine per installed job kind (a kind that cannot be loaded is a problem)."""
    engines, problems = [source_engine()], {}
    for entry in plugins.discover(plugins.JOB_KINDS, entry_points=entry_points):
        kind = entry["name"]
        try:
            engines.append(job_engine(load_job_engine(kind, entry_points=entry_points)))
        except plugins.PluginError as exc:
            problems[kind] = str(exc)
    return EngineRegistry(engines, problems)

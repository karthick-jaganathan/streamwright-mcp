"""Schemas and guides, served from the engines: a small index by default, then one schema or section at a time."""

from typing import Any

from streamwright.core.validation import schema as source_schema

from streamwright.mcp.engines import EngineDescriptor, EngineError, EngineRegistry


def _sections(schema: dict[str, Any]) -> list[str]:
    return sorted(set(schema.get("definitions", {})) | set(schema.get("properties", {})))


def _index(registry: EngineRegistry) -> dict[str, Any]:
    engines = []
    for engine in registry:
        schemas = {name: {"sections": _sections(build())} for name, build in engine.schemas.items()}
        engines.append({"kind": engine.kind, "title": engine.title, "schemas": schemas})
    return {
        "version": source_schema.VERSION,
        "supported_versions": list(source_schema.SUPPORTED_VERSIONS),
        "engines": engines,
        "unavailable": registry.problems,
        "usage": "Call get_core_schema(kind=<engine or schema name>) for a schema, add section=<name> for one "
                 "definition; get_engine_guide(kind) for the engine's guide.",
    }


def get_core_schema(registry: EngineRegistry, kind: str | None = None, section: str | None = None) -> dict[str, Any]:
    """The index of schemas (no `kind`), one schema, or one section of one schema; unknown names are errors."""
    if kind is None:
        if section is not None:
            raise EngineError("'section' needs a 'kind'; call get_core_schema() for the index.")
        return _index(registry)
    found = registry.find_schema(kind)
    if found is None:
        names = list(dict.fromkeys(name for engine in registry for name in (engine.kind, *engine.schemas)))
        raise EngineError(f"Unknown kind '{kind}'; available: {', '.join(names)}.")
    engine, name = found
    schema = engine.schemas[name]()
    result: dict[str, Any] = {"version": source_schema.VERSION, "kind": engine.kind, "schema_name": name}
    if section is None:
        return {**result, "schema": schema}
    wanted = section.replace("definitions.", "").strip().lower()
    for container in ("definitions", "properties"):
        definition = schema.get(container, {}).get(wanted)
        if definition is not None:
            return {**result, "section": wanted, "definition": definition}
    raise EngineError(f"Section '{section}' is not in the {name} schema; sections: {', '.join(_sections(schema))}.")


def _guide_of(registry: EngineRegistry, kind: str) -> EngineDescriptor:
    engine = registry.find(kind)
    if engine is None:
        raise EngineError(f"Unknown engine '{kind}'; installed engines: {', '.join(registry.kinds())}.")
    return engine


def get_engine_guide(registry: EngineRegistry, kind: str, section: str | None = None) -> dict[str, Any]:
    """An engine's guide: its section titles, or one section by title."""
    engine = _guide_of(registry, kind)
    return {"kind": engine.kind, **engine.guide(section)}

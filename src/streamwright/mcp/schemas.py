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

"""Schemas and guides, served from the engines: a small index by default, then one schema or section at a time."""

from typing import Any

from streamwright.core.validation import schema as source_schema

from streamwright.mcp.engines import EngineDescriptor, EngineError, EngineRegistry

_LINE = 160   # the characters of a description an outline keeps (its first line)


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


def _deref(schema: dict[str, Any], node: Any) -> dict[str, Any]:
    while isinstance(node, dict) and str(node.get("$ref", "")).startswith("#/"):
        target: Any = schema
        for part in node["$ref"][2:].split("/"):
            target = target.get(part, {}) if isinstance(target, dict) else {}
        node = target
    return node if isinstance(node, dict) else {}


def _children(schema: dict[str, Any], node: Any) -> dict[str, Any]:
    """The named sub-schemas below `node`: its properties, through $ref, items, additionalProperties and *Of."""
    node = _deref(schema, node)
    found = dict(node.get("properties", {}))
    for key in ("items", "additionalProperties"):
        if isinstance(node.get(key), dict):
            found = {**_children(schema, node[key]), **found}
    for key in ("oneOf", "anyOf", "allOf"):
        for option in node.get(key, []):
            found = {**_children(schema, option), **found}
    return found


def _line(node: dict[str, Any]) -> str:
    return (node.get("description") or "").strip().split("\n")[0][:_LINE]


def _type(node: dict[str, Any]) -> Any:
    if "type" in node:
        return node["type"]
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    options = node.get("oneOf") or node.get("anyOf") or []
    return [_type(option) for option in options] or ("enum" if "enum" in node else None)


def _outline(schema: dict[str, Any]) -> dict[str, Any]:
    properties = {name: {key: value for key, value in (("type", _type(node)), ("description", _line(node)),
                                                       ("fields", list(_children(schema, node)))) if value}
                  for name, node in schema.get("properties", {}).items()}
    definitions = {name: _line(node) for name, node in schema.get("definitions", {}).items()}
    return {"description": _line(schema), "properties": properties, "definitions": definitions,
            "usage": "add section=<definition> or a dotted path through properties (e.g. <property>.<field>) for "
                     "one part in full"}


def _section(schema: dict[str, Any], name: str, section: str) -> dict[str, Any]:
    """A definition by name, or the sub-schema at a dotted path through the properties (from a definition too)."""
    wanted = section.replace("definitions.", "").strip().lower()
    node: Any = schema
    reached: list[str] = []
    for part in wanted.split("."):
        children = _children(schema, node) if reached else {**_children(schema, schema),
                                                             **schema.get("definitions", {})}
        if part not in children:
            where = f"below '{'.'.join(reached)}'" if reached else "sections"
            raise EngineError(f"Section '{section}' is not in the {name} schema; {where}: "
                              f"{', '.join(sorted(children)) or 'nothing'}.")
        node, reached = children[part], [*reached, part]
    return {"section": wanted, "definition": _deref(schema, node) or node}


def get_core_schema(registry: EngineRegistry, kind: str | None = None, section: str | None = None) -> dict[str, Any]:
    """The index of schemas (no `kind`), one schema's outline, or one section of it; unknown names are errors."""
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
        return {**result, "outline": _outline(schema)}
    return {**result, **_section(schema, name, section)}


def _guide_of(registry: EngineRegistry, kind: str) -> EngineDescriptor:
    engine = registry.find(kind)
    if engine is None:
        raise EngineError(f"Unknown engine '{kind}'; installed engines: {', '.join(registry.kinds())}.")
    return engine


def get_engine_guide(registry: EngineRegistry, kind: str, section: str | None = None) -> dict[str, Any]:
    """An engine's guide: its section titles, or one section by title."""
    engine = _guide_of(registry, kind)
    return {"kind": engine.kind, **engine.guide(section)}

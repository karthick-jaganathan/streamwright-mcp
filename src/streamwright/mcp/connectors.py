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

"""Connector listing and contracts: installed connectors from their definitions, contracts from the engines."""

import re
from typing import Any

from streamwright.core import catalog
from streamwright.core.jobs.state.url import DRIVERS, missing_driver
from streamwright.core.runtime import components

from streamwright.mcp.engines import SOURCE_KIND, EngineDescriptor, EngineError, EngineRegistry, paged_guide

_CONNECTOR_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
_TYPE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,199}\Z")
_INSTALL_COMMAND = "streamwright connectors install {name}"
_NESTED_DEFINITION = "definition"   # a job engine's contract may nest the connector definition under this key
_OPERATION_SUMMARY = ("name", "kind", "idempotent", "max_chunk", "actions")
_OPERATION_HINT = ("operations are summarised (argument names, `required` marks the required ones); "
                   "get_connector_contract(name='{name}', operation='<operation name>') returns one in full")


def is_valid_connector_name(name: Any) -> bool:
    """Whether `name` is a plain connector identifier."""
    return isinstance(name, str) and _CONNECTOR_NAME.fullmatch(name) is not None


def _install_details(name: str, entry: dict[str, Any] | None) -> dict[str, Any]:
    details: dict[str, Any] = {"install_command": _INSTALL_COMMAND.format(name=name)}
    if entry and entry.get("install"):
        details["install"] = entry["install"]
    return details


def _catalog_entries() -> dict[str, dict[str, Any]]:
    return dict(catalog.connectors())


def _select_engines(registry: EngineRegistry, engine: str | None) -> list[EngineDescriptor]:
    if not engine:
        return list(registry)
    found = registry.find(engine)
    if found is None:
        raise EngineError(f"Unknown engine '{engine}'; installed engines: {', '.join(registry.kinds())}.")
    return [found]


def list_connectors(registry: EngineRegistry, include_hub: bool = False,
                    engine: str | None = None) -> list[dict[str, Any]]:
    """
    Installed connectors with the engines each one supports (from the connector definitions: only their specs are
    imported); with `include_hub`, also the catalog connectors that are not installed (with how to install them).
    """
    engines = _select_engines(registry, engine)
    found: dict[str, dict[str, Any]] = {}
    for descriptor in engines:
        for item in descriptor.connectors():
            entry = found.setdefault(item["name"], {"name": item["name"], "installed": True,
                                                    "distribution": item["distribution"], "version": item["version"],
                                                    "engines": [], "reach": {}})
            entry["engines"].append(descriptor.kind)
            entry["reach"][descriptor.kind] = item.get("support", "native")   # native adapter or a call step
    if include_hub:
        entries = _catalog_entries()
        for name, entry in entries.items():
            if name in found:
                found[name].update({"title": entry.get("title"), "family": entry.get("family"),
                                    "summary": entry.get("summary")})
            elif not engine:
                found[name] = {"name": name, "installed": False, "title": entry.get("title"),
                               "family": entry.get("family"), "summary": entry.get("summary"),
                               **_install_details(name, entry)}
    return [found[name] for name in sorted(found)]


def _drivers(name: str) -> dict[str, Any]:
    """The DB-API driver a database lookup on this connector's connections needs, and whether it is installed."""
    if name not in DRIVERS:
        return {}
    modules, install = DRIVERS[name]
    ready = missing_driver(name) is None
    return {"driver": {"modules": list(modules), "installed": ready, "needed_by": "database lookups (spec.lookups "
                       "type: database)", **({} if ready else {"install": install})}}


def _lean(field: Any) -> Any:
    """A declared field (a connection key, an argument) without its empty attributes: None, "", [] and {} go;
    false and 0 stay."""
    if not isinstance(field, dict):
        return field
    return {key: value for key, value in field.items() if value is not None and value not in ("", [], {})}


def _lean_fields(contract: dict[str, Any]) -> dict[str, Any]:
    """The contract with its connection keys' and operations' arguments' empty attributes left out."""
    lean = dict(contract)
    if isinstance(lean.get("connection"), dict):
        lean["connection"] = {name: _lean(field) for name, field in lean["connection"].items()}
    if isinstance(lean.get("operation"), dict) and isinstance(lean["operation"].get("arguments"), list):
        lean["operation"] = {**_lean(lean["operation"]),
                             "arguments": [_lean(argument) for argument in lean["operation"]["arguments"]]}
    return lean


def _compact_operation(operation: dict[str, Any]) -> dict[str, Any]:
    compact = {key: operation[key] for key in _OPERATION_SUMMARY if key in operation}
    if operation.get("destructive_actions"):
        compact["destructive_actions"] = operation["destructive_actions"]
    arguments = operation.get("arguments") or []
    compact["arguments"] = [argument.get("name") for argument in arguments]
    compact["required"] = [argument.get("name") for argument in arguments if argument.get("required")]
    return compact


def _flatten(contract: dict[str, Any]) -> dict[str, Any]:
    """An engine's contract as one mapping: the definition it nests (if any) under its own keys."""
    nested = contract.get(_NESTED_DEFINITION)
    if not isinstance(nested, dict):
        return contract
    return {**nested, **{key: value for key, value in contract.items() if key != _NESTED_DEFINITION}}


def _split_shared(contracts: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """The keys every engine declares with the same value, once; and per engine, only what differs."""
    flat = {kind: _flatten(contract) for kind, contract in contracts.items()}
    first = next(iter(flat.values()))
    shared = {key: value for key, value in first.items()
              if all(key in other and other[key] == value for other in flat.values())}
    differing = {kind: {key: value for key, value in contract.items() if key not in shared}
                 for kind, contract in flat.items()}
    return shared, differing


def _with_compact_operations(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract.get("operations"), list):
        return contract
    return {**contract, "operations": [_compact_operation(item) for item in contract["operations"]]}


def _one_operation(name: str, contracts: list[dict[str, Any]], wanted: str) -> dict[str, Any]:
    names: list[str] = []
    for contract in contracts:
        for operation in contract.get("operations") or []:
            if str(operation.get("name", "")).lower() == wanted.strip().lower():
                return {"name": name, "installed": True, "operation": operation}
            names.append(operation.get("name"))
    raise EngineError(f"Connector '{name}' has no operation '{wanted}'; operations: "
                      f"{', '.join(dict.fromkeys(names)) or 'none'}.")


def get_connector_contract(registry: EngineRegistry, name: str, engine: str | None = None,
                           operation: str | None = None) -> dict[str, Any]:
    """
    The contract of connector `name` as the engines declare it (nothing is connected): what all its engines share
    once, then under `engines` only what differs per engine, with operations summarised; with `operation`, that
    operation in full. When it is not installed: how to install it.
    """
    if not is_valid_connector_name(name):
        raise EngineError("Invalid connector name: expected lowercase letters, digits and '_', starting with a "
                          "letter (max 63 characters).")
    wanted = _select_engines(registry, engine)[0].kind if engine else None
    contracts: dict[str, Any] = {}
    for descriptor in registry:
        reach = {item["name"]: item.get("support", "native") for item in descriptor.connectors()}
        if name not in reach:
            continue
        if reach[name] == "call":                          # reachable through a source-adapter call step
            source = registry.find(SOURCE_KIND)
            described = source.describe_connector(name) if source is not None else None
            contracts[descriptor.kind] = {"via": "call step", **(described or {})}
            continue
        description = descriptor.describe_connector(name)
        contracts[descriptor.kind] = description or {
            "error": f"Connector '{name}' is installed but could not be loaded."}
    selected = [kind for kind in contracts if wanted in (None, kind)]
    if selected:
        shared, differing = _split_shared(contracts)
        if operation is not None:
            return _lean_fields(_one_operation(name, [shared, *differing.values()], operation))
        guide = guide_text(name)
        sections = {"guide_sections": paged_guide(guide)(None)["sections"]} if guide else {}
        engines = {kind: _with_compact_operations(differing[kind]) for kind in selected}
        shared = {key: value for key, value in _with_compact_operations(shared).items() if key != "engines"}
        return _lean_fields({**shared, "name": name, "installed": True, **_drivers(name),
                             "engines": engines, **sections, "operation_hint": _OPERATION_HINT.format(name=name)})
    if contracts:
        return {"name": name, "installed": True, "engines": {},
                "message": f"Connector '{name}' ships no adapter for {engine}; it supports: "
                           f"{', '.join(contracts)}."}
    result = {"name": name, "installed": False,
              "message": f"Connector '{name}' is not installed in the current Python environment."}
    try:
        entry = _catalog_entries().get(name)
    except RuntimeError as exc:
        entry = None
        result["catalog_error"] = str(exc)
    return {**result, **_install_details(name, entry)}


def guide_text(name: str) -> str | None:
    try:
        return components.guide(name)
    except components.ComponentLoadError:
        return None


def get_connector_guide(name: str, section: str | None = None) -> dict[str, Any]:
    """
    The user guide an installed connector ships (examples, query builders, vendor arguments, engine notes, with the
    tables generated from its definition), paged: without `section` the section titles, otherwise that section.
    """
    if not is_valid_connector_name(name):
        raise EngineError("Invalid connector name: expected lowercase letters, digits and '_', starting with a "
                          "letter (max 63 characters).")
    if name not in components.available():
        raise EngineError(f"Connector '{name}' is not installed; get_connector_contract('{name}') says how to "
                          "install it.")
    text = guide_text(name)
    if not text:
        raise EngineError(f"Connector '{name}' ships no guide; get_connector_contract('{name}') has its contract.")
    return {"name": name, **paged_guide(text)(section)}


def describe_connector_type(name: str, type_name: str) -> dict[str, Any]:
    """
    A vendor type of an installed SDK connector, read offline from its installed library: an enum's values or an
    object's fields and their types. Not found (or a REST connector, which has no library to ask): a hint instead.
    """
    if not is_valid_connector_name(name):
        raise EngineError("Invalid connector name: expected lowercase letters, digits and '_', starting with a "
                          "letter (max 63 characters).")
    if not isinstance(type_name, str) or not _TYPE_NAME.match(type_name):
        raise EngineError("Invalid type name: letters, digits, '_' and '.', starting with a letter (max 200).")
    if name not in components.available():
        raise EngineError(f"Connector '{name}' is not installed; get_connector_contract('{name}') says how to "
                          "install it.")
    if components.load(name).describe_type is None:
        return {"connector": name, "name": type_name, "found": False,
                "hint": f"'{name}' has no type lookup (REST API connectors have no library to ask): its guide lists "
                        f"the values it takes, get_connector_guide('{name}')."}
    found = components.describe_type(name, type_name)
    if found is None:
        return {"connector": name, "name": type_name, "found": False,
                "hint": "No such type in the installed library. Names are case-sensitive, as the vendor's library "
                        "spells them; an object's type lists its fields' types, which you can look up in turn."}
    return {"found": True, **found}

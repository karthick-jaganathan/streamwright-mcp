"""Connector listing and contracts: installed connectors from their definitions, contracts from the engines."""

import re
from typing import Any

from streamwright.core import catalog
from streamwright.core.runtime import components

from streamwright.mcp.engines import SOURCE_KIND, EngineDescriptor, EngineError, EngineRegistry, paged_guide

_CONNECTOR_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
_INSTALL_COMMAND = "streamwright connectors install {name}"


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


def get_connector_contract(registry: EngineRegistry, name: str, engine: str | None = None) -> dict[str, Any]:
    """
    The contract of connector `name` for each engine that has an adapter for it, as the engines declare it
    (nothing is connected). When it is not installed: how to install it.
    """
    if not is_valid_connector_name(name):
        raise EngineError("Invalid connector name: expected lowercase letters, digits and '_', starting with a "
                          "letter (max 63 characters).")
    engines = _select_engines(registry, engine)
    contracts: dict[str, Any] = {}
    for descriptor in engines:
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
    if contracts:
        guide = _guide_text(name)
        sections = {"guide_sections": paged_guide(guide)(None)["sections"]} if guide else {}
        return {"name": name, "installed": True, "engines": contracts, **sections}
    installed_elsewhere = [d.kind for d in registry if name in {item["name"] for item in d.connectors()}]
    if installed_elsewhere:
        return {"name": name, "installed": True, "engines": {},
                "message": f"Connector '{name}' ships no adapter for {engine}; it supports: "
                           f"{', '.join(installed_elsewhere)}."}
    result = {"name": name, "installed": False,
              "message": f"Connector '{name}' is not installed in the current Python environment."}
    try:
        entry = _catalog_entries().get(name)
    except RuntimeError as exc:
        entry = None
        result["catalog_error"] = str(exc)
    return {**result, **_install_details(name, entry)}


def _guide_text(name: str) -> str | None:
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
    text = _guide_text(name)
    if not text:
        raise EngineError(f"Connector '{name}' ships no guide; get_connector_contract('{name}') has its contract.")
    return {"name": name, **paged_guide(text)(section)}

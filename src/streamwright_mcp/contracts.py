"""
Dynamic reflection and in-code contract inspection for StreamWright connectors.

Zero duplication: extracts contracts, schemas, auth specifications, and execution
behaviors directly from live Python connector modules and core schema definitions.
"""

import importlib
import importlib.metadata
import inspect
from typing import Any, Dict, List, Optional

from streamwright.core.validation import schema as core_schema
from streamwright_mcp.hub import fetch_hub_connector, list_hub_connectors


def list_installed_connectors() -> List[Dict[str, Any]]:
    """
    Discovers all StreamWright connectors installed in the current Python environment
    using the 'streamwright.connectors' entry points group.
    """
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        group = eps.select(group="streamwright.connectors")
    else:
        group = eps.get("streamwright.connectors", [])

    results = []
    seen = set()

    for ep in group:
        if ep.name in seen:
            continue
        seen.add(ep.name)

        try:
            cls = ep.load()
            spec = getattr(cls, "spec", None)
            dist = getattr(ep, "dist", None)
            version = dist.version if dist else None

            results.append({
                "name": ep.name,
                "title": getattr(spec, "title", ep.name.replace("_", " ").title()) if spec else ep.name,
                "category": getattr(spec, "category", "general") if spec else "general",
                "transport": getattr(spec, "transport", "unknown") if spec else "unknown",
                "version": version,
                "installed": True,
            })
        except Exception as exc:
            results.append({
                "name": ep.name,
                "title": ep.name,
                "category": "error",
                "transport": "unknown",
                "version": None,
                "installed": False,
                "error": str(exc),
            })

    results.sort(key=lambda x: x["name"])
    return results


def get_connector_contract(name: str) -> Dict[str, Any]:
    """
    Retrieves the complete in-code contract for a connector.

    If the connector is installed, extracts its 5-part contract from module/class docstrings,
    its ConnectorSpec, auth schemas, and supported methods.
    If not installed, returns Hub installation instructions.
    """
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        group = eps.select(group="streamwright.connectors")
    else:
        group = eps.get("streamwright.connectors", [])

    matching_ep = None
    for ep in group:
        if ep.name == name:
            matching_ep = ep
            break

    if matching_ep is not None:
        try:
            cls = matching_ep.load()
            spec = getattr(cls, "spec", None)
            mod = importlib.import_module(cls.__module__)
            module_doc = inspect.getdoc(mod) or ""
            class_doc = inspect.getdoc(cls) or ""

            spec_info = {}
            if spec:
                spec_info = {
                    "name": getattr(spec, "name", name),
                    "title": getattr(spec, "title", name),
                    "category": getattr(spec, "category", None),
                    "transport": getattr(spec, "transport", None),
                    "extension": getattr(spec, "extension", None),
                    "package": getattr(spec, "package", None),
                }

            auth_required = getattr(cls, "auth_required", ())
            auth_optional = getattr(cls, "auth_optional", ())
            services = getattr(mod, "SERVICES", None) or getattr(cls, "SERVICES", None)
            default_service = getattr(mod, "DEFAULT_SERVICE", None) or getattr(cls, "DEFAULT_SERVICE", None)

            # Build full contract documentation
            contract_doc = module_doc if module_doc else class_doc

            return {
                "name": name,
                "installed": True,
                "spec": spec_info,
                "auth": {
                    "required_fields": list(auth_required) if isinstance(auth_required, (list, tuple)) else auth_required,
                    "optional_fields": list(auth_optional) if isinstance(auth_optional, (list, tuple)) else auth_optional,
                },
                "services": services,
                "default_service": default_service,
                "contract_documentation": contract_doc,
            }
        except Exception as exc:
            return {
                "name": name,
                "installed": False,
                "error": f"Failed to load installed connector: {exc}",
            }

    # Not installed: look up in StreamWright Hub
    hub_data = fetch_hub_connector(name)
    install_cmd = f"sw connectors install {name}"
    note = f"Connectors are managed through StreamWright Hub (run '{install_cmd}' or 'sw connectors -i {name}')."
    if hub_data and "install" in hub_data and isinstance(hub_data["install"], dict):
        git_target = hub_data["install"].get("git")
        if git_target:
            note += f" Direct source target: pip install \"{git_target}\""

    return {
        "name": name,
        "installed": False,
        "message": f"Connector '{name}' is not installed in the current Python environment.",
        "install_command": install_cmd,
        "note": note,
        "hub_metadata": hub_data or {
            "title": name.replace("_", " ").title(),
            "install_hint": install_cmd,
            "note": note,
        },
    }


def get_core_schema(kind: str = "all", section: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the formal JSON schema and DSL documentation for StreamWright sources and streams.

    Args:
        kind: 'source', 'stream', 'dsl' (concise markdown guide), or 'all' (default).
        section: Optional specific definition name to extract (e.g. 'paginator', 'auth', 'http_request', 'records').
    """
    if section:
        clean_section = section.replace("definitions.", "").strip().lower()
        stream_defs = core_schema.stream_json_schema().get("definitions", {})
        if clean_section in stream_defs:
            return {
                "version": core_schema.VERSION,
                "section": clean_section,
                "definition": stream_defs[clean_section],
            }
        source_defs = core_schema.json_schema().get("definitions", {})
        if clean_section in source_defs:
            return {
                "version": core_schema.VERSION,
                "section": clean_section,
                "definition": source_defs[clean_section],
            }
        available = sorted(list(set(list(stream_defs.keys()) + list(source_defs.keys()))))
        return {
            "version": core_schema.VERSION,
            "error": f"Section '{section}' not found in schema definitions.",
            "available_sections": available,
        }

    if kind == "dsl":
        return {
            "version": core_schema.VERSION,
            "supported_versions": list(core_schema.SUPPORTED_VERSIONS),
            "kind": "dsl",
            "dsl_specification": inspect.getdoc(core_schema) or "",
        }

    result: Dict[str, Any] = {
        "version": core_schema.VERSION,
        "supported_versions": list(core_schema.SUPPORTED_VERSIONS),
        "kind": kind,
    }

    if kind in ("source", "all"):
        result["source_schema"] = core_schema.json_schema()
    if kind in ("stream", "all"):
        result["stream_schema"] = core_schema.stream_json_schema()
    if kind == "all":
        result["dsl_specification"] = inspect.getdoc(core_schema) or ""

    return result


def get_cli_reference(command: Optional[str] = None) -> Dict[str, Any]:
    """
    Guides the AI assistant on how to inspect, discover, and execute StreamWright CLI commands.
    Directs the LLM to run or inspect the live CLI help directly in the user's terminal/workspace.

    Args:
        command: Optional subcommand to inspect ('run', 'validate', 'connectors', 'mcp').
    """
    subcommand = (command or "").strip().lower()

    env_hints = [
        "If 'sw' is not found in PATH, verify your active virtual environment or pyenv version.",
        "Locate the binary using: 'which sw', 'pyenv which sw', or 'which streamwright'.",
        "Direct execution via active Python interpreter: '<python_bin> -m streamwright.core.cli <args>'."
    ]

    if subcommand in ("run", "validate", "connectors", "mcp"):
        return {
            "binary": "streamwright",
            "alias": "sw",
            "command": subcommand,
            "instruction": f"To get the most accurate and up-to-date options for '{subcommand}', inspect the CLI directly by running or checking: `sw {subcommand} --help` (or `streamwright {subcommand} --help`).",
            "recommended_command": f"sw {subcommand} --help",
            "fallback_command": f"python -m streamwright.core.cli {subcommand} --help",
            "environment_hints": env_hints,
            "summary": {
                "run": "Executes a pipeline source and exports records to Singer, JSONL, Parquet, DuckDB, or dlt.",
                "validate": "Statically validates source and stream YAML configurations, refs, and DuckDB SQL.",
                "connectors": "Lists installed connectors or searches/installs connectors from the StreamWright Hub.",
                "mcp": "Runs the StreamWright Model Context Protocol server for AI coding assistants.",
            }.get(subcommand, ""),
        }

    return {
        "binary": "streamwright",
        "alias": "sw",
        "invocation_notes": "Both 'sw' and 'streamwright' are completely interchangeable.",
        "instruction": "To discover all commands and live options, ask the user's terminal to inspect: `sw --help` (or `streamwright --help`). For specific subcommands, run `sw <command> --help`.",
        "recommended_command": "sw --help",
        "fallback_command": "python -m streamwright.core.cli --help",
        "environment_hints": env_hints,
        "available_subcommands": {
            "run": "sw run --help",
            "validate": "sw validate --help",
            "connectors": "sw connectors --help",
            "mcp": "sw mcp --help",
        },
    }





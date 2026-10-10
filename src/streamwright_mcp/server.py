"""
StreamWright Model Context Protocol (MCP) Server.

Exposes programmatic tools and resources for inspecting connector contracts,
core schemas, source validation, and transform analysis without file duplication.
"""

import json
from typing import Any, Dict, List, Optional

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from streamwright_mcp.contracts import (
    get_cli_reference as _get_cli_reference,
    get_connector_contract as _get_contract,
    get_core_schema as _get_schema,
    list_installed_connectors,
)
from streamwright_mcp.hub import list_hub_connectors
from streamwright_mcp.inspector import inspect_stream_transform as _inspect_transform
from streamwright_mcp.validator import validate_source_config as _validate_source

server = MCPServer("streamwright-mcp")


@server.tool()
def list_connectors(include_hub: bool = False) -> List[Dict[str, Any]]:
    """
    Lists StreamWright connectors.

    Args:
        include_hub: If True, also includes uninstalled connectors available in the StreamWright Hub registry.

    Returns:
        List of connector summaries containing name, title, category, transport, and installation status.
    """
    installed = list_installed_connectors()
    if not include_hub:
        return installed

    installed_names = {c["name"] for c in installed}
    hub_connectors = list_hub_connectors()

    results = list(installed)
    for h in hub_connectors:
        key = h.get("key")
        if key and key not in installed_names:
            results.append({
                "name": key,
                "title": h.get("title", key.replace("_", " ").title()),
                "category": h.get("family", "hub"),
                "transport": "unknown",
                "version": None,
                "installed": False,
                "install_hint": h.get("install_hint", f"pip install streamwright-{key.replace('_', '-')}"),
            })

    results.sort(key=lambda x: x["name"])
    return results


@server.tool()
def get_connector_contract(name: str) -> Dict[str, Any]:
    """
    Retrieves the complete in-code contract for a StreamWright connector.

    Returns the 5-part specification:
    1. source.yaml contract snippet
    2. streams/<stream>.yaml contract snippet
    3. Authentication & secrets requirements
    4. Transform & DuckDB SQL data shaping
    5. Execution & runtime behaviors (transport, pagination, retries)

    If the connector is not installed locally, returns the installation command.

    Args:
        name: Name of the connector (e.g. 's3', 'postgres', 'restapi', 'google_ads', 'openai_ads').
    """
    return _get_contract(name)


@server.tool()
def get_core_schema(kind: str = "all") -> Dict[str, Any]:
    """
    Returns the formal Draft 7 JSON schema and declarative DSL specification for StreamWright.

    Args:
        kind: 'source' (source.yaml schema), 'stream' (streams/*.yaml schema), or 'all' (both schemas plus full DSL documentation).
    """
    return _get_schema(kind)


@server.tool()
def validate_source_config(source_dir: str) -> Dict[str, Any]:
    """
    Performs static validation on a StreamWright source folder (source.yaml and streams/*.yaml).

    Checks YAML structure, keys, credentials, Jinja references, DuckDB SQL transforms,
    and export consistency with pinpoint file:line diagnostics.

    Args:
        source_dir: Absolute or relative path to the source directory.
    """
    return _validate_source(source_dir)


@server.tool()
def inspect_stream_transform(source_dir: str, stream_name: str) -> Dict[str, Any]:
    """
    Parses and explains the requests, DuckDB SQL transform steps, table inputs,
    and export contracts for a specific stream.

    Args:
        source_dir: Path to the pipeline source directory.
        stream_name: Name of the stream to inspect.
    """
    return _inspect_transform(source_dir, stream_name)


@server.tool()
def get_cli_reference(command: Optional[str] = None) -> Dict[str, Any]:
    """
    Guides the AI assistant on how to inspect, discover, and run StreamWright CLI commands.
    Directs the LLM to run and inspect `sw --help` or `sw <subcommand> --help` directly in the user's workspace.

    Args:
        command: Optional subcommand to inspect ('run', 'validate', 'connectors', 'mcp').
    """
    return _get_cli_reference(command)


# Resources
@server.resource("streamwright://schema/source")
def source_schema_resource() -> str:
    """JSON Schema (Draft 7) for StreamWright source.yaml."""
    schema_dict = _get_schema("source").get("source_schema", {})
    return json.dumps(schema_dict, indent=2)


@server.resource("streamwright://schema/stream")
def stream_schema_resource() -> str:
    """JSON Schema (Draft 7) for StreamWright streams/<stream>.yaml."""
    schema_dict = _get_schema("stream").get("stream_schema", {})
    return json.dumps(schema_dict, indent=2)


@server.resource("streamwright://schema/core")
def core_dsl_resource() -> str:
    """Complete markdown specification contract of the StreamWright DSL."""
    return _get_schema("all").get("dsl_specification", "")

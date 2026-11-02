"""
StreamWright Model Context Protocol (MCP) server.

A thin adapter: every tool and resource is built from the engine registry (see engines.py) and calls the engines'
public APIs; nothing here re-implements an engine.
"""

import json
from collections.abc import Mapping
from typing import Any

from mcp.server.mcpserver import MCPServer

from streamwright.mcp import cli_reference, connectors, inspection, schemas, validation
from streamwright.mcp.engines import EngineDescriptor, EngineRegistry, discover_engines

SERVER_NAME = "streamwright-mcp"

# A Mapping (not a dict) return type keeps MCP's `{"result": ...}` envelope of the tools' structured output.
ToolResult = Mapping[str, Any]

JOB_TOOL_DESCRIPTION = """Statically validates a {kind} manifest ({title}).

Offline and credential-free: nothing is connected, and no secret values are accepted. `{{{{ secrets.NAME }}}}`
references are checked against the names declared in spec.secrets. The verdict is the one `streamwright validate`
gives.

Args:
    content: The manifest as YAML text (at most 5 MiB). Give either content or path.
    path: A manifest or its folder, inside the allowed workspace roots (STREAMWRIGHT_MCP_ROOTS, default: the server's
        working directory).
    config: Values for spec.config (not secrets).
    overlays: Paths of overlay manifests merged in order, inside the allowed workspace roots.
    strict: If True, warnings fail the validation.
    analyze: If True, include the execution plan."""


def _register_job_tool(server: MCPServer, engine: EngineDescriptor) -> None:
    def validate(
        content: str | None = None,
        path: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        overlays: list[str] | None = None,
        strict: bool = False,
        analyze: bool = False,
    ) -> ToolResult:
        return validation.validate_job(engine, content, path, config=config, overlays=overlays, strict=strict,
                                       analyze=analyze)

    name = f"validate_{engine.key}_job"
    validate.__name__ = name
    server.add_tool(validate, name=name, description=JOB_TOOL_DESCRIPTION.format(kind=engine.kind, title=engine.title))


def _register_schema_resource(server: MCPServer, engine: EngineDescriptor, name: str) -> None:
    def read() -> str:
        return json.dumps(engine.schemas[name](), indent=2)

    server.resource(f"streamwright://schema/{name}", name=f"{name}_schema", mime_type="application/json",
                    description=f"JSON Schema (draft 7) of the {engine.kind} engine's `{name}` document.")(read)


def _register_guide_resources(server: MCPServer, engine: EngineDescriptor) -> None:
    def index() -> str:
        return json.dumps(engine.guide(None), indent=2)

    def read_section(section: str) -> str:
        return json.dumps(engine.guide(section), indent=2)

    server.resource(f"streamwright://guide/{engine.key}", name=f"{engine.key}_guide", mime_type="application/json",
                    description=f"The section titles of the {engine.kind} engine's guide.")(index)
    server.resource(f"streamwright://guide/{engine.key}/{{section}}", name=f"{engine.key}_guide_section",
                    mime_type="application/json",
                    description=f"One section of the {engine.kind} engine's guide, found by title.")(read_section)


def build_server(registry: EngineRegistry) -> MCPServer:
    server = MCPServer(SERVER_NAME)

    @server.tool()
    def list_connectors(include_hub: bool = False, engine: str | None = None) -> list[dict[str, Any]]:
        """
        Lists the installed StreamWright connectors with the engines each supports; nothing is imported.

        Args:
            include_hub: If True, also lists the connectors of the StreamWright Hub catalog that are not installed,
                with how to install them (ignored with `engine`).
            engine: Optional engine filter: an engine kind or key from get_core_schema().
        """
        return connectors.list_connectors(registry, include_hub, engine)

    @server.tool()
    def get_connector_contract(name: str, engine: str | None = None) -> ToolResult:
        """
        The contract of a connector for each engine that has an adapter for it: capabilities, authentication and
        secret keys, as the engines declare them. If the connector is not installed: how to install it.

        Args:
            name: The connector name, as listed by list_connectors.
            engine: Optional engine filter: an engine kind or key from get_core_schema().
        """
        return connectors.get_connector_contract(registry, name, engine)

    @server.tool()
    def get_connector_guide(name: str, section: str | None = None) -> ToolResult:
        """
        An installed connector's user guide, paged by section: examples, its query builder (e.g. google_ads `gaql`:
        `query: {gaql: {select, from, where, ...}}`, the way to use config, partition or window values in a query),
        vendor arguments and engine notes. Without `section`: the section titles; with it: that section's text.

        Args:
            name: The connector name, as listed by list_connectors.
            section: A section title (or part of one) from the list of sections.
        """
        return connectors.get_connector_guide(name, section)

    @server.tool()
    def get_core_schema(kind: str | None = None, section: str | None = None) -> ToolResult:
        """
        The StreamWright JSON schemas (draft 7). Without arguments: an index of the engines, their schemas and
        sections. With `kind`: that schema. With `kind` and `section`: one definition of it.

        Args:
            kind: An engine kind or key, or a schema name from the index. An unknown kind is an error.
            section: A definition or top-level property of that schema.
        """
        return schemas.get_core_schema(registry, kind, section)

    @server.tool()
    def get_engine_guide(kind: str, section: str | None = None) -> ToolResult:
        """
        An engine's guide, paged by section: without `section` the section titles, otherwise that section's text.

        Args:
            kind: An engine kind or key from get_core_schema().
            section: A section title (or part of it).
        """
        return schemas.get_engine_guide(registry, kind, section)

    @server.tool()
    def validate_source_config(source_dir: str, strict: bool = False) -> ToolResult:
        """
        Validates a source (source.yaml and streams/*.yaml) with the same checks as `streamwright validate`: YAML
        structure, keys, credentials, references, installed connectors, SQL transforms and exports, with
        file:line diagnostics. A path that holds a job manifest is validated by that job's engine.

        Args:
            source_dir: A source folder or file, inside the allowed workspace roots (STREAMWRIGHT_MCP_ROOTS, default:
                the server's working directory).
            strict: If True, warnings fail the validation (except a connector that is not installed).
        """
        return validation.validate_source_config(registry, source_dir, strict)

    @server.tool()
    def inspect_stream_transform(source_dir: str, stream_name: str) -> ToolResult:
        """
        Explains one stream as the source engine plans it: its requests, the steps with the tables they read and
        their columns, and the exports with their primary-key check.

        Args:
            source_dir: A source folder, inside the allowed workspace roots.
            stream_name: The stream to inspect.
        """
        return inspection.inspect_stream_transform(source_dir, stream_name)

    @server.tool()
    def get_cli_reference(command: str | None = None) -> ToolResult:
        """
        The live usage and help of the `streamwright` (`sw`) commands, read from the CLI's own parsers.

        Args:
            command: Optional command, such as 'run', 'validate' or 'duckdb run'. Without it: the command list.
        """
        return cli_reference.get_cli_reference(command)

    for engine in registry.job_engines():
        _register_job_tool(server, engine)
    for engine in registry:
        for name in engine.schemas:
            _register_schema_resource(server, engine, name)
        _register_guide_resources(server, engine)
    return server


server = build_server(discover_engines())

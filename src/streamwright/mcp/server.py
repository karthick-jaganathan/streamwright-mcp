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
StreamWright Model Context Protocol (MCP) server.

A thin adapter: every tool and resource is built from the engine registry (see engines.py) and calls the engines'
public APIs; nothing here re-implements an engine.
"""

import functools
import json
from collections.abc import Callable, Mapping
from typing import Any

from mcp.server.mcpserver import MCPServer

from streamwright.mcp import cli_reference, connectors, inspection, schemas, search, validation
from streamwright.mcp.engines import EngineDescriptor, EngineRegistry, discover_engines

SERVER_NAME = "streamwright-mcp"

# A Mapping (not a dict) return type keeps MCP's `{"result": ...}` envelope of the tools' structured output.
ToolResult = Mapping[str, Any]

MAX_RESULT_CHARS = 20_000   # the JSON size of a tool result above which it is shortened
TRUNCATED_HINT = ("The result was shortened to fit {limit} characters. Narrow the request: get_connector_contract "
                  "with `operation`, get_core_schema or a guide with `section`, or search_docs(query).")

JOB_TOOL_DESCRIPTION = """Statically validates a {kind} manifest ({title}).

Offline and credential-free: nothing is connected, and no secret values are accepted. `{{{{ secrets.NAME }}}}`
references are checked against the names declared in spec.secrets. The verdict is the one `streamwright validate`
gives.

Args:
    content: The manifest as YAML text (at most 5 MiB). Give either content or path.
    path: A manifest or its folder, inside the allowed workspace roots (STREAMWRIGHT_MCP_ROOTS, default: the server's
        working directory).
    config: Values for spec.config (not secrets); they render references such as runtime.state.scope
        (`client:{{{{ config.client }}}}`) and lock.each lists, as `--set` does on the command line.
    overlays: Paths of overlay manifests merged in order, inside the allowed workspace roots.
    strict: If True, warnings fail the validation.
    analyze: If True, include the execution plan, as `streamwright plan` prints it: the steps and outputs in run
        order with what each reads and feeds (nothing runs)."""


def _size(value: Any) -> int:
    return len(json.dumps(value, default=str))


def _shrink(value: Any, items: int, chars: int, top: bool = False) -> Any:
    if isinstance(value, str):
        return value if len(value) <= chars else value[:chars] + "..."
    if isinstance(value, Mapping):
        kept = list(value.items()) if top else list(value.items())[:items]
        return {key: _shrink(item, items, chars) for key, item in kept}
    if isinstance(value, (list, tuple)):
        return [_shrink(item, items, chars) for item in value[:items]]
    return value


def cap_result(result: Any, limit: int = MAX_RESULT_CHARS) -> Any:
    """`result` if its JSON fits `limit`, else a copy with its top-level keys whose nested lists, mappings and
    strings are cut deterministically (fewer items and characters each round), marked `truncated` with a hint."""
    if _size(result) <= limit:
        return result
    items, chars = 64, 4096
    shrunk = _shrink(result, items, chars, top=True)
    while _size(shrunk) > limit and (items > 1 or chars > 64):
        items, chars = max(1, items // 2), max(64, chars // 2)
        shrunk = _shrink(result, items, chars, top=True)
    if isinstance(shrunk, Mapping):
        shrunk = {**shrunk, "truncated": True, "hint": TRUNCATED_HINT.format(limit=limit)}
    return shrunk


def _add_tool(server: MCPServer, fn: Callable[..., Any], **options: Any) -> Callable[..., Any]:
    """Registers `fn` as a tool whose results go through cap_result (signature and docstring kept)."""
    @functools.wraps(fn)
    def capped(*args: Any, **kwargs: Any) -> Any:
        return cap_result(fn(*args, **kwargs))

    server.add_tool(capped, **options)
    return fn


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
    _add_tool(server, validate, name=name,
              description=JOB_TOOL_DESCRIPTION.format(kind=engine.kind, title=engine.title))


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
    tool = functools.partial(_add_tool, server)

    @tool
    def list_connectors(include_hub: bool = False, engine: str | None = None) -> list[dict[str, Any]]:
        """
        Lists the installed StreamWright connectors with the engines each supports; nothing is imported.

        Args:
            include_hub: If True, also lists the connectors of the StreamWright Hub catalog that are not installed,
                with how to install them (ignored with `engine`).
            engine: Optional engine filter: an engine kind or key from get_core_schema().
        """
        return connectors.list_connectors(registry, include_hub, engine)

    @tool
    def get_connector_contract(name: str, engine: str | None = None, operation: str | None = None) -> ToolResult:
        """
        The contract of a connector as the engines declare it: connection, authentication and secret keys,
        operations and query builders once, then under `engines` only what differs per engine (capabilities,
        transport, reach). Operations are summarised (kind, idempotent, max_chunk, actions, argument names and the
        required ones); `operation` returns one in full. If the connector is not installed: how to install it.

        Args:
            name: The connector name, as listed by list_connectors.
            engine: Optional engine filter: an engine kind or key from get_core_schema().
            operation: Optional operation name from the summary (e.g. `Service.method`, any case): that operation
                with every declared field, argument types and descriptions included.
        """
        return connectors.get_connector_contract(registry, name, engine, operation)

    @tool
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

    @tool
    def describe_connector_type(name: str, type_name: str) -> ToolResult:
        """
        A vendor type of an SDK connector, read offline from its installed library, so a call uses names and values
        the API accepts: an enum's values in their exact case (microsoft_ads `ReportAggregation`, `ReportTimePeriod`;
        meta_ads `AdsInsights.DatePreset`, `AdsInsights.Level`; google_ads `CampaignStatus`), or an object's fields
        and their types (`CampaignPerformanceReportRequest`, `AdsInsights`, `Campaign`), each of which you can look up
        in turn. REST API connectors have no library to ask: their guides list the values.

        Args:
            name: The connector name, as listed by list_connectors.
            type_name: The type as the vendor's library names it (case-sensitive).
        """
        return connectors.describe_connector_type(name, type_name)

    @tool
    def get_core_schema(kind: str | None = None, section: str | None = None) -> ToolResult:
        """
        The StreamWright JSON schemas (draft 7). Without arguments: an index of the engines, their schemas and
        sections. With `kind`: an outline of that schema (top-level properties with type, description and fields;
        definitions with description). With `kind` and `section`: that part in full.

        Args:
            kind: An engine kind or key, or a schema name from the index. An unknown kind is an error.
            section: A definition or top-level property, or a dotted path through properties such as
                `steps.sql` or `runtime.state`.
        """
        return schemas.get_core_schema(registry, kind, section)

    @tool
    def get_engine_guide(kind: str, section: str | None = None) -> ToolResult:
        """
        An engine's guide, paged by section: without `section` the section titles, otherwise that section's text.
        For example the DuckDBJob section "State, scopes and locks": running one job for many clients
        (runtime.state.scope), keeping two runs off a shared item (runtime.state.lock with each/as/token and the
        fail, wait or prune policy), the section "Lookups and accounts" (credentials looked up at run time from a
        database, a command, a Python function or AWS Secrets Manager; runtime.fan_out runs the job once per
        account), what a run does with a failed batch (runtime.state.failed_job_policy: abandon,
        the default, retry up to max_job_attempts, or block), retrying or abandoning it by hand, and applying the
        state tables' migrations (a run only checks them: `state migrate` first, or --apply-state-migrations).

        Args:
            kind: An engine kind or key from get_core_schema().
            section: A section title (or part of it).
        """
        return schemas.get_engine_guide(registry, kind, section)

    @tool
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

    @tool
    def inspect_stream_transform(source_dir: str, stream_name: str) -> ToolResult:
        """
        Explains one stream as the source engine plans it: its requests, the steps with the tables they read and
        their columns, and the exports with their primary-key check.

        Args:
            source_dir: A source folder, inside the allowed workspace roots.
            stream_name: The stream to inspect.
        """
        return inspection.inspect_stream_transform(source_dir, stream_name)

    @tool
    def search_docs(query: str) -> ToolResult:
        """
        Searches the shipped guides (every engine's and installed connector's) and the CLI help by keywords and
        identifiers (`snake_case` or dotted names match whole): the 10 best sections, each with a snippet and the
        tool call that opens it.

        Args:
            query: Words or identifiers to look for.
        """
        return search.search_docs(registry, query)

    @tool
    def get_cli_reference(command: str | None = None) -> ToolResult:
        """
        The live usage and help of the `streamwright` (`sw`) commands, read from the CLI's own parsers: every
        option with its meaning, and the subcommands of a command.

        Args:
            command: Optional command, such as 'run', 'validate', 'duckdb run' (with --state-lock-policy,
                --failed-job-policy, --max-job-attempts, --apply-state-migrations, --allow-lookup-exec), 'duckdb state'
                (migrate, check, list, show, retry, abandon), 'state migrate' or 'spark run'. Without it: the command
                list and the options every job command takes.
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

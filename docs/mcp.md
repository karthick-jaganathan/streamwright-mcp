# StreamWright Model Context Protocol (MCP) Reference

The **StreamWright MCP Server** provides AI coding assistants and autonomous agents (such as Google Antigravity, Claude Desktop, Cursor, GitHub Copilot, Zed, and Windsurf) with direct, programmatic access to the StreamWright runtime.

By exposing live in-code contracts, core Draft-7 JSON schemas, static validation diagnostics, DuckDB SQL transform analyzers, and CLI references, the MCP server ensures that AI agents build and troubleshoot data pipelines with **zero hallucinations** and **pinpoint accuracy**.

---

## Architecture & Transports

StreamWright MCP is a thin adapter over the engines' public APIs. It discovers the installed engines from the `streamwright.job_kinds` entry-point group (plus core's `source` engine) and the installed connectors from the engines' connector groups, so it never relies on static copies of schemas, contracts or connector lists. The `streamwright mcp` subcommand is registered through the `streamwright.commands` group.

### Supported Transports

The server supports three transport modes via the `--transport` CLI flag:

1. **`stdio` (Standard Input/Output, Default)**: Used by local desktop clients (Claude Desktop, Cursor, Antigravity, Zed).
   ```bash
   streamwright-mcp --transport stdio
   # Or via shorthand:
   sw mcp
   ```

2. **`sse` (Server-Sent Events)**: Used for remote or containerized AI agents. Requires `--allow-http` and a bearer token (see [Security](#security)).
   ```bash
   STREAMWRIGHT_MCP_TOKEN=<token> streamwright-mcp --transport sse --allow-http --port 8000
   ```

3. **`streamable-http`**: For streaming HTTP client integrations; same requirements as `sse`.

### Security

- **Workspace roots**: every filesystem path a tool accepts (`source_dir`, `path`, `overlays`) must resolve (symlinks and `..` included) inside the allowed roots: `STREAMWRIGHT_MCP_ROOTS` (separated by `os.pathsep`), default the server's working directory. URIs (`s3://`, `file://`, `http://`) are rejected. Inline `content` is limited to 5 MiB, and YAML errors report only line and column, never file content.
- **No secret values**: `validate_duckdb_job` takes no secrets; `{{ secrets.NAME }}` references are checked against `spec.secrets`.
- **HTTP transports** are off unless `--allow-http` is passed. They bind `127.0.0.1` (`--host` to change), validate the `Host`/`Origin` headers (DNS-rebinding protection), and require `Authorization: Bearer <token>` matching `STREAMWRIGHT_MCP_TOKEN`; the server refuses to start without it. The token is a shared secret over plain HTTP: keep the server on loopback or behind a TLS-terminating proxy.

---

## MCP Tools and Resources Reference

Generated from the server's registry by `python -m streamwright.mcp.docs`; do not edit between the markers.

<!-- mcp-reference:start -->

#### Tools

##### `list_connectors`

Lists the installed StreamWright connectors with the engines each supports; nothing is imported.

Args:
    include_hub: If True, also lists the connectors of the StreamWright Hub catalog that are not installed,
        with how to install them (ignored with `engine`).
    engine: Optional engine filter: an engine kind or key from get_core_schema().

##### `get_connector_contract`

The contract of a connector for each engine that has an adapter for it: capabilities, authentication and
secret keys, as the engines declare them. If the connector is not installed: how to install it.

Args:
    name: The connector name, as listed by list_connectors.
    engine: Optional engine filter: an engine kind or key from get_core_schema().

##### `get_connector_guide`

An installed connector's user guide, paged by section: examples, its query builder (e.g. google_ads `gaql`:
`query: {gaql: {select, from, where, ...}}`, the way to use config, partition or window values in a query),
vendor arguments and engine notes. Without `section`: the section titles; with it: that section's text.

Args:
    name: The connector name, as listed by list_connectors.
    section: A section title (or part of one) from the list of sections.

##### `get_core_schema`

The StreamWright JSON schemas (draft 7). Without arguments: an index of the engines, their schemas and
sections. With `kind`: that schema. With `kind` and `section`: one definition of it.

Args:
    kind: An engine kind or key, or a schema name from the index. An unknown kind is an error.
    section: A definition or top-level property of that schema.

##### `get_engine_guide`

An engine's guide, paged by section: without `section` the section titles, otherwise that section's text.

Args:
    kind: An engine kind or key from get_core_schema().
    section: A section title (or part of it).

##### `validate_source_config`

Validates a source (source.yaml and streams/*.yaml) with the same checks as `streamwright validate`: YAML
structure, keys, credentials, references, installed connectors, SQL transforms and exports, with
file:line diagnostics. A path that holds a job manifest is validated by that job's engine.

Args:
    source_dir: A source folder or file, inside the allowed workspace roots (STREAMWRIGHT_MCP_ROOTS, default:
        the server's working directory).
    strict: If True, warnings fail the validation (except a connector that is not installed).

##### `inspect_stream_transform`

Explains one stream as the source engine plans it: its requests, the steps with the tables they read and
their columns, and the exports with their primary-key check.

Args:
    source_dir: A source folder, inside the allowed workspace roots.
    stream_name: The stream to inspect.

##### `get_cli_reference`

The live usage and help of the `streamwright` (`sw`) commands, read from the CLI's own parsers.

Args:
    command: Optional command, such as 'run', 'validate' or 'duckdb run'. Without it: the command list.

##### `validate_<engine>_job`

One tool per installed job engine (for example `validate_duckdb_job`, `validate_spark_job`), generated from the engine registry.

Statically validates a <Kind> manifest (<engine title>).

Offline and credential-free: nothing is connected, and no secret values are accepted. `{{ secrets.NAME }}`
references are checked against the names declared in spec.secrets. The verdict is the one `streamwright validate`
gives.

Args:
    content: The manifest as YAML text (at most 5 MiB). Give either content or path.
    path: A manifest or its folder, inside the allowed workspace roots (STREAMWRIGHT_MCP_ROOTS, default: the server's
        working directory).
    config: Values for spec.config (not secrets).
    overlays: Paths of overlay manifests merged in order, inside the allowed workspace roots.
    strict: If True, warnings fail the validation.
    analyze: If True, include the execution plan.

#### Resources

- `streamwright://schema/source`: JSON Schema (draft 7) of the source engine's `source` document.
- `streamwright://schema/stream`: JSON Schema (draft 7) of the source engine's `stream` document.
- `streamwright://guide/source`: The section titles of the source engine's guide.
- `streamwright://guide/source/{section}`: One section of the source engine's guide, found by title.
- `streamwright://schema/<name>`, `streamwright://guide/<engine>` and `streamwright://guide/<engine>/{section}`: the same for every installed job engine.

<!-- mcp-reference:end -->

---

## Client Setup Configurations

### 1. Claude Desktop
Add to your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "streamwright-mcp"
    }
  }
}
```

Or via StreamWright CLI shorthand:
```json
{
  "mcpServers": {
    "streamwright": {
      "command": "sw",
      "args": ["mcp"]
    }
  }
}
```

### 2. Cursor
Add to `.cursor/mcp.json` in your workspace or global settings:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "streamwright-mcp"
    }
  }
}
```

### 3. Google Antigravity
Add to `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "streamwright-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

### 4. Ephemeral Runner (`uvx`)
Run on-demand without installing packages globally:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "uvx",
      "args": ["streamwright-mcp", "--transport", "stdio"]
    }
  }
}
```

---

## Agent Prompting Recipes

### Recipe 1: Authoring a New Pipeline
> *"I want to pull data from a REST API endpoint `https://api.github.com/repos/org/repo/issues`. Use StreamWright MCP to inspect the restapi connector contract and generate the `source.yaml` and `streams/issues.yaml` files."*

### Recipe 2: Validating Existing Pipelines
> *"Check the pipeline in `./sources/hubspot`. Run static validation and fix any errors with line-level diagnostics."*

### Recipe 3: Explaining DuckDB Transforms
> *"Inspect the transform steps in `streams/daily_metrics.yaml` and show me what intermediate DuckDB tables are created."*

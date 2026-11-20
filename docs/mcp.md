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

- **Workspace roots** (`--root DIR`, repeatable, or `STREAMWRIGHT_MCP_ROOTS`): every filesystem path a tool accepts (`source_dir`, `path`, `overlays`) must resolve (symlinks and `..` included) inside the allowed roots: `STREAMWRIGHT_MCP_ROOTS` (separated by `os.pathsep`), default the server's working directory. A source is checked file by file before it is read: its source folder (also when found from a `streams/` folder or stream file), its `source.yaml` and every stream file must resolve inside the roots too, so a symlinked stream file cannot lead outside them. URIs (`s3://`, `file://`, `http://`) are rejected. Inline `content` is limited to 5 MiB, and YAML errors report only line and column, never file content.
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

The contract of a connector as the engines declare it: connection, authentication and secret keys,
operations and query builders once, then under `engines` only what differs per engine (capabilities,
transport, reach). Operations are summarised (kind, idempotent, max_chunk, actions, argument names and the
required ones); `operation` returns one in full. If the connector is not installed: how to install it.

Args:
    name: The connector name, as listed by list_connectors.
    engine: Optional engine filter: an engine kind or key from get_core_schema().
    operation: Optional operation name from the summary (e.g. `Service.method`, any case): that operation
        with every declared field, argument types and descriptions included.

##### `get_connector_guide`

An installed connector's user guide, paged by section: examples, its query builder (e.g. google_ads `gaql`:
`query: {gaql: {select, from, where, ...}}`, the way to use config, partition or window values in a query),
vendor arguments and engine notes. Without `section`: the section titles; with it: that section's text.

Args:
    name: The connector name, as listed by list_connectors.
    section: A section title (or part of one) from the list of sections.

##### `describe_connector_type`

A vendor type of an SDK connector, read offline from its installed library, so a call uses names and values
the API accepts: an enum's values in their exact case (microsoft_ads `ReportAggregation`, `ReportTimePeriod`;
meta_ads `AdsInsights.DatePreset`, `AdsInsights.Level`; google_ads `CampaignStatus`), or an object's fields
and their types (`CampaignPerformanceReportRequest`, `AdsInsights`, `Campaign`), each of which you can look up
in turn. REST API connectors have no library to ask: their guides list the values.

Args:
    name: The connector name, as listed by list_connectors.
    type_name: The type as the vendor's library names it (case-sensitive).

##### `get_core_schema`

The StreamWright JSON schemas (draft 7). Without arguments: an index of the engines, their schemas and
sections. With `kind`: an outline of that schema (top-level properties with type, description and fields;
definitions with description). With `kind` and `section`: that part in full.

Args:
    kind: An engine kind or key, or a schema name from the index. An unknown kind is an error.
    section: A definition or top-level property, or a dotted path through properties such as
        `steps.sql` or `runtime.state`.

##### `get_engine_guide`

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

##### `search_docs`

Searches the shipped guides (every engine's and installed connector's) and the CLI help by keywords and
identifiers (`snake_case` or dotted names match whole): the 10 best sections, each with a snippet and the
tool call that opens it.

Args:
    query: Words or identifiers to look for.

##### `get_cli_reference`

The live usage and help of the `streamwright` (`sw`) commands, read from the CLI's own parsers: every
option with its meaning, and the subcommands of a command.

Args:
    command: Optional command, such as 'run', 'validate', 'duckdb run' (with --state-lock-policy,
        --failed-job-policy, --max-job-attempts, --apply-state-migrations, --allow-lookup-exec), 'duckdb state'
        (migrate, check, list, show, retry, abandon), 'state migrate' or 'spark run'. Without it: the command
        list and the options every job command takes.

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
    config: Values for spec.config (not secrets); they render references such as runtime.state.scope
        (`client:{{ config.client }}`) and lock.each lists, as `--set` does on the command line.
    overlays: Paths of overlay manifests merged in order, inside the allowed workspace roots.
    strict: If True, warnings fail the validation.
    analyze: If True, include the execution plan, as `streamwright plan` prints it: the steps and outputs in run
        order with what each reads and feeds (nothing runs).

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

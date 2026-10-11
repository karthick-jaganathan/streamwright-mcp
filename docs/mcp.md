# StreamWright Model Context Protocol (MCP) Reference

The **StreamWright MCP Server** provides AI coding assistants and autonomous agents (such as Google Antigravity, Claude Desktop, Cursor, GitHub Copilot, Zed, and Windsurf) with direct, programmatic access to the StreamWright runtime.

By exposing live in-code contracts, core Draft-7 JSON schemas, static validation diagnostics, DuckDB SQL transform analyzers, and CLI references, the MCP server ensures that AI agents build and troubleshoot data pipelines with **zero hallucinations** and **pinpoint accuracy**.

---

## Architecture & Transports

StreamWright MCP dynamically introspects your active Python environment using standard `streamwright.connectors` entry points. It never relies on stale static YAML copies or fragile local catalogs.

### Supported Transports

The server supports three transport modes via the `--transport` CLI flag:

1. **`stdio` (Standard Input/Output, Default)**: Used by local desktop clients (Claude Desktop, Cursor, Antigravity, Zed).
   ```bash
   streamwright-mcp --transport stdio
   # Or via shorthand:
   sw mcp
   ```

2. **`sse` (Server-Sent Events)**: Used for remote or containerized AI agents.
   ```bash
   streamwright-mcp --transport sse --port 8000
   ```

3. **`streamable-http`**: For streaming HTTP client integrations.

---

## MCP Tools Reference

The server registers 6 core tools designed for LLM workflows:

### 1. `list_connectors`

Discovers and lists connectors available in the Python runtime or from the remote StreamWright Hub.

- **Parameters**:
  - `include_hub` *(boolean, default: `false`)*: When `true`, queries the remote StreamWright Hub registry to include uninstalled connectors along with their installation hints.

- **Example Call**:
  ```json
  {
    "name": "list_connectors",
    "arguments": {
      "include_hub": true
    }
  }
  ```

- **Example Response**:
  ```json
  [
    {
      "name": "restapi",
      "title": "REST API Connector",
      "category": "api",
      "transport": "http",
      "version": "0.1.7",
      "installed": true
    },
    {
      "name": "postgres",
      "title": "PostgreSQL Connector",
      "category": "database",
      "transport": "sql",
      "version": "0.1.7",
      "installed": true
    },
    {
      "name": "shopify",
      "title": "Shopify Connector",
      "category": "hub",
      "transport": "unknown",
      "version": null,
      "installed": false,
      "install_hint": "pip install streamwright-shopify"
    }
  ]
  ```

---

### 2. `get_connector_contract`

Retrieves the live 5-part contract specification for an individual connector.

- **Parameters**:
  - `name` *(string, required)*: Connector identifier (e.g. `"restapi"`, `"postgres"`, `"s3"`, `"google_ads"`, `"openai_ads"`).

- **5-Part Contract Return**:
  1. `source.yaml` specification & parameters.
  2. `streams/*.yaml` stream schemas and partition options.
  3. Authentication schemes, required credential fields, and optional parameters.
  4. DuckDB SQL data shaping, transformations, and types.
  5. Execution behaviors (pagination, rate limits, retries, concurrency).

- **Example Call**:
  ```json
  {
    "name": "get_connector_contract",
    "arguments": {
      "name": "restapi"
    }
  }
  ```

- **Example Response (Installed)**:
  ```json
  {
    "name": "restapi",
    "installed": true,
    "spec": {
      "name": "restapi",
      "title": "REST API Connector",
      "category": "api",
      "transport": "http",
      "package": "streamwright-restapi"
    },
    "auth": {
      "required_fields": ["base_url"],
      "optional_fields": ["api_key", "bearer_token", "basic_auth", "headers"]
    },
    "services": null,
    "default_service": null,
    "contract_documentation": "StreamWright REST API Connector specification and examples..."
  }
  ```

- **Example Response (Uninstalled)**:
  ```json
  {
    "name": "salesforce",
    "installed": false,
    "message": "Connector 'salesforce' is not installed in the current Python environment.",
    "install_command": "pip install streamwright-salesforce",
    "hub_metadata": {
      "title": "Salesforce Connector",
      "install_hint": "pip install streamwright-salesforce"
    }
  }
  ```

---

### 3. `get_core_schema`

Returns the authoritative Draft-7 JSON Schemas and declarative DSL documentation from `streamwright.core.validation.schema`.

- **Parameters**:
  - `kind` *(string, default: `"all"`)*:
    - `"source"`: Returns JSON Schema for `source.yaml`.
    - `"stream"`: Returns JSON Schema for `streams/*.yaml`.
    - `"all"`: Returns both schemas plus the full Markdown DSL specification.

- **Example Call**:
  ```json
  {
    "name": "get_core_schema",
    "arguments": {
      "kind": "all"
    }
  }
  ```

- **Example Response**:
  ```json
  {
    "version": "1.0.0",
    "supported_versions": ["1.0.0"],
    "kind": "all",
    "source_schema": {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "title": "StreamWright Source Configuration",
      "type": "object",
      "required": ["version", "source"],
      "properties": {
        "version": {"type": "string"},
        "source": {"type": "object"}
      }
    },
    "stream_schema": {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "title": "StreamWright Stream Configuration",
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {"type": "string"},
        "request": {"type": "object"},
        "transform": {"type": "object"}
      }
    },
    "dsl_specification": "# StreamWright Declarative DSL Specification..."
  }
  ```

---

### 4. `validate_source_config`

Performs static validation on a pipeline source folder or file without executing network requests or database connections. Returns exact file:line:column diagnostics.

- **Parameters**:
  - `source_dir` *(string, required)*: Path to the pipeline source directory (containing `source.yaml` and `streams/*.yaml`).

- **Validation Rules Checked**:
  - YAML syntax and JSON Schema conformance.
  - Connector existence and credential requirements.
  - Jinja expression syntax and parameter references.
  - DuckDB SQL transform step validity and table lineage.
  - Export destination configurations.

- **Example Call**:
  ```json
  {
    "name": "validate_source_config",
    "arguments": {
      "source_dir": "./pipelines/stripe_charges"
    }
  }
  ```

- **Example Response (Pass)**:
  ```json
  {
    "valid": true,
    "error_count": 0,
    "warning_count": 0,
    "errors": [],
    "warnings": [],
    "summary": "Validation passed with 0 errors and 0 warnings."
  }
  ```

- **Example Response (Diagnostics Found)**:
  ```json
  {
    "valid": false,
    "error_count": 1,
    "warning_count": 0,
    "errors": [
      {
        "severity": "error",
        "code": "missing-auth-field",
        "message": "Required auth field 'api_key' is missing from source.yaml",
        "file": "./pipelines/stripe_charges/source.yaml",
        "line": 12,
        "column": 5,
        "path": "source.auth"
      }
    ],
    "warnings": [],
    "summary": "Validation failed with 1 error(s)."
  }
  ```

---

### 5. `inspect_stream_transform`

Parses and explains the execution plan, DuckDB SQL transform stages, table inputs, and export targets for an individual stream.

- **Parameters**:
  - `source_dir` *(string, required)*: Path to the source directory.
  - `stream_name` *(string, required)*: Name of the stream to analyze.

- **Example Call**:
  ```json
  {
    "name": "inspect_stream_transform",
    "arguments": {
      "source_dir": "./pipelines/ecommerce",
      "stream_name": "orders"
    }
  }
  ```

- **Example Response**:
  ```json
  {
    "found": true,
    "stream_name": "orders",
    "requests": {
      "path": "/v1/orders",
      "method": "GET",
      "pagination": "cursor",
      "partition_by": "status"
    },
    "transform_steps": [
      {
        "step_name": "flatten_line_items",
        "sql": "SELECT id, unnest(line_items) AS item, created_at FROM raw_orders",
        "referenced_tables": ["raw_orders"]
      },
      {
        "step_name": "calculate_totals",
        "sql": "SELECT id, sum(item.price * item.quantity) AS total_amount FROM flatten_line_items GROUP BY id",
        "referenced_tables": ["flatten_line_items"]
      }
    ],
    "exports": [
      {
        "format": "parquet",
        "destination": "s3://my-lakehouse/orders/"
      }
    ]
  }
  ```

---

### 6. `get_cli_reference`

Provides authoritative reference and live inspection guidance for StreamWright CLI commands and the `sw` alias. Rather than returning hardcoded or outdated flags, it instructs the AI agent to inspect live help in the caller's workspace.

- **Parameters**:
  - `command` *(string, optional)*: Subcommand to inspect (`"run"`, `"validate"`, `"connectors"`, `"mcp"`). Omit to get all commands.

- **Example Call**:
  ```json
  {
    "name": "get_cli_reference",
    "arguments": {
      "command": "run"
    }
  }
  ```

- **Example Response**:
  ```json
  {
    "binary": "streamwright",
    "alias": "sw",
    "command": "run",
    "instruction": "To get the most accurate and up-to-date options for 'run', inspect the CLI directly by running or checking: `sw run --help` (or `streamwright run --help`).",
    "recommended_command": "sw run --help",
    "fallback_command": "python -m streamwright.core.cli run --help",
    "summary": "Executes a pipeline source and exports records to Singer, JSONL, Parquet, DuckDB, or dlt."
  }
  ```

---

## MCP Resources Reference

For IDEs and clients that support resource attachments:

| URI | MIME Type | Description |
|---|---|---|
| `streamwright://schema/source` | `application/json` | Formal Draft-7 JSON Schema for `source.yaml`. |
| `streamwright://schema/stream` | `application/json` | Formal Draft-7 JSON Schema for `streams/<stream>.yaml`. |
| `streamwright://schema/core` | `text/markdown` | Full Markdown specification of the StreamWright DSL. |

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

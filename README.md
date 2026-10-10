# StreamWright MCP Server

Model Context Protocol (MCP) server for [StreamWright](https://streamwright.web.app), the zero-code, declarative ELT framework.

Provides AI coding assistants (Claude Desktop, Cursor, Antigravity, Roo Code, GitHub Copilot) with programmatic access to:
1. **In-Code Connector Contracts**: Complete contracts, `source.yaml` specs, `streams/*.yaml` syntax, authentication parameters, DuckDB SQL transforms, and execution details.
2. **Core Schema & DSL Specification**: Draft 7 JSON schemas and comprehensive reference contracts for `source.yaml` and stream configurations.
3. **Static Source Validation**: Validates pipelines and provides file:line:column pinpoint diagnostics before execution.
4. **Transform Inspection & Analysis**: Inspects stream SQL transforms, dependencies, inputs, and exports.
5. **Zero Duplication**: Dynamically inspects installed StreamWright packages and modules directly from code—no fragile static YAML duplication or local catalog caches.

---

## Installation

Install via pip in your StreamWright Python environment:

```bash
pip install streamwright-mcp
```

Or install in development mode:

```bash
git clone https://github.com/karthick-jaganathan/streamwright-mcp.git
cd streamwright-mcp
pip install -e .
```

---

## Configuration

### Claude Desktop / Antigravity / Cursor Configuration

Add `streamwright-mcp` to your MCP client configuration (e.g. `claude_desktop_config.json` or `mcp.json`).

Using the standalone command:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "streamwright-mcp"
    }
  }
}
```

Or via the StreamWright CLI shorthand `sw mcp` / `streamwright mcp`:

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

Or run via python directly:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "python",
      "args": ["-m", "streamwright_mcp.cli"]
    }
  }
}
```

---

## Tools

| Tool | Description |
|------|-------------|
| `list_connectors` | Lists installed StreamWright connectors and optionally discovers uninstalled connectors from the StreamWright Hub. |
| `get_connector_contract` | Retrieves the full in-code 5-part contract (`source.yaml`, `streams/*.yaml`, auth, methods, execution) for any connector. If not installed, provides the installation command. |
| `get_core_schema` | Returns the formal schema and DSL definition for `source.yaml` and `streams/*.yaml`. |
| `validate_source_config` | Runs static validation checks on a local pipeline directory and returns errors, warnings, and file locations. |
| `inspect_stream_transform` | Parses and explains the SQL steps, dependencies, inputs, and exports of a specific stream. |
| `get_cli_reference` | Returns the authoritative reference for StreamWright CLI commands, options, outputs, execution recipes, and the `sw` alias. |

---

## Resources

- `streamwright://schema/source`: JSON Schema (Draft 7) for `source.yaml`.
- `streamwright://schema/stream`: JSON Schema (Draft 7) for `streams/<stream>.yaml`.
- `streamwright://schema/core`: Complete markdown contract of the StreamWright DSL.

---

## License

Apache-2.0

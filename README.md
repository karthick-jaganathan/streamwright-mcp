# StreamWright MCP Server

[![PyPI version](https://img.shields.io/pypi/v/streamwright-mcp.svg)](https://pypi.org/project/streamwright-mcp/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**StreamWright MCP** is the official [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for [StreamWright](https://streamwright.web.app), the declarative data integration and ELT framework.

It allows AI coding assistants (such as Claude Desktop, Cursor, Google Antigravity, GitHub Copilot, and Zed) to inspect installed connectors, query Draft-7 pipeline schemas, validate YAML sources with pinpoint error locations, and analyze DuckDB SQL transform pipelines in real time — eliminating hallucinations when building data pipelines.

---

## Key Capabilities

- **In-Code Connector Contracts**: Introspects installed connector packages (`restapi`, `postgres`, `s3`, etc.) directly from Python entry points to extract live contracts, authentication specs, and transport behaviors without static copies.
- **Hub Discovery**: Discovers uninstalled connectors from the StreamWright Hub registry and provides instant installation recipes.
- **Static Pipeline Validation**: Validates `source.yaml` and `streams/*.yaml` pipelines before execution, returning structured diagnostics with file, line, and column locations.
- **SQL Transform Inspection**: Parses and traces multi-step DuckDB SQL transformations, table dependencies, and export formats for any stream.
- **Core DSL Schemas**: Exposes authoritative Draft-7 JSON schemas for editor autocomplete, linting, and LLM grounding.
- **CLI Guidance**: Steers AI agents to explore live CLI commands (`sw run`, `sw validate`, `sw connectors`, `sw mcp`) in the local workspace.

---

## Installation

Install via `pip`:

```bash
pip install streamwright-mcp
```

Or using `uv`:

```bash
uv pip install streamwright-mcp
```

---

## Configuration

Add `streamwright-mcp` to your MCP client configuration file (e.g., `claude_desktop_config.json`, `mcp.json`, or Antigravity's `mcp_config.json`).

### Standard Configuration

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "streamwright-mcp"
    }
  }
}
```

### Using StreamWright CLI Shorthand (`sw`)

If you have `streamwright` installed, you can launch the MCP server directly via `sw mcp`:

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

### Ephemeral Execution (`uvx`)

Run on-demand without installing into your global environment:

```json
{
  "mcpServers": {
    "streamwright": {
      "command": "uvx",
      "args": ["streamwright-mcp"]
    }
  }
}
```

---

## Usage

### Starting the Server

The server runs over standard input/output (`stdio`) by default:

```bash
streamwright-mcp
```

You can also specify transport options:

```bash
# stdio (default)
streamwright-mcp --transport stdio

# Server-Sent Events (SSE)
streamwright-mcp --transport sse
```

Or run as a Python module:

```bash
python -m streamwright_mcp.cli
```

---

## Resources

MCP clients that support resource attachments can access:

- `streamwright://schema/source` — JSON Schema (Draft 7) for `source.yaml`.
- `streamwright://schema/stream` — JSON Schema (Draft 7) for `streams/<stream>.yaml`.
- `streamwright://schema/core` — Full Markdown specification of the StreamWright DSL.

---

## Documentation & Ecosystem

- **Documentation**: https://streamwright.web.app
- **MCP Guide**: https://streamwright.web.app/docs/ai/mcp
- **Core Package**: https://pypi.org/project/streamwright/
- **Repository**: https://github.com/karthick-jaganathan/streamwright-mcp

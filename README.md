# StreamWright MCP

[![PyPI](https://img.shields.io/pypi/v/streamwright-mcp.svg)](https://pypi.org/project/streamwright-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/streamwright-mcp.svg)](https://pypi.org/project/streamwright-mcp/)
[![License](https://img.shields.io/pypi/l/streamwright-mcp.svg)](https://github.com/karthick-jaganathan/streamwright-mcp/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-streamwright.web.app-brightgreen.svg)](https://streamwright.web.app/docs/ai/mcp/)

A [Model Context Protocol](https://modelcontextprotocol.io) server for [StreamWright](https://pypi.org/project/streamwright/).
AI assistants use it to discover connectors, read their contracts and the engine guides, and validate sources and
jobs. It never runs a pipeline and never reads secret values.

## Install

```bash
pip install streamwright-mcp
```

```json
{
  "mcpServers": {
    "streamwright": {"command": "streamwright-mcp"}
  }
}
```

stdio by default; `--transport sse | streamable-http` needs `--allow-http` and a token in `STREAMWRIGHT_MCP_TOKEN`.

## Tools

`list_connectors` · `get_connector_contract` · `get_connector_guide` · `get_core_schema` · `get_engine_guide` ·
`get_cli_reference` · `validate_source_config` · `inspect_stream_transform` · `validate_duckdb_job` · `validate_spark_job`

## Links

[Documentation](https://streamwright.web.app/docs/ai/mcp/) ·
[Tool reference](https://github.com/karthick-jaganathan/streamwright-mcp/blob/main/docs/mcp.md) ·
[Source code](https://github.com/karthick-jaganathan/streamwright-mcp)

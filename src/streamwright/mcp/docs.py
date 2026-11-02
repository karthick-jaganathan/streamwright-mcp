"""
Generates the tool and resource reference of docs/mcp.md from the server's registry:

    python -m streamwright.mcp.docs [--check] DOCUMENT...

Each DOCUMENT holds a block between `<!-- mcp-reference:start -->` and `<!-- mcp-reference:end -->`. The reference is
rendered for the `source` engine; job engines add one `validate_<engine>_job` tool and one set of schema and guide
resources each, rendered here once from the same templates.
"""

import argparse
import asyncio
import inspect
import sys
from pathlib import Path

from streamwright.mcp.engines import EngineRegistry, source_engine
from streamwright.mcp.server import JOB_TOOL_DESCRIPTION, build_server

START = "<!-- mcp-reference:start -->"
END = "<!-- mcp-reference:end -->"


def render_reference() -> str:
    server = build_server(EngineRegistry([source_engine()]))
    lines = ["#### Tools", ""]
    for tool in asyncio.run(server.list_tools()):
        lines += [f"##### `{tool.name}`", "", inspect.cleandoc(tool.description or ""), ""]
    lines += ["##### `validate_<engine>_job`", "",
              "One tool per installed job engine (for example `validate_duckdb_job`, `validate_spark_job`), generated "
              "from the engine registry.", "",
              inspect.cleandoc(JOB_TOOL_DESCRIPTION.format(kind="<Kind>", title="<engine title>")), "",
              "#### Resources", ""]
    for resource in asyncio.run(server.list_resources()):
        lines.append(f"- `{resource.uri}`: {resource.description}")
    for template in asyncio.run(server.list_resource_templates()):
        lines.append(f"- `{template.uri_template}`: {template.description}")
    lines += ["- `streamwright://schema/<name>`, `streamwright://guide/<engine>` and "
              "`streamwright://guide/<engine>/{section}`: the same for every installed job engine."]
    return "\n".join(lines) + "\n"


def replace_block(text: str, block: str) -> str:
    start, end = text.index(START) + len(START), text.index(END)
    return f"{text[:start]}\n\n{block}\n{text[end:]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the MCP tool reference in documentation documents.")
    parser.add_argument("--check", action="store_true",
                        help="fail if a document is out of date instead of rewriting it")
    parser.add_argument("documents", nargs="+", type=Path)
    args = parser.parse_args(argv)
    block, stale = render_reference(), []
    for path in args.documents:
        current = path.read_text(encoding="utf-8")
        updated = replace_block(current, block)
        if updated != current:
            stale.append(str(path))
            if not args.check:
                path.write_text(updated, encoding="utf-8")
    if stale and args.check:
        sys.stderr.write("out of date (run python -m streamwright.mcp.docs): " + ", ".join(stale) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

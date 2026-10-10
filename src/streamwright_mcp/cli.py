"""
CLI entry point for StreamWright MCP server.
"""

import argparse
import sys
from streamwright_mcp.server import server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StreamWright Model Context Protocol (MCP) server."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    args = parser.parse_args()

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()

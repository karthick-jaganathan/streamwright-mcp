"""
Command line of the StreamWright MCP server: the `streamwright-mcp` script and the `streamwright mcp` subcommand
(registered through the `streamwright.commands` entry-point group).
"""

import argparse
import os
from collections.abc import Sequence

TOKEN_ENV = "STREAMWRIGHT_MCP_TOKEN"
TRANSPORTS = ("stdio", "sse", "streamable-http")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transport", choices=TRANSPORTS, default="stdio",
                        help="MCP transport protocol (default: stdio)")
    parser.add_argument("--allow-http", action="store_true",
                        help="required for the sse and streamable-http transports, which serve over the network; "
                             f"callers must send the bearer token in {TOKEN_ENV}")
    parser.add_argument("--host", default="127.0.0.1",
                        help="interface the HTTP transports bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port the HTTP transports listen on (default: 8000)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="streamwright-mcp",
                                     description="StreamWright Model Context Protocol (MCP) server.")
    add_arguments(parser)
    return parser


def serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from streamwright.mcp.server import server  # noqa: PLC0415  loads every job engine: only when serving

    if args.transport == "stdio":
        server.run(transport="stdio")
        return 0
    if not args.allow_http:
        parser.error(f"--transport {args.transport} serves over the network; pass --allow-http to enable it")
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        parser.error(f"--transport {args.transport} requires a bearer token in the {TOKEN_ENV} environment variable")

    from streamwright.mcp.http_transport import create_http_app, serve_http_app  # noqa: PLC0415  imports the server

    serve_http_app(create_http_app(args.transport, args.host, args.port, token), args.host, args.port)
    return 0


def register(subparsers) -> None:
    """`streamwright.commands` entry point: adds `streamwright mcp`."""
    parser = subparsers.add_parser("mcp", help="run the StreamWright Model Context Protocol (MCP) server",
                                   description="Run the StreamWright Model Context Protocol (MCP) server.")
    add_arguments(parser)
    parser.set_defaults(command_handler=lambda args: serve(args, parser))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    return serve(parser.parse_args(argv), parser)


if __name__ == "__main__":
    raise SystemExit(main())

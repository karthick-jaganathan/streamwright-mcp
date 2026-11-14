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
Command line of the StreamWright MCP server: the `streamwright-mcp` script and the `streamwright mcp` subcommand
(registered through the `streamwright.commands` entry-point group).
"""

import argparse
import os
from collections.abc import Sequence

from streamwright.mcp.workspace import ROOTS_ENV

TOKEN_ENV = "STREAMWRIGHT_MCP_TOKEN"
TRANSPORTS = ("stdio", "sse", "streamable-http")
DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 8000


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transport", choices=TRANSPORTS, default="stdio",
                        help="MCP transport protocol (default: stdio)")
    parser.add_argument("--allow-http", action="store_true",
                        help="required for the sse and streamable-http transports, which serve over the network; "
                             f"callers must send the bearer token in {TOKEN_ENV}")
    parser.add_argument("--host", help="sse, streamable-http: the interface to bind (default: %s)" % DEFAULT_HOST)
    parser.add_argument("--port", type=int,
                        help="sse, streamable-http: the port to listen on (default: %d)" % DEFAULT_PORT)
    parser.add_argument("--root", action="append", default=[], metavar="DIR",
                        help="a folder the tools may read manifests from (repeatable; default: $%s, else the "
                             "working directory)" % ROOTS_ENV)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="streamwright-mcp",
                                     description="StreamWright Model Context Protocol (MCP) server.")
    add_arguments(parser)
    return parser


def serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.transport == "stdio":
        given = [option for option, value in (("--host", args.host), ("--port", args.port),
                                              ("--allow-http", args.allow_http)) if value]
        if given:
            parser.error("%s only %s to the sse and streamable-http transports"
                         % (", ".join(given), "applies" if len(given) == 1 else "apply"))
    if args.root:
        missing = [root for root in args.root if not os.path.isdir(root)]
        if missing:
            parser.error("--root %s is not a folder" % ", ".join(missing))
        os.environ[ROOTS_ENV] = os.pathsep.join(os.path.abspath(root) for root in args.root)

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

    host, port = args.host or DEFAULT_HOST, args.port or DEFAULT_PORT
    serve_http_app(create_http_app(args.transport, host, port, token), host, port)
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

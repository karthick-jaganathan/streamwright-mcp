"""
Authenticated HTTP transports (SSE and streamable HTTP) for the StreamWright MCP server.

The MCP SDK's HTTP apps do not authenticate callers. This module adds bearer-token
authentication and DNS-rebinding protection (Host/Origin validation), and is only
reached when the operator opts in explicitly (see cli.py).
"""

import hmac
from typing import Literal

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from streamwright.mcp.server import server

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

HttpTransport = Literal["sse", "streamable-http"]


def build_transport_security(host: str, port: int) -> TransportSecuritySettings:
    """Host and Origin allow-lists for a server bound to `host`:`port` (any port on loopback)."""
    names = [f"[{host}]" if ":" in host else host]
    if host in LOOPBACK_HOSTS:
        names = ["127.0.0.1", "localhost", "[::1]"]
        port_pattern = "*"
    else:
        port_pattern = str(port)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"{name}:{port_pattern}" for name in names],
        allowed_origins=[f"http://{name}:{port_pattern}" for name in names],
    )


class BearerTokenMiddleware:
    """Rejects every HTTP request that lacks `Authorization: Bearer <token>`."""

    def __init__(self, app: ASGIApp, token: str):
        self.app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        presented = dict(scope["headers"]).get(b"authorization", b"")
        if hmac.compare_digest(presented, self._expected):
            await self.app(scope, receive, send)
            return
        response = PlainTextResponse("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"})
        await response(scope, receive, send)


def create_http_app(transport: HttpTransport, host: str, port: int, token: str) -> Starlette:
    """The MCP server as an ASGI app with bearer-token authentication and Host/Origin validation."""
    if not token:
        raise ValueError(f"A bearer token is required for the {transport} transport.")
    security = build_transport_security(host, port)
    if transport == "sse":
        app = server.sse_app(host=host, transport_security=security)
    else:
        app = server.streamable_http_app(host=host, transport_security=security)
    app.add_middleware(BearerTokenMiddleware, token=token)
    return app


def serve_http_app(app: Starlette, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port)

import asyncio
from unittest.mock import patch

import pytest

from streamwright.mcp import cli
from streamwright.mcp.cli import TOKEN_ENV
from streamwright.mcp.http_transport import BearerTokenMiddleware, build_transport_security, create_http_app


def test_stdio_is_the_default_transport():
    with patch("streamwright.mcp.server.server.run") as run:
        cli.main([])
    run.assert_called_once_with(transport="stdio")


@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
def test_http_transport_requires_explicit_opt_in(transport, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "secret")
    with patch("streamwright.mcp.http_transport.serve_http_app") as serve, pytest.raises(SystemExit):
        cli.main(["--transport", transport])
    serve.assert_not_called()


@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
def test_http_transport_requires_a_token(transport, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with patch("streamwright.mcp.http_transport.serve_http_app") as serve, pytest.raises(SystemExit):
        cli.main(["--transport", transport, "--allow-http"])
    serve.assert_not_called()


def test_http_transport_binds_loopback_with_protection(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "secret")
    with patch("streamwright.mcp.http_transport.serve_http_app") as serve:
        cli.main(["--transport", "streamable-http", "--allow-http"])
    app, host, port = serve.call_args.args
    assert (host, port) == ("127.0.0.1", 8000)
    assert any(layer.cls is BearerTokenMiddleware for layer in app.user_middleware)


def test_transport_security_allows_only_loopback_hosts_by_default():
    security = build_transport_security("127.0.0.1", 8000)
    assert security.enable_dns_rebinding_protection is True
    assert security.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    assert security.allowed_origins == ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def test_transport_security_for_other_hosts_is_limited_to_that_host_and_port():
    security = build_transport_security("mcp.internal", 9000)
    assert security.allowed_hosts == ["mcp.internal:9000"]
    assert security.allowed_origins == ["http://mcp.internal:9000"]


def test_create_http_app_rejects_empty_token():
    with pytest.raises(ValueError):
        create_http_app("sse", "127.0.0.1", 8000, "")


def _call(app, headers):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": headers}
    asyncio.run(app(scope, receive, send))
    return sent[0]["status"]


def test_bearer_middleware_requires_the_token():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})

    app = BearerTokenMiddleware(downstream, token="secret")

    assert _call(app, []) == 401
    assert _call(app, [(b"authorization", b"Bearer wrong")]) == 401
    assert _call(app, [(b"authorization", b"secret")]) == 401
    assert _call(app, [(b"authorization", b"Bearer secret")]) == 200

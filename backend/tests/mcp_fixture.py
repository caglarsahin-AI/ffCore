"""A real MCP server (streamable HTTP, official SDK) on 127.0.0.1 for 05a tests.

Every POST is recorded with its JSON-RPC method, tool arguments and the headers the client
sent, so a test can see which identity went with which call (U5). Synthetic values only.
"""

import asyncio
import json
import socket
import threading
import time
from dataclasses import dataclass, field

import uvicorn
from mcp.server.mcpserver import MCPServer


@dataclass
class Seen:
    method: str
    arguments: dict
    headers: dict[str, str]


@dataclass
class FixtureServer:
    url: str
    seen: list[Seen] = field(default_factory=list)

    def calls(self) -> list[Seen]:
        return [s for s in self.seen if s.method == "tools/call"]


def _build(record: list[Seen]):
    server = MCPServer("ffcore-test")

    @server.tool()
    async def echo(text: str) -> str:
        """Returns the text."""
        return text

    @server.tool()
    async def whoami(caller: str) -> str:
        """Returns the caller the client meant; slow enough for concurrent calls to overlap."""
        await asyncio.sleep(0.2)
        return caller

    @server.tool()
    async def big(size: int) -> str:
        """Returns `size` characters."""
        return "x" * size

    @server.tool()
    async def slow(seconds: float) -> str:
        """Sleeps, then answers."""
        await asyncio.sleep(seconds)
        return "late"

    @server.tool()
    async def fail() -> str:
        """Always fails inside the tool."""
        raise ValueError("tool failed on purpose")

    inner = server.streamable_http_app()

    async def app(scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            await inner(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        body, more = b"", True
        while more:
            message = await receive()
            body += message.get("body", b"")
            more = message.get("more_body", False)
        try:
            data = json.loads(body)
        except ValueError:
            data = {}
        params = data.get("params") or {}
        record.append(Seen(data.get("method", "?"), params.get("arguments") or {}, headers))
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await inner(scope, replay, send)

    return app


def start() -> tuple[FixtureServer, uvicorn.Server]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    fixture = FixtureServer(url=f"http://127.0.0.1:{port}/mcp")
    server = uvicorn.Server(
        uvicorn.Config(_build(fixture.seen), host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("MCP fixture server did not start")
        time.sleep(0.05)
    return fixture, server

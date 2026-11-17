"""A fake HTTP upstream (Superset-shaped) on 127.0.0.1 for 05b tests.

Every request is recorded with its method, path, query, JSON body and headers, so a test sees
exactly what the published MCP server sent upstream. Synthetic values only.
"""

import json
import socket
import threading
import time
from dataclasses import dataclass, field

import uvicorn


@dataclass
class Hit:
    method: str
    path: str
    query: str
    body: object
    headers: dict[str, str]


@dataclass
class Upstream:
    url: str
    hits: list[Hit] = field(default_factory=list)


def _answer(method: str, path: str, body: object) -> tuple[int, dict[str, str], bytes]:
    if path == "/api/v1/dashboard/":
        result = {"count": 1, "result": [{"id": 3, "dashboard_title": "Yatak doluluk"}]}
        return 200, {}, json.dumps(result).encode()
    if path == "/api/v1/chart/" and method == "POST":
        return 201, {}, json.dumps({"id": 7, "slice_name": (body or {}).get("slice_name")}).encode()
    if path == "/api/v1/chart/" and method == "GET":
        return 200, {}, json.dumps({"count": 0, "result": []}).encode()
    if path.startswith("/api/v1/chart/") and method == "PUT":
        return 200, {}, json.dumps({"id": int(path.rsplit("/", 1)[-1])}).encode()
    if path.startswith("/api/v1/chart/") and path.endswith("/data/"):
        return 200, {}, json.dumps({"result": [{"rowcount": 2, "data": [{}, {}]}]}).encode()
    if path.startswith("/api/v1/dataset/"):
        return 200, {}, json.dumps({"result": {"table_name": "yatak"}}).encode()
    if path == "/redirect":
        return 302, {"location": "http://203.0.113.9/elsewhere"}, b""
    if path == "/big":
        return 200, {}, b"x" * 3_000_000
    if path == "/fail":
        return 500, {}, b"upstream secret detail"
    return 404, {}, b"not found"


def _app(hits: list[Hit]):
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        raw, more = b"", True
        while more:
            message = await receive()
            raw += message.get("body", b"")
            more = message.get("more_body", False)
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode(errors="replace")
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        path = scope["path"]
        hits.append(Hit(scope["method"], path, scope["query_string"].decode(), body, headers))
        status, extra, payload = _answer(scope["method"], path, body)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")]
                + [(k.encode(), v.encode()) for k, v in extra.items()],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    return app


def start() -> tuple[Upstream, uvicorn.Server]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    upstream = Upstream(url=f"http://127.0.0.1:{port}")
    server = uvicorn.Server(
        uvicorn.Config(_app(upstream.hits), host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("upstream fixture did not start")
        time.sleep(0.05)
    return upstream, server

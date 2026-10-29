"""ticket-desk: a fake ticket system for the plan/18 scenarios (F2 triage, F11 poisoned ticket).

Test stack only (compose `test` profile, package 18). It stands for an external ticket system a
project registers as an MCP tool with auth `none`: FFCore sends it no identity. MCP server
(streamable HTTP, official SDK) with three tools:

- `list_tickets(limit)`: id, subject and received_at of the tickets, by id;
- `get_ticket(ticket_id)`: one ticket with its body;
- `send_reply(ticket_id, body)`: records the reply and answers with its id. Nothing leaves the
  process: the module imports no outbound client.

Tickets are the 13a/18 samples (`TICKET_FILES`, read-only); the generator's `pii` answer key is
dropped on load. Inspection for tests (plain HTTP, not MCP): `GET /_calls` (tool, arguments and
the header names each call carried), `GET /_sent`, `POST /_reset`, `GET /healthz`.
"""

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.responses import JSONResponse

DEFAULT_TICKET_FILES = "/data/tickets/tickets-20.jsonl,/data/poison/tickets-poison.jsonl"
# Fields the generator adds for the tests; a real ticket system does not have them.
TEST_ONLY_FIELDS = ("pii",)


def load_tickets(paths: list[Path]) -> dict[str, dict[str, Any]]:
    tickets: dict[str, dict[str, Any]] = {}
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            ticket = json.loads(line)
            if ticket["id"] in tickets:
                raise ValueError(f"duplicate ticket id {ticket['id']}")
            tickets[ticket["id"]] = {k: v for k, v in ticket.items() if k not in TEST_ONLY_FIELDS}
    if not tickets:
        raise ValueError("no tickets loaded")
    return tickets


class Desk:
    """What the tools did, for the inspection endpoints; one lock, the server is tiny."""

    def __init__(self, tickets: dict[str, dict[str, Any]]) -> None:
        self.tickets = tickets
        self.lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []

    def record(self, tool: str, arguments: dict[str, Any], ctx: Context) -> None:
        names = sorted({name.lower() for name in (ctx.headers or {})})
        with self.lock:
            self.calls.append({"tool": tool, "arguments": arguments, "header_names": names})

    def ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise ToolError("ticket_not_found")
        return ticket

    def snapshot(self, name: str) -> list[dict[str, Any]]:
        with self.lock:
            return list(getattr(self, name))

    def reset(self) -> dict[str, str]:
        with self.lock:
            self.calls.clear()
            self.sent.clear()
        return {"status": "reset"}


def build_server(desk: Desk) -> MCPServer:
    server = MCPServer("ticket-desk")

    @server.tool()
    async def list_tickets(ctx: Context, limit: Annotated[int, Field(ge=1, le=100)] = 20) -> str:
        """List tickets by id: id, subject and received time. Read one with get_ticket."""
        desk.record("list_tickets", {"limit": limit}, ctx)
        rows = [
            {"id": t["id"], "subject": t["subject"], "received_at": t["received_at"]}
            for t in sorted(desk.tickets.values(), key=lambda t: t["id"])
        ]
        return json.dumps(rows[:limit], ensure_ascii=False)

    @server.tool()
    async def get_ticket(
        ticket_id: Annotated[str, Field(min_length=1, max_length=64)], ctx: Context
    ) -> str:
        """One ticket with its channel, received time, subject and body."""
        desk.record("get_ticket", {"ticket_id": ticket_id}, ctx)
        return json.dumps(desk.ticket(ticket_id), ensure_ascii=False)

    @server.tool()
    async def send_reply(
        ticket_id: Annotated[str, Field(min_length=1, max_length=64)],
        body: Annotated[str, Field(min_length=1, max_length=4000)],
        ctx: Context,
    ) -> str:
        """Send a reply to the ticket's requester. Returns the reply id."""
        desk.record("send_reply", {"ticket_id": ticket_id, "body": body}, ctx)
        desk.ticket(ticket_id)
        reply_id = f"reply-{uuid.uuid4().hex[:12]}"
        with desk.lock:
            desk.sent.append({"reply_id": reply_id, "ticket_id": ticket_id, "body": body})
        return f"Reply {reply_id} sent for {ticket_id}."

    return server


def build_app(tickets: dict[str, dict[str, Any]], *, allowed_hosts: list[str]):
    desk = Desk(tickets)
    security = TransportSecuritySettings(allowed_hosts=allowed_hosts, allowed_origins=[])
    inner = build_server(desk).streamable_http_app(transport_security=security)
    routes = {
        ("GET", "/healthz"): lambda: {"status": "ok"},
        ("GET", "/_calls"): lambda: desk.snapshot("calls"),
        ("GET", "/_sent"): lambda: desk.snapshot("sent"),
        ("POST", "/_reset"): desk.reset,
    }

    async def app(scope, receive, send):
        route = routes.get((scope.get("method"), scope.get("path")))
        if scope["type"] == "http" and route is not None:
            await JSONResponse(route())(scope, receive, send)
            return
        await inner(scope, receive, send)

    return app


if __name__ == "__main__":
    files = os.environ.get("TICKET_FILES", DEFAULT_TICKET_FILES)
    hosts = os.environ.get("MCP_ALLOWED_HOSTS", "ticket-desk:*")
    application = build_app(
        load_tickets([Path(p.strip()) for p in files.split(",") if p.strip()]),
        allowed_hosts=[h.strip() for h in hosts.split(",") if h.strip()],
    )
    uvicorn.run(application, host="0.0.0.0", port=8000, access_log=False)

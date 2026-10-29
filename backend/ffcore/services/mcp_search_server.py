"""mcp-search (05a): the MCP server behind `search_documents(query, kb_key, top_k)` (C7).

Runs as its own compose service from the backend image: `python -m ffcore.services.
mcp_search_server`. It holds no signing key and no database access: it relays the caller's
`X-On-Behalf-Of` token unchanged to the backend's knowledge-base search (04a), whose ACL
applies to that user. Request checks: services/mcp_server_common.CallerCheck.
"""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from ffcore.core.config import Settings
from ffcore.services import mcp_server_common
from ffcore.services.mcp_server_common import Relay

DEFAULT_TOOL_KEY = "mcp-search"
NO_HITS = "No passages found."


def format_hits(hits: list[dict[str, Any]]) -> str:
    """Numbered passages with document name and page; the runtime cites them as sources."""
    if not hits:
        return NO_HITS
    parts = []
    for number, hit in enumerate(hits, start=1):
        page = f" (p. {hit['page']})" if hit.get("page") else ""
        parts.append(f"{number}. {hit['document_name']}{page}\n{hit['text']}")
    return "\n\n".join(parts)


def build_server(settings: Settings) -> MCPServer:
    server = MCPServer("mcp-search")

    @server.tool()
    async def search_documents(
        query: Annotated[str, Field(min_length=1, max_length=2000)],
        kb_key: Annotated[str, Field(min_length=1, max_length=64)],
        ctx: Context,
        top_k: Annotated[int, Field(ge=1, le=50)] = 5,
    ) -> str:
        """Search a knowledge base the caller can read. Returns numbered passages with the
        document name and page."""
        relay = Relay(ctx.headers)
        base = f"/api/v1/projects/{relay.project_id}/knowledge-bases"
        listing = await relay.call(settings, "GET", base)
        kb_id = next((kb["id"] for kb in listing["data"] if kb["key"] == kb_key), None)
        if kb_id is None:
            raise ToolError("kb_not_found")
        found = await relay.call(
            settings,
            "POST",
            f"{base}/{kb_id}/search",
            {"query": query, "top_k": top_k},
            not_found="kb_not_found",
        )
        return format_hits(found["hits"])

    return server


def build_app(settings: Settings, *, tool_key: str, allowed_hosts: list[str]):
    return mcp_server_common.build_app(
        build_server(settings), settings, tool_key=tool_key, allowed_hosts=allowed_hosts
    )


if __name__ == "__main__":
    mcp_server_common.serve(build_app, default_key=DEFAULT_TOOL_KEY, key_env="MCP_SEARCH_TOOL_KEY")

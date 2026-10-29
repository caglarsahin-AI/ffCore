# mcp-search

MCP server (streamable HTTP) with one tool, `search_documents(query, kb_key, top_k=5)` (contract
C7). It searches a knowledge base on behalf of the calling user and returns numbered passages
with document name and page.

- Code: `backend/ffcore/services/mcp_search_server.py`. The service runs from the backend image
  (`python -m ffcore.services.mcp_search_server`); the image is built from `backend/`, so the
  code lives in the backend package. This folder holds no code.
- Register it in a project as tool key `mcp-search` with auth type `forward_user`. The key
  matters: the caller's token lists the tool key in `aud`, and this service accepts only tokens
  cut for `mcp-search` (`MCP_SEARCH_TOOL_KEY`).
- It holds no signing key and no database access. It relays the caller's `X-On-Behalf-Of` token
  unchanged to `POST /api/v1/projects/{id}/knowledge-bases/{kb_id}/search`, where the user's
  ACL applies.
- Every request needs `Authorization: Bearer <SERVICE_TOKEN>` and a token for this tool that
  has not expired (401 `token_expired`, 403 `audience_mismatch`). `GET /healthz` is open.

See `docs/araclar.md`.

"""Render a package's OpenAPI draft (`backend/openapi/<package>.yaml`) from the application routes.

Tools container: python -m ffcore.api.openapi_export <package> > openapi/<package>.yaml (03a, 03c,
04a, 05a, 05b, 06a, 06b, 07, 08).
The contract tests compare each committed file with this output, so no draft ever drifts.
Each draft holds only its package's routes: adding a package never changes an earlier draft.
"""

import sys

import yaml
from fastapi.openapi.utils import get_openapi

from ffcore.api import api_router, facade, internal, memories
from ffcore.core.readiness import router as readiness_router

PACKAGES = {
    "03a": {
        "version": "0.3a",
        "description": "Identity, projects, providers, models and audit (package 03a).",
        "tags": {"auth", "users", "projects", "providers", "models", "audit"},
    },
    "03c": {
        "version": "0.3c",
        "description": "Governance: API keys, quotas, usage, retention, alerts and notification "
        "settings (package 03c).",
        "tags": {"api-keys", "quotas", "usage", "retention", "alerts", "notifications"},
    },
    "04a": {
        "version": "0.4a",
        "description": "Knowledge bases, documents, search, internal embedding and readiness "
        "(package 04a).",
        "tags": {"knowledge-bases", "internal", "readiness"},
    },
    "05a": {
        "version": "0.5a",
        "description": "Tool registry: MCP tools, actions, discovery, test calls and the SQL "
        "tool context (package 05a).",
        "tags": {"tools"},
    },
    "05b": {
        "version": "0.5b",
        "description": "Published MCP servers: OpenAPI documents and remote MCP servers served "
        "at /mcp/{key}/, their operations, connection test, calls and self-consumption "
        "(package 05b). The /mcp/{key}/ endpoint itself is MCP streamable HTTP (docs/araclar.md).",
        "tags": {"mcp-servers"},
    },
    "07": {
        "version": "0.7",
        "description": "Approval queue: tool calls waiting for a person (package 07).",
        "tags": {"approvals"},
    },
    "08": {
        "version": "0.8",
        "description": "Guardrail and PII policies, test panel and internal evaluation "
        "(package 08-lite).",
        "tags": {"guardrails", "guardrails-internal"},
    },
    "06a": {
        "version": "0.6a",
        "description": "Agents, versions, runs, run events and run streams (package 06a).",
        "tags": {"agents", "runs"},
    },
    "06b": {
        "version": "0.6b",
        "description": "OpenAI-compatible facade (/v1, contract C11), agent manifest export and "
        "import, external agents (06b-2), and the internal search of runs started by an API key "
        "(package 06b).",
        "tags": {"facade", "facade-internal", "agent-manifest", "agent-external"},
    },
    "09": {
        "version": "0.9",
        "description": "Exams over Langfuse datasets: suites, exam runs, progress (package 09).",
        "tags": {"evaluation"},
    },
    "14": {
        "version": "0.14",
        "description": "User memory: the member's own items, opt-out, administrator settings and "
        "statistics (no text), and the worker's internal recall and extraction writes "
        "(package 14).",
        "tags": {"memories", "memories-internal"},
    },
}


def _routes_with_tags(tags: set[str]) -> list:
    # 04a's /internal and /readyz live outside /api/v1; the other packages' routes do not.
    routes = (
        list(api_router.routes)
        + list(internal.router.routes)
        + list(readiness_router.routes)
        + list(facade.router.routes)  # 06b: /v1, outside /api/v1
        + list(internal.facade_router.routes)
        + list(memories.internal_router.routes)  # 14: /internal/memories
    )
    selected = []
    for route in routes:
        own = getattr(getattr(route, "original_router", None), "tags", None) or getattr(
            route, "tags", None
        )
        if own and set(own) & tags:
            selected.append(route)
    return selected


def render(package: str = "03a") -> str:
    info = PACKAGES[package]
    spec = get_openapi(
        title="FFCore API",
        version=info["version"],
        description=info["description"],
        routes=_routes_with_tags(info["tags"]),
    )
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    sys.stdout.write(render(sys.argv[1] if len(sys.argv) > 1 else "03a"))

"""Render a package's OpenAPI draft (`backend/openapi/<package>.yaml`) from the application routes.

Tools container: python -m ffcore.api.openapi_export <package> > openapi/<package>.yaml (03a, 03c,
04a, 05a, 06a, 07, 08).
The contract tests compare each committed file with this output, so no draft ever drifts.
Each draft holds only its package's routes: adding a package never changes an earlier draft.
"""

import sys

import yaml
from fastapi.openapi.utils import get_openapi

from ffcore.api import api_router, internal
from ffcore.core.readiness import router as readiness_router

PACKAGES = {
    "03a": {
        "version": "0.3a",
        "description": "Identity, projects, providers, models and audit (package 03a).",
        "tags": {"auth", "users", "projects", "providers", "models", "audit"},
    },
    "03c": {
        "version": "0.3c",
        "description": "Governance: API keys, quotas and usage (package 03c).",
        "tags": {"api-keys", "quotas", "usage"},
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
}


def _routes_with_tags(tags: set[str]) -> list:
    # 04a's /internal and /readyz live outside /api/v1; the other packages' routes do not.
    routes = list(api_router.routes) + list(internal.router.routes) + list(readiness_router.routes)
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

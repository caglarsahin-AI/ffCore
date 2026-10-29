"""Application API under /api/v1."""

from fastapi import APIRouter

from ffcore.api import (
    agents,
    audit,
    auth,
    guardrails,
    knowledge,
    models,
    projects,
    providers,
    runs,
    tools,
    tools_internal,
    users,
)

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
for _module in (
    auth,
    users,
    projects,
    providers,
    models,
    audit,
    guardrails,
    knowledge,
    tools,
    tools_internal,
    agents,
    runs,
):
    api_router.include_router(_module.router)

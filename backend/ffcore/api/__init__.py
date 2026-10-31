"""Application API under /api/v1."""

from fastapi import APIRouter

from ffcore.api import (
    agents,
    approvals,
    approvals_internal,
    audit,
    auth,
    guardrails,
    keys,
    knowledge,
    models,
    projects,
    providers,
    quotas,
    runs,
    tools,
    tools_internal,
    usage,
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
    approvals,
    approvals_internal,
    keys,
    quotas,
    usage,
):
    api_router.include_router(_module.router)

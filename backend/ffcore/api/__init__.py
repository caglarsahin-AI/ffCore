"""Application API under /api/v1."""

from fastapi import APIRouter

from ffcore.api import (
    agents,
    alerts,
    approvals,
    approvals_internal,
    audit,
    auth,
    eval,
    guardrails,
    keys,
    knowledge,
    models,
    notifications,
    projects,
    providers,
    quotas,
    retention,
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
    alerts,
    notifications,
    retention,
    eval,
):
    api_router.include_router(_module.router)
# 06b: the agent manifest routes (their own OpenAPI tag).
api_router.include_router(agents.manifest_router)
api_router.include_router(agents.external_router)

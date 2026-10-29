"""Application API under /api/v1."""

from fastapi import APIRouter

from ffcore.api import audit, auth, guardrails, knowledge, models, projects, providers, users

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
for _module in (auth, users, projects, providers, models, audit, guardrails, knowledge):
    api_router.include_router(_module.router)

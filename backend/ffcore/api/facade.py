"""The OpenAI-compatible facade (06b, CONTRACTS C11): the only public entry for model calls.

A client changes only its base URL and API key. `model` picks the path:

- `agent:<project_key>/<agent_key>` runs a published agent (06a runtime; scope `agents`);
- `<project_key>.<model_key>`, or the short `<model_key>` in the key's own project, is a direct
  model call through LiteLLM with the one internal key (A4; scope `chat_direct`).

Identity comes from resolve_actor (C2) plus the `user` field (services/facade_identity.py); the
scope is checked before anything about the target is looked up, so a key cannot probe what
exists outside its scopes. Errors use the OpenAI error schema (03b).
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ffcore.api.common import ERROR_RESPONSES
from ffcore.api.facade_schemas import (
    AGENT_PREFIX,
    ChatCompletionRequest,
    ModelEntry,
    ModelList,
)
from ffcore.api.runs import QueueDep
from ffcore.core import db
from ffcore.core.auth import Actor, resolve_actor
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.models.agents import Agent
from ffcore.models.catalog import Model
from ffcore.models.identity import Project
from ffcore.services import facade_agent, facade_proxy
from ffcore.services.facade_identity import FacadeCaller, facade_caller, require_scope

router = APIRouter(prefix="/v1", tags=["facade"], responses=ERROR_RESPONSES)

SettingsDep = Annotated[Settings, Depends(get_settings)]
ActorDep = Annotated[Actor, Depends(resolve_actor)]


@dataclass(frozen=True)
class Target:
    kind: Literal["agent", "model"]
    key: str  # agent key or model key, inside the caller's project
    name: str  # the full public name (what the client sent, made complete)


def model_not_found(name: str) -> ApiError:
    # Same answer for "no such model" and "another project's model": nothing leaks.
    return ApiError(
        404, "not_found_error", "model_not_found", f"The model '{name}' does not exist."
    )


async def _project_key(project_id: str) -> str:
    async with db.session_scope() as session:
        key = await session.scalar(select(Project.key).where(Project.id == project_id))
    if key is None:
        raise ApiError(401, "authentication_error", "invalid_api_key", "The API key is not valid.")
    return key


def parse_target(name: str, project_key: str) -> tuple[Literal["agent", "model"], str | None]:
    """(path, key inside the caller's project or None when the name points elsewhere)."""
    if name.startswith(AGENT_PREFIX):
        owner, sep, agent_key = name[len(AGENT_PREFIX) :].partition("/")
        if not sep or not agent_key:
            return "agent", None
        return "agent", agent_key if owner == project_key else None
    owner, sep, model_key = name.partition(".")
    if not sep:
        return "model", name  # the short name: always the caller's own project
    return "model", model_key if owner == project_key and model_key else None


async def target_of(caller: FacadeCaller, name: str) -> Target:
    project_key = await _project_key(caller.project_id)
    kind, key = parse_target(name, project_key)
    # The scope first: a key without it learns nothing about what exists (K-06b-0002).
    require_scope(caller, "agents" if kind == "agent" else "chat_direct")
    if key is None:
        raise model_not_found(name)
    full = f"{AGENT_PREFIX}{project_key}/{key}" if kind == "agent" else f"{project_key}.{key}"
    return Target(kind=kind, key=key, name=full)


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    actor: ActorDep,
    settings: SettingsDep,
    queue: QueueDep,
):
    """OpenAI chat completions; `stream: true` answers with OpenAI chunks over SSE."""
    caller = await facade_caller(request, actor, settings, body.user)
    target = await target_of(caller, body.model)
    if target.kind == "agent":
        return await facade_agent.complete(request, caller, target, body, settings, queue)
    return await facade_proxy.complete(request, caller, target, body, settings)


@router.get("/models", response_model=ModelList)
async def list_models(request: Request, actor: ActorDep, settings: SettingsDep):
    """The key's own project: its active models (scope `chat_direct`) and its published agents
    (scope `agents`). Nothing from another project."""
    caller = await facade_caller(request, actor, settings, None)
    project_key = await _project_key(caller.project_id)
    entries: list[ModelEntry] = []
    async with db.session_scope() as session:
        if "chat_direct" in caller.scopes:
            rows = await session.execute(
                select(Model.key, Model.created_at).where(
                    Model.project_id == caller.project_id,
                    Model.is_active,
                    Model.deleted_at.is_(None),
                    Model.category == "llm",
                )
            )
            entries += [
                ModelEntry(id=f"{project_key}.{key}", created=_ts(created), owned_by=project_key)
                for key, created in rows
            ]
        if "agents" in caller.scopes:
            rows = await session.execute(
                select(Agent.key, Agent.created_at).where(
                    Agent.project_id == caller.project_id,
                    Agent.status == "published",
                    Agent.deleted_at.is_(None),
                    # External agents are reserved until 06b-2: not offered (K-06b-0004).
                    Agent.kind == "native",
                )
            )
            entries += [
                ModelEntry(
                    id=f"{AGENT_PREFIX}{project_key}/{key}",
                    created=_ts(created),
                    owned_by=project_key,
                )
                for key, created in rows
            ]
    return ModelList(data=sorted(entries, key=lambda e: e.id))


def _ts(value) -> int:
    return int(value.astimezone(UTC).timestamp()) if value is not None else 0

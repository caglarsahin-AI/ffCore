"""Agents and their versions: two-step creation, draft editing, publish and rollback (06a).

Creation has two steps (brief 06, console review): POST /agents takes key, name, description and
model and opens draft version 1; the rest of the definition is filled with
PUT .../versions/{version}. Only a draft version can be edited; publishing points the agent at a
version, rollback points it back at an earlier published one.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from ffcore.api.agents_schemas import (
    AgentCreate,
    AgentList,
    AgentOut,
    AgentUpdate,
    PublishRequest,
    RollbackRequest,
    VersionCreate,
    VersionList,
    VersionOut,
    VersionUpdate,
)
from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.core.auth import Actor, require_role

router = APIRouter(
    prefix="/projects/{project_id}/agents", tags=["agents"], responses=ERROR_RESPONSES
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
# Analysts build and publish agents (PLAN 1: no code needed to publish an agent).
Editor = Annotated[Actor, Depends(require_role("analyst", write=True))]


@router.get("", response_model=AgentList)
async def list_agents(project_id: UUID, actor: Reader):
    """Agents of the project, deleted ones left out."""
    raise not_implemented()


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(project_id: UUID, body: AgentCreate, actor: Editor):
    """Step one: the agent and its draft version 1."""
    raise not_implemented()


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(project_id: UUID, agent_id: UUID, actor: Reader):
    raise not_implemented()


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(project_id: UUID, agent_id: UUID, body: AgentUpdate, actor: Editor):
    """Name and description; the definition changes through versions."""
    raise not_implemented()


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(project_id: UUID, agent_id: UUID, actor: Editor):
    """Soft delete; runs and versions stay for audit and traces."""
    raise not_implemented()


@router.get("/{agent_id}/versions", response_model=VersionList)
async def list_versions(project_id: UUID, agent_id: UUID, actor: Reader):
    raise not_implemented()


@router.post("/{agent_id}/versions", response_model=VersionOut, status_code=201)
async def create_version(project_id: UUID, agent_id: UUID, body: VersionCreate, actor: Editor):
    """A new draft copied from an existing version (default: the latest)."""
    raise not_implemented()


@router.get("/{agent_id}/versions/{version}", response_model=VersionOut)
async def get_version(project_id: UUID, agent_id: UUID, version: int, actor: Reader):
    raise not_implemented()


@router.put("/{agent_id}/versions/{version}", response_model=VersionOut)
async def update_version(
    project_id: UUID, agent_id: UUID, version: int, body: VersionUpdate, actor: Editor
):
    """Replace a draft's definition. A published version is never edited (409). A definition
    whose context_tokens exceed the model's context window or OLLAMA_CONTEXT_LENGTH is 400
    `context_configuration_invalid` (C13)."""
    raise not_implemented()


@router.post("/{agent_id}/publish", response_model=AgentOut)
async def publish_agent(project_id: UUID, agent_id: UUID, body: PublishRequest, actor: Editor):
    """Publish a version: runs without an explicit version use it. The exam gate (09) is a flag
    until 09 lands."""
    raise not_implemented()


@router.post("/{agent_id}/rollback", response_model=AgentOut)
async def rollback_agent(project_id: UUID, agent_id: UUID, body: RollbackRequest, actor: Editor):
    """Point the agent back at an earlier published version."""
    raise not_implemented()

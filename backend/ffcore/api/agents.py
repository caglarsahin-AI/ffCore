"""Agents and their versions: two-step creation, draft editing, publish and rollback (06a).

Creation has two steps (brief 06, console review): POST /agents takes key, name, description and
model and opens draft version 1; the rest of the definition is filled with
PUT .../versions/{version}. Only a draft version can be edited; publishing points the agent at a
version, rollback points it back at an earlier published one.
"""

import json
from typing import Annotated, Literal
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select

from ffcore.api.agents_schemas import (
    AgentCreate,
    AgentList,
    AgentOut,
    AgentUpdate,
    ExternalAgentCreate,
    ExternalAgentOut,
    ExternalAgentUpdate,
    ExternalEndpoint,
    ImportResult,
    Manifest,
    ManifestAgent,
    PublishRequest,
    RollbackRequest,
    VersionCreate,
    VersionList,
    VersionOut,
    VersionUpdate,
)
from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, not_found, path_resource
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.catalog import Model, Provider
from ffcore.runtime.contracts import AgentStatus
from ffcore.runtime.definition import AgentDefinition, parse_definition
from ffcore.services.facade_external import ExternalConfig, check_base_url

router = APIRouter(
    prefix="/projects/{project_id}/agents", tags=["agents"], responses=ERROR_RESPONSES
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
# Analysts build and publish agents (PLAN 1: no code needed to publish an agent).
Editor = Annotated[Actor, Depends(require_role("analyst", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AgentIdDep = Annotated[str, Depends(path_resource("agent_id"))]

FIRST_PROMPT = "You are a helpful assistant."


def context_invalid(message: str) -> ApiError:
    return ApiError(400, "invalid_request_error", "context_configuration_invalid", message)


async def _agent(session, project_id: UUID, agent_id: UUID) -> Agent:
    agent = await session.scalar(
        select(Agent).where(
            Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None)
        )
    )
    if agent is None:
        raise not_found("agent")
    return agent


def no_versions() -> ApiError:
    return conflict(
        "external_agent_has_no_versions",
        "An external agent has no versions; it is configured at .../external (06b-2).",
    )


def _native(agent: Agent) -> Agent:
    """Version and definition endpoints are for native agents only (06b-2)."""
    if agent.kind == "external":
        raise no_versions()
    return agent


async def _version(session, agent: Agent, version: int) -> AgentVersion:
    row = await session.scalar(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent.id, AgentVersion.version == version
        )
    )
    if row is None:
        raise not_found("version")
    return row


async def _latest(session, agent_id) -> int:
    return await session.scalar(
        select(func.coalesce(func.max(AgentVersion.version), 0)).where(
            AgentVersion.agent_id == agent_id
        )
    )


async def agent_out(session, agent: Agent) -> AgentOut:
    return AgentOut(
        id=agent.id,
        project_id=agent.project_id,
        key=agent.key,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        kind=agent.kind,
        current_version_id=agent.current_version_id,
        latest_version=await _latest(session, agent.id),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def version_out(row: AgentVersion) -> VersionOut:
    return VersionOut(
        id=row.id,
        agent_id=row.agent_id,
        version=row.version,
        definition=parse_definition(row.definition),
        created_by=row.created_by,
        created_at=row.created_at,
        published_at=row.published_at,
        eval_run_id=row.eval_run_id,
    )


async def check_context(
    session, project_id: UUID, definition: AgentDefinition, settings: Settings
) -> None:
    """C13: the budget never exceeds what the model can take; no silent trimming later.
    An unknown or inactive model is 400 too: the version could never run."""
    row = (
        await session.execute(
            select(Model.limits, Provider.driver)
            .join(Provider, Provider.id == Model.provider_id)
            .where(
                Model.project_id == project_id,
                Model.key == definition.model,
                Model.category == "llm",
                Model.is_active.is_(True),
                Model.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise ApiError(
            400,
            "invalid_request_error",
            "model_not_found",
            f"No active chat model {definition.model} in this project.",
        )
    limits, driver = row
    run_timeout = definition.limits.run_timeout_s
    if run_timeout is not None and run_timeout > settings.run_timeout_s:
        # The worker's job timeout follows RUN_TIMEOUT_S; a longer run would be cut by arq.
        raise ApiError(
            400,
            "invalid_request_error",
            "run_timeout_too_long",
            f"limits.run_timeout_s {run_timeout} exceeds RUN_TIMEOUT_S={settings.run_timeout_s}.",
        )
    tokens = definition.limits.context_tokens
    window = (limits or {}).get("context_window")
    if window is not None and tokens > window:
        raise context_invalid(f"context_tokens {tokens} exceed the model's window {window}.")
    if driver == "ollama":
        configured = settings.ollama_context_length
        if configured is None or tokens > configured:
            raise context_invalid(
                f"context_tokens {tokens} exceed OLLAMA_CONTEXT_LENGTH={configured}."
            )


async def _agent_before(session, project_id: UUID, agent_id: UUID, **_) -> AgentOut:
    return await agent_out(session, await _agent(session, project_id, agent_id))


@router.get("", response_model=AgentList)
async def list_agents(project_id: UUID, actor: Reader, session: SessionDep):
    """Agents of the project, deleted ones left out."""
    rows = await session.scalars(
        select(Agent)
        .where(Agent.project_id == project_id, Agent.deleted_at.is_(None))
        .order_by(Agent.key)
    )
    return AgentList(items=[await agent_out(session, a) for a in rows.all()])


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
@audited("create_agent", "agent")
async def create_agent(
    project_id: UUID,
    body: AgentCreate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
):
    """Step one: the agent and its draft version 1."""
    taken = await session.scalar(
        select(Agent.id).where(
            Agent.project_id == project_id, Agent.key == body.key, Agent.deleted_at.is_(None)
        )
    )
    if taken is not None:
        raise conflict("agent_key_taken", "This agent key is already used in the project.")
    definition = parse_definition({"model": body.model, "system_prompt": FIRST_PROMPT})
    await check_context(session, project_id, definition, settings)
    agent = Agent(
        project_id=project_id,
        key=body.key,
        name=body.name,
        description=body.description,
        created_by=actor.actor_id,
    )
    session.add(agent)
    await session.flush()
    session.add(
        AgentVersion(
            agent_id=agent.id,
            version=1,
            definition=definition.model_dump(mode="json"),
            created_by=actor.actor_id,
        )
    )
    await session.flush()
    await session.refresh(agent)
    return await agent_out(session, agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(project_id: UUID, agent_id: UUID, actor: Reader, session: SessionDep):
    return await agent_out(session, await _agent(session, project_id, agent_id))


@router.patch("/{agent_id}", response_model=AgentOut)
@audited("update_agent", "agent", load_before=_agent_before)
async def update_agent(
    project_id: UUID,
    agent_id: UUID,
    body: AgentUpdate,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    """Name and description; the definition changes through versions."""
    agent = await _agent(session, project_id, agent_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await session.flush()
    await session.refresh(agent)
    return await agent_out(session, agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("delete_agent", "agent", load_before=_agent_before)
async def delete_agent(
    project_id: UUID,
    agent_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    resource_id: AgentIdDep,
) -> None:
    """Soft delete; runs and versions stay for audit and traces."""
    agent = await _agent(session, project_id, agent_id)
    agent.deleted_at = func.now()
    agent.status = AgentStatus.inactive


@router.get("/{agent_id}/versions", response_model=VersionList)
async def list_versions(project_id: UUID, agent_id: UUID, actor: Reader, session: SessionDep):
    agent = _native(await _agent(session, project_id, agent_id))
    rows = await session.scalars(
        select(AgentVersion).where(AgentVersion.agent_id == agent.id).order_by(AgentVersion.version)
    )
    return VersionList(items=[version_out(r) for r in rows.all()])


@router.post("/{agent_id}/versions", response_model=VersionOut, status_code=201)
@audited("create_agent_version", "agent_version")
async def create_version(
    project_id: UUID,
    agent_id: UUID,
    body: VersionCreate,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    """A new draft copied from an existing version (default: the latest)."""
    agent = _native(await _agent(session, project_id, agent_id))
    latest = await _latest(session, agent.id)
    source = await _version(session, agent, body.from_version or latest)
    row = AgentVersion(
        agent_id=agent.id,
        version=latest + 1,
        definition=dict(source.definition),
        created_by=actor.actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return version_out(row)


@router.get("/{agent_id}/versions/{version}", response_model=VersionOut)
async def get_version(
    project_id: UUID, agent_id: UUID, version: int, actor: Reader, session: SessionDep
):
    agent = _native(await _agent(session, project_id, agent_id))
    return version_out(await _version(session, agent, version))


async def _version_before(session, project_id, agent_id, version, **_) -> VersionOut:
    agent = _native(await _agent(session, project_id, agent_id))
    return version_out(await _version(session, agent, version))


@router.put("/{agent_id}/versions/{version}", response_model=VersionOut)
@audited("update_agent_version", "agent_version", load_before=_version_before)
async def update_version(
    project_id: UUID,
    agent_id: UUID,
    version: int,
    body: VersionUpdate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
):
    """Replace a draft's definition. A published version is never edited (409). A definition
    whose context_tokens exceed the model's context window or OLLAMA_CONTEXT_LENGTH is 400
    `context_configuration_invalid` (C13)."""
    agent = _native(await _agent(session, project_id, agent_id))
    row = await _version(session, agent, version)
    if row.published_at is not None:
        raise conflict("version_published", "A published version cannot be edited.")
    await check_context(session, project_id, body.definition, settings)
    row.definition = body.definition.model_dump(mode="json")
    await session.flush()
    await session.refresh(row)
    return version_out(row)


async def _point_at(session, agent: Agent, row: AgentVersion) -> None:
    agent.current_version_id = row.id
    agent.status = AgentStatus.published
    if row.published_at is None:
        row.published_at = func.now()
    await session.flush()
    await session.refresh(agent)


@router.post("/{agent_id}/publish", response_model=AgentOut)
@audited("publish_agent", "agent", load_before=_agent_before)
async def publish_agent(
    project_id: UUID,
    agent_id: UUID,
    body: PublishRequest,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
):
    """Publish a version: runs without an explicit version use it. The exam gate (09) is a flag
    until 09 lands."""
    agent = _native(await _agent(session, project_id, agent_id))
    row = await _version(session, agent, body.version)
    # The model may have changed since the draft was saved: checked again (C13).
    await check_context(session, project_id, parse_definition(row.definition), settings)
    await _point_at(session, agent, row)
    return await agent_out(session, agent)


@router.post("/{agent_id}/rollback", response_model=AgentOut)
@audited("rollback_agent", "agent", load_before=_agent_before)
async def rollback_agent(
    project_id: UUID,
    agent_id: UUID,
    body: RollbackRequest,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    """Point the agent back at an earlier published version."""
    agent = _native(await _agent(session, project_id, agent_id))
    row = await _version(session, agent, body.version)
    if row.published_at is None:
        raise conflict("version_never_published", "Rollback goes to a published version only.")
    await _point_at(session, agent, row)
    return await agent_out(session, agent)


# --- 06b: manifest export and import (brief 06 "Manifest") ---

# Own tag: 06b's OpenAPI draft carries these routes, 06a's stays as it is.
manifest_router = APIRouter(
    prefix="/projects/{project_id}/agents", tags=["agent-manifest"], responses=ERROR_RESPONSES
)


def not_portable() -> ApiError:
    # The code 06b gave the refused import (C11: manifest import of kind external is 422); the
    # export of an external agent (06b-2) answers the same way.
    return ApiError(
        422,
        "invalid_request_error",
        "external_agent_not_available",
        "An external agent is not exported or imported: its endpoint and key stay in this "
        "installation. Register it at .../agents/external.",
    )


def _manifest_invalid(message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", "manifest_invalid", message)


@manifest_router.get(
    "/{agent_id}/manifest",
    response_model=Manifest,
    responses={200: {"content": {"application/yaml": {}}}},
)
async def export_manifest(
    project_id: UUID,
    agent_id: UUID,
    actor: Reader,
    session: SessionDep,
    version: int | None = None,
    format: Literal["json", "yaml"] = "json",
):
    """The agent and one version's definition (default: the published one, else the latest).
    Secrets are not in it: an external agent's endpoint and key stay in this installation."""
    agent = await _agent(session, project_id, agent_id)
    if agent.kind == "external":
        raise not_portable()
    if version is None:
        row = (
            await session.get(AgentVersion, agent.current_version_id)
            if agent.current_version_id
            else await _version(session, agent, await _latest(session, agent.id))
        )
    else:
        row = await _version(session, agent, version)
    manifest = Manifest(
        agent=ManifestAgent(
            key=agent.key, name=agent.name, description=agent.description, kind=agent.kind
        ),
        version=row.version,
        definition=parse_definition(row.definition).model_dump(mode="json"),
    )
    if format == "yaml":
        text = yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
        return Response(text, media_type="application/yaml")
    return manifest


async def _manifest_from(request: Request) -> Manifest:
    raw = await request.body()
    kind = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    try:
        if kind in ("application/yaml", "application/x-yaml", "text/yaml"):
            data = yaml.safe_load(raw.decode("utf-8"))
        elif kind == "application/json":
            data = json.loads(raw)
        else:
            raise _manifest_invalid("A manifest is application/json or application/yaml.")
        return Manifest.model_validate(data)
    except (ValueError, yaml.YAMLError, ValidationError) as exc:
        if isinstance(exc, ApiError):
            raise
        raise _manifest_invalid(f"The manifest does not parse: {type(exc).__name__}.") from None


@manifest_router.post(
    "/import",
    response_model=ImportResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/Manifest"}},
                "application/yaml": {"schema": {"$ref": "#/components/schemas/Manifest"}},
            },
        }
    },
)
@audited("import_agent", "agent")
async def import_manifest(
    project_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    dry_run: bool = False,
):
    """A manifest becomes a new agent (draft version 1) or, when the key exists, its next
    draft version; nothing is published. `dry_run=true` validates and writes nothing. An older
    `schema_version` is read as such (C8)."""
    manifest = await _manifest_from(request)
    if manifest.agent.kind != "native":
        # Never imported as a native agent (K-06b-0004); an external agent is registered at
        # .../agents/external with its endpoint, which a manifest does not carry (06b-2).
        raise not_portable()
    try:
        definition = parse_definition(manifest.definition)
    except ValidationError as exc:
        where = ".".join(str(p) for p in exc.errors()[0].get("loc", ()))
        raise _manifest_invalid(f"definition.{where}: {exc.errors()[0].get('msg')}") from None
    await check_context(session, project_id, definition, settings)
    agent = await session.scalar(
        select(Agent).where(
            Agent.project_id == project_id,
            Agent.key == manifest.agent.key,
            Agent.deleted_at.is_(None),
        )
    )
    action = "new_version" if agent is not None else "create"
    version = await _latest(session, agent.id) + 1 if agent is not None else 1
    if dry_run:
        await session.rollback()
        return ImportResult(
            dry_run=True,
            action=action,
            agent_key=manifest.agent.key,
            id=agent.id if agent is not None else None,
            version=version,
            definition=definition,
        )
    if agent is None:
        agent = Agent(
            project_id=project_id,
            key=manifest.agent.key,
            name=manifest.agent.name,
            description=manifest.agent.description,
            created_by=actor.actor_id,
        )
        session.add(agent)
        await session.flush()
    session.add(
        AgentVersion(
            agent_id=agent.id,
            version=version,
            definition=definition.model_dump(mode="json"),
            created_by=actor.actor_id,
        )
    )
    await session.flush()
    return ImportResult(
        dry_run=False,
        action=action,
        agent_key=agent.key,
        id=agent.id,
        version=version,
        definition=definition,
    )


# --- 06b-2: external agents (kind: external) ---

# Own tag: the routes belong to 06b's OpenAPI draft; 06a's draft stays as it is.
external_router = APIRouter(
    prefix="/projects/{project_id}/agents", tags=["agent-external"], responses=ERROR_RESPONSES
)
# Registering an endpoint outside the installation is an administrator's decision (K-06b2-0002).
ExternalAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]


def not_external() -> ApiError:
    return conflict("agent_not_external", "This agent is not an external agent.")


async def external_out(session, agent: Agent, settings: Settings) -> ExternalAgentOut:
    base = await agent_out(session, agent)
    public = ExternalConfig.decrypt(agent.external_config, settings).public()
    return ExternalAgentOut(**base.model_dump(), external=ExternalEndpoint(**public))


async def _external(session, project_id: UUID, agent_id: UUID) -> Agent:
    agent = await _agent(session, project_id, agent_id)
    if agent.kind != "external":
        raise not_external()
    return agent


async def _external_before(session, project_id: UUID, agent_id: UUID, settings, **_):
    return await external_out(session, await _external(session, project_id, agent_id), settings)


@external_router.post("/external", response_model=ExternalAgentOut, status_code=201)
@audited("create_external_agent", "agent")
async def create_external_agent(
    project_id: UUID,
    body: ExternalAgentCreate,
    request: Request,
    actor: ExternalAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Register an external agent (a draft). Its base URL must pass the egress policy now and
    again when it is published and at every call."""
    taken = await session.scalar(
        select(Agent.id).where(
            Agent.project_id == project_id, Agent.key == body.key, Agent.deleted_at.is_(None)
        )
    )
    if taken is not None:
        raise conflict("agent_key_taken", "This agent key is already used in the project.")
    config = ExternalConfig(base_url=body.base_url, model=body.model, api_key=body.api_key)
    await check_base_url(config.base_url, settings)
    agent = Agent(
        project_id=project_id,
        key=body.key,
        name=body.name,
        description=body.description,
        kind="external",
        external_config=config.encrypt(settings),
        created_by=actor.actor_id,
    )
    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    return await external_out(session, agent, settings)


@external_router.get("/{agent_id}/external", response_model=ExternalAgentOut)
async def get_external_agent(
    project_id: UUID, agent_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep
):
    """The agent and its endpoint; the key is never returned."""
    return await external_out(session, await _external(session, project_id, agent_id), settings)


@external_router.put("/{agent_id}/external", response_model=ExternalAgentOut)
@audited("update_external_agent", "agent", load_before=_external_before)
async def update_external_agent(
    project_id: UUID,
    agent_id: UUID,
    body: ExternalAgentUpdate,
    request: Request,
    actor: ExternalAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Change the base URL, remote model or key (omitted fields stay); the kind never changes.
    The resulting base URL is checked again."""
    agent = await _external(session, project_id, agent_id)
    current = ExternalConfig.decrypt(agent.external_config, settings)
    config = current.model_copy(update=body.model_dump(exclude_unset=True))
    config = ExternalConfig.model_validate(
        {**config.model_dump(), "api_key": config.api_key.get_secret_value()}
    )
    await check_base_url(config.base_url, settings)
    agent.external_config = config.encrypt(settings)
    await session.flush()
    await session.refresh(agent)
    return await external_out(session, agent, settings)


@external_router.post("/{agent_id}/external/publish", response_model=ExternalAgentOut)
@audited("publish_external_agent", "agent", load_before=_external_before)
async def publish_external_agent(
    project_id: UUID,
    agent_id: UUID,
    request: Request,
    actor: ExternalAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Publish an external agent (it has no versions): its configuration must exist and its
    base URL passes the egress policy again (K-06b2-0002 S3a)."""
    agent = await _external(session, project_id, agent_id)
    if agent.external_config is None:
        raise conflict(
            "external_agent_not_configured", "The external agent has no endpoint configured."
        )
    config = ExternalConfig.decrypt(agent.external_config, settings)
    await check_base_url(config.base_url, settings)
    agent.status = AgentStatus.published
    await session.flush()
    await session.refresh(agent)
    return await external_out(session, agent, settings)

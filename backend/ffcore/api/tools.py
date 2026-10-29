"""Tool registry (05a): MCP tools of a project, their actions, discovery and test calls.

Reading needs the developer role, every change admin (endpoints and upstream credentials are
security relevant). Secret auth fields are stored encrypted and returned as ***.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, not_found, path_resource
from ffcore.api.tools_schemas import ToolActionOut, ToolCreate, ToolList, ToolOut, ToolUpdate
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.models.tools import Tool, ToolAction
from ffcore.services import mcp_tools

router = APIRouter(prefix="/projects/{project_id}/tools", tags=["tools"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("developer"))]
Admin = Annotated[Actor, Depends(require_role("admin", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ToolIdDep = Annotated[str, Depends(path_resource("tool_id"))]


async def _get(session, project_id: UUID, tool_id: UUID) -> Tool:
    tool = await session.scalar(
        select(Tool).where(
            Tool.id == tool_id, Tool.project_id == project_id, Tool.deleted_at.is_(None)
        )
    )
    if tool is None:
        raise not_found("tool")
    return tool


async def tool_out(session, tool: Tool, settings: Settings) -> ToolOut:
    actions = await session.scalars(
        select(ToolAction).where(ToolAction.tool_id == tool.id).order_by(ToolAction.name)
    )
    fields = mcp_tools.decrypt_auth(tool.auth_config_encrypted, settings)
    return ToolOut(
        id=tool.id,
        project_id=tool.project_id,
        key=tool.key,
        name=tool.name,
        kind=tool.kind,
        endpoint_url=tool.endpoint_url,
        auth=mcp_tools.masked_auth(tool.auth_type, fields),
        status=tool.status,
        discovered_at=tool.discovered_at,
        last_error_code=tool.last_error_code,
        actions=[ToolActionOut.model_validate(a, from_attributes=True) for a in actions],
        created_by=tool.created_by,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


async def _before(session, project_id: UUID, tool_id: UUID, settings: Settings, **_) -> ToolOut:
    return await tool_out(session, await _get(session, project_id, tool_id), settings)


async def _key_taken(session, project_id: UUID, key: str) -> bool:
    found = await session.scalar(
        select(Tool.id).where(
            Tool.project_id == project_id, Tool.key == key, Tool.deleted_at.is_(None)
        )
    )
    return found is not None


@router.get("", response_model=ToolList, summary="List the project's tools")
async def list_tools(project_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep):
    rows = await session.scalars(
        select(Tool)
        .where(Tool.project_id == project_id, Tool.deleted_at.is_(None))
        .order_by(Tool.key)
    )
    return ToolList(data=[await tool_out(session, t, settings) for t in rows])


@router.post("", response_model=ToolOut, status_code=201, summary="Register a tool")
@audited("create_tool", "tool")
async def create_tool(
    project_id: UUID,
    body: ToolCreate,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
):
    """The endpoint passes the outbound policy now and again at every call (C5); forward_user
    only to internal services (C3). Discover the actions next (POST .../discover)."""
    auth = body.auth.model_dump()
    mcp_tools.check_endpoint(body.endpoint_url, auth["type"], settings)
    fields = mcp_tools.new_auth(auth)
    if await _key_taken(session, project_id, body.key):
        raise conflict("tool_key_taken", "This tool key is already used in the project.")
    tool = Tool(
        project_id=project_id,
        key=body.key,
        name=body.name,
        kind=body.kind,
        endpoint_url=body.endpoint_url,
        auth_type=auth["type"],
        auth_config_encrypted=mcp_tools.encrypt_auth(fields, settings),
        status="registered",
        created_by=actor.actor_id,
    )
    session.add(tool)
    await session.flush()
    await session.refresh(tool)
    return await tool_out(session, tool, settings)


@router.get("/{tool_id}", response_model=ToolOut, summary="Get a tool with its actions")
async def get_tool(
    project_id: UUID, tool_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep
):
    return await tool_out(session, await _get(session, project_id, tool_id), settings)


@router.patch("/{tool_id}", response_model=ToolOut, summary="Update a tool")
@audited("update_tool", "tool", load_before=_before)
async def update_tool(
    project_id: UUID,
    tool_id: UUID,
    body: ToolUpdate,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Secret auth fields sent back as *** keep their stored value (same auth type only)."""
    tool = await _get(session, project_id, tool_id)
    changes = body.model_dump(exclude_unset=True)
    auth_type = tool.auth_type
    if "auth" in changes:
        auth = changes.pop("auth")
        stored = mcp_tools.decrypt_auth(tool.auth_config_encrypted, settings)
        fields = mcp_tools.merged_auth(auth, tool.auth_type, stored)
        auth_type = auth["type"]
        tool.auth_config_encrypted = mcp_tools.encrypt_auth(fields, settings)
    mcp_tools.check_endpoint(changes.get("endpoint_url", tool.endpoint_url), auth_type, settings)
    tool.auth_type = auth_type
    for field, value in changes.items():
        setattr(tool, field, value)
    await session.flush()
    await session.refresh(tool)
    return await tool_out(session, tool, settings)


@router.delete("/{tool_id}", status_code=204, summary="Delete a tool")
@audited("delete_tool", "tool", load_before=_before)
async def delete_tool(
    project_id: UUID,
    tool_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ToolIdDep,
) -> None:
    """Soft delete; the key can be used again."""
    tool = await _get(session, project_id, tool_id)
    tool.deleted_at = func.now()

"""Tool registry (05a): MCP tools of a project, their actions, discovery and test calls.

Reading needs the developer role, every change admin (endpoints and upstream credentials are
security relevant). Secret auth fields are stored encrypted and returned as ***.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    not_found,
    not_implemented,
    path_resource,
)
from ffcore.api.tools_schemas import (
    InvokeRequest,
    InvokeResult,
    SqlColumn,
    SqlContext,
    SqlContextRequest,
    SqlExample,
    SqlTable,
    ToolActionOut,
    ToolActionUpdate,
    ToolCreate,
    ToolList,
    ToolOut,
    ToolUpdate,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.models.tools import Tool, ToolAction
from ffcore.services import mcp_client, mcp_sql_context, mcp_tools

router = APIRouter(prefix="/projects/{project_id}/tools", tags=["tools"], responses=ERROR_RESPONSES)

AnyMember = Annotated[Actor, Depends(require_role("user"))]
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


async def _action(session, tool: Tool, name: str) -> ToolAction:
    action = await session.scalar(
        select(ToolAction).where(ToolAction.tool_id == tool.id, ToolAction.name == name)
    )
    if action is None:
        raise ApiError(404, "not_found_error", "action_not_found", "Action not found.")
    return action


@router.post("/{tool_id}/discover", response_model=ToolOut, summary="Discover the tool's actions")
@audited("discover_tool", "tool")
async def discover_tool(
    project_id: UUID,
    tool_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
):
    """MCP tools/list with the tool's own identity. The outcome is the result: a failed
    discovery answers 200 with status=error and last_error_code (the connection test shown on
    screen). New actions start disabled and needing approval."""
    tool = await _get(session, project_id, tool_id)
    if tool.kind != "mcp":
        raise not_implemented()
    caller = mcp_client.Caller(user_id=actor.actor_id, project_id=str(project_id))
    try:
        found = await mcp_client.discover(
            mcp_tools.target_of(tool, settings), settings, caller=caller
        )
    except mcp_client.ToolCallError as exc:
        tool.status, tool.last_error_code = "error", exc.code
    else:
        await mcp_tools.apply_discovery(session, tool, found)
        tool.status, tool.last_error_code, tool.discovered_at = "discovered", None, func.now()
    await session.flush()
    await session.refresh(tool)
    return await tool_out(session, tool, settings)


@router.patch(
    "/{tool_id}/actions/{action_name}",
    response_model=ToolActionOut,
    summary="Change an action's settings",
)
@audited("update_tool_action", "tool")
async def update_tool_action(
    project_id: UUID,
    tool_id: UUID,
    action_name: str,
    body: ToolActionUpdate,
    request: Request,
    actor: Admin,
    session: SessionDep,
    resource_id: ToolIdDep,
):
    """enabled, needs_approval, max_calls_per_run and timeout_s; discovery never changes them."""
    tool = await _get(session, project_id, tool_id)
    action = await _action(session, tool, action_name)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(action, field, value)
    await session.flush()
    await session.refresh(action)
    return ToolActionOut.model_validate(action, from_attributes=True)


@router.post(
    "/{tool_id}/actions/{action_name}/invoke",
    response_model=InvokeResult,
    summary="Call an action directly (test call)",
)
@audited("invoke_tool_action", "tool", audit_payload=False)
async def invoke_tool_action(
    project_id: UUID,
    tool_id: UUID,
    action_name: str,
    body: InvokeRequest,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ToolIdDep,
):
    """An admin's test call, with the tool's identity (forward_user: the admin's). It runs
    whether the action is enabled or not and asks no approval: the admin calling it is the
    decision, and the audit records it (arguments and result are not stored there). A missing
    action is refused (409 action_missing); a failed call is 502 with its code."""
    tool = await _get(session, project_id, tool_id)
    action = await _action(session, tool, action_name)
    if tool.kind != "mcp":
        raise not_implemented()
    if action.status == "missing":
        raise conflict("action_missing", "The tool no longer lists this action.")
    caller = mcp_client.Caller(user_id=actor.actor_id, project_id=str(project_id))
    try:
        result = await mcp_client.call(
            mcp_tools.target_of(tool, settings),
            action.name,
            body.arguments,
            settings,
            caller=caller,
            timeout_s=action.timeout_s,
        )
    except mcp_client.ToolCallError as exc:
        raise ApiError(502, "api_error", exc.code, f"The tool call failed ({exc.code}).") from None
    return InvokeResult(
        text=result.text,
        truncated=result.truncated,
        total_chars=result.total_chars,
        is_error=result.is_error,
        latency_ms=result.latency_ms,
    )


@router.post("/sql-context", response_model=SqlContext, summary="SQL tool context (mcp-sql)")
async def sql_context(
    project_id: UUID,
    body: SqlContextRequest,
    actor: AnyMember,
    session: SessionDep,
    settings: SettingsDep,
):
    """For mcp-sql's get_schema, on behalf of the user running the agent (any project role).
    Descriptions narrowed to the question by keywords, and the project's five nearest
    question-SQL examples (in-process embedding, pgvector cosine)."""
    found = await mcp_sql_context.context(session, project_id, body.question, settings)
    return SqlContext(
        tables=[
            SqlTable(
                name=t.name,
                description=t.description,
                columns=[SqlColumn(**vars(c)) for c in t.columns],
            )
            for t in found.tables
        ],
        matched=found.matched,
        examples=[SqlExample(question=q, sql=s) for q, s in found.examples],
    )

"""Published MCP servers (05b): an OpenAPI document or a remote MCP server served at
`/mcp/{key}/` (services/mcp_publish), its operations, selection, connection test, calls and the
step that adds it to the project's tools (self-consumption, 05a registry).

Reading needs the analyst role, every change admin with edit access (upstream credentials and
what agents may call are security relevant). The document and the upstream identity are stored
encrypted; secret identity fields are returned as ***; the document is never returned.
"""

import statistics
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import httpx2
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, not_found, path_resource
from ffcore.api.mcp_servers_schemas import (
    CallOut,
    CallsSummary,
    ConnectionTest,
    McpServerCreate,
    McpServerList,
    McpServerOut,
    McpServerUpdate,
    OperationOut,
    SpecUpload,
)
from ffcore.api.tools import tool_out
from ffcore.api.tools_schemas import ToolOut
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json
from ffcore.guardrails.service import resolve_policy
from ffcore.models.mcp_servers import McpServer, McpServerCall
from ffcore.models.tools import Tool
from ffcore.services import mcp_client, mcp_openapi, mcp_tools
from ffcore.services.mcp_publish import check_upstream_url

router = APIRouter(
    prefix="/projects/{project_id}/mcp-servers", tags=["mcp-servers"], responses=ERROR_RESPONSES
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
Admin = Annotated[Actor, Depends(require_role("admin", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ServerIdDep = Annotated[str, Depends(path_resource("server_id"))]
RECENT = 50


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", code, message)


def _spec_error(exc: mcp_openapi.SpecError) -> ApiError:
    return _invalid(exc.code, str(exc))


async def _get(session, project_id: UUID, server_id: UUID) -> McpServer:
    row = await session.scalar(
        select(McpServer).where(
            McpServer.id == server_id,
            McpServer.project_id == project_id,
            McpServer.deleted_at.is_(None),
        )
    )
    if row is None:
        raise not_found("mcp_server")
    return row


def server_out(row: McpServer, settings: Settings) -> McpServerOut:
    exposed = set(row.exposed_operations or [])
    fields = mcp_tools.decrypt_auth(row.upstream_auth_encrypted, settings)
    return McpServerOut(
        id=row.id,
        project_id=row.project_id,
        key=row.key,
        name=row.name,
        source_kind=row.source_kind,
        endpoint_path=f"/mcp/{row.key}/",
        upstream_base_url=row.upstream_base_url,
        upstream_auth=mcp_tools.masked_auth(row.upstream_auth_type, fields),
        operations=[
            OperationOut(
                name=op["name"],
                method=op.get("method"),
                path=op.get("path"),
                description=op.get("description"),
                input_schema=op.get("input_schema") or {},
                exposable=bool(op.get("exposable")),
                reason=op.get("reason"),
                alias=op.get("alias"),
                alias_description=op.get("alias_description"),
                exposed=op["name"] in exposed,
            )
            for op in row.operations or []
        ],
        exposed_operations=sorted(exposed),
        protocols=list(row.protocols or []),
        access=row.access,
        guardrail_mode=row.guardrail_mode,
        guardrail_policy_key=row.guardrail_policy_key,
        status=row.status,
        discovered_at=row.discovered_at,
        last_error_code=row.last_error_code,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _out(session, row: McpServer, settings: Settings) -> McpServerOut:
    await session.flush()
    await session.refresh(row)
    return server_out(row, settings)


async def _before(session, project_id: UUID, server_id: UUID, settings: Settings, **_):
    return server_out(await _get(session, project_id, server_id), settings)


async def _check_policy(session, project_id: UUID, key: str) -> None:
    try:
        await resolve_policy(session, project_id, key)
    except ApiError as exc:
        if exc.status_code == 404:
            raise _invalid(
                "guardrail_policy_not_found", "No guardrail policy with this key in the project."
            ) from None
        raise


def _merge_catalog(old: list[dict], new: list[dict], exposed: list[str]) -> list[dict]:
    """New catalog keeping aliases by name; a selected operation that disappeared or became
    unpublishable is refused (409), never dropped silently."""
    aliases = {op["name"]: (op.get("alias"), op.get("alias_description")) for op in old}
    by_name = {op["name"]: op for op in new}
    lost = [n for n in exposed if n not in by_name or not by_name[n].get("exposable")]
    if lost:
        raise conflict(
            "exposed_operation_missing",
            "Selected operations are missing or not publishable in the new document: "
            + ", ".join(sorted(lost)),
        )
    for op in new:
        op["alias"], op["alias_description"] = aliases.get(op["name"], (None, None))
    return new


def _catalog_from_spec(text: str) -> list[dict]:
    try:
        return mcp_openapi.catalog(mcp_openapi.load_spec(text))
    except mcp_openapi.SpecError as exc:
        raise _spec_error(exc) from None


@router.get("", response_model=McpServerList, summary="List the project's published MCP servers")
async def list_servers(project_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep):
    """Analyst role or above; secret identity fields are returned as ***."""
    rows = await session.scalars(
        select(McpServer)
        .where(McpServer.project_id == project_id, McpServer.deleted_at.is_(None))
        .order_by(McpServer.key)
    )
    return McpServerList(data=[server_out(r, settings) for r in rows])


@router.post("", response_model=McpServerOut, status_code=201, summary="Register an MCP server")
@audited("create_mcp_server", "mcp_server")
async def create_server(
    project_id: UUID,
    body: McpServerCreate,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
):
    """openapi: the document is read now and its operations listed (none selected). remote_mcp:
    discover next. The server starts as draft; selecting operations and status=active serve it.
    The key is unique in the installation (409 mcp_server_key_taken)."""
    check_upstream_url(body.upstream_base_url, settings)
    fields = mcp_tools.new_auth(body.upstream_auth.model_dump())
    operations, spec = [], None
    if body.source_kind == "openapi":
        if body.spec is None:
            raise _invalid("spec_required", "An openapi server needs its OpenAPI document.")
        operations = _catalog_from_spec(body.spec)
        spec = encrypt_json({"text": body.spec}, settings)
    elif body.spec is not None:
        raise _invalid("spec_not_applicable", "A remote_mcp server takes no document.")
    await _check_policy(session, project_id, body.guardrail_policy_key)
    taken = await session.scalar(
        select(McpServer.id).where(McpServer.key == body.key, McpServer.deleted_at.is_(None))
    )
    if taken is not None:
        raise conflict("mcp_server_key_taken", "This MCP server key is already used.")
    row = McpServer(
        project_id=project_id,
        key=body.key,
        name=body.name,
        source_kind=body.source_kind,
        spec_encrypted=spec,
        upstream_base_url=body.upstream_base_url,
        upstream_auth_type=body.upstream_auth.type,
        upstream_auth_encrypted=mcp_tools.encrypt_auth(fields, settings),
        operations=operations,
        exposed_operations=[],
        access=body.access,
        guardrail_mode=body.guardrail_mode,
        guardrail_policy_key=body.guardrail_policy_key,
        status="draft",
        discovered_at=func.now() if body.source_kind == "openapi" else None,
        created_by=actor.actor_id,
    )
    session.add(row)
    return await _out(session, row, settings)


@router.get("/{server_id}", response_model=McpServerOut, summary="Get an MCP server")
async def get_server(
    project_id: UUID, server_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep
):
    """Analyst role or above; secret identity fields are returned as ***."""
    return server_out(await _get(session, project_id, server_id), settings)


@router.patch("/{server_id}", response_model=McpServerOut, summary="Update an MCP server")
@audited("update_mcp_server", "mcp_server", load_before=_before)
async def update_server(
    project_id: UUID,
    server_id: UUID,
    body: McpServerUpdate,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Selection by operation name (422 operation_unknown / operation_not_exposable); aliases
    must be unique tool names (422 alias_conflict). Secret identity fields sent back as *** keep
    their stored value (same type only)."""
    row = await _get(session, project_id, server_id)
    changes = body.model_dump(exclude_unset=True)
    if "upstream_auth" in changes:
        auth = changes.pop("upstream_auth")
        stored = mcp_tools.decrypt_auth(row.upstream_auth_encrypted, settings)
        fields = mcp_tools.merged_auth(auth, row.upstream_auth_type, stored)
        row.upstream_auth_type = auth["type"]
        row.upstream_auth_encrypted = mcp_tools.encrypt_auth(fields, settings)
    if "upstream_base_url" in changes:
        check_upstream_url(changes["upstream_base_url"], settings)
    if "guardrail_policy_key" in changes:
        await _check_policy(session, project_id, changes["guardrail_policy_key"])
    operations = [dict(op) for op in row.operations or []]
    by_name = {op["name"]: op for op in operations}
    if "aliases" in changes:
        for name, alias in changes.pop("aliases").items():
            if name not in by_name:
                raise _invalid("operation_unknown", f"No operation named {name}.")
            by_name[name]["alias"] = alias.get("name")
            by_name[name]["alias_description"] = alias.get("description")
        row.operations = operations
    if "exposed_operations" in changes:
        chosen = sorted(set(changes.pop("exposed_operations")))
        for name in chosen:
            if name not in by_name:
                raise _invalid("operation_unknown", f"No operation named {name}.")
            if not by_name[name].get("exposable"):
                raise _invalid(
                    "operation_not_exposable",
                    f"{name} cannot be published ({by_name[name].get('reason')}).",
                )
        row.exposed_operations = chosen
    visible = [op.get("alias") or op["name"] for op in operations]
    if len(visible) != len(set(visible)):
        raise _invalid("alias_conflict", "Two operations would have the same tool name.")
    for field, value in changes.items():
        setattr(row, field, value)
    return await _out(session, row, settings)


@router.delete("/{server_id}", status_code=204, summary="Delete an MCP server")
@audited("delete_mcp_server", "mcp_server", load_before=_before)
async def delete_server(
    project_id: UUID,
    server_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ServerIdDep,
) -> None:
    """Soft delete: the endpoint stops at once; the key can be used again. Its calls are kept."""
    row = await _get(session, project_id, server_id)
    row.deleted_at = func.now()


@router.put("/{server_id}/spec", response_model=McpServerOut, summary="Replace the document")
@audited("update_mcp_server_spec", "mcp_server", audit_payload=False)
async def replace_spec(
    project_id: UUID,
    server_id: UUID,
    body: SpecUpload,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ServerIdDep,
):
    """openapi only (409 spec_not_applicable). Selection and aliases are kept by operation name;
    a selected operation missing from the new document is 409 exposed_operation_missing and
    nothing changes."""
    row = await _get(session, project_id, server_id)
    if row.source_kind != "openapi":
        raise conflict("spec_not_applicable", "Only an openapi server has a document.")
    new = _catalog_from_spec(body.spec)
    row.operations = _merge_catalog(row.operations or [], new, row.exposed_operations or [])
    row.spec_encrypted = encrypt_json({"text": body.spec}, settings)
    row.discovered_at, row.last_error_code = func.now(), None
    return await _out(session, row, settings)


def _target(row: McpServer, settings: Settings) -> mcp_client.ToolTarget:
    return mcp_client.ToolTarget(
        key=row.key,
        endpoint_url=row.upstream_base_url,
        auth_type=row.upstream_auth_type,
        auth=mcp_tools.decrypt_auth(row.upstream_auth_encrypted, settings),
    )


@router.post("/{server_id}/discover", response_model=McpServerOut, summary="Discover operations")
@audited("discover_mcp_server", "mcp_server", audit_payload=False)
async def discover_server(
    project_id: UUID,
    server_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ServerIdDep,
):
    """openapi: the stored document read again. remote_mcp: the upstream's tools/list with the
    server's upstream identity; a failed discovery answers 200 with last_error_code (shown on
    screen) and keeps the previous catalog."""
    row = await _get(session, project_id, server_id)
    if row.source_kind == "openapi":
        text = decrypt_json(row.spec_encrypted, settings)["text"]
        new = _catalog_from_spec(text)
    else:
        caller = mcp_client.Caller(user_id=actor.actor_id, project_id=str(project_id))
        try:
            check_upstream_url(row.upstream_base_url, settings)
            found = await mcp_client.discover(_target(row, settings), settings, caller=caller)
        except mcp_client.ToolCallError as exc:
            row.last_error_code = exc.code
            return await _out(session, row, settings)
        new = [
            {
                "name": action.name,
                "method": None,
                "path": None,
                "description": action.description,
                "input_schema": action.input_schema,
                "exposable": mcp_openapi.TOOL_NAME.fullmatch(action.name) is not None,
                "reason": None
                if mcp_openapi.TOOL_NAME.fullmatch(action.name)
                else "operation_name_invalid",
                "alias": None,
                "alias_description": None,
            }
            for action in found
        ]
    row.operations = _merge_catalog(row.operations or [], new, row.exposed_operations or [])
    row.discovered_at, row.last_error_code = func.now(), None
    return await _out(session, row, settings)


@router.post("/{server_id}/test", response_model=ConnectionTest, summary="Test the upstream")
@audited("test_mcp_server", "mcp_server", audit_payload=False)
async def test_server(
    project_id: UUID,
    server_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ServerIdDep,
):
    """openapi: one GET to the upstream base URL with the server's identity (redirects not
    followed); any HTTP answer is reachable and its status is shown. remote_mcp: initialize and
    tools/list. Nothing of the answer is stored or returned but the status."""
    row = await _get(session, project_id, server_id)
    started = datetime.now(UTC)

    def ms() -> int:
        return int((datetime.now(UTC) - started).total_seconds() * 1000)

    check_upstream_url(row.upstream_base_url, settings)
    if row.source_kind == "remote_mcp":
        caller = mcp_client.Caller(user_id=actor.actor_id, project_id=str(project_id))
        try:
            found = await mcp_client.discover(_target(row, settings), settings, caller=caller)
        except mcp_client.ToolCallError as exc:
            return ConnectionTest(
                reachable=False, status_code=None, error_code=exc.code, latency_ms=ms(), tools=None
            )
        return ConnectionTest(
            reachable=True, status_code=None, error_code=None, latency_ms=ms(), tools=len(found)
        )
    limit = settings.mcp_call_timeout_s
    timeout = EgressTimeout(connect=min(5, limit), read=limit, total=limit)
    fields = mcp_tools.decrypt_auth(row.upstream_auth_encrypted, settings)
    headers = mcp_client.static_auth_headers(row.upstream_auth_type, fields)
    try:
        async with SafeOutboundClient(timeout=timeout, settings=settings, max_redirects=0) as http:
            async with http.stream("GET", row.upstream_base_url, headers=headers) as response:
                status = response.status_code
    except EgressError as exc:
        code = exc.code
        if code == "egress_too_many_redirects":
            return ConnectionTest(
                reachable=True, status_code=None, error_code=code, latency_ms=ms(), tools=None
            )
        return ConnectionTest(
            reachable=False, status_code=None, error_code=code, latency_ms=ms(), tools=None
        )
    except httpx2.HTTPError:
        return ConnectionTest(
            reachable=False,
            status_code=None,
            error_code="upstream_unreachable",
            latency_ms=ms(),
            tools=None,
        )
    return ConnectionTest(
        reachable=True, status_code=status, error_code=None, latency_ms=ms(), tools=None
    )


@router.post(
    "/{server_id}/tools",
    response_model=ToolOut,
    status_code=201,
    summary="Add the server to the project's tools",
)
@audited("add_mcp_server_tool", "mcp_server")
async def add_to_tools(
    project_id: UUID,
    server_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ServerIdDep,
):
    """A 05a tool with the server's key at <INTERNAL_API_URL>/mcp/<key>/ and forward_user, so an
    agent calls it with the user's identity through this endpoint (guardrail, quota and log of
    the server apply). Discover it next in the tools registry; its actions start disabled and
    needing approval (05a rule; 07 approval happens on the agent side). 409 tool_key_taken."""
    row = await _get(session, project_id, server_id)
    taken = await session.scalar(
        select(Tool.id).where(
            Tool.project_id == project_id, Tool.key == row.key, Tool.deleted_at.is_(None)
        )
    )
    if taken is not None:
        raise conflict("tool_key_taken", "This tool key is already used in the project.")
    endpoint = mcp_tools.self_endpoint(settings, row.key)
    mcp_tools.check_endpoint(endpoint, "forward_user", settings)
    tool = Tool(
        project_id=project_id,
        key=row.key,
        name=row.name,
        kind="mcp",
        endpoint_url=endpoint,
        auth_type="forward_user",
        auth_config_encrypted=mcp_tools.encrypt_auth({}, settings),
        status="registered",
        created_by=actor.actor_id,
    )
    session.add(tool)
    await session.flush()
    await session.refresh(tool)
    return await tool_out(session, tool, settings)


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return int(statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1])


@router.get("/{server_id}/calls", response_model=CallsSummary, summary="Calls of the server")
async def calls_summary(
    project_id: UUID,
    server_id: UUID,
    actor: Reader,
    session: SessionDep,
    hours: Annotated[int, Query(ge=1, le=24 * 31)] = 24,
):
    """Requests, errors and latency in the window, and the last 50 calls (10c-3 monitoring).
    Rows carry no arguments or results."""
    row = await _get(session, project_id, server_id)
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = (
        await session.scalars(
            select(McpServerCall)
            .where(McpServerCall.server_id == row.id, McpServerCall.ts >= since)
            .order_by(McpServerCall.ts.desc(), McpServerCall.id)
        )
    ).all()
    latencies = sorted(r.latency_ms for r in rows)
    return CallsSummary(
        window_hours=hours,
        requests=len(rows),
        errors=sum(1 for r in rows if r.status != "ok"),
        blocked=sum(1 for r in rows if r.status == "blocked"),
        p50_ms=_percentile(latencies, 50),
        p95_ms=_percentile(latencies, 95),
        recent=[
            CallOut(
                operation=r.operation,
                status=r.status,
                error_code=r.error_code,
                latency_ms=r.latency_ms,
                ts=r.ts,
                run_id=r.run_id,
                actor_type=r.actor_type,
            )
            for r in rows[:RECENT]
        ],
    )

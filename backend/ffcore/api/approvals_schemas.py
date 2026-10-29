"""Request and response bodies of the 07 approval queue; the source of `backend/openapi/07.yaml`."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    """`expired`: no decision within APPROVAL_TTL_MIN; the run was closed (`approval_expired`)."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ApproverRole(StrEnum):
    """The least role that may decide; `user` never approves."""

    analyst = "analyst"
    developer = "developer"
    admin = "admin"


class ApprovalOut(BaseModel):
    id: UUID
    project_id: UUID
    run_id: UUID
    tool_call_id: str
    action: str = Field(description="Model-facing tool name `<tool_key>__<action>` (C7).")
    tool_key: str | None = Field(description="The tool part of `action`; null if it has none.")
    arguments: dict[str, Any] = Field(
        description="Tool call arguments as masked by the guardrail before the run stopped; "
        "raw values are never stored."
    )
    reason_from_model: str | None
    status: ApprovalStatus
    assigned_role: ApproverRole
    requested_at: datetime
    expires_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None
    can_decide: bool = Field(
        description="Whether this caller may approve or reject: console session, `edit` access "
        "and a role at least `assigned_role`. Shown for buttons; the decision route checks again."
    )


class ApprovalList(BaseModel):
    data: list[ApprovalOut]


class ApprovalCount(BaseModel):
    status: ApprovalStatus
    count: int

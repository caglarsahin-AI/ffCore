"""Request and response bodies of the 03c quotas; part of `backend/openapi/03c.yaml`."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import Patch, Strict

Count = int | None


class QuotaScope(StrEnum):
    """Whom the quota limits. The project's quota is a ceiling for every key and user in it."""

    project = "project"
    api_key = "api_key"
    user = "user"


class QuotaAction(StrEnum):
    """block: the call is refused (quota_exceeded); warn: the call goes on and is reported."""

    block = "block"
    warn = "warn"


class QuotaWindows(Strict):
    rpm: Count = Field(default=None, gt=0, description="Calls per minute (UTC).")
    rph: Count = Field(default=None, gt=0, description="Calls per hour.")
    rpd: Count = Field(default=None, gt=0, description="Calls per day.")
    rpm_month: Count = Field(default=None, gt=0, description="Calls per calendar month.")
    concurrent: Count = Field(default=None, gt=0, description="Calls in flight at once.")


class QuotaTokens(Strict):
    tpm: Count = Field(default=None, gt=0, description="Tokens per minute.")
    tpd: Count = Field(default=None, gt=0, description="Tokens per day.")
    tpm_month: Count = Field(default=None, gt=0, description="Tokens per calendar month.")
    max_input: Count = Field(default=None, gt=0, description="Input tokens of one call.")
    max_output: Count = Field(default=None, gt=0, description="Output tokens of one call.")
    max_total: Count = Field(default=None, gt=0, description="Input + output of one call.")


class QuotaBudget(Strict):
    daily_usd: Decimal | None = Field(default=None, ge=0, description="USD per UTC day.")
    monthly_usd: Decimal | None = Field(default=None, ge=0, description="USD per month.")


class QuotaCreate(Strict):
    scope_type: QuotaScope
    scope_id: UUID | None = Field(
        default=None, description="API key or user id; omitted (the project) for scope project."
    )
    label: str = Field(min_length=1, max_length=120)
    priority: int = 0
    windows: QuotaWindows = Field(default_factory=QuotaWindows)
    tokens: QuotaTokens = Field(default_factory=QuotaTokens)
    budget: QuotaBudget = Field(default_factory=QuotaBudget)
    action: QuotaAction = QuotaAction.block
    is_active: bool = True
    activate_at: datetime | None = Field(
        default=None, description="The quota counts from this moment on; empty: at once."
    )


class QuotaUpdate(Patch):
    label: str = Field(default=None, min_length=1, max_length=120)
    priority: int = Field(default=None)
    windows: QuotaWindows = Field(default=None)
    tokens: QuotaTokens = Field(default=None)
    budget: QuotaBudget = Field(default=None)
    action: QuotaAction = Field(default=None)
    is_active: bool = Field(default=None)
    activate_at: datetime | None = Field(default=None)


class QuotaOut(BaseModel):
    id: UUID
    project_id: UUID
    scope_type: QuotaScope
    scope_id: UUID
    label: str
    priority: int
    windows: QuotaWindows
    tokens: QuotaTokens
    budget: QuotaBudget
    action: QuotaAction
    is_active: bool
    activate_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class QuotaList(BaseModel):
    data: list[QuotaOut]

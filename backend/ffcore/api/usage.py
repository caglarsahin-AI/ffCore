"""Usage (03c): the project's usage_daily rows over a date range, with totals.

Reporting only; quotas decide from Redis (C20). `unpriced_requests` counts calls whose cost is
unknown (model without a price, FOLLOWUP-69): their cost is not in `cost_usd`.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, invalid
from ffcore.core.auth import Actor, require_role
from ffcore.models.quota import UsageDaily

router = APIRouter(prefix="/projects/{project_id}/usage", tags=["usage"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
MAX_DAYS = 400


class UsageRow(BaseModel):
    date: date
    model: str = Field(description="Virtual model name `<project_key>.<model_key>` (C1).")
    api_key_id: UUID | None
    user_id: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    requests: int
    unpriced_requests: int = Field(description="Calls on a model without a price.")


class UsageTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    requests: int
    unpriced_requests: int


class UsageSummary(BaseModel):
    project_id: UUID
    date_from: date
    date_to: date
    totals: UsageTotals
    data: list[UsageRow]


@router.get("", response_model=UsageSummary, summary="Usage of the project over a date range")
async def get_usage(
    project_id: UUID,
    actor: Reader,
    session: SessionDep,
    date_from: Annotated[
        date | None, Query(description="First UTC day; default 30 days ago.")
    ] = None,
    date_to: Annotated[date | None, Query(description="Last UTC day; default today.")] = None,
):
    today = datetime.now(UTC).date()
    date_to = date_to or today
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to or (date_to - date_from).days >= MAX_DAYS:
        raise invalid("date_range_invalid", f"date_from..date_to must be 1..{MAX_DAYS} days.")
    rows = list(
        await session.scalars(
            select(UsageDaily)
            .where(
                UsageDaily.project_id == project_id,
                UsageDaily.date >= date_from,
                UsageDaily.date <= date_to,
            )
            .order_by(UsageDaily.date, UsageDaily.model, UsageDaily.id)
        )
    )
    data = [
        UsageRow(
            date=r.date,
            model=r.model,
            api_key_id=r.api_key_id,
            user_id=r.user_id,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            cost_usd=r.cost_usd,
            requests=r.requests,
            unpriced_requests=r.unpriced_requests,
        )
        for r in rows
    ]
    totals = UsageTotals(
        input_tokens=sum(r.input_tokens for r in data),
        output_tokens=sum(r.output_tokens for r in data),
        cost_usd=sum((r.cost_usd for r in data), Decimal(0)),
        requests=sum(r.requests for r in data),
        unpriced_requests=sum(r.unpriced_requests for r in data),
    )
    return UsageSummary(
        project_id=project_id, date_from=date_from, date_to=date_to, totals=totals, data=data
    )

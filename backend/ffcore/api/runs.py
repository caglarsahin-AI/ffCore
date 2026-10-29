"""Runs: start an agent, follow it as server-sent events, resume, cancel and read back (06a).

A run is one arq job on the agent worker (C10); the API never runs the graph. Events go to
Postgres (`run_events`, durable) and a Redis Stream (live, replay for late or reconnecting
clients; K-06a-0002 S2). Closing the stream never cancels a run: only POST .../cancel does
(K-06a-0002 S8); a running run with no subscriber for RUN_ABANDON_GRACE_S is `abandoned`.

Starting a run and answering its question are chat, open in read-only access mode like 11's
chat (brief 03 read-only exceptions). Approving is a platform mutation: resume with a decision
checks the definition's `approval.assign_to` role and `edit` access in the handler, because
the body decides which rule applies (write-flag scan exemption, with this reason).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse

from ffcore.api.agents_schemas import (
    SSE_DESCRIPTION,
    AgentKey,
    ResumeRequest,
    RunCreate,
    RunEventList,
    RunList,
    RunOut,
)
from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.core.auth import Actor, require_role
from ffcore.runtime.contracts import Channel, RunStatus

router = APIRouter(prefix="/projects/{project_id}", tags=["runs"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
LastEventId = Annotated[
    str | None,
    Header(alias="Last-Event-ID", description="Continue after this event id (reconnect)."),
]


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


SSE_RESPONSE = {
    200: {
        "description": SSE_DESCRIPTION,
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}


@router.post(
    "/agents/{agent_key}/runs",
    response_class=EventStreamResponse,
    responses=SSE_RESPONSE,
)
async def create_run(project_id: UUID, agent_key: AgentKey, body: RunCreate, actor: Reader):
    """Queue a run of the published version (or, with channel=test, a given version) and
    stream its events. The run id is the first event (`progress` with `run_id`)."""
    raise not_implemented()


@router.get("/runs", response_model=RunList)
async def list_runs(
    project_id: UUID,
    actor: Reader,
    agent_id: UUID | None = None,
    channel: Channel | None = None,
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Newest first."""
    raise not_implemented()


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(project_id: UUID, run_id: UUID, actor: Reader):
    raise not_implemented()


@router.get("/runs/{run_id}/events", response_model=RunEventList)
async def list_run_events(
    project_id: UUID, run_id: UUID, actor: Reader, after_seq: Annotated[int, Query(ge=0)] = 0
):
    """Every event of the run in order (from Postgres)."""
    raise not_implemented()


@router.get("/runs/{run_id}/stream", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def stream_run(
    project_id: UUID, run_id: UUID, actor: Reader, last_event_id: LastEventId = None
):
    """(Re)attach to a run's events: replay, then live until the run stops or waits."""
    raise not_implemented()


@router.post("/runs/{run_id}/resume", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def resume_run(project_id: UUID, run_id: UUID, body: ResumeRequest, actor: Reader):
    """Continue a waiting run from its checkpoint: a decision for waiting_approval (role
    `approval.assign_to` with edit access), an answer for waiting_user (the run's user). Any
    other state is 409 `run_not_waiting`."""
    raise not_implemented()


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(project_id: UUID, run_id: UUID, actor: Reader):
    """Stop a run at its next step boundary: the run's user or a project admin."""
    raise not_implemented()

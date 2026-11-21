"""The end user chat's read side (11, K-11-0002): the published agents a member may chat with,
the caller's own conversations and their messages, and soft delete.

Every member reads here, `user` and read-only access included: chatting is the read-only
exception (brief 03, brief 11), and deleting one's own conversation is own data. A conversation
belongs to the user it was started for (`conversations.user_id`); anyone else's is 404, its
existence is not shown. Writing a message is `POST .../agents/{key}/runs` (06a); the title comes
from the first message there, without a model call.

The routes carry the `runs` tag, so they are part of the 06a contract (`backend/openapi/06a.yaml`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from ffcore.api.agents_schemas import (
    ChatAgentList,
    ChatAgentOut,
    ChatMessageList,
    ChatMessageOut,
    ConversationList,
    ConversationOut,
)
from ffcore.api.common import ERROR_RESPONSES, SessionDep, invalid, not_found, path_resource
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.runs import Conversation, Message, Run
from ffcore.runtime.contracts import AgentKind, AgentStatus
from ffcore.runtime.definition import parse_definition

router = APIRouter(prefix="/projects/{project_id}", tags=["runs"], responses=ERROR_RESPONSES)

# Any project member (`user` included), read-only access included (module docstring).
Member = Annotated[Actor, Depends(require_role("user"))]
ConversationIdDep = Annotated[str, Depends(path_resource("conversation_id"))]
# Newest conversations first; the list is a sidebar, not an archive (no search in 11).
CONVERSATIONS_LIMIT_MAX = 200


def _user_id(actor: Actor) -> UUID:
    if actor.actor_type != "user":
        raise invalid("conversation_user_missing", "Conversations belong to a signed-in user.")
    return UUID(actor.actor_id)


async def _own_conversation(session, project_id: UUID, conversation_id: UUID, actor: Actor):
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.project_id == project_id,
            Conversation.user_id == _user_id(actor),
            Conversation.deleted_at.is_(None),
        )
    )
    if conversation is None:
        raise not_found("conversation")
    return conversation


@router.get("/chat/agents", response_model=ChatAgentList)
async def list_chat_agents(project_id: UUID, actor: Member, session: SessionDep):
    """The project's published agents, for the chat's agent picker. External agents are reached
    through the facade only (06b-2), so they are not listed."""
    rows = await session.scalars(
        select(Agent)
        .where(
            Agent.project_id == project_id,
            Agent.deleted_at.is_(None),
            Agent.status == AgentStatus.published,
            Agent.kind != AgentKind.external,
            Agent.current_version_id.is_not(None),
        )
        .order_by(Agent.name, Agent.key)
    )
    return ChatAgentList(
        items=[
            ChatAgentOut(
                id=a.id,
                key=a.key,
                name=a.name,
                description=a.description,
                portal_config=a.portal_config,
            )
            for a in rows.all()
        ]
    )


@router.get("/conversations", response_model=ConversationList)
async def list_conversations(
    project_id: UUID,
    actor: Member,
    session: SessionDep,
    agent_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=CONVERSATIONS_LIMIT_MAX)] = 50,
):
    """The caller's own conversations, newest message first."""
    last = (
        select(Message.conversation_id, func.max(Message.created_at).label("last_at"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    last_at = func.coalesce(last.c.last_at, Conversation.created_at)
    query = (
        select(Conversation, Agent.key, last_at)
        .join(Agent, Agent.id == Conversation.agent_id)
        .outerjoin(last, last.c.conversation_id == Conversation.id)
        .where(
            Conversation.project_id == project_id,
            Conversation.user_id == _user_id(actor),
            Conversation.deleted_at.is_(None),
        )
        .order_by(last_at.desc(), Conversation.id)
        .limit(limit)
    )
    if agent_id is not None:
        query = query.where(Conversation.agent_id == agent_id)
    rows = (await session.execute(query)).all()
    return ConversationList(
        items=[
            ConversationOut(
                id=c.id,
                agent_id=c.agent_id,
                agent_key=key,
                title=c.title,
                created_at=c.created_at,
                last_message_at=at,
            )
            for c, key, at in rows
        ]
    )


def _low_confidence(definition, confidence: float | None) -> bool | None:
    """Brief 11 (06, PayCore K3): only an agent with show_confidence and a calibrated threshold
    gets the badge; otherwise there is no flag at all (null), not 'false'."""
    if definition is None or not definition.answer_rules.show_confidence:
        return None
    threshold = definition.answer_rules.confidence_threshold
    if threshold is None or confidence is None:
        return None
    return confidence < threshold


@router.get("/conversations/{conversation_id}/messages", response_model=ChatMessageList)
async def list_messages(
    project_id: UUID, conversation_id: UUID, actor: Member, session: SessionDep
):
    """The conversation's messages in order, each with the state of its run (a waiting or failed
    run shows in the chat after a reload)."""
    await _own_conversation(session, project_id, conversation_id, actor)
    rows = (
        await session.execute(
            select(Message, Run)
            .outerjoin(Run, Run.id == Message.run_id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.role.desc())
        )
    ).all()
    version_ids = {run.agent_version_id for _, run in rows if run is not None}
    definitions = {}
    if version_ids:
        versions = await session.scalars(
            select(AgentVersion).where(AgentVersion.id.in_(version_ids))
        )
        definitions = {v.id: parse_definition(v.definition) for v in versions.all()}
    items = []
    for message, run in rows:
        definition = definitions.get(run.agent_version_id) if run is not None else None
        assistant = message.role == "assistant"
        items.append(
            ChatMessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                run_id=message.run_id,
                run_status=run.status if run is not None else None,
                outcome_label=run.outcome_label if run is not None else None,
                error_code=run.error_code if run is not None else None,
                sources=message.sources if assistant else None,
                feedback=message.feedback if assistant else None,
                user_feedback=message.user_feedback if assistant else None,
                low_confidence=(
                    _low_confidence(definition, run.confidence)
                    if assistant and run is not None
                    else None
                ),
                created_at=message.created_at,
            )
        )
    return ChatMessageList(items=items)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("delete_conversation", "conversation")
async def delete_conversation(
    project_id: UUID,
    conversation_id: UUID,
    request: Request,
    actor: Member,
    session: SessionDep,
    resource_id: ConversationIdDep,
) -> None:
    """Soft delete (retention `content` class removes the text later). The audit event keeps
    the id only: the title is the user's own words."""
    conversation = await _own_conversation(session, project_id, conversation_id, actor)
    conversation.deleted_at = func.now()

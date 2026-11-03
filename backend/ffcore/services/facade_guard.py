"""Guardrails on the facade's own paths (06b): the 08 engine called directly, as 06a's graph does
(B3: there is no hook inside LiteLLM). The direct model path and the external agent have no
graph, so their `input.pre`, `egress` and `output.pre` checks run here and their events go to
`guardrail_events` with source `api` (and the run id when there is a run)."""

import json
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.errors import ApiError
from ffcore.guardrails import engine
from ffcore.guardrails.masking import (
    RedisTokenStore,
    StreamDetokenizer,
    count_placeholders,
    log_skipped_policy,
    log_skipped_url,
    log_unresolved,
    reserve_carried,
    reveal_text,
)
from ffcore.guardrails.service import record_events, resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings

OUTPUT_STAGES = frozenset({"output.pre", "output.stream.delta"})
# The roles whose text comes from the client and is checked as input (S9: tool results too);
# every message, the assistant's included, leaves through `egress`.
INPUT_ROLES = frozenset({"system", "developer", "user", "tool"})
# The message fields the facade accepts (OpenAI's); every one that carries text is checked.
MESSAGE_FIELDS = frozenset({"role", "content", "name", "tool_calls", "tool_call_id"})
# Fields of an earlier answer that OpenAI SDKs send back with it (review r2 MINOR-A): accepted on
# assistant messages, never passed on, and reported (`dropped_fields`), not dropped silently.
ECHO_FIELDS = frozenset({"annotations", "refusal", "audio"})


class GuardrailBlocked(ApiError):
    def __init__(self, message: str | None, reference_id: str | None) -> None:
        text = message or "The request was blocked by a guardrail."
        if reference_id:
            text = f"{text} (reference {reference_id})"
        super().__init__(400, "invalid_request_error", "guardrail_blocked", text)
        self.reference_id = reference_id


def content_not_supported() -> ApiError:
    return ApiError(
        400,
        "invalid_request_error",
        "content_type_not_supported",
        "Only text content parts are accepted: guardrails cannot check other parts.",
    )


@dataclass
class FacadeGuard:
    session: AsyncSession
    redis: Any
    policy: Any
    project_id: str
    run_id: str | None = None
    # The token scope of `tokenize` (08: tokens are reversible within one scope). A run's scope is
    # its id; a direct call has no run, so one request is one scope. Pass the same scope to every
    # guard of one request (input, egress and output must share their tokens).
    scope: str = field(default_factory=lambda: f"facade-{uuid.uuid4().hex}")
    events: int = field(default=0)

    @classmethod
    async def load(
        cls, session, redis, project_id, *, policy_key="default", run_id=None, scope=None
    ):
        policy = await resolve_policy(session, project_id, policy_key)
        guard = cls(session, redis, policy, str(project_id), run_id)
        if scope is not None or run_id is not None:
            guard.scope = scope or str(run_id)
        return guard

    @property
    def egress_enabled(self) -> bool:
        return get_guardrail_settings().guardrail_egress_enabled

    @property
    def streams_live(self) -> bool:
        """06a V8: when an enforce rule checks output (its own mode or the policy's), nothing is
        shown before the check (review r1 MAJOR-2)."""
        return not engine.enforced_at(self.policy, OUTPUT_STAGES)

    async def text(self, stage: str, text: str) -> str:
        """The checked text (redacted, tokenized); a block raises GuardrailBlocked."""
        if not text:
            return text
        if stage == "egress" and not self.egress_enabled:
            # GUARDRAIL_EGRESS_ENABLED=false (airgap): the stage does not exist there (08 S3).
            return text
        guard = get_guardrail_settings()
        ctx = engine.EvalContext(
            # The engine's token scope is its run id (08 masking); see `scope` above.
            run_id=self.scope,
            project_id=self.project_id,
            source="api",
            token_store=RedisTokenStore(self.redis, guard.pii_token_ttl_s),
            egress_enabled=self.egress_enabled,
        )
        decision = await engine.evaluate(text, stage, self.policy, ctx=ctx)
        if decision.events:
            # Events name the real run (or none), never the request's token scope.
            events = [replace(e, run_id=self.run_id) for e in decision.events]
            record_events(self.session, self.project_id, events, decision.reference_id)
            await self.session.commit()
            self.events += len(decision.events)
        if decision.action == "block":
            raise GuardrailBlocked(decision.message, decision.reference_id)
        return decision.text_out

    @property
    def reveals(self) -> bool:
        """Placeholders go back to values unless an enforced `pii` rule checks the output (the
        policy hides personal data from answers; the placeholders stay, C17)."""
        return not engine.masks_pii_at(self.policy, OUTPUT_STAGES)

    def _token_store(self) -> RedisTokenStore:
        return RedisTokenStore(self.redis, get_guardrail_settings().pii_token_ttl_s)

    async def reserve_carried(self, data: Any) -> None:
        """Before the scope's first check: its counter passes every placeholder number the
        request carries in (r2 MAJOR-r2-2), so none of them becomes one of its values."""
        await reserve_carried(self._token_store(), self.scope, data)

    async def reveal(self, text: str, *, json_escape: bool = False) -> str:
        """C17: the request's placeholders back to their values, at the exit to the caller who
        made the request (S8). A placeholder the scope never issued stays as it is and is logged
        with its count (S9); one inside a URL stays and is logged (r1 MAJOR-3); nothing is
        invented. `json_escape` for tool call arguments, which are JSON text (r1 MINOR-3)."""
        if not text or "<<PII_" not in text:
            return text
        if not self.reveals:
            log_skipped_policy(self.scope, count_placeholders(text))
            return text
        out, unresolved, skipped = await reveal_text(
            text, store=self._token_store(), scope=self.scope, json_escape=json_escape
        )
        log_unresolved(self.scope, unresolved)
        log_skipped_url(self.scope, skipped)
        return out

    def stream_reveal(self, *, json_escape: bool = False) -> StreamDetokenizer:
        """The same for a live stream: a placeholder split over two chunks is held until whole;
        a URL that began in an earlier chunk is seen."""
        return StreamDetokenizer(self._token_store(), self.scope, json_escape=json_escape)

    async def json_text(self, stage: str, value: Any) -> Any:
        """A JSON value (tool definitions, tool call arguments) through a text stage; the result
        must still parse, otherwise the call is refused (a broken argument is never sent)."""
        raw = json.dumps(value, ensure_ascii=False)
        checked = await self.text(stage, raw)
        if checked == raw:
            return value
        try:
            return json.loads(checked)
        except ValueError:
            raise ApiError(
                400,
                "invalid_request_error",
                "guardrail_unparseable",
                "A guardrail changed structured content so that it no longer parses.",
            ) from None


def client_messages(body) -> tuple[list[dict], list[str]]:
    """(messages with OpenAI's known fields only, the echo fields left out as
    `messages[i].<field>`). What is passed on is what is checked (review r1 MAJOR-1); an echo
    field of an assistant message is left out and reported (r2 MINOR-A); any other field is
    refused."""
    out, dropped = [], []
    for i, message in enumerate(body.messages):
        given = message.model_dump(exclude_none=True)
        echoed = set(given) & ECHO_FIELDS if given["role"] == "assistant" else set()
        unknown = sorted(set(given) - MESSAGE_FIELDS - echoed)
        if unknown:
            raise ApiError(
                400,
                "invalid_request_error",
                "unsupported_field",
                f"Unsupported fields in messages[{i}]: {unknown}",
            )
        dropped += [f"messages[{i}].{name}" for name in sorted(echoed)]
        out.append({k: v for k, v in given.items() if k in MESSAGE_FIELDS})
    return out, dropped


def message_text(message: dict) -> str:
    """A message's text; list content is accepted only when every part is text."""
    content = message.get("content")
    if content is None or isinstance(content, str):
        return content or ""
    parts = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text":
            raise content_not_supported()
        parts.append(str(part.get("text") or ""))
    return "".join(parts)


async def guard_messages(guard: FacadeGuard, messages: list[dict]) -> list[dict]:
    """`input.pre` on the client's own text, then `egress` on every text field that leaves:
    content, `name`, `tool_call_id` and earlier tool calls (review r1 MAJOR-1)."""
    await guard.reserve_carried(messages)
    out = []
    for message in messages:
        message = dict(message)
        text = message_text(message)
        if message["role"] in INPUT_ROLES:
            text = await guard.text("input.pre", text)
        text = await guard.text("egress", text)
        if message.get("content") is not None:
            message["content"] = text
        for name in ("name", "tool_call_id"):
            if message.get(name):
                message[name] = await guard.text("egress", message[name])
        if message.get("tool_calls"):
            # An earlier assistant turn's calls go out again: egress, like any text.
            message["tool_calls"] = await guard.json_text("egress", message["tool_calls"])
        out.append(message)
    return out

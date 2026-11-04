"""Policy resolution and event persistence around the pure engine."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.errors import ApiError
from ffcore.guardrails.builtin import (
    BUILTIN_DEFAULT,
    BUILTIN_KEY,
    DEFAULT_PII,
    EGRESS_PII_KEY,
    builtin_egress_pii,
)
from ffcore.guardrails.engine import GuardrailEvent
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.guardrails.schemas import (
    GuardrailConfigError,
    PiiPolicySpec,
    PolicySpec,
    ResolvedPolicy,
)
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.models.guardrails import GuardrailEventRow, GuardrailPolicy, PiiPolicy


def config_error(exc: GuardrailConfigError) -> ApiError:
    return ApiError(422, "invalid_request_error", exc.code, exc.message)


def pii_spec(row: PiiPolicy) -> PiiPolicySpec:
    return PiiPolicySpec(
        engine=row.engine,
        default_action=row.default_action,
        languages=row.languages,
        min_confidence=row.min_confidence,
        context_boost=row.context_boost,
        categories=row.categories,
        custom_patterns=row.custom_patterns,
    )


def policy_spec(row: GuardrailPolicy) -> PolicySpec:
    return PolicySpec(
        rules=row.rules,
        mode=row.mode,
        short_circuit=row.short_circuit,
        on_error=row.on_error,
        block_message=row.block_message,
    )


async def stored_pii(session: AsyncSession, project_id, key: str) -> PiiPolicy | None:
    return await session.scalar(
        select(PiiPolicy).where(
            PiiPolicy.project_id == project_id, PiiPolicy.key == key, PiiPolicy.deleted_at.is_(None)
        )
    )


async def stored_policy(session: AsyncSession, project_id, key: str) -> GuardrailPolicy | None:
    return await session.scalar(
        select(GuardrailPolicy).where(
            GuardrailPolicy.project_id == project_id,
            GuardrailPolicy.key == key,
            GuardrailPolicy.deleted_at.is_(None),
        )
    )


async def available_pii_keys(session: AsyncSession, project_id) -> set[str]:
    rows = await session.scalars(
        select(PiiPolicy.key).where(
            PiiPolicy.project_id == project_id, PiiPolicy.deleted_at.is_(None)
        )
    )
    return {*rows, BUILTIN_KEY}


async def resolve_pii(session: AsyncSession, project_id, key: str) -> PiiPolicySpec | None:
    row = await stored_pii(session, project_id, key)
    if row is not None:
        return pii_spec(row)
    if key == BUILTIN_KEY:
        return DEFAULT_PII
    if key == EGRESS_PII_KEY:
        # 08 tam 1b: the built-in egress PII follows GUARDRAIL_EGRESS_NER (K-08T1B-0004 A).
        return builtin_egress_pii(get_guardrail_settings().guardrail_egress_ner)
    return None


async def resolve_policy(session: AsyncSession, project_id, key: str) -> ResolvedPolicy:
    """A stored policy by key; `default` falls back to the built-in one. Anything else is 404."""
    row = await stored_policy(session, project_id, key)
    if row is None:
        if key == BUILTIN_KEY:
            # K-08lite-0006 (A): the built-in chain's `pii_policy_key` means the same as in a stored
            # chain: the project's stored PII policy first, the built-in one otherwise.
            pii = {
                ref: await resolve_pii(session, project_id, ref)
                for ref in BUILTIN_DEFAULT.pii_policies
            }
            return ResolvedPolicy(
                key=BUILTIN_KEY, spec=BUILTIN_DEFAULT.spec, pii_policies=pii, builtin=True
            )
        raise ApiError(
            404, "not_found_error", "guardrail_policy_not_found", "Guardrail policy not found."
        )
    spec = policy_spec(row)
    pii = {}
    for rule in spec.rules:
        if rule.pii_policy_key and rule.pii_policy_key not in pii:
            resolved = await resolve_pii(session, project_id, rule.pii_policy_key)
            if resolved is None:
                # Deletion of a referenced PII policy is refused (409); this is a broken state.
                raise ApiError(
                    409,
                    "conflict_error",
                    "pii_policy_not_found",
                    f"PII policy '{rule.pii_policy_key}' referenced by the policy is missing.",
                )
            pii[rule.pii_policy_key] = resolved
    return ResolvedPolicy(key=row.key, spec=spec, pii_policies=pii, builtin=False)


def record_events(
    session: AsyncSession, project_id, events: list[GuardrailEvent], reference_id: str | None
) -> None:
    for event in events:
        session.add(
            GuardrailEventRow(
                id=uuid.uuid4(),
                project_id=project_id,
                run_id=uuid.UUID(event.run_id) if event.run_id else None,
                reference_id=reference_id,
                policy_key=event.policy_key,
                stage=event.stage,
                rule=event.rule,
                action_taken=event.action_taken,
                status=event.status,
                mode=event.mode,
                input_preview=event.input_preview,
                findings=event.findings,
                matches=event.matches,
                severity=event.severity,
                source=event.source,
                latency_ms=event.latency_ms,
                error=event.error,
            )
        )


@asynccontextmanager
async def redis_token_store() -> AsyncIterator[RedisTokenStore]:
    """The run-scoped tokenize mapping in the compose Redis (REDIS_URL), one client per call."""
    from redis.asyncio import Redis

    from ffcore.guardrails.settings import get_guardrail_settings

    settings = get_guardrail_settings()
    if settings.redis_url is None:
        raise RuntimeError("REDIS_URL is not set; tokenize needs Redis")
    client = Redis.from_url(settings.redis_url.get_secret_value())
    try:
        yield RedisTokenStore(client, settings.pii_token_ttl_s)
    finally:
        await client.aclose()

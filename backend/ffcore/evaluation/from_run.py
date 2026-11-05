"""An exam item from a run (09-2; plan/09 Akış 4, KARARLAR "09-2 plan kararları", "09-2 r1
kararları").

The run's question (and its variables) and the expected output the caller gives leave for the
suite's Langfuse dataset only after the agent version's guardrail policy at the `egress` stage,
in the API process, with one token store: a value the question and the expected answer share
gets the same placeholder (r1 MINOR-9). Identifiers are tokenized; with
GUARDRAIL_EGRESS_NER=false the regex categories only, so a person's name is stored in the
(in-house) Langfuse item as written: accepted, documented behaviour that the answer shows as
`masking: "regex"` (r1 live probe). A blocked text is refused (`run_input_blocked`), a NER
outage is `ner_unavailable`, a policy or NER configuration error and a text over the engine's
limit are coded errors (r1 MINOR-8; fail-loud). The masking runs whatever
GUARDRAIL_EGRESS_ENABLED says: the item is stored text, not a model call.
"""

import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.errors import ApiError
from ffcore.guardrails import engine
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers.ner import NerConfigError, local_ner
from ffcore.guardrails.schemas import GuardrailConfigError, ResolvedPolicy
from ffcore.guardrails.service import config_error, record_events, resolve_policy
from ffcore.models.agents import AgentVersion
from ffcore.runtime.definition import parse_definition

Masking = Literal["regex", "regex+ner"]


def item_id(suite_key: str, run_id) -> str:
    return f"{suite_key}-run-{run_id}"


def masking_of(policy: ResolvedPolicy) -> Masking:
    """`regex+ner` when a PII rule of the policy runs at egress with an `engine: ner` PII
    policy (person names are masked too), else `regex`."""
    for rule in policy.spec.rules:
        if rule.type != "pii" or "egress" not in rule.stages:
            continue
        pii = policy.pii_policies.get(rule.pii_policy_key or "")
        if pii is not None and pii.engine == "ner":
            return "regex+ner"
    return "regex"


def _engine_error(exc: Exception) -> ApiError:
    if isinstance(exc, NerConfigError):
        # As the API's own NER endpoint answers it: the service is not usable (503).
        return ApiError(503, "api_error", exc.code, exc.message)
    if isinstance(exc, GuardrailConfigError):
        return config_error(exc)
    return ApiError(422, "invalid_request_error", "text_too_long", str(exc))


async def masked_item(
    session: AsyncSession,
    project_id,
    version: AgentVersion,
    message: str,
    variables: dict,
    expected: dict[str, Any],
) -> tuple[dict, dict, Masking]:
    """(input, expected output, masking) as they may leave for Langfuse."""
    definition = parse_definition(version.definition)
    policy = await resolve_policy(session, project_id, definition.guardrail_policy_key)
    tokens = MemoryTokenStore()
    scope = str(uuid.uuid4())

    async def mask(text: str) -> str:
        ctx = engine.EvalContext(
            run_id=scope,
            project_id=str(project_id),
            token_store=tokens,
            egress_enabled=True,
            ner=local_ner(),
        )
        try:
            decision = await engine.evaluate(text, "egress", policy, ctx=ctx)
        except (GuardrailConfigError, engine.TextTooLong) as exc:
            raise _engine_error(exc) from None
        if decision.events:
            record_events(session, project_id, decision.events, decision.reference_id)
        if decision.action == "block":
            raise ApiError(
                422,
                "invalid_request_error",
                "run_input_blocked",
                "The run's question is blocked by the agent's egress policy; nothing was saved.",
            )
        return decision.text_out

    async def walk(value):
        if isinstance(value, str):
            return await mask(value)
        if isinstance(value, list):
            return [await walk(v) for v in value]
        return value  # numbers, booleans and null in sql_result carry no text

    masked_input = {
        "message": await mask(message),
        "variables": {k: await mask(str(v)) for k, v in (variables or {}).items()},
    }
    masked_expected = {k: await walk(v) for k, v in expected.items()}
    return masked_input, masked_expected, masking_of(policy)

"""An exam item from a run (09-2; plan/09 Akış 4, KARARLAR "09-2 plan kararları").

The run's question (and its variables) leave for the suite's Langfuse dataset only after the
agent version's guardrail policy at the `egress` stage, in the API process: identifiers are
tokenized (with GUARDRAIL_EGRESS_NER=false the regex categories only, 08 tam 1b), a blocked
text is refused (`run_input_blocked`), a NER outage is `ner_unavailable` (fail-loud). The
masking runs whatever GUARDRAIL_EGRESS_ENABLED says: the item is stored text, not a model call.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.errors import ApiError
from ffcore.guardrails import engine
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers.ner import local_ner
from ffcore.guardrails.service import record_events, resolve_policy
from ffcore.models.agents import AgentVersion
from ffcore.runtime.definition import parse_definition


def item_id(suite_key: str, run_id) -> str:
    return f"{suite_key}-run-{run_id}"


async def masked_input(
    session: AsyncSession, project_id, version: AgentVersion, message: str, variables: dict
) -> dict:
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
        decision = await engine.evaluate(text, "egress", policy, ctx=ctx)
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

    return {
        "message": await mask(message),
        "variables": {k: await mask(str(v)) for k, v in (variables or {}).items()},
    }

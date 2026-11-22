"""The one PII check every memory text passes before it is stored (brief 14 "Yazma" 3 and 6,
C19; K-14-0003): extraction candidates and "remember this" alike, in the API process (the NER
model lives there).

The policy is fixed in code (`memory`): one `pii` rule, action `block`, mode `enforce`. Its
categories are the project's own: the stored `default` PII policy (custom patterns included)
or the built-in identifiers, plus person names through NER (`builtin_egress_pii(True, ...)`,
08 tam 1b). A finding drops the text; the guardrail event is recorded (`guardrail_events`,
policy key `memory`, stage `input.pre`: the text is entering the platform's storage). A text
that carries an egress placeholder (`<<PII_n>>`) refers to tokenized personal data and is
refused the same way, without an engine call, and recorded as a `pii` block with the category
`egress_placeholder` (no value: the placeholder is all there is).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.guardrails import engine
from ffcore.guardrails.builtin import BUILTIN_KEY, builtin_egress_pii
from ffcore.guardrails.masking import PLACEHOLDER
from ffcore.guardrails.recognizers.ner import local_ner
from ffcore.guardrails.schemas import BlockMessage, PolicySpec, ResolvedPolicy, Rule
from ffcore.guardrails.service import pii_spec, record_events, stored_pii

POLICY_KEY = "memory"
STAGE = "input.pre"


@dataclass(frozen=True)
class PiiOutcome:
    blocked: bool
    reference_id: str | None = None
    # The categories found (codes only; never the value).
    categories: tuple[str, ...] = ()
    reason: str | None = None


def ner_client():
    """The API process's NER (LocalNer); a test replaces this function."""
    return local_ner()


async def memory_policy(session: AsyncSession, project_id) -> ResolvedPolicy:
    stored = await stored_pii(session, project_id, BUILTIN_KEY)
    pii = builtin_egress_pii(True, pii_spec(stored) if stored is not None else None)
    spec = PolicySpec(
        mode="enforce",
        short_circuit=True,
        on_error="block",
        block_message=BlockMessage(
            en="Personal data cannot be stored in memory.",
            tr="Kişisel veri hafızaya kaydedilemez.",
        ),
        rules=[Rule(type="pii", action="block", stages=[STAGE], pii_policy_key=POLICY_KEY)],
    )
    return ResolvedPolicy(key=POLICY_KEY, spec=spec, pii_policies={POLICY_KEY: pii})


async def check_memory_text(
    session: AsyncSession, project_id, text: str, *, run_id=None, source: str = "chat"
) -> PiiOutcome:
    if PLACEHOLDER.search(text):
        reference_id = uuid.uuid4().hex
        event = engine.GuardrailEvent(
            policy_key=POLICY_KEY,
            stage=STAGE,
            rule="pii#0",
            action_taken="block",
            status="failed",
            mode="enforce",
            input_preview="",
            findings=[
                {
                    "category": "egress_placeholder",
                    "evidence": "refers to tokenized personal data",
                    "action": "block",
                }
            ],
            severity="high",
            source=source,
            run_id=str(run_id) if run_id else None,
        )
        record_events(session, uuid.UUID(str(project_id)), [event], reference_id)
        return PiiOutcome(True, reference_id, ("egress_placeholder",), "placeholder")
    policy = await memory_policy(session, project_id)
    ctx = engine.EvalContext(
        run_id=str(run_id) if run_id else None,
        project_id=str(project_id),
        source=source,
        ner=ner_client(),
    )
    decision = await engine.evaluate(text, STAGE, policy, ctx=ctx)
    if decision.action != "block":
        return PiiOutcome(False)
    record_events(session, uuid.UUID(str(project_id)), decision.events, decision.reference_id)
    categories = sorted(
        {f["category"] for e in decision.events for f in e.findings if f.get("category")}
    )
    return PiiOutcome(True, decision.reference_id, tuple(categories), "pii")

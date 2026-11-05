"""An exam item from a run (09-2; plan/09 Akış 4, KARARLAR "09-2 plan kararları", "09-2 r1
kararları").

The run's question (and its variables) and the expected output the caller gives leave for the
suite's Langfuse dataset only after the agent version's guardrail policy at the `egress` stage,
in the API process, with one token store: a value the question and the expected answer share
gets the same placeholder (r1 MINOR-9). Identifiers are tokenized; with
GUARDRAIL_EGRESS_NER=false the regex categories only, so a person's name is stored in the
(in-house) Langfuse item as written: accepted, documented behaviour that the answer shows as
`masking: "regex"` (r1 live probe; r2 MINOR-2: the value is what the egress rule really
does, `none` when it masks nothing). An expectation compared with real rows, ids or text
(`sql_result`, `must_cite`, `regex`) that a mask would change is refused
(`expected_would_be_masked`, r2 MINOR-3): a placeholder there could never match. `answer` and
`must_contain` are saved masked and `masked_fields` names them. A blocked text is refused
(`run_input_blocked`), a NER
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

Masking = Literal["none", "regex", "regex+ner"]
# Compared with the agent's real output (rows, cited ids, a pattern): a mask breaks them.
EXACT_FIELDS = ("sql_result", "must_cite", "regex")
_MASKING_ACTIONS = ("redact", "mask", "tokenize")


def item_id(suite_key: str, run_id) -> str:
    return f"{suite_key}-run-{run_id}"


def masking_of(policy: ResolvedPolicy) -> Masking:
    """What the egress PII rules really mask (r2 MINOR-2), as the engine runs them: nothing
    when the policy is off or the rule does not enforce; per category the rule's action, else
    the category's, else the PII policy's default; `redact`, `mask` and `tokenize` change the
    text. `regex+ner` when such a rule masks person names with an `engine: ner` PII policy,
    `regex` when it masks something else, `none` when it masks nothing."""
    spec, found = policy.spec, "none"
    if spec.mode == "off":
        return found
    for rule in spec.rules:
        if rule.type != "pii" or "egress" not in rule.stages:
            continue
        if engine.rule_mode(spec, rule) != "enforce":
            continue
        pii = policy.pii_policies.get(rule.pii_policy_key or "")
        if pii is None:
            continue
        masked = {
            code
            for code, setting in engine._active(pii).items()
            if (rule.action or setting.action or pii.default_action) in _MASKING_ACTIONS
        }
        if pii.engine == "ner" and "PERSON" in masked:
            return "regex+ner"
        if masked:
            found = "regex"
    return found


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
) -> tuple[dict, dict, Masking, list[str]]:
    """(input, expected output, masking, masked fields) as they may leave for Langfuse."""
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

    plain_variables = {k: str(v) for k, v in (variables or {}).items()}
    masked_input = {
        "message": await mask(message),
        "variables": {k: await mask(v) for k, v in plain_variables.items()},
    }
    masked_expected = {k: await walk(v) for k, v in expected.items()}
    changed = [k for k in EXACT_FIELDS if k in expected and masked_expected[k] != expected[k]]
    if changed:
        raise ApiError(
            422,
            "invalid_request_error",
            "expected_would_be_masked",
            f"The expected {', '.join(changed)} would be masked; a placeholder there never "
            "matches the agent's real output. Give an expectation without personal data.",
        )
    shown = [k for k in ("answer", "must_contain") if k in expected]
    pairs = [
        ("message", message, masked_input["message"]),
        ("variables", plain_variables, masked_input["variables"]),
        *((k, expected[k], masked_expected[k]) for k in shown),
    ]
    fields = [name for name, before, after in pairs if before != after]
    return masked_input, masked_expected, masking_of(policy), fields

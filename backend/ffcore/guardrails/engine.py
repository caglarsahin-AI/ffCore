"""Guardrail engine: `evaluate(text, stage, policy, *, ctx) -> Decision` (CONTRACTS C4).

Rules bound to the stage run in order; each rule's `text_out` is the next rule's input. `block`
ends the chain (with `short_circuit=false` the remaining rules still run for a complete record,
the decision stays `block`). The strongest action wins. Monitor computes and records everything
and applies nothing. A rule that fails follows `on_error` (default `block`, fail-closed).

The engine stores nothing: the caller persists `Decision.events` (service.record_events).
"""

import re
import time
import uuid
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields

from ffcore.guardrails.categories import ACTION_RANK, STAGES
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import TokenStore, apply_findings, mask_value, redact_label
from ffcore.guardrails.recognizers import regex as regex_recognizers
from ffcore.guardrails.recognizers.regex import recognize, resolve_overlaps
from ffcore.guardrails.rules import find_secrets, find_tool_arg_violations
from ffcore.guardrails.schemas import GuardrailConfigError, PiiPolicySpec, ResolvedPolicy, Rule

__all__ = [
    "Decision",
    "EgressStageDisabled",
    "EvalContext",
    "GuardrailEvent",
    "TextTooLong",
    "dataclass_fields",
    "evaluate",
]

# The egress packet carries system prompt, history and RAG chunks; larger input is refused,
# never cut (ARCH-06).
MAX_TEXT_CHARS = 200_000
PREVIEW_CHARS = 60


class EgressStageDisabled(RuntimeError):
    """`egress` was evaluated while GUARDRAIL_EGRESS_ENABLED is false (airgap seed)."""


class TextTooLong(ValueError):
    pass


@dataclass(frozen=True)
class EvalContext:
    run_id: str | None = None
    project_id: str | None = None
    source: str = "api"
    locale: str = "en"
    # "<tool_key>.<action>" at tool.pre / tool.post.
    tool: str | None = None
    token_store: TokenStore | None = None
    # None: read GUARDRAIL_EGRESS_ENABLED from the environment.
    egress_enabled: bool | None = None


@dataclass
class GuardrailEvent:
    policy_key: str
    stage: str
    rule: str
    action_taken: str
    status: str
    mode: str
    input_preview: str
    findings: list[dict] = field(default_factory=list)
    matches: list[dict] = field(default_factory=list)
    severity: str | None = None
    latency_ms: float = 0.0
    error: str | None = None
    source: str = "api"
    run_id: str | None = None


@dataclass
class Decision:
    """C4. `action`: `allow` or an `action_taken` value. On `block`, `text_out` is empty and
    `message` (policy block_message in the caller's locale) goes to the user."""

    action: str
    text_out: str
    events: list[GuardrailEvent]
    message: str | None = None
    reference_id: str | None = None


_SEVERITY_RANK = {None: 0, "low": 1, "medium": 2, "high": 3}


def _egress_enabled(ctx: EvalContext) -> bool:
    if ctx.egress_enabled is not None:
        return ctx.egress_enabled
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


def _pii_findings(text: str, rule: Rule, pii: PiiPolicySpec) -> list[tuple[Finding, str, str]]:
    active = {
        code: setting
        for code, setting in pii.categories.items()
        if setting.enabled and (setting.lang is None or set(setting.lang) & set(pii.languages))
    }
    hits = list(recognize(text, active, context_boost=pii.context_boost))
    for pattern in pii.custom_patterns:
        if pattern.category not in active:
            continue
        for m in re.finditer(pattern.pattern, text):
            hits.append(
                Finding(
                    pattern.category,
                    m.start(),
                    m.end(),
                    pattern.score,
                    f"custom pattern '{pattern.name}'",
                    m.group(0),
                )
            )
    result = []
    for finding in resolve_overlaps(hits):
        if finding.score < pii.min_confidence:
            continue
        setting = active[finding.category]
        action = rule.action or setting.action or pii.default_action
        result.append((finding, action, setting.severity))
    return result


def _rule_findings(
    text: str, stage: str, rule: Rule, policy: ResolvedPolicy, ctx: EvalContext
) -> list[tuple[Finding, str, str]]:
    if rule.type == "pii":
        pii = policy.pii_policies.get(rule.pii_policy_key or "")
        if pii is None:
            raise GuardrailConfigError(
                "pii_policy_not_found", f"PII policy '{rule.pii_policy_key}' not found."
            )
        return _pii_findings(text, rule, pii)
    if rule.type == "secrets":
        return [(f, rule.action, "high") for f in find_secrets(text)]
    if rule.type == "tool_args":
        return [
            (f, rule.action, "high") for f in find_tool_arg_violations(text, rule.params, ctx.tool)
        ]
    raise GuardrailConfigError("rule_type_unsupported", f"Rule type '{rule.type}' is unsupported.")


def _preview(text: str, findings: list[Finding]) -> str:
    """First characters with every regex PII and this rule's findings redacted (never raw)."""
    hits = resolve_overlaps([*regex_recognizers.recognize(text), *findings])
    out, cursor = [], 0
    for f in hits:
        out.append(text[cursor : f.start])
        out.append(redact_label(f.category))
        cursor = f.end
    out.append(text[cursor:])
    return "".join(out)[:PREVIEW_CHARS]


def _strongest(actions) -> str:
    best = "allow"
    for action in actions:
        if ACTION_RANK[action] > ACTION_RANK[best]:
            best = action
    return best


async def evaluate(
    text: str, stage: str, policy: ResolvedPolicy, *, ctx: EvalContext | None = None
) -> Decision:
    ctx = ctx or EvalContext()
    if stage not in STAGES:
        raise GuardrailConfigError("stage_unknown", f"Unknown guardrail stage '{stage}'.")
    if len(text) > MAX_TEXT_CHARS:
        raise TextTooLong(f"text has {len(text)} characters; the limit is {MAX_TEXT_CHARS}")
    if stage == "egress" and not _egress_enabled(ctx):
        raise EgressStageDisabled("the egress stage is disabled (GUARDRAIL_EGRESS_ENABLED=false)")
    spec = policy.spec
    if spec.mode == "off":
        return Decision("allow", text, [])

    current, events, applied, blocked = text, [], [], False
    for index, rule in enumerate(spec.rules):
        if stage not in rule.stages:
            continue
        if blocked and spec.short_circuit:
            break
        started = time.perf_counter()
        event = GuardrailEvent(
            policy_key=policy.key,
            stage=stage,
            rule=f"{rule.type}#{index}",
            action_taken="log",
            status="passed",
            mode=spec.mode,
            input_preview="",
            source=ctx.source,
            run_id=ctx.run_id,
        )
        try:
            hits = _rule_findings(current, stage, rule, policy, ctx)
            action = _strongest(a for _, a, _ in hits)
            event.input_preview = _preview(current, [f for f, _, _ in hits])
            event.findings = [
                {
                    "category": f.category,
                    "score": round(f.score, 3),
                    "severity": s,
                    "evidence": f.evidence,
                    "action": a,
                }
                for f, a, s in hits
            ]
            event.matches = [
                {
                    "category": f.category,
                    "start": f.start,
                    "end": f.end,
                    "value": mask_value(f.category, f.value),
                }
                for f, _, _ in hits
            ]
            event.severity = max((s for _, _, s in hits), key=_SEVERITY_RANK.get, default=None)
            event.action_taken = "log" if action == "allow" else action
            if spec.mode == "enforce" and hits:
                if action == "block":
                    event.status, blocked = "failed", True
                else:
                    rewritten = await apply_findings(
                        current,
                        [(f, a) for f, a, _ in hits],
                        store=ctx.token_store,
                        scope=ctx.run_id,
                    )
                    if rewritten != current:
                        event.status = "redacted"
                    current = rewritten
                applied.append(action)
        except GuardrailConfigError:
            raise
        except Exception as exc:  # noqa: BLE001 - every rule failure follows on_error
            event.status = "failed"
            event.error = type(exc).__name__
            event.findings = [{"category": "rule_error", "evidence": type(exc).__name__}]
            event.action_taken = "block" if spec.on_error == "block" else "log"
            if spec.on_error == "block":
                blocked = True
                applied.append("block")
        event.latency_ms = round((time.perf_counter() - started) * 1000, 3)
        events.append(event)

    if spec.mode == "monitor":
        return Decision("allow", text, events)
    if blocked:
        message = getattr(spec.block_message, ctx.locale, None) or spec.block_message.en
        return Decision("block", "", events, message=message, reference_id=uuid.uuid4().hex)
    return Decision(_strongest(applied), current, events)

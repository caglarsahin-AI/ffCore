"""Guardrail engine: `evaluate(text, stage, policy, *, ctx) -> Decision` (CONTRACTS C4).

Rules bound to the stage run in order; each rule's `text_out` is the next rule's input. `block`
ends the chain (with `short_circuit=false` the remaining rules still run for a complete record,
the decision stays `block`). The strongest action wins. Monitor computes and records everything
and applies nothing. A rule that fails follows `on_error` (default `block`, fail-closed).

The engine stores nothing: the caller persists `Decision.events` (service.record_events).
"""

import asyncio
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


def rule_mode(spec, rule: Rule) -> str:
    """The mode a rule runs in: its own when it has one, else the policy's."""
    return rule.mode or spec.mode


def enforced_at(policy: ResolvedPolicy, stages) -> bool:
    """True when some rule on one of these stages can change or block the text: its mode is
    enforce and the policy is not off (an off policy runs nothing). A guard that streams decides
    with this whether text may be shown before the check (06a V8, review 06b r1 MAJOR-2)."""
    spec = policy.spec
    if spec.mode == "off":
        return False
    wanted = set(stages)
    return any(wanted & set(r.stages) and rule_mode(spec, r) == "enforce" for r in spec.rules)


def masks_pii_at(policy: ResolvedPolicy, stages) -> bool:
    """True when an enforced `pii` rule checks one of these stages. C17 (08-tam-1a): the exit
    then keeps the egress placeholders, because turning them back into values after
    `output.pre` would show what the policy hides from the output."""
    spec = policy.spec
    if spec.mode == "off":
        return False
    wanted = set(stages)
    return any(
        r.type == "pii" and wanted & set(r.stages) and rule_mode(spec, r) == "enforce"
        for r in spec.rules
    )


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


# The preview reads only the start of the text: PREVIEW_WINDOW characters are scanned and at most
# PREVIEW_WINDOW - PREVIEW_MARGIN are shown, so a value cut by the window edge is never emitted
# (review r2: bounded cost; nothing raw, nothing skipped in the findings themselves).
PREVIEW_WINDOW = 4096
PREVIEW_MARGIN = 256


def _preview(text: str, own: list[Finding], values: dict[str, str]) -> str:
    """First characters with every regex PII, every secret, this rule's findings and every value
    any rule of the chain found redacted. Monitor, warn and log leave the text as it was, so a
    rule's input can hold what another rule finds (before or after it): the preview never does
    (review r1). Cost is bounded by the window and the number of distinct values (review r2)."""
    window = text[:PREVIEW_WINDOW]
    limit = len(text) if len(text) <= PREVIEW_WINDOW else PREVIEW_WINDOW - PREVIEW_MARGIN
    spans = [
        (f.start, f.end, f.category)
        for f in (*regex_recognizers.recognize(window), *find_secrets(window))
    ]
    spans.extend((f.start, f.end, f.category) for f in own if f.start < limit)
    for value, category in values.items():
        # Look slightly past the window so a value straddling its edge is still found.
        haystack = text[: PREVIEW_WINDOW + len(value)]
        start = haystack.find(value)
        while start != -1 and start < limit:
            spans.append((start, start + len(value), category))
            start = haystack.find(value, start + 1)
    # Union of overlapping spans (sorted, one pass): an overlap is widened, never shown.
    merged: list[list] = []
    for start, end, category in sorted(spans):
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end, category])
    out: list[str] = []
    size, cursor = 0, 0
    for start, end, category in merged:
        if start >= limit or size >= PREVIEW_CHARS:
            break
        out.append(text[cursor:start])
        out.append(redact_label(category))
        size += start - cursor + len(out[-1])
        cursor = max(cursor, end)
    if size < PREVIEW_CHARS and cursor < limit:
        out.append(text[cursor:limit])
    return "".join(out)[:PREVIEW_CHARS]


def _previews(pending: list[tuple["GuardrailEvent", str, list[Finding]]], seen: dict) -> list:
    timings = []
    for event, rule_input, own in pending:
        started = time.perf_counter()
        event.input_preview = _preview(rule_input, own, seen)
        timings.append((event, (time.perf_counter() - started) * 1000))
    return timings


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
    # Previews are built after the chain: every value any rule found is redacted in every
    # event, whatever the mode and the rule order (review r1).
    seen: dict[str, str] = {}  # distinct values found by the chain -> category
    pending: list[tuple[GuardrailEvent, str, list[Finding]]] = []
    for index, rule in enumerate(spec.rules):
        if stage not in rule.stages:
            continue
        if blocked and spec.short_circuit:
            break
        started = time.perf_counter()
        mode = rule_mode(spec, rule)  # a rule may carry its own mode (built-in egress PII)
        event = GuardrailEvent(
            policy_key=policy.key,
            stage=stage,
            rule=f"{rule.type}#{index}",
            action_taken="log",
            status="passed",
            mode=mode,
            input_preview="",
            source=ctx.source,
            run_id=ctx.run_id,
        )
        try:
            # CPU-bound scanning runs off the event loop (00i pattern).
            hits = await asyncio.to_thread(_rule_findings, current, stage, rule, policy, ctx)
            action = _strongest(a for _, a, _ in hits)
            pending.append((event, current, [f for f, _, _ in hits]))
            for f, _, _ in hits:
                if f.value:
                    seen.setdefault(f.value, f.category)
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
                    "masked_value": mask_value(f.category, f.value),
                }
                for f, _, _ in hits
            ]
            event.severity = max((s for _, _, s in hits), key=_SEVERITY_RANK.get, default=None)
            event.action_taken = "log" if action == "allow" else action
            if mode == "enforce" and hits:
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
            pending.append((event, current, []))
            event.error = type(exc).__name__
            event.findings = [{"category": "rule_error", "evidence": type(exc).__name__}]
            event.action_taken = "block" if spec.on_error == "block" else "log"
            if spec.on_error == "block" and mode == "enforce":  # monitor only records
                blocked = True
                applied.append("block")
        event.latency_ms = round((time.perf_counter() - started) * 1000, 3)
        events.append(event)

    for event, preview_ms in await asyncio.to_thread(_previews, pending, seen):
        event.latency_ms = round(event.latency_ms + preview_ms, 3)

    # Only enforce-mode rules change the text or block; a monitor rule only records.
    if blocked:
        message = getattr(spec.block_message, ctx.locale, None) or spec.block_message.en
        return Decision("block", "", events, message=message, reference_id=uuid.uuid4().hex)
    return Decision(_strongest(applied), current, events)

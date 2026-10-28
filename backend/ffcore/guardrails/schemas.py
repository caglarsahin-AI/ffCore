"""Policy shapes (stored as JSON in guardrail_policies / pii_policies) and their validation.

Pydantic checks types; `validate_policy` / `validate_pii_policy` check meaning and raise
GuardrailConfigError with a stable code (rule_type_unsupported, category_unsupported, ...),
so nothing that looks enabled is silently ignored (ARCH-13, fail-loud).
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ffcore.guardrails.categories import (
    ACTIONS,
    CATEGORIES,
    LANGUAGES,
    MODES,
    ON_ERROR,
    SEVERITIES,
    STAGES,
)

Action = Literal[ACTIONS]
Stage = Literal[STAGES]
MAX_PATTERN_CHARS = 200
SUPPORTED_RULE_TYPES = ("pii", "secrets", "tool_args")
# Brief 08 rule types that arrive with 08 full (or later); refused until then.
LATER_RULE_TYPES = ("injection", "topic", "output_format", "banned_words")
# Streaming needs the sliding buffer (C17, 08 full); a rule there would see partial chunks.
UNSUPPORTED_STAGES = ("output.stream.delta",)


class GuardrailConfigError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PiiCategorySetting(_Spec):
    enabled: bool = True
    severity: Literal[SEVERITIES] = "medium"
    # None: the PII policy's default_action (or the guardrail rule's action, which wins).
    action: Action | None = None
    # None: active for every language of the policy.
    lang: list[Literal[LANGUAGES]] | None = None


class CustomPattern(_Spec):
    name: str = Field(min_length=1, max_length=64)
    category: str
    pattern: str = Field(min_length=1, max_length=MAX_PATTERN_CHARS)
    score: float = Field(default=0.8, ge=0, le=1)


class PiiPolicySpec(_Spec):
    engine: Literal["regex", "ner"] = "regex"
    default_action: Action = "redact"
    languages: list[Literal[LANGUAGES]] = Field(default_factory=lambda: list(LANGUAGES))
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    context_boost: bool = True
    categories: dict[str, PiiCategorySetting] = Field(default_factory=dict)
    custom_patterns: list[CustomPattern] = Field(default_factory=list)


class Rule(_Spec):
    type: str
    # One action per rule (brief); for `pii` it may be omitted: per-category actions then apply.
    action: Action | None = None
    stages: list[Stage] = Field(min_length=1)
    params: dict = Field(default_factory=dict)
    pii_policy_key: str | None = None


class ToolArgsParams(_Spec):
    # Tool names as "<tool_key>.<action>"; "*" matches every tool, shell-style wildcards allowed.
    tools: list[str] = Field(min_length=1)
    patterns: list[str] = Field(min_length=1)
    # Only these argument values are searched; None searches the whole argument text.
    args: list[str] | None = None


class BlockMessage(_Spec):
    en: str = Field(default="This request was blocked by a guardrail policy.", min_length=1)
    tr: str | None = None


class PolicySpec(_Spec):
    rules: list[Rule] = Field(default_factory=list)
    mode: Literal[MODES] = "monitor"  # a new policy starts in monitor (brief 08)
    short_circuit: bool = True
    on_error: Literal[ON_ERROR] = "block"  # fail-closed
    block_message: BlockMessage = Field(default_factory=BlockMessage)


@dataclass(frozen=True)
class ResolvedPolicy:
    """What the engine runs: a guardrail policy with the PII policies its rules reference."""

    key: str
    spec: PolicySpec
    pii_policies: dict[str, PiiPolicySpec] = field(default_factory=dict)
    builtin: bool = False


def _compile(pattern: str, where: str) -> re.Pattern:
    if len(pattern) > MAX_PATTERN_CHARS:
        raise GuardrailConfigError("pattern_invalid", f"{where}: pattern is too long.")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise GuardrailConfigError("pattern_invalid", f"{where}: {exc.msg}.") from None


def validate_policy(spec: PolicySpec, pii_policy_keys) -> None:
    keys = set(pii_policy_keys)
    for i, rule in enumerate(spec.rules):
        where = f"rules[{i}]"
        if rule.type not in SUPPORTED_RULE_TYPES:
            later = (
                " It arrives with the full guardrail package."
                if rule.type in LATER_RULE_TYPES
                else ""
            )
            raise GuardrailConfigError(
                "rule_type_unsupported",
                f"{where}: rule type '{rule.type}' is not supported.{later}",
            )
        if bad := [s for s in rule.stages if s in UNSUPPORTED_STAGES]:
            raise GuardrailConfigError(
                "rule_stage_unsupported", f"{where}: stage {bad[0]} needs the streaming buffer."
            )
        if rule.type != "pii" and rule.action is None:
            raise GuardrailConfigError("rule_action_required", f"{where}: action is required.")
        if rule.type == "pii":
            if rule.pii_policy_key is None or rule.pii_policy_key not in keys:
                raise GuardrailConfigError(
                    "pii_policy_not_found",
                    f"{where}: PII policy '{rule.pii_policy_key}' not found.",
                )
            if rule.params:
                raise GuardrailConfigError("rule_params_invalid", f"{where}: pii takes no params.")
        elif rule.pii_policy_key is not None:
            raise GuardrailConfigError(
                "rule_params_invalid", f"{where}: pii_policy_key only applies to pii rules."
            )
        if rule.type == "secrets" and rule.params:
            raise GuardrailConfigError("rule_params_invalid", f"{where}: secrets takes no params.")
        if rule.type == "tool_args":
            # Offsets point into argument values, not the JSON text: no rewriting actions.
            if rule.action not in ("block", "warn", "log"):
                raise GuardrailConfigError(
                    "rule_action_invalid", f"{where}: tool_args allows block, warn or log."
                )
            if set(rule.stages) != {"tool.pre"}:
                raise GuardrailConfigError(
                    "rule_stage_invalid", f"{where}: tool_args runs only at tool.pre."
                )
            try:
                params = ToolArgsParams.model_validate(rule.params)
            except ValueError:
                raise GuardrailConfigError(
                    "rule_params_invalid", f"{where}: tool_args needs tools and patterns."
                ) from None
            for j, pattern in enumerate(params.patterns):
                _compile(pattern, f"{where}.params.patterns[{j}]")


def validate_pii_policy(spec: PiiPolicySpec) -> None:
    if spec.engine != "regex":
        raise GuardrailConfigError(
            "engine_unsupported", "The ner engine arrives with the full guardrail package."
        )
    for code in list(spec.categories) + [p.category for p in spec.custom_patterns]:
        if code not in CATEGORIES:
            raise GuardrailConfigError("category_unknown", f"Unknown PII category '{code}'.")
    custom = set()
    for i, pattern in enumerate(spec.custom_patterns):
        _compile(pattern.pattern, f"custom_patterns[{i}]")
        custom.add(pattern.category)
    for code, setting in spec.categories.items():
        if setting.enabled and not CATEGORIES[code].regex and code not in custom:
            raise GuardrailConfigError(
                "category_unsupported",
                f"Category '{code}' has no recognizer in this release; add a custom pattern "
                "or keep it disabled.",
            )

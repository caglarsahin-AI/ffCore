"""The built-in `default` policy (S5): used when a project has no stored policy with that key.

Visible in the API (`builtin: true`, `builtin_version`), in monitor mode: it blocks and redacts
nothing until an administrator stores an enforce policy. One rule is enforced regardless: PII
at egress leaves tokenized (version 2, K-SEN-0029 A; plan/18 F4 found raw identifiers reaching
the provider under version 1). A stored policy with key `default` replaces it.

Version 3 (08 tam 1b, K-08T1B-0004 A): the egress rule reads its own PII policy,
`default-egress`: with GUARDRAIL_EGRESS_NER=true the regex identifiers plus person names
(`engine: ner`), with false the same regex identifiers as before. The text stages keep
`default` (regex) and never call NER. A stored PII policy with either key replaces the built-in.
"""

from ffcore.guardrails.categories import CATEGORIES, STAGES
from ffcore.guardrails.schemas import PiiPolicySpec, PolicySpec, ResolvedPolicy, Rule

BUILTIN_KEY = "default"
BUILTIN_VERSION = 3
EGRESS_PII_KEY = "default-egress"

# Text stages except egress (tokenized instead) and the stream (needs the C17 buffer, 08 full).
_TEXT_STAGES = [s for s in STAGES if s not in ("egress", "output.stream.delta")]

DEFAULT_PII = PiiPolicySpec(
    engine="regex",
    default_action="redact",
    categories={
        code: {"enabled": True, "severity": "high" if code == "TR_NATIONAL_ID" else "medium"}
        for code, category in CATEGORIES.items()
        if category.default_on and category.regex
    },
)

# GUARDRAIL_EGRESS_NER=true: what leaves for the provider has person names tokenized too.
DEFAULT_EGRESS_PII_NER = PiiPolicySpec(
    engine="ner",
    default_action="tokenize",
    categories={
        **DEFAULT_PII.model_dump()["categories"],
        "PERSON": {"enabled": True, "severity": "high"},
    },
)


def builtin_egress_pii(egress_ner: bool) -> PiiPolicySpec:
    return DEFAULT_EGRESS_PII_NER if egress_ner else DEFAULT_PII


DEFAULT_SPEC = PolicySpec(
    mode="monitor",
    short_circuit=True,
    on_error="block",
    rules=[
        Rule(type="secrets", action="block", stages=[*_TEXT_STAGES, "egress"]),
        Rule(type="pii", action="redact", stages=_TEXT_STAGES, pii_policy_key=BUILTIN_KEY),
        # llmaas egress (brief R7.4): identifiers leave as placeholders and come back on output.
        # Enforced even though the policy is monitor: a project that sets no policy must not
        # send raw identifiers to an external provider (K-SEN-0029 A, plan/18 F4).
        Rule(
            type="pii",
            action="tokenize",
            stages=["egress"],
            pii_policy_key=EGRESS_PII_KEY,
            mode="enforce",
        ),
    ],
)


def builtin_default(egress_ner: bool) -> ResolvedPolicy:
    return ResolvedPolicy(
        key=BUILTIN_KEY,
        spec=DEFAULT_SPEC,
        pii_policies={BUILTIN_KEY: DEFAULT_PII, EGRESS_PII_KEY: builtin_egress_pii(egress_ner)},
        builtin=True,
    )


# Regex-only egress (GUARDRAIL_EGRESS_NER=false); resolve_policy builds the live one.
BUILTIN_DEFAULT = builtin_default(False)

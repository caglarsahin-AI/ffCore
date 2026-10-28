"""The built-in `default` policy (S5): used when a project has no stored policy with that key.

Visible in the API (`builtin: true`, `builtin_version`), starts in monitor mode, so merging 08
blocks no traffic until an administrator switches a stored policy to enforce. A stored policy
with key `default` replaces it.
"""

from ffcore.guardrails.categories import CATEGORIES, STAGES
from ffcore.guardrails.schemas import PiiPolicySpec, PolicySpec, ResolvedPolicy, Rule

BUILTIN_KEY = "default"
BUILTIN_VERSION = 1

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

DEFAULT_SPEC = PolicySpec(
    mode="monitor",
    short_circuit=True,
    on_error="block",
    rules=[
        Rule(type="secrets", action="block", stages=[*_TEXT_STAGES, "egress"]),
        Rule(type="pii", action="redact", stages=_TEXT_STAGES, pii_policy_key=BUILTIN_KEY),
        # llmaas egress (brief R7.4): identifiers leave as placeholders and come back on output.
        Rule(type="pii", action="tokenize", stages=["egress"], pii_policy_key=BUILTIN_KEY),
    ],
)

BUILTIN_DEFAULT = ResolvedPolicy(
    key=BUILTIN_KEY, spec=DEFAULT_SPEC, pii_policies={BUILTIN_KEY: DEFAULT_PII}, builtin=True
)

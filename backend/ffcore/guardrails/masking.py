"""Masking modes (brief 08): redact `[CODE]`, mask (last characters visible), tokenize
`<<PII_n>>` with the mapping in Redis for the run (`PII_TOKEN_TTL_S`), reversed on the way out.

Streaming reversal across SSE chunks (C17) is 08 full; `detokenize` works on whole texts.
"""

import re
from collections.abc import Sequence
from typing import Protocol

from ffcore.guardrails.findings import Finding

KEEP_VISIBLE = 4
PLACEHOLDER = re.compile(r"<<PII_\d+>>")


class TokenScopeMissing(ValueError):
    """tokenize needs a scope (the run id); without one the mapping could not be reversed."""


class TokenStore(Protocol):
    async def token_for(self, scope: str, key: str, value: str) -> str: ...

    async def lookup(self, scope: str, token: str) -> str | None: ...


def _identity(category: str, value: str) -> str:
    # Exactly the same value gets the same placeholder. No normalisation: "a.b@x" and "ab@x" are
    # different addresses (review r1); a reformatted number gets a new placeholder, never a
    # wrong one.
    return category + ":" + value


class MemoryTokenStore:
    """In-process store for unit tests and the dry-run test panel."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict[str, str]] = {}

    async def token_for(self, scope: str, key: str, value: str) -> str:
        mapping = self._scopes.setdefault(scope, {})
        if "k:" + key not in mapping:
            token = f"<<PII_{sum(1 for k in mapping if k.startswith('k:')) + 1}>>"
            mapping["k:" + key] = token
            mapping["t:" + token] = value
        return mapping["k:" + key]

    async def lookup(self, scope: str, token: str) -> str | None:
        return self._scopes.get(scope, {}).get("t:" + token)


# Get-or-create in one Redis call: Lua runs atomically, so no caller ever sees the forward entry
# (`k:`) without the reverse one (`t:`) (review r1).
_TOKEN_FOR = """
local token = redis.call('HGET', KEYS[1], 'k:' .. ARGV[1])
if not token then
  token = '<<PII_' .. redis.call('HINCRBY', KEYS[1], 'n', 1) .. '>>'
  redis.call('HSET', KEYS[1], 'k:' .. ARGV[1], token, 't:' .. token, ARGV[2])
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
return token
"""


class RedisTokenStore:
    """One hash per scope: `k:<identity>` → token, `t:<token>` → value, `n` → counter.

    The TTL is renewed on every write so the mapping lives as long as the run uses it.
    """

    def __init__(self, redis, ttl_s: int, prefix: str = "ffcore:pii:") -> None:
        self._redis = redis
        self._ttl = ttl_s
        self._prefix = prefix

    async def token_for(self, scope: str, key: str, value: str) -> str:
        token = await self._redis.eval(_TOKEN_FOR, 1, self._prefix + scope, key, value, self._ttl)
        return token.decode() if isinstance(token, bytes) else token

    async def lookup(self, scope: str, token: str) -> str | None:
        value = await self._redis.hget(self._prefix + scope, "t:" + token)
        return value.decode() if isinstance(value, bytes) else value


def redact_label(category: str) -> str:
    return f"[{category}]"


def mask_value(category: str, value: str) -> str:
    """A masked value never equals the raw one (review r1): at most the last four characters,
    and never more than half of them, stay visible; a one-letter e-mail local part becomes "*"."""
    if category == "EMAIL_ADDRESS" and "@" in value:
        local, _, domain = value.partition("@")
        head = local[:1] if len(local) > 1 else ""
        return head + "*" * (len(local) - len(head)) + "@" + domain
    alnum = sum(1 for c in value if c.isalnum())
    visible = min(KEEP_VISIBLE, alnum // 2)
    hide, out = alnum - visible, []
    for char in value:
        if char.isalnum() and hide > 0:
            out.append("*")
            hide -= 1
        else:
            out.append(char)
    masked = "".join(out)
    if masked == value:
        # Nothing alphanumeric to hide ("...", "--"): mask every character instead.
        masked = "*" * len(value)
    return masked


async def apply_action(
    text: str,
    findings: Sequence[Finding],
    action: str,
    *,
    store: TokenStore | None = None,
    scope: str | None = None,
) -> str:
    """Rewrite `text` for a transforming action; other actions return it unchanged."""
    return await apply_findings(text, [(f, action) for f in findings], store=store, scope=scope)


async def apply_findings(
    text: str,
    actions: Sequence[tuple[Finding, str]],
    *,
    store: TokenStore | None = None,
    scope: str | None = None,
) -> str:
    """Rewrite each finding with its own action (a PII policy may mix redact, mask, tokenize).

    Findings must not overlap (recognizers resolve overlaps). Non-transforming actions keep text.
    """
    ordered = sorted(
        ((f, a) for f, a in actions if a in ("redact", "mask", "tokenize")),
        key=lambda x: x[0].start,
    )
    if any(a == "tokenize" for _, a in ordered) and (store is None or not scope):
        raise TokenScopeMissing("tokenize needs a token store and a scope (run id)")
    out, cursor = [], 0
    for finding, action in ordered:
        if action == "redact":
            replacement = redact_label(finding.category)
        elif action == "mask":
            replacement = mask_value(finding.category, finding.value)
        else:
            key = _identity(finding.category, finding.value)
            replacement = await store.token_for(scope, key, finding.value)
        out.append(text[cursor : finding.start])
        out.append(replacement)
        cursor = finding.end
    out.append(text[cursor:])
    return "".join(out)


async def detokenize(text: str, *, store: TokenStore, scope: str) -> tuple[str, list[str]]:
    """Put the original values back. Placeholders the run never issued stay as they are and are
    returned in `unresolved` (a model can invent one); nothing is guessed."""
    unresolved: list[str] = []
    out, cursor = [], 0
    for match in PLACEHOLDER.finditer(text):
        value = await store.lookup(scope, match.group(0))
        out.append(text[cursor : match.start()])
        if value is None:
            unresolved.append(match.group(0))
            out.append(match.group(0))
        else:
            out.append(value)
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out), unresolved

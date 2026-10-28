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
    # The same person/number gets the same placeholder however it was spaced or cased.
    return category + ":" + re.sub(r"[\s.-]", "", value).casefold()


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


class RedisTokenStore:
    """One hash per scope: `k:<identity>` → token, `t:<token>` → value, `n` → counter.

    The TTL is renewed on every write so the mapping lives as long as the run uses it.
    """

    def __init__(self, redis, ttl_s: int, prefix: str = "ffcore:pii:") -> None:
        self._redis = redis
        self._ttl = ttl_s
        self._prefix = prefix

    async def token_for(self, scope: str, key: str, value: str) -> str:
        name = self._prefix + scope
        existing = await self._redis.hget(name, "k:" + key)
        if existing is not None:
            await self._redis.expire(name, self._ttl)
            return existing.decode() if isinstance(existing, bytes) else existing
        token = f"<<PII_{await self._redis.hincrby(name, 'n', 1)}>>"
        if not await self._redis.hsetnx(name, "k:" + key, token):
            # Another call of the same run won the race; use its token.
            token = await self._redis.hget(name, "k:" + key)
            token = token.decode() if isinstance(token, bytes) else token
        else:
            await self._redis.hset(name, "t:" + token, value)
        await self._redis.expire(name, self._ttl)
        return token

    async def lookup(self, scope: str, token: str) -> str | None:
        value = await self._redis.hget(self._prefix + scope, "t:" + token)
        return value.decode() if isinstance(value, bytes) else value


def redact_label(category: str) -> str:
    return f"[{category}]"


def mask_value(category: str, value: str) -> str:
    if category == "EMAIL_ADDRESS" and "@" in value:
        local, _, domain = value.partition("@")
        return local[:1] + "*" * (len(local) - 1) + "@" + domain
    alnum = sum(1 for c in value if c.isalnum())
    hide, out = alnum - KEEP_VISIBLE, []
    for char in value:
        if char.isalnum() and hide > 0:
            out.append("*")
            hide -= 1
        else:
            out.append(char)
    return "".join(out)


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

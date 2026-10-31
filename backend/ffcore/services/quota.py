"""Quota engine (03c, R2.1, R2.3, C20): the one place that says whether a model call may run.

Every active quota that applies to the caller is checked: the project's (a ceiling for every
key and user under it), the API key's and the user's. A rule with `action=block` refuses with
`quota_exceeded`; a `warn` rule only reports (the call goes on; 03c-2 turns it into an alert).

Counters live in Redis (C20): request windows count calls as they start (atomic Lua: no window
is incremented unless every blocking window has room); token windows and USD budgets grow as
calls finish (`commit`), so a budget is crossed by at most the call that crossed it. `concurrent`
is a lease set per rule, like LLM_SLOTS (06a scheduler). Windows are UTC minute/hour/day/month.

Cost is `models.pricing` x tokens, the formula LiteLLM applies (U2: the stream response has no
cost header; state/evidence/03c-u1-u2-probe-20261031.md). A budget over a model without a price
fails loud (`pricing_missing`, FOLLOWUP-69): it would otherwise count 0 and never stop.
Without Redis the engine refuses (`quota_unavailable`): no quota is never "no limit".
"""

import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.models.quota import Quota

log = logging.getLogger("ffcore.quota")

PREFIX = "ffcore:quota"
MICRO = Decimal(1_000_000)
# window -> (seconds of one bucket, Redis key time format); months use the calendar month.
_SPANS = {"minute": 60, "hour": 3600, "day": 86400, "month": 32 * 86400}
REQUEST_WINDOWS = {"rpm": "minute", "rph": "hour", "rpd": "day", "rpm_month": "month"}
TOKEN_WINDOWS = {"tpm": "minute", "tpd": "day", "tpm_month": "month"}
BUDGET_WINDOWS = {"daily_usd": "day", "monthly_usd": "month"}

# Check every blocking window first, then count in all of them (or in none).
_COUNT_REQUEST = """
local n = tonumber(ARGV[1])
for i = 1, n do
  local cur = tonumber(redis.call('GET', KEYS[i]) or '0')
  if tonumber(ARGV[1 + n + n + i]) == 1 and cur + 1 > tonumber(ARGV[1 + n + i]) then
    return i
  end
end
for i = 1, n do
  redis.call('INCR', KEYS[i])
  redis.call('EXPIRE', KEYS[i], tonumber(ARGV[1 + i]))
end
return 0
"""

# Concurrent leases: drop expired members, refuse when a blocking rule is full, else add.
_LEASE = """
local now = tonumber(ARGV[1])
local member = ARGV[2]
local ttl = tonumber(ARGV[3])
local n = #KEYS
for i = 1, n do
  redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now)
  local limit = tonumber(ARGV[3 + i])
  local blocking = tonumber(ARGV[3 + n + i])
  if blocking == 1 and redis.call('ZCARD', KEYS[i]) >= limit then
    return i
  end
end
for i = 1, n do
  redis.call('ZADD', KEYS[i], now + ttl, member)
  redis.call('EXPIRE', KEYS[i], ttl + 60)
end
return 0
"""


@dataclass(frozen=True)
class Subject:
    """Who a call counts against. `api_key_id` only when the caller is a key (06b facade)."""

    project_id: str
    user_id: str | None = None
    api_key_id: str | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    scope_type: str
    scope_id: str
    label: str
    windows: dict
    tokens: dict
    budget: dict
    blocking: bool

    @classmethod
    def of(cls, row: Quota) -> "Rule":
        return cls(
            id=str(row.id),
            scope_type=row.scope_type,
            scope_id=str(row.scope_id),
            label=row.label,
            windows=dict(row.windows or {}),
            tokens=dict(row.tokens or {}),
            budget=dict(row.budget or {}),
            blocking=row.action == "block",
        )


@dataclass(frozen=True)
class Violation:
    quota_id: str
    scope_type: str
    window: str
    limit: Any
    used: Any
    blocking: bool


@dataclass(frozen=True)
class Decision:
    action: str  # allow | warn | block
    code: str | None = None  # quota_exceeded | pricing_missing
    violation: Violation | None = None
    warnings: tuple[Violation, ...] = ()
    # The output cap the call must respect (max_output, max_total - input); None: no cap.
    max_output_tokens: int | None = None

    @property
    def blocked(self) -> bool:
        return self.action == "block"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal | None = field(default=None)


class QuotaUnavailable(ApiError):
    def __init__(self) -> None:
        super().__init__(503, "api_error", "quota_unavailable", "Quota checks need Redis.")


def price(pricing: dict | None, input_tokens: int, output_tokens: int) -> Decimal | None:
    """USD for one call from `models.pricing` (per 1M tokens); None when a price is missing."""
    pricing = pricing or {}
    rates = (pricing.get("input_per_1m"), pricing.get("output_per_1m"))
    if any(r is None for r in rates):
        return None
    return (Decimal(str(rates[0])) * input_tokens + Decimal(str(rates[1])) * output_tokens) / MICRO


def pricing_missing(pricing: dict | None) -> bool:
    return price(pricing, 0, 0) is None


def applies(rule: Rule, subject: Subject) -> bool:
    return (
        (rule.scope_type == "project" and rule.scope_id == subject.project_id)
        or (rule.scope_type == "api_key" and rule.scope_id == subject.api_key_id)
        or (rule.scope_type == "user" and rule.scope_id == subject.user_id)
    )


async def load_rules(session: AsyncSession, project_id, now: datetime | None = None) -> list[Rule]:
    """Active rules of the project, in priority order (higher first), as of `now`."""
    now = now or datetime.now(UTC)
    rows = await session.scalars(
        select(Quota)
        .where(
            Quota.project_id == uuid.UUID(str(project_id)),
            Quota.deleted_at.is_(None),
            Quota.is_active,
            or_(Quota.activate_at.is_(None), Quota.activate_at <= now),
        )
        .order_by(Quota.priority.desc(), Quota.created_at, Quota.id)
    )
    return [Rule.of(r) for r in rows]


def _bucket(span: str, now: float) -> str:
    if span == "month":
        return datetime.fromtimestamp(now, UTC).strftime("%Y%m")
    return str(int(now) // _SPANS[span])


class QuotaEngine:
    def __init__(self, redis, *, lease_ttl_s: int, prefix: str = PREFIX) -> None:
        self._redis = redis
        self._lease_ttl_s = lease_ttl_s
        self._prefix = prefix
        self._count = redis.register_script(_COUNT_REQUEST)
        self._lease = redis.register_script(_LEASE)

    def _k(self, rule: Rule, window: str, span: str, now: float) -> str:
        return f"{self._prefix}:{rule.id}:{window}:{_bucket(span, now)}"

    async def check(
        self,
        rules: Iterable[Rule],
        subject: Subject,
        *,
        input_tokens: int = 0,
        priced: bool = True,
        now: float | None = None,
    ) -> Decision:
        """Before a call. `priced`: the model has input and output prices (budgets need them).
        Counts the request in every request window when the call may go on."""
        now = time.time() if now is None else now
        mine = [r for r in rules if applies(r, subject)]
        warnings: list[Violation] = []
        cap: int | None = None
        try:
            for rule in mine:
                for violation in await self._standing(rule, input_tokens, priced, now):
                    if violation.window == "pricing":
                        return Decision("block", "pricing_missing", violation)
                    if violation.blocking:
                        return Decision("block", "quota_exceeded", violation, tuple(warnings))
                    warnings.append(violation)
                cap = _min(cap, rule.tokens.get("max_output"))
                total = rule.tokens.get("max_total")
                if total is not None:
                    cap = _min(cap, max(int(total) - input_tokens, 0))
            requests = [
                (rule, window, span)
                for rule in mine
                for window, span in REQUEST_WINDOWS.items()
                if rule.windows.get(window) is not None
            ]
            if requests:
                failed = await self._count_requests(requests, now)
                if failed:
                    rule, window, _ = requests[failed - 1]
                    limit = rule.windows[window]
                    return Decision(
                        "block",
                        "quota_exceeded",
                        Violation(rule.id, rule.scope_type, window, limit, limit, True),
                        tuple(warnings),
                    )
                warnings += await self._request_warnings(requests, now)
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001 - any Redis failure: refuse, never allow
            log.error("quota_unavailable error=%s", type(exc).__name__)
            raise QuotaUnavailable() from None
        action = "warn" if warnings else "allow"
        for warning in warnings:
            log.warning(
                "quota_warn quota_id=%s window=%s used=%s limit=%s",
                warning.quota_id,
                warning.window,
                warning.used,
                warning.limit,
            )
        return Decision(action, None, None, tuple(warnings), cap)

    async def _standing(
        self, rule: Rule, input_tokens: int, priced: bool, now: float
    ) -> list[Violation]:
        """Limits already crossed by finished calls (tokens, budgets) and request sizes."""
        found = []
        if rule.budget and any(rule.budget.get(f) is not None for f in BUDGET_WINDOWS):
            if not priced:
                return [Violation(rule.id, rule.scope_type, "pricing", None, None, True)]
        for name, limit in (("max_input", rule.tokens.get("max_input")),):
            if limit is not None and input_tokens > int(limit):
                found.append(
                    Violation(rule.id, rule.scope_type, name, limit, input_tokens, rule.blocking)
                )
        total = rule.tokens.get("max_total")
        if total is not None and input_tokens > int(total):
            found.append(
                Violation(rule.id, rule.scope_type, "max_total", total, input_tokens, rule.blocking)
            )
        windows = [
            (w, s, rule.tokens.get(w), False)
            for w, s in TOKEN_WINDOWS.items()
            if rule.tokens.get(w) is not None
        ] + [
            (w, s, rule.budget.get(w), True)
            for w, s in BUDGET_WINDOWS.items()
            if rule.budget.get(w) is not None
        ]
        if windows:
            values = await self._redis.mget([self._k(rule, w, s, now) for w, s, _, _ in windows])
            for (window, _, limit, money), raw in zip(windows, values, strict=True):
                used = int(raw or 0)
                bound = int(Decimal(str(limit)) * MICRO) if money else int(limit)
                if used >= bound:
                    shown = Decimal(used) / MICRO if money else used
                    found.append(
                        Violation(rule.id, rule.scope_type, window, limit, shown, rule.blocking)
                    )
        return found

    async def _count_requests(self, requests, now: float) -> int:
        keys = [self._k(r, w, s, now) for r, w, s in requests]
        ttls = [_SPANS[s] + 60 for _, _, s in requests]
        limits = [int(r.windows[w]) for r, w, _ in requests]
        blocking = [1 if r.blocking else 0 for r, _, _ in requests]
        return int(await self._count(keys=keys, args=[len(keys), *ttls, *limits, *blocking]))

    async def _request_warnings(self, requests, now: float) -> list[Violation]:
        warn = [(r, w, s) for r, w, s in requests if not r.blocking]
        if not warn:
            return []
        values = await self._redis.mget([self._k(r, w, s, now) for r, w, s in warn])
        return [
            Violation(r.id, r.scope_type, w, r.windows[w], int(v or 0), False)
            for (r, w, _), v in zip(warn, values, strict=True)
            if int(v or 0) > int(r.windows[w])
        ]

    async def commit(
        self, rules: Iterable[Rule], subject: Subject, usage: Usage, *, now: float | None = None
    ) -> None:
        """After a call: tokens and cost into every applying token and budget window."""
        now = time.time() if now is None else now
        tokens = usage.input_tokens + usage.output_tokens
        micro = int(usage.cost_usd * MICRO) if usage.cost_usd is not None else 0
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                for rule in rules:
                    if not applies(rule, subject):
                        continue
                    for window, span in TOKEN_WINDOWS.items():
                        if rule.tokens.get(window) is not None and tokens:
                            key = self._k(rule, window, span, now)
                            pipe.incrby(key, tokens).expire(key, _SPANS[span] + 60)
                    for window, span in BUDGET_WINDOWS.items():
                        if rule.budget.get(window) is not None and micro:
                            key = self._k(rule, window, span, now)
                            pipe.incrby(key, micro).expire(key, _SPANS[span] + 60)
                await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            log.error("quota_commit_failed error=%s", type(exc).__name__)
            raise QuotaUnavailable() from None

    @contextlib.asynccontextmanager
    async def hold(
        self, rules: Iterable[Rule], subject: Subject, *, now: float | None = None
    ) -> AsyncIterator[Decision]:
        """`concurrent` window: a lease for the call's lifetime. Yields the decision; a blocked
        decision holds nothing (the caller stops)."""
        mine = [r for r in rules if applies(r, subject) and r.windows.get("concurrent")]
        if not mine:
            yield Decision("allow")
            return
        now = time.time() if now is None else now
        member = uuid.uuid4().hex
        keys = [f"{self._prefix}:{r.id}:concurrent" for r in mine]
        args = [
            now,
            member,
            self._lease_ttl_s,
            *[int(r.windows["concurrent"]) for r in mine],
            *[1 if r.blocking else 0 for r in mine],
        ]
        try:
            failed = int(await self._lease(keys=keys, args=args))
        except Exception as exc:  # noqa: BLE001
            log.error("quota_unavailable error=%s", type(exc).__name__)
            raise QuotaUnavailable() from None
        if failed:
            rule = mine[failed - 1]
            limit = rule.windows["concurrent"]
            yield Decision(
                "block",
                "quota_exceeded",
                Violation(rule.id, rule.scope_type, "concurrent", limit, limit, True),
            )
            return
        try:
            yield Decision("allow")
        finally:
            with contextlib.suppress(Exception):
                # A lease that cannot be removed expires after lease_ttl_s.
                async with self._redis.pipeline(transaction=False) as pipe:
                    for key in keys:
                        pipe.zrem(key, member)
                    await pipe.execute()


def _min(a: int | None, b) -> int | None:
    if b is None:
        return a
    return int(b) if a is None else min(a, int(b))


def redis_client(settings: Settings):
    import redis.asyncio as aioredis

    if settings.redis_url is None:
        raise QuotaUnavailable()
    return aioredis.from_url(settings.redis_url.get_secret_value())


def engine_for(settings: Settings, redis) -> QuotaEngine:
    return QuotaEngine(redis, lease_ttl_s=settings.run_timeout_s + 120)

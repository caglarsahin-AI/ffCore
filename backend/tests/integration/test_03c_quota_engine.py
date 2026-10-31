"""03c quota engine on the compose Redis (C20): decisions from counters, never from usage_daily.

Brief 03 acceptance: a key with daily_usd=1 is refused once it spent more than 1 USD (2); a
project with monthly_usd=0 and block refuses at once (4). Plus the window rules (10) and the
warn action (1, engine half: the call goes on). The facade's 429 is 06b's criterion.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import redis.asyncio as aioredis

from ffcore.services.quota import QuotaEngine, Rule, Subject, Usage, price

PROJECT, KEY, USER = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
SUBJECT = Subject(project_id=PROJECT, user_id=USER, api_key_id=KEY)
# 2026-10-31 12:00:30 UTC: mid-minute, so a test's few calls share one minute bucket.
NOW = datetime(2026, 10, 31, 12, 0, 30, tzinfo=UTC).timestamp()


def with_redis(test):
    """No async test plugin in this project (04a pattern): each test runs its own loop."""

    def run():
        url = os.environ.get("REDIS_URL")
        if not url:
            pytest.fail("REDIS_URL is not set; run in the tools container with redis up")

        async def main():
            client = aioredis.from_url(url)
            try:
                await test(QuotaEngine(client, lease_ttl_s=60, prefix=f"t03c:{uuid.uuid4().hex}"))
            finally:
                await client.aclose()

        asyncio.run(main())

    run.__name__ = test.__name__
    return run


def rule(scope_type="project", scope_id=PROJECT, *, action="block", **parts) -> Rule:
    return Rule(
        id=uuid.uuid4().hex,
        scope_type=scope_type,
        scope_id=scope_id,
        label="t",
        windows=parts.get("windows", {}),
        tokens=parts.get("tokens", {}),
        budget=parts.get("budget", {}),
        blocking=action == "block",
    )


def test_03c_2_price_matches_litellm():
    # U2 probe: LiteLLM charged 39.0 for 3 + 2 tokens at 3e6 / 15e6 USD per 1M.
    assert price({"input_per_1m": 3_000_000, "output_per_1m": 15_000_000}, 3, 2) == Decimal(39)
    assert price({"input_per_1m": 3}, 1, 1) is None


@with_redis
async def test_03c_2_api_key_daily_usd_exceeded(engine):
    rules = [rule("api_key", KEY, budget={"daily_usd": 1})]
    assert (await engine.check(rules, SUBJECT, now=NOW)).action == "allow"
    await engine.commit(rules, SUBJECT, Usage(10, 10, Decimal("0.6")), now=NOW)
    assert (await engine.check(rules, SUBJECT, now=NOW)).action == "allow"
    await engine.commit(rules, SUBJECT, Usage(10, 10, Decimal("0.6")), now=NOW)
    decision = await engine.check(rules, SUBJECT, now=NOW)
    assert decision.blocked and decision.code == "quota_exceeded"
    assert decision.violation.window == "daily_usd" and decision.violation.scope_type == "api_key"
    assert decision.violation.used == Decimal("1.2")
    # Another key of the same project is not affected.
    other = Subject(project_id=PROJECT, user_id=USER, api_key_id=str(uuid.uuid4()))
    assert (await engine.check(rules, other, now=NOW)).action == "allow"
    # The next UTC day starts empty.
    assert (await engine.check(rules, SUBJECT, now=NOW + 86400)).action == "allow"


@with_redis
async def test_03c_4_project_zero_budget_blocks(engine):
    rules = [rule(budget={"monthly_usd": 0})]
    decision = await engine.check(rules, SUBJECT, now=NOW)
    assert decision.blocked and decision.violation.window == "monthly_usd"


@with_redis
async def test_03c_10_project_cap_over_key(engine):
    """The project limit is a ceiling for every key and user under it."""
    rules = [rule(windows={"rpm": 2}), rule("api_key", KEY, windows={"rpm": 100})]
    for _ in range(2):
        assert (await engine.check(rules, SUBJECT, now=NOW)).action == "allow"
    decision = await engine.check(rules, SUBJECT, now=NOW)
    assert decision.blocked and decision.violation.scope_type == "project"


@with_redis
async def test_03c_10_rpm_window_resets(engine):
    rules = [rule(windows={"rpm": 1})]
    assert (await engine.check(rules, SUBJECT, now=NOW)).action == "allow"
    assert (await engine.check(rules, SUBJECT, now=NOW)).blocked
    assert (await engine.check(rules, SUBJECT, now=NOW + 60)).action == "allow"


@with_redis
async def test_03c_10_blocked_request_counts_nowhere(engine):
    """A refused call increments no window (atomic): the key's own window keeps its room."""
    project, key = rule(windows={"rpm": 1}), rule("api_key", KEY, windows={"rpm": 5})
    await engine.check([project], SUBJECT, now=NOW)  # project window full
    for _ in range(3):
        assert (await engine.check([project, key], SUBJECT, now=NOW)).blocked
    for _ in range(5):
        assert (await engine.check([key], SUBJECT, now=NOW)).action == "allow"


@with_redis
async def test_03c_10_token_windows_and_sizes(engine):
    rules = [rule(tokens={"tpm": 100, "max_input": 50, "max_output": 30, "max_total": 70})]
    too_big = await engine.check(rules, SUBJECT, input_tokens=60, now=NOW)
    assert too_big.blocked and too_big.violation.window == "max_input"
    fits = await engine.check(rules, SUBJECT, input_tokens=45, now=NOW)
    assert fits.action == "allow" and fits.max_output_tokens == 25  # min(30, 70 - 45)
    await engine.commit(rules, SUBJECT, Usage(80, 20), now=NOW)
    assert (await engine.check(rules, SUBJECT, now=NOW)).violation.window == "tpm"


@with_redis
async def test_03c_10_concurrent_window(engine):
    rules = [rule("user", USER, windows={"concurrent": 1})]
    async with engine.hold(rules, SUBJECT, now=NOW) as first:
        assert first.action == "allow"
        async with engine.hold(rules, SUBJECT, now=NOW) as second:
            assert second.blocked and second.violation.window == "concurrent"
    async with engine.hold(rules, SUBJECT, now=NOW) as again:
        assert again.action == "allow"  # released


@with_redis
async def test_03c_10_concurrent_lease_expires(engine):
    """A worker that died holding a lease frees it after lease_ttl_s (60 s here)."""
    rules = [rule(windows={"concurrent": 1})]
    async with engine.hold(rules, SUBJECT, now=NOW):
        async with engine.hold(rules, SUBJECT, now=NOW + 61) as later:
            assert later.action == "allow"


@with_redis
async def test_03c_1_warn_quota_alerts_not_blocks(engine):
    rules = [rule(action="warn", windows={"rpm": 1}, budget={"daily_usd": 1})]
    assert (await engine.check(rules, SUBJECT, now=NOW)).action == "allow"
    second = await engine.check(rules, SUBJECT, now=NOW)
    assert second.action == "warn" and not second.blocked
    assert second.warnings[0].window == "rpm"
    await engine.commit(rules, SUBJECT, Usage(1, 1, Decimal(2)), now=NOW)
    third = await engine.check(rules, SUBJECT, now=NOW)
    assert third.action == "warn" and {w.window for w in third.warnings} >= {"daily_usd"}


@with_redis
async def test_03c_11_budget_on_unpriced_model_blocks(engine):
    """FOLLOWUP-69 at run time: a model without a price never counts as 0 under a budget."""
    rules = [rule(budget={"monthly_usd": 100})]
    decision = await engine.check(rules, SUBJECT, priced=False, now=NOW)
    assert decision.blocked and decision.code == "pricing_missing"
    no_budget = [rule(windows={"rpm": 10})]
    assert (await engine.check(no_budget, SUBJECT, priced=False, now=NOW)).action == "allow"


def test_03c_10_redis_down_refuses():
    from ffcore.core.errors import ApiError

    async def main():
        client = aioredis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
        engine = QuotaEngine(client, lease_ttl_s=60)
        try:
            with pytest.raises(ApiError) as caught:
                await engine.check([rule(windows={"rpm": 1})], SUBJECT, now=NOW)
            assert caught.value.code == "quota_unavailable"
        finally:
            await client.aclose()

    asyncio.run(main())

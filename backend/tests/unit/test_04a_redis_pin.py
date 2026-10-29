"""K-04a-0008: redis 5.3.1 (arq 0.28 needs redis<6) keeps the redis.asyncio API other packages use.

08-lite's guardrails (service.py, masking.py) call Redis.hget/hincrby/hsetnx/hset/expire; this
pins their presence and parameters so a lock change cannot break them silently.
"""

import inspect

import redis
from redis.asyncio import Redis

USED = {
    "hget": ["self", "name", "key"],
    "hincrby": ["self", "name", "key", "amount"],
    "hsetnx": ["self", "name", "key", "value"],
    "hset": ["self", "name", "key", "value", "mapping", "items"],
    "expire": ["self", "name", "time", "nx", "xx", "gt", "lt"],
}


def test_04a_redis_pinned_below_6_for_arq():
    assert redis.__version__ == "5.3.1"


def test_04a_redis_asyncio_calls_used_by_08_lite_exist():
    for name, params in USED.items():
        method = getattr(Redis, name)
        assert list(inspect.signature(method).parameters)[: len(params)] == params, name
    assert callable(Redis.pipeline) and callable(Redis.from_url)


def test_04a_arq_importable_with_this_redis():
    from arq import create_pool  # noqa: F401
    from arq.connections import RedisSettings

    assert RedisSettings.from_dsn("redis://:p@redis:6379/0").host == "redis"

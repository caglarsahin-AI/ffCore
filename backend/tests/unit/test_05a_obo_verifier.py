"""05a review r1 MAJOR-1: mcp-sql's verifier asks the backend (POST /internal/obo/verify) and
keeps the answer for the token's lifetime (KARARLAR "05a review r1 kararları" item 2).

One entry per token, keyed by the whole token: a forged token that copies a verified token's
jti is a different token and is asked about again.
"""

import asyncio
import time

import jwt
import pytest

from ffcore.services.mcp_server_common import CallerCheck, OboVerifier, VerifyRefused

NOW = 1_900_000_000


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


class Counting(OboVerifier):
    def __init__(self, answers, clock) -> None:
        self.answers, self.asked = answers, []
        self.tool_key, self.clock, self.cache = "mcp-sql", clock, {}

    async def _ask(self, token: str) -> dict:
        self.asked.append(token)
        answer = self.answers[token]
        if isinstance(answer, VerifyRefused):
            raise answer
        return answer


def _token(jti: str, key: str = "k" * 32) -> str:
    claims = {"sub": "u", "project_id": "p", "aud": ["mcp-sql"], "exp": NOW + 60, "jti": jti}
    return jwt.encode(claims, key, algorithm="HS256")


def _claims(jti: str) -> dict:
    return {"sub": "u", "project_id": "p", "exp": NOW + 60, "jti": jti}


def run(coro):
    return asyncio.run(coro)


def test_05a_verifier_asks_once_per_token():
    clock, token = Clock(), _token("a")
    verifier = Counting({token: _claims("a")}, clock)
    assert run(verifier.claims(token))["sub"] == "u"
    assert run(verifier.claims(token))["sub"] == "u"
    assert verifier.asked == [token]


def test_05a_verifier_cache_ends_with_the_token():
    clock, token = Clock(), _token("a")
    verifier = Counting({token: _claims("a")}, clock)
    run(verifier.claims(token))
    clock.now = NOW + 60
    verifier.answers[token] = VerifyRefused(401, "token_expired")
    with pytest.raises(VerifyRefused):
        run(verifier.claims(token))
    assert verifier.asked == [token, token]


def test_05a_verifier_same_jti_other_token_asked_again():
    clock = Clock()
    good, forged = _token("same"), _token("same", key="f" * 32)
    verifier = Counting({good: _claims("same"), forged: VerifyRefused(401, "invalid_token")}, clock)
    run(verifier.claims(good))
    with pytest.raises(VerifyRefused) as err:
        run(verifier.claims(forged))
    assert err.value.code == "invalid_token" and verifier.asked == [good, forged]


def test_05a_verifier_refusal_not_cached():
    clock, token = Clock(), _token("a")
    verifier = Counting({token: VerifyRefused(401, "invalid_token")}, clock)
    for _ in range(2):
        with pytest.raises(VerifyRefused):
            run(verifier.claims(token))
    assert verifier.asked == [token, token]


def test_05a_caller_check_uses_the_verifier_answer(settings):
    """The routing read passes a token signed with any key; the verifier's answer decides."""
    from ffcore.core.auth import service_authorization

    clock = Clock()
    clock.now = time.time()
    token = jwt.encode(
        {"sub": "u", "project_id": "p", "aud": ["mcp-sql"], "exp": int(clock.now) + 60, "jti": "x"},
        "f" * 32,
        algorithm="HS256",
    )
    verifier = Counting({token: VerifyRefused(401, "invalid_token")}, clock)
    reached = []

    async def app(scope, receive, send):
        reached.append(True)

    check = CallerCheck(app, settings, "mcp-sql", verifier=verifier)
    sent = []

    async def send(message):
        sent.append(message)

    headers = [
        (b"authorization", service_authorization(settings)["Authorization"].encode()),
        (b"x-on-behalf-of", token.encode()),
    ]
    scope = {"type": "http", "path": "/mcp", "headers": headers}
    run(check(scope, None, send))
    assert reached == [] and sent[0]["status"] == 401
    assert b"invalid_token" in sent[1]["body"]

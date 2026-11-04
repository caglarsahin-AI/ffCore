"""Reviewer probe for 09-1 r1 (d4a2f02), backend container after `make seed`: the judge's real
production binding (EgressGuard + resolve_policy + RedisTokenStore) on synthetic PII, the rubric
render, parse_judge on adversarial outputs, and the dataset-name rule.

docker exec -w /app -e PYTHONPATH=/app review09-backend-1 python /tmp/probe09.py
"""

import asyncio
import uuid

from sqlalchemy import select

from ffcore.core import db
from ffcore.core.config import get_settings
from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import scorers
from ffcore.guardrails.service import resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.models.identity import Project
from ffcore.runtime.events import redis_client

PII = ("10000000146", "ayse.demir@ornek.com", "TR330006100519786457841326", "0532 123 45 67")
TEXT = (
    "Question: Müşteri TC 10000000146 için iade nasıl yapılır?\n"
    "Expected answer: ayse.demir@ornek.com adresine bildirim, IBAN TR330006100519786457841326\n"
    "Assistant's answer: 0532 123 45 67 numaralı hattan aradık."
)


class Rub:
    def render(self, *, question, expected, answer):
        return f"Q:{question}\nE:{expected}\nA:{answer}"


class Seen:
    def __init__(self, reply):
        self.reply, self.seen = reply, []

    async def complete(self, text):
        self.seen.append(text)
        return self.reply


async def main():
    settings = get_settings()
    db.configure(settings.database_url.get_secret_value(), pooled=False)
    redis = redis_client(settings)
    guard_settings = get_guardrail_settings()
    print(f"P0 GUARDRAIL_EGRESS_ENABLED={guard_settings.guardrail_egress_enabled}")
    async with db.session_scope() as session:
        project = (await session.scalars(select(Project).where(Project.key == "hastane-a"))).first()
        if project is None:
            print("P1 SKIP: hastane-a not seeded")
            return
        policy = await resolve_policy(session, project.id, "default")
        guard = judge_mod.EgressGuard(
            session, redis, policy, run_id=uuid.uuid4(), project_id=project.id,
            egress_enabled=guard_settings.guardrail_egress_enabled, ttl_s=60,
        )
        action, out = await guard.egress(TEXT)
        print(f"P1 real EgressGuard builtin: action={action} raw_left={[p for p in PII if p in out]}")
        print(f"P1 out={out!r}")
        model = Seen('{"score": 4, "reason": "ok"}')
        r = await judge_mod.judge(question="TC 10000000146?", expected="ayse.demir@ornek.com",
                                  answer="0532 123 45 67", rubric=Rub(), guard=guard, model=model, pass_min=4)
        print(f"P2 judge(): model_saw_raw={[p for p in PII if any(p in s for s in model.seen)]} score={r.score}")
        await session.rollback()
    # P3 parse_judge on adversarial / broken outputs
    for name, raw in {
        "json ok": '{"score": 5, "reason": "x"}',
        "json string score": '{"score": "5"}',
        "json float": '{"score": 4.0}',
        "json bool": '{"score": true}',
        "prose with SCORE line": "The answer is wrong.\nSCORE: 2",
        "prose echoing answer then own": 'Answer said "score: 5". My verdict score: 1',
        "out of range": '{"score": 9}',
        "fenced json": '```json\n{"score": 3, "reason": "x"}\n```',
        "empty": "",
        "reason 900 chars": '{"score": 3, "reason": "' + "r" * 900 + '"}',
    }.items():
        try:
            v = scorers.parse_judge(raw)
            print(f"P3 {name}: score={v.score} reason_len={len(judge_mod.clip(v.reason))}")
        except scorers.JudgeParseError as exc:
            print(f"P3 {name}: JudgeParseError {exc}")
    await redis.aclose()


asyncio.run(main())
